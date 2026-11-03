"""AC-2 / AC-4 / AC-8: readable, hand-built checks of the JS semantics the vectors pin down.

Payloads are built with the test-side Base45/zlib/CBOR oracles in conftest (never with SDK internals),
so a failure here points at one semantic rule rather than at a vector id.
"""
from __future__ import annotations

import json

import pytest

from conftest import (
    b64url,
    cbor_array,
    cbor_double,
    cbor_map,
    cbor_text,
    cbor_uint,
    ref_encode_bytes,
    same_value,
)


def _dec(pp, raw: bytes) -> str:
    return pp.decode(ref_encode_bytes(raw))


# ----------------------------------------------------------------------------- JS property order (AC-2, AC-4)
def test_ac4_decode_orders_array_index_keys_first(pp):
    raw = cbor_map([(cbor_text("b"), cbor_uint(1)), (cbor_text("10"), cbor_uint(2)), (cbor_text("2"), cbor_uint(3)), (cbor_text("a"), cbor_uint(4))])
    assert _dec(pp, raw) == '{"2":3,"10":2,"b":1,"a":4}'


def test_ac4_decode_index_boundary_4294967294_is_index_4294967295_is_not(pp):
    raw = cbor_map([(cbor_text("x"), cbor_uint(0)), (cbor_text("4294967295"), cbor_uint(1)), (cbor_text("4294967294"), cbor_uint(2)), (cbor_text("01"), cbor_uint(3))])
    assert _dec(pp, raw) == '{"4294967294":2,"x":0,"4294967295":1,"01":3}'


def test_ac2_generate_qr_data_keeps_js_key_order(pp):
    a = pp.generate_qr_data('{"b":1,"2":2}')
    b = pp.generate_qr_data('{"2":2,"b":1}')
    assert a == b, "JSON.parse puts integer-like keys first, so both inputs encode identically"


def test_ac2_duplicate_json_keys_last_value_first_position(pp):
    assert pp.decode(pp.generate_qr_data('{"a":1,"b":2,"a":3}')) == '{"a":3,"b":2}'


# ----------------------------------------------------------------------------- number formatting (ES Number::toString)
@pytest.mark.parametrize(
    "x, js",
    [
        (1.5, "1.5"),
        (100.0, "100"),
        (0.1, "0.1"),
        (1e21, "1e+21"),
        (1e20, "100000000000000000000"),
        (1e-7, "1e-7"),
        (0.000001, "0.000001"),
        (1.23e-18, "1.23e-18"),
        (-2.5, "-2.5"),
        (9007199254740992.0, "9007199254740992"),
        (1.7976931348623157e308, "1.7976931348623157e+308"),
        (5e-324, "5e-324"),
        (123456789.125, "123456789.125"),
    ],
)
def test_ac4_decode_prints_numbers_like_js(pp, x, js):
    assert _dec(pp, cbor_array([cbor_double(x)])) == "[" + js + "]"


def test_ac4_negative_zero_nested_prints_0_top_level_is_falsy_text(pp):
    assert _dec(pp, cbor_array([cbor_double(-0.0)])) == "[0]"
    # top-level -0 is falsy: JS returns the TextDecoder text of the raw bytes fb 80 00.. (U+FFFD for invalid UTF-8)
    assert _dec(pp, cbor_double(-0.0)) == "��" + "\x00" * 7


def test_ac4_non_finite_nested_prints_null(pp):
    assert _dec(pp, cbor_array([cbor_double(float("inf")), cbor_double(float("nan"))])) == "[null,null]"


# ----------------------------------------------------------------------------- JSON.stringify escaping
def test_ac4_json_stringify_escaping(pp):
    s = "\x00\x01\b\t\n\x0c\r\x1f\"\\/\x7f  é\U0001F600"
    expected = '"\\u0000\\u0001\\b\\t\\n\\f\\r\\u001f\\"\\\\/\x7f  é\U0001F600"'
    assert _dec(pp, cbor_text(s)) == expected


# ----------------------------------------------------------------------------- TextDecoder (WHATWG) rules
def test_ac4_text_path_strips_one_bom_only(pp):
    assert _dec(pp, b"\xef\xbb\xbfhello") == "hello"
    assert _dec(pp, b"\xef\xbb\xbf\xef\xbb\xbfhi") == "﻿hi"


def test_ac4_text_path_replaces_invalid_utf8_per_whatwg(pp):
    # 0xff invalid; c3 28 -> U+FFFD then '('; e2 82 truncated -> one U+FFFD
    assert _dec(pp, b"\xff\xfeA\xc3(") == "��A�("
    assert _dec(pp, b"\xffA\xe2\x82") == "�A�"


# ----------------------------------------------------------------------------- decode quirks kept (AC-4)
@pytest.mark.parametrize(
    "raw, expected",
    [
        (b"\xf4", "�"),  # false is falsy -> text of byte f4
        (b"\x00", "\x00"),  # 0 is falsy
        (b"\xf6", "�"),  # null
        (b"\x60", "`"),  # "" is falsy -> text "`"
        (b" ", "-1"),  # text " " parses as CBOR -1
        (b"\x01\x02", "\x01\x02"),  # trailing bytes after first item -> text path
        (b"\x80", "[]"),
        (b"\xa0", "{}"),
    ],
)
def test_ac4_decode_quirks(pp, raw, expected):
    assert _dec(pp, raw) == expected


