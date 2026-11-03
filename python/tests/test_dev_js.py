"""Developer unit tests for the JS emulation layer (pixelpass._js). Not part of the SDET oracle."""
from __future__ import annotations

import math

import pytest

from pixelpass import _js


@pytest.mark.parametrize(
    "x, expected",
    [
        (0.0, "0"),
        (-0.0, "0"),
        (math.nan, "NaN"),
        (math.inf, "Infinity"),
        (-math.inf, "-Infinity"),
        (123.0, "123"),
        (1e21, "1e+21"),
        (1.5e-7, "1.5e-7"),
        (0.000123, "0.000123"),
        (-1.25e30, "-1.25e+30"),
        (12345.678, "12345.678"),
    ],
)
def test_number_to_string(x, expected):
    assert _js.number_to_string(x) == expected


@pytest.mark.parametrize(
    "s, expected",
    [("", 0.0), ("  12 ", 12.0), ("0x1f", 31.0), ("1e3", 1000.0), ("-Infinity", -math.inf), (".5", 0.5), ("﻿7", 7.0)],
)
def test_to_number(s, expected):
    assert _js.to_number(s) == expected


@pytest.mark.parametrize("s", ["abc", "1x", "0x", "--1", "1e"])
def test_to_number_nan(s):
    assert math.isnan(_js.to_number(s))


def test_parse_int10():
    assert _js.parse_int10(" 1x") == 1.0
    assert _js.parse_int10("-12.9") == -12.0
    assert math.isnan(_js.parse_int10("x1"))


def test_js_order_and_index_keys():
    assert list(_js.js_order({"b": 1, "10": 2, "2": 3, "01": 4})) == ["2", "10", "b", "01"]
    assert _js.is_array_index("4294967294") and not _js.is_array_index("4294967295")


def test_js_string_of_values():
    assert _js.js_string([1.0, None, [2.0, "a"], _js.UNDEFINED]) == "1,,2,a,"
    assert _js.js_string({"a": 1}) == "[object Object]"
    assert _js.js_string(_js.Simple(16)) == "simple(16)"
    assert _js.js_string(_js.Buffer(b"hi")) == "hi"
    assert _js.js_string(_js.Tagged(30, [1.0])) == "30([1])"
    assert _js.js_string(_js.JSDate(math.nan)) == "Invalid Date"
    assert _js.js_string(_js.JSDate(0.0)).startswith("Thu Jan 01 1970 00:00:00")
    assert _js.js_string(_js.JSMap([])) == "[object Map]"
    assert _js.js_string(_js.JSSet([])) == "[object Set]"
    assert _js.js_string(_js.JSRegExp("a")) == "/a/"
    assert _js.js_string(_js.JSURL("http://x/")) == "http://x/"
    assert _js.js_string(_js.TypedArray("u8", [1.0, 2.0], b"\x01\x02")) == "1,2"
    assert _js.js_string(b"ok") == "ok"
    assert _js.js_string(object()) == "[object Object]"


def test_spread_string_uses_utf16_units():
    assert _js.spread("a\U0001F600") == {"0": "a", "1": "\ud83d", "2": "\ude00"}
    assert _js.spread(5) == {} and _js.spread(None) == {}
    assert _js.spread(("x",)) == {"0": "x"}


def test_stringify_escapes_lone_surrogates_and_keeps_pairs():
    assert _js.stringify("\ud83d") == '"\\ud83d"'
    assert _js.stringify("😀") == '"\U0001F600"'


def test_stringify_skips_undefined_and_functions():
    assert _js.stringify({"a": _js.UNDEFINED, "b": len, "c": 1.0}) == '{"c":1}'
    assert _js.stringify([_js.UNDEFINED, object()]) == "[null,null]"
    assert _js.stringify(_js.UNDEFINED) is None
    assert _js.stringify(7, bigint_error=False) == "7"
    with pytest.raises(_js.JSBigIntError):
        _js.stringify([7])


