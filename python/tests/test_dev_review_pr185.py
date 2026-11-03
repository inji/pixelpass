"""Developer regression tests for PR #185 review comments (oversized hex literals, bignum cap). Not part of the SDET oracle."""
from __future__ import annotations

import math

import pytest

from conftest import _cbor_head, b64url, cbor_map, cbor_text, ref_encode_bytes
from pixelpass import DecodingError, PixelPass, _cbor, _js
from pixelpass.exceptions import SanitizedCause

HUGE_HEX = "0x" + "f" * 300  # far above the double range


def _bignum(tag: int, size: int) -> bytes:
    return bytes([0xC0 | tag]) + _cbor_head(2, size) + b"\x01" * size


# ----------------------------------------------------------------------------- to_number overflow
@pytest.mark.parametrize("text", [HUGE_HEX, "0o" + "7" * 400, "0b" + "1" * 1100])
def test_to_number_oversized_non_decimal_literal_is_infinity(text):
    assert _js.to_number(text) == math.inf


def test_decode_tag1_with_oversized_hex_string_is_invalid_date_null():
    # JS: new Date(1e3 * Number("0xfff...")) is an invalid Date; JSON.stringify gives null
    raw = b"\xc1" + cbor_text(HUGE_HEX)
    assert PixelPass().decode(ref_encode_bytes(raw)) == "null"


def test_decode_mapped_data_oversized_hex_key_is_kept():
    assert PixelPass().decode_mapped_data('{"%s":1}' % HUGE_HEX) == '{"%s":1}' % HUGE_HEX


def test_decode_mapped_data_cbor_oversized_hex_key_is_kept():
    hexdata = cbor_map([(cbor_text(HUGE_HEX), b"\x01")]).hex()
    assert PixelPass().decode_mapped_data(hexdata) == '{"%s":1}' % HUGE_HEX


# ----------------------------------------------------------------------------- bignum cap
@pytest.mark.parametrize("tag", [2, 3])
def test_bignum_at_cap_decodes(tag):
    n = int.from_bytes(b"\x01" * _cbor.MAX_BIGNUM_BYTES, "big")
    assert _cbor.decode_first(_bignum(tag, _cbor.MAX_BIGNUM_BYTES)) == (n if tag == 2 else -1 - n)


@pytest.mark.parametrize("tag", [2, 3])
def test_bignum_over_cap_is_cbor_error(tag):
    with pytest.raises(_cbor.BignumTooLargeError, match="bignum too large"):
        _cbor.decode_first(_bignum(tag, _cbor.MAX_BIGNUM_BYTES + 1))


def _assert_sanitized(exc):
    assert isinstance(exc.__cause__, SanitizedCause)
    assert exc.__context__ is None
    for text in (str(exc), str(exc.__cause__)):
        assert "0101" not in text and "\x01" not in text and "257" not in text  # no payload digits or bytes


def test_to_json_bignum_over_cap_raises_sanitized_decoding_error():
    with pytest.raises(DecodingError) as ei:
        PixelPass().to_json(b64url(_bignum(2, 4096)))
    _assert_sanitized(ei.value)


def test_decode_bignum_over_cap_takes_text_path():
    raw = _bignum(2, 4096)
    assert PixelPass().decode(ref_encode_bytes(raw)) == _js.text_decode(raw)


def test_decode_regexp_of_bignum_over_cap_does_not_leak_value_error():
    # tag 35 (RegExp) of a bignum called str() on the int: past 4300 digits that was a raw ValueError
    raw = b"\xd8\x23" + _bignum(2, 4096)
    assert PixelPass().decode(ref_encode_bytes(raw)) == _js.text_decode(raw)


def test_decode_mapped_data_bignum_over_cap_raises_sanitized_decoding_error():
    with pytest.raises(DecodingError, match="bignum longer than 1024 bytes") as ei:
        PixelPass().decode_mapped_data(_bignum(2, 4096).hex())
    _assert_sanitized(ei.value)


@pytest.mark.parametrize("tag", [2, 3])
def test_to_json_bignum_at_cap_decodes_through_public_api(tag):
    n = int.from_bytes(b"\x01" * _cbor.MAX_BIGNUM_BYTES, "big")
    assert PixelPass().to_json(b64url(_bignum(tag, _cbor.MAX_BIGNUM_BYTES))) == (n if tag == 2 else -1 - n)


def test_decode_mapped_data_bignum_at_cap_prints_integer():
    n = int.from_bytes(b"\x01" * _cbor.MAX_BIGNUM_BYTES, "big")
    hexdata = cbor_map([(cbor_text("x"), _bignum(2, _cbor.MAX_BIGNUM_BYTES))]).hex()
    assert PixelPass().decode_mapped_data(hexdata, key_mapper=None) == '{"x":%d}' % n


@pytest.mark.parametrize("tag", [2, 3])
def test_decode_mapped_data_bignum_biometric_data_format_does_not_overflow(tag):
    # "Data format" goes through Number() in replaceValuesForClaim169; a 200-byte BigInt is past the double range
    face = cbor_map([(cbor_text("Data format"), _bignum(tag, 200)), (cbor_text("Data sub format"), b"\x01")])
    hexdata = cbor_map([(cbor_text("Face"), face)]).hex()
    out = PixelPass().decode_mapped_data(hexdata, key_mapper=None)
    n = int.from_bytes(b"\x01" * 200, "big")
    assert out == '{"Face":{"Data format":%d,"Data sub format":1}}' % (n if tag == 2 else -1 - n)
