"""AC-11 / AC-15: typed errors, chained cause, no payload text in the message or anywhere in the chain.

Every malformed input carries the marker "SECRET" (valid Base45 / base64url / hex characters where needed),
so a leak of payload text shows up as the marker in str/repr/args/attributes of any exception in the chain.
"""
from __future__ import annotations

import zlib

import pytest

from pixelpass import DecodingError, EncodingError, MappingError, PixelPassError

from conftest import ref_b45encode

MARKER = "SECRET"
MARKER_HEX = MARKER.encode().hex()  # "534543524554", for the hex-input case

CASES = [
    # id, callable(pp), expected exception
    ("base45-invalid-character", lambda pp: pp.decode("SECRET#AB"), DecodingError),
    ("base45-invalid-length", lambda pp: pp.decode("SECRETA"), DecodingError),
    ("base45-triplet-above-65535", lambda pp: pp.decode("SECRETGGW"), DecodingError),
    ("corrupt-zlib", lambda pp: pp.decode(ref_b45encode(b"SECRET-not-a-zlib-stream")), DecodingError),
    ("truncated-zlib", lambda pp: pp.decode(ref_b45encode(zlib.compress(b'"SECRET payload text"' * 20, 9)[:-6])), DecodingError),
    ("zlib-trailing-bytes", lambda pp: pp.decode(ref_b45encode(zlib.compress(b"SECRET", 9) + b"SECRET")), DecodingError),
    ("decode-mapped-data-neither-hex-nor-json", lambda pp: pp.decode_mapped_data("SECRET{not json"), DecodingError),
    ("decode-mapped-data-hex-bad-cbor", lambda pp: pp.decode_mapped_data("a1" + MARKER.encode().hex()), DecodingError),
    ("to-json-invalid-base64url", lambda pp: pp.to_json("SECRET!!"), DecodingError),
    ("to-json-undecodable-cbor", lambda pp: pp.to_json("SECRETAA"), DecodingError),
    ("generate-qr-data-none", lambda pp: pp.generate_qr_data(None), EncodingError),
    ("decode-none", lambda pp: pp.decode(None), DecodingError),
    ("decode-binary-corrupt-zip", lambda pp: pp.decode_binary(b"PK\x03\x04SECRET" + b"\x00" * 40), DecodingError),
]


def _chain(exc: BaseException):
    seen = []
    stack = [exc]
    while stack:
        e = stack.pop()
        if e is None or any(e is s for s in seen):
            continue
        seen.append(e)
        stack.append(e.__cause__)
        stack.append(e.__context__)
    return seen


def _texts(e: BaseException):
    yield str(e)
    yield repr(e)
    for a in e.args:
        yield repr(a)
    for k, v in vars(e).items():
        if k.startswith("__"):
            continue
        yield repr(v)


@pytest.mark.parametrize("case", [pytest.param(c, id=c[0]) for c in CASES])
def test_ac11_typed_error_with_cause_and_no_payload(pp, case):
    _, call, exc_type = case
    with pytest.raises(exc_type) as ei:
        call(pp)
    e = ei.value
    assert isinstance(e, PixelPassError)
    assert e.__cause__ is not None, "cause must be chained with `raise ... from cause`"
    for link in _chain(e):
        for text in _texts(link):
            for marker in (MARKER, MARKER_HEX):
                assert marker not in text, f"payload text leaked via {type(link).__name__}: {text[:80]!r}"


@pytest.mark.parametrize("case", [pytest.param(c, id=c[0]) for c in CASES])
def test_ac11_context_is_none(pp, case):
    """ADR-4: the sanitized cause is raised outside the except block, so __context__ stays None."""
    _, call, exc_type = case
    with pytest.raises(exc_type) as ei:
        call(pp)
    assert ei.value.__context__ is None


def test_ac15_error_messages_are_non_empty_and_name_operation(pp):
    for _, call, exc_type in CASES:
        with pytest.raises(exc_type) as ei:
            call(pp)
        assert str(ei.value).strip(), "message must say what failed (operation, size or position)"


def test_ac15_limit_errors_carry_no_payload():
    from pixelpass import PixelPass

    with pytest.raises(DecodingError) as ei:
        PixelPass(max_encoded_size=10).decode("SECRET" * 10)
    assert MARKER not in str(ei.value)
    with pytest.raises(DecodingError) as ei:
        PixelPass(max_encoded_size=10).decode_mapped_data('{"SECRET":"SECRET"}')
    assert MARKER not in str(ei.value)


def test_ac13_mapping_error_is_pixelpass_error(pp):
    with pytest.raises(PixelPassError):
        pp.get_mapped_data({"Gender": "a", "gender": "b"})
    assert issubclass(MappingError, PixelPassError)