def test_stringify_objects():
    assert _js.stringify(_js.JSURL("http://x/")) == '"http://x/"'
    assert _js.stringify(_js.JSSet([1.0])) == "{}"
    assert _js.stringify(_js.Tagged(30, 1.0, "bad")) == '{"tag":30,"value":1,"err":"bad"}'
    t = _js.Tagged(22, _js.Buffer(b"\x01\x02\x03"))
    t.json_kind = "base64"
    assert _js.stringify(t) == '"AQID"'
    b = _js.Buffer(b"\xab")
    b.json_kind = "hex"
    assert _js.stringify(b) == '"ab"'
    ta = _js.TypedArray("u8", [1.0], b"\x01")
    ta.json_kind = "base64url"
    assert _js.stringify(ta) == '"AQ"'


@pytest.mark.parametrize(
    "s, iso",
    [
        ("2013-03-21T20:04:00Z", "2013-03-21T20:04:00.000Z"),
        ("2013-03-21", "2013-03-21T00:00:00.000Z"),
        ("2013-03-21T20:04:00.1234+01:30", "2013-03-21T18:34:00.123Z"),
        ("2013-03-21T20:04-02:00", "2013-03-21T22:04:00.000Z"),
        ("+012345-01-01T00:00:00Z", "+012345-01-01T00:00:00.000Z"),
        ("-000001-12-31T00:00:00Z", "-000001-12-31T00:00:00.000Z"),
        ("2020-02-29T24:00:00Z", "2020-03-01T00:00:00.000Z"),
        ("-000401-03-01T00:00:00Z", "-000401-03-01T00:00:00.000Z"),
    ],
)
def test_parse_date_iso_round_trip(s, iso):
    assert _js.date_to_iso(_js.parse_date(s)) == iso


@pytest.mark.parametrize(
    "s",
    ["2013-13-01", "2013-02-30", "-000000-01-01", "2013-03-21T24:01:00Z", "2013-03-21T20:60Z", "March 21", "2013-03-21T20:04:00+24:00"],
)
def test_parse_date_invalid(s):
    assert math.isnan(_js.parse_date(s))
    assert _js.date_to_iso(_js.parse_date(s)) is None


def test_time_clip():
    assert math.isnan(_js.time_clip(8.64e15 + 1))
    assert _js.time_clip(-1.5) == -1.0


def test_text_decode_and_well_formed():
    assert _js.text_decode(b"\xef\xbb\xbf") == ""
    assert _js.well_formed("a\ud800") == "a�"
    assert _js.utf8_encode("😀") == "\U0001F600".encode("utf-8")


def test_js_parse_rejects_non_json_and_orders_keys():
    assert list(_js.js_parse('{"b":1,"1":2}')) == ["1", "b"]
    for bad in ("NaN", "[Infinity]", "{", "﻿{}"):
        with pytest.raises(_js.JSONParseError):
            _js.js_parse(bad)


def test_to_python_view():
    value = {"a": 1.0, "b": 1e21, "c": -0.0, "d": _js.UNDEFINED, "e": [_js.UNDEFINED], "f": 2**60}
    assert _js.to_python(value) == {"a": 1, "b": 1e21, "c": 0, "e": [None], "f": 2**60}
    assert _js.to_python(_js.UNDEFINED) is None
    assert _js.to_python(_js.JSMap([(1.0, "x"), ("1", "y"), (True, _js.UNDEFINED)])) == {"1": "y"}
    assert _js.to_python(_js.Tagged(5, [1.0], "e")) == {"tag": 5, "value": [1], "err": "e"}
    assert _js.to_python(_js.JSDate(0.0)) == {}


def test_is_truthy():
    assert not any(_js.is_truthy(x) for x in (None, _js.UNDEFINED, False, 0.0, math.nan, 0, ""))
    assert all(_js.is_truthy(x) for x in (1.0, 1, "a", [], {}, _js.Buffer(b"")))
