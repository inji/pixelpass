"""Developer unit tests for the cbor-web compatible codec (pixelpass._cbor). Not part of the SDET oracle."""
from __future__ import annotations

import math

import pytest

from pixelpass import _cbor, _js


def dec(hexstr: str):
    return _cbor.decode_first(bytes.fromhex(hexstr))


def js(hexstr: str) -> str:
    return _js.stringify(dec(hexstr))


# ----------------------------------------------------------------------------- encoder
def test_encode_bytes_undefined_tuple_and_huge_int():
    assert _cbor.encode(b"\x01").hex() == "4101"
    assert _cbor.encode(_js.UNDEFINED).hex() == "f7"
    assert _cbor.encode((1, 2)).hex() == "820102"
    assert _cbor.encode(10**400).hex() == "f97c00"
    assert _cbor.encode(-(10**400)).hex() == "f9fc00"
    assert _cbor.encode(-9007199254740992.0).hex() == "fada000000"
    assert _cbor.encode({1: "a", "f": len}).hex() == "a1613161" + "61"


def test_encode_unsupported_type_raises():
    with pytest.raises(_cbor.CborError):
        _cbor.encode({1, 2})


# ----------------------------------------------------------------------------- decoder errors
@pytest.mark.parametrize(
    "hexstr",
    [
        "",  # insufficient
        "1c",  # additional info 28
        "1f",  # indefinite uint
        "ff",  # BREAK outside indefinite
        "f810",  # two-byte simple < 32
        "5f6161ff",  # text chunk in indefinite byte string
        "bf61610ff0",  # odd indefinite map... then trailing
        "bf6161ff",  # indefinite map with odd item count
        "6280ff",  # invalid UTF-8 text
        "0102",  # trailing data
        "db0020000000000000" + "00",  # tag number above 2^53-1
        "8201",  # truncated array
    ],
)
def test_decode_errors(hexstr):
    with pytest.raises(_cbor.CborError):
        dec(hexstr)


def test_decode_deep_nesting_is_an_error_not_a_crash():
    with pytest.raises(_cbor.CborError):
        _cbor.decode_first(b"\x81" * 100000 + b"\x00")


# ----------------------------------------------------------------------------- integers and simple values
def test_integer_bigint_boundaries():
    assert dec("1b001fffffffffffff") == 9007199254740991.0
    assert dec("1b0020000000000000") == 2**53 and isinstance(dec("1b0020000000000000"), int)
    assert dec("3b001fffffffffffff") == -(2**53) and isinstance(dec("3b001fffffffffffff"), int)
    assert dec("3b001ffffffffffffe") == -9007199254740991.0
    assert isinstance(dec("19ffff"), float)


def test_simple_values():
    assert dec("f5") is True and dec("f6") is None and dec("f7") is _js.UNDEFINED
    assert dec("f820").value == 32
    assert dec("f93c00") == 1.0 and dec("f90001") == 5.960464477539063e-8 and dec("f9fc00") == -math.inf


def test_indefinite_nested_text_chunk_and_map_dedupe():
    assert dec("7f7f6161ff6162ff") == "ab"
    m = dec("a3" "01" "6161" "6131" "01" "fb3ff0000000000000" "02")
    assert isinstance(m, _js.JSMap)
    # uint 1 and double 1.0 are the same SameValueZero key: the later value wins in the first position
    assert [(k, v) for k, v in m.pairs] == [(1.0, 2.0), ("1", 1.0)]


def test_proto_key_makes_a_map():
    assert isinstance(dec("a1695f5f70726f746f5f5f01"), _js.JSMap)


def test_map_key_identity_kinds():
    m = dec("a6f401f402f603f604f705f706")
    assert [v for _, v in m.pairs] == [2.0, 4.0, 6.0]
    m = dec("a2f97e0001f97e0002")
    assert len(m.pairs) == 1
    m = dec("a24001400" + "2")
    assert len(m.pairs) == 2  # byte strings are distinct objects