def test_ac4_map_with_non_string_key_stringifies_as_empty_object(pp):
    assert _dec(pp, cbor_map([(cbor_uint(1), cbor_text("x"))])) == "{}"
    assert _dec(pp, cbor_map([(cbor_text("k"), cbor_map([(cbor_uint(1), cbor_uint(2))]))])) == '{"k":{}}'


def test_ac4_byte_string_stringifies_as_buffer_json(pp):
    assert _dec(pp, b"\x43\x01\x02\x03") == '{"type":"Buffer","data":[1,2,3]}'


def test_ac4_bigint_falls_back_to_text(pp):
    raw = b"\x1b\x00\x20\x00\x00\x00\x00\x00\x01"  # 2^53+1: cbor-web yields BigInt, JSON.stringify throws
    assert _dec(pp, raw) == raw.decode("utf-8", errors="replace")


# ----------------------------------------------------------------------------- JSON.parse semantics on encode (AC-2)
@pytest.mark.parametrize(
    "text, decoded",
    [
        ("NaN", "NaN"),  # not JSON -> UTF-8 text path
        ('{"a":NaN}', '{"a":NaN}'),
        ("1e400", "null"),  # JSON.parse -> Infinity -> CBOR f97c00 -> JSON.stringify null
        ("1E2", "100"),
        ("9007199254740993", "9007199254740992"),  # IEEE double
        (' { "a" : [ 1 , 2 ] } ', '{"a":[1,2]}'),
        ('"a\\ud800b"', '"a�b"'),  # lone surrogate encoded as U+FFFD (TextEncoder)
    ],
)
def test_ac2_json_parse_semantics_round_trip(pp, text, decoded):
    assert pp.decode(pp.generate_qr_data(text)) == decoded


@pytest.mark.parametrize(
    "value, text",
    [
        ({"b": [1, 2.5, True, None], "a": {"x": "y"}}, '{"b":[1,2.5,true,null],"a":{"x":"y"}}'),
        ([1, "two", {"3": 4}], '[1,"two",{"3":4}]'),
        (123, "123"),
        (1.5, "1.5"),
        (2.0, "2"),
        (True, "true"),
        (False, "false"),
    ],
)
def test_ac2_value_input_equals_json_text_input(pp, value, text):
    assert pp.generate_qr_data(value) == pp.generate_qr_data(text)
    assert pp.generate_qr_data(value, header="HDR:") == pp.generate_qr_data(text, header="HDR:")


# ----------------------------------------------------------------------------- header handling (AC-2, AC-4)
def test_ac2_header_is_prefixed(pp):
    body = pp.generate_qr_data('{"a":1}')
    assert pp.generate_qr_data('{"a":1}', header="NCB:") == "NCB:" + body


def test_ac4_header_stripped_only_when_prefix(pp):
    body = pp.generate_qr_data('{"a":1}')
    assert pp.decode("NCB:" + body, header="NCB:") == '{"a":1}'
    # data does not start with the header: nothing is stripped, the full string is decoded
    assert pp.decode(body, header="NCB:") == '{"a":1}'
    assert pp.decode(body, header="") == pp.decode(body)


# ----------------------------------------------------------------------------- decode_to_object (AC-4)
@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"a":[1,{"b":null}]}', {"a": [1, {"b": None}]}),
        ("hello world", "hello world"),
        (" ", -1),
        ('"str"', "str"),
        ("[]", []),
        ("{'a':1}", "{'a':1}"),
    ],
)
def test_ac4_decode_to_object(pp, text, expected):
    assert same_value(pp.decode_to_object(pp.generate_qr_data(text)), expected)


def test_ac4_decode_to_object_is_json_loads_of_decode(pp):
    s = pp.generate_qr_data('{"2":1,"b":{"1":true}}', header="H")
    text = pp.decode(s, header="H")
    assert pp.decode_to_object(s, header="H") == json.loads(text)
    assert list(pp.decode_to_object(s, header="H")) == ["2", "b"]


# ----------------------------------------------------------------------------- to_json number model (AC-8)
def test_ac8_to_json_whole_doubles_and_negative_zero_are_int(pp):
    raw = cbor_array([cbor_double(1.0), cbor_double(-0.0), cbor_double(2.5), cbor_double(1e16)])
    result = pp.to_json(b64url(raw))
    assert result == [1, 0, 2.5, 10000000000000000]
    assert [type(x) for x in result] == [int, int, float, int]


def test_ac8_to_json_int_keys_become_str(pp):
    raw = cbor_map([(cbor_uint(1), cbor_text("a")), (cbor_text("b"), cbor_uint(2))])
    assert pp.to_json(b64url(raw)) == {"1": "a", "b": 2}


def test_ac8_to_json_accepts_trailing_padding(pp):
    raw = cbor_map([(cbor_text("a"), cbor_uint(1))])
    s = b64url(raw)
    for pad in ("", "=", "==", "==="):
        assert pp.to_json(s + pad) == {"a": 1}


def test_ac8_to_json_non_str_raises_type_error(pp):
    for bad in (b"oWFhAQ", None, 123, ["oWFhAQ"]):
        with pytest.raises(TypeError):
            pp.to_json(bad)
