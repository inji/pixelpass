"""AC-1 (own CBOR, cbor2 test-only cross-check), AC-2 / AC-6 / AC-10 cbor-web encoder rules.

The encoder is reached through public behaviour: get_mapped_data(..., cbor_enable=True) returns the
lowercase hex of cbor-web's encoding; generate_qr_data is Base45(zlib(CBOR)). Expected hex strings were
taken from cbor-web 9.0.2 (and are also in the golden vectors).
"""
from __future__ import annotations

import math
import zlib

import pytest

cbor2 = pytest.importorskip("cbor2")  # test extra; test_public_api::test_ac1_test_extras_available fails if missing

from conftest import b64url, js_compact, ref_b45decode, ref_encode_bytes

NO_MAP = {"key_mapper": {}, "value_mapper": {}, "cbor_enable": True}


def _hex(pp, value):
    return pp.get_mapped_data(value, **NO_MAP)


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, "00"),
        (23, "17"),
        (24, "1818"),
        (255, "18ff"),
        (256, "190100"),
        (65535, "19ffff"),
        (65536, "1a00010000"),
        (4294967295, "1affffffff"),
        (4294967296, "1b0000000100000000"),
        (9007199254740991, "1b001fffffffffffff"),
        (-1, "20"),
        (-24, "37"),
        (-25, "3818"),
        (-9007199254740991, "3b001ffffffffffffe"),
        (1.0, "01"),  # integral double -> CBOR integer
        (2.0, "02"),
        (9007199254740992, "fa5a000000"),  # |x| > 2^53-1 -> float32 when exact
        (9007199254740992.0, "fa5a000000"),
        (-9007199254740992, "fada000000"),
        (9007199254740994, "fb4340000000000001"),
        (1.5, "fa3fc00000"),
        (-2.5, "fac0200000"),
        (100000.5, "fa47c35040"),
        (3.4028234663852886e38, "fa7f7fffff"),
        (0.1, "fb3fb999999999999a"),
        (1e300, "fb7e37e43c8800759c"),
        (5e-324, "fb0000000000000001"),
        (1e21, "fb444b1ae4d6e2ef50"),
        (-0.0, "f98000"),  # half-precision specials only
        (math.nan, "f97e00"),
        (math.inf, "f97c00"),
        (-math.inf, "f9fc00"),
        (True, "f5"),
        (False, "f4"),
        ("", "60"),
        ("a", "6161"),
        ("a" * 23, "77" + "61" * 23),
        ("a" * 24, "7818" + "61" * 24),
        ("\U0001F600", "64f09f9880"),
        ("a\ud800b", "6561efbfbd62"),  # lone surrogate -> U+FFFD like TextEncoder
        ({}, "a0"),
        ({"b": 1, "2": 2, "a": 3, "1": 0}, "a4613100613202616201616103"),  # JS property order, text keys
        ({"x": [1, None, {"y": True}]}, "a161788301f6a16179f5"),
    ],
)
def test_ac6_ac10_cbor_web_encoding_rules(pp, value, expected):
    assert _hex(pp, value) == expected


def test_ac6_list_input_returns_list_of_hex(pp):
    assert pp.get_mapped_data([1, "a", {}], **NO_MAP) == ["01", "6161", "a0"]


@pytest.mark.parametrize(
    "value",
    [
        {"name": "Alice", "n": 30, "nested": {"list": [1, 2, {"k": "v"}], "t": True, "f": False, "z": None}},
        {"list": ["x", 1, -7, [], {}]},  # wrapped: a top-level list returns per-item hex (AC-6)
        {"emoji": "\U0001F600 नम", "big": 4294967296},
        {"floats": [1.5, 0.1, -2.5]},
    ],
)
def test_ac1_encoder_output_is_valid_cbor_cross_check_cbor2(pp, value):
    raw = bytes.fromhex(_hex(pp, value))
    assert cbor2.loads(raw) == value


def test_ac2_generate_qr_data_is_base45_of_zlib_of_cbor(pp):
    out = pp.generate_qr_data('{"a":1}')
    assert zlib.decompress(ref_b45decode(out)) == bytes.fromhex("a1616101")


def test_ac2_generate_qr_data_text_path_is_utf8(pp):
    out = pp.generate_qr_data("héllo \U0001F600")
    assert zlib.decompress(ref_b45decode(out)) == "héllo \U0001F600".encode("utf-8")


@pytest.mark.parametrize(
    "value",
    [
        {"name": "Alice", "list": [1, 2, 3], "t": True, "n": None, "neg": -5},
        ["a", {"b": "c"}, 12345678],
        {"unicode": "Jörg \U0001F600"},
    ],
)
def test_ac4_decode_of_cbor2_payload_cross_check(pp, value):
    payload = ref_encode_bytes(cbor2.dumps(value))
    assert pp.decode(payload) == js_compact(value)


def test_ac8_to_json_of_cbor2_payload_cross_check(pp):
    raw = cbor2.dumps({1: "a", "b": [1, 2, {"c": b"\x01\x02"}], 2: 1.5})
    assert pp.to_json(b64url(raw)) == {"1": "a", "2": 1.5, "b": [1, 2, {"c": {"0": 1, "1": 2}}]}


def test_ac7_decode_mapped_data_of_cbor2_int_key_payload(pp):
    raw = cbor2.dumps({1: "123", 4: "Name", 9: 2, 62: {0: b"", 1: 0, 2: 1}})
    assert pp.decode_mapped_data(raw.hex()) == (
        '{"ID":"123","Full Name":"Name","Gender":"Female",'
        '"Face":{"Data":{},"Data format":"Image","Data sub format":"JPEG"}}'
    )