# ----------------------------------------------------------------------------- tags
def test_tags_22_23_and_nested_21():
    assert js("d81643010203") == '"AQID"'
    assert js("d81743abcdef") == '"abcdef"'
    assert js("d815824101a1616141ff") == '{"tag":21,"value":["AQ",{"a":"_w"}]}'
    assert js("d81582d8164101d8184102") == '{"tag":21,"value":["AQ==",{"tag":24,"value":"Ag"}]}'
    assert js("d815d84043010203") == '"AQID"'


def test_tag_0_and_1_variants():
    assert js("c0f6") == '"1970-01-01T00:00:00.000Z"'
    assert js("c0f5") == '"1970-01-01T00:00:00.001Z"'
    assert js("c0fb4000000000000000") == '"1970-01-01T00:00:00.002Z"'
    assert js("c0816161") == "null"  # array -> String -> unparsable
    assert js("c0a0") == "null"
    assert js("c0f7") == "null"
    assert js("c11a00000001") == '"1970-01-01T00:00:01.000Z"'
    assert js("c1f6") == '"1970-01-01T00:00:00.000Z"'
    assert js("c1f5") == '"1970-01-01T00:00:01.000Z"'
    assert js("c1623130") == '"1970-01-01T00:00:10.000Z"'
    assert js("c180") == "null"
    for hexstr in ("c11b0020000000000001", "c01b0020000000000001"):
        tagged = dec(hexstr)  # BigInt input: JS throws inside the converter, Tagged keeps the error
        assert isinstance(tagged, _js.Tagged) and tagged.err
        with pytest.raises(_js.JSBigIntError):
            js(hexstr)


def test_tag_2_3_errors():
    assert '"err"' in js("c240")
    assert '"err"' in js("c201")


def test_tag_32_uri():
    assert js("d8206f687474703a2f2f6578616d706c652f") == '"http://example/"'
    assert '"err"' in js("d820626e6f")
    assert _js.to_python(dec("d8206f687474703a2f2f6578616d706c652f")) == {}


@pytest.mark.parametrize(
    "hexstr, err",
    [
        ("d82163212121", "Invalid base64url characters"),
        ("d8216141", "Invalid base64url length"),
        ("d821624142", "Invalid base64 padding"),
        ("d82163414141", None),
        ("d82163414142", "Invalid base64 padding"),
        ("d82101", "e.match is not a function"),
        ("d82265212121213d", "Invalid base64 characters"),
        ("d8226441414141", None),
        ("d82263414141", "Invalid base64 length"),
        ("d822644142423d", "Invalid base64 padding"),
        ("d8226441423d3d", "Invalid base64 padding"),
        ("d8226441413d3d", None),
        ("d82201", "e.match is not a function"),
    ],
)
def test_tag_33_34_validation(hexstr, err):
    out = dec(hexstr)
    assert isinstance(out, _js.Tagged)
    assert (out.err if out.err is not _js.UNDEFINED else None) == err


def test_tag_35_and_258():
    assert isinstance(dec("d8236161"), _js.JSRegExp)
    assert isinstance(dec("d901026161"), _js.JSSet)
    assert isinstance(dec("d901024101"), _js.JSSet)
    assert '"err"' in js("d9010201")


def test_typed_arrays():
    assert js("d842480000000000000000") == '{"0":0,"1":0}'
    assert js("d8454401000200") == '{"0":1,"1":2}'
    assert js("d8484101") == '{"0":1}'
    assert js("d8494401000200")  # uint16 big endian
    assert js("d84842ff7f") == '{"0":-1,"1":127}'
    assert js("d856480000000000000040") == '{"0":2}'
    with pytest.raises(_js.JSBigIntError):
        js("d8434800000000000000ff")
    assert '"err"' in js("d84143010203")  # odd length for uint16
    assert '"err"' in js("d84101")  # not a buffer
    assert isinstance(dec("d84c4101"), _js.Tagged)  # tag 76 is not a typed array in cbor-web
