"""AC-2 / AC-4 / AC-11: Base45 (RFC 9285) through the public API, strict on malformed input."""
from __future__ import annotations

import pytest

from pixelpass import DecodingError

from conftest import B45_ALPHABET, cbor_text, ref_b45decode, ref_b45encode, ref_encode_bytes


@pytest.mark.parametrize(
    "raw, encoded",
    [(b"AB", "BB8"), (b"Hello!!", "%69 VD92EX0"), (b"base-45", "UJCLQE7W581"), (b"ietf!", "QED8WEX0"), (b"", "")],
)
def test_reference_codec_matches_rfc9285(raw, encoded):
    """Sanity of the test-side oracle itself (RFC 9285 section 4 examples)."""
    assert ref_b45encode(raw) == encoded
    assert ref_b45decode(encoded) == raw


@pytest.mark.parametrize("text", ['{"a":1}', "plain text \U0001F600", "", "x" * 1000])
def test_ac2_output_uses_only_base45_alphabet(pp, text):
    out = pp.generate_qr_data(text)
    assert out and set(out) <= set(B45_ALPHABET)


def test_ac2_header_may_use_any_characters(pp):
    out = pp.generate_qr_data("{}", header="hé://")
    assert out.startswith("hé://") and set(out[len("hé://"):]) <= set(B45_ALPHABET)


@pytest.mark.parametrize("n", [1, 2, 3, 47, 255, 256, 1001])
def test_ac4_decodes_reference_base45_of_every_length_parity(pp, n):
    s = "a" * n
    assert pp.decode(ref_encode_bytes(cbor_text(s))) == '"' + s + '"'


@pytest.mark.parametrize(
    "data, reason",
    [
        ("AB#", "invalid character"),
        ("ab8", "lowercase is outside the alphabet"),
        ("A", "length % 3 == 1"),
        ("AAAA", "length % 3 == 1"),
        ("GGW", "triplet 65536 > 65535"),
        (":::", "triplet > 65535"),
        (":Z", "pair 1619 > 255"),
        ("BB8\n", "newline is not in the alphabet"),
    ],
)
def test_ac11_malformed_base45_raises_decoding_error(pp, data, reason):
    with pytest.raises(DecodingError):
        pp.decode(data)
