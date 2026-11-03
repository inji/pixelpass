"""AC-12: configuration, encoded-size limits (exact boundary, header included, per list item) and bounded inflation."""
from __future__ import annotations

import io
import json
import tracemalloc
import zipfile
import zlib

import pytest

from pixelpass import DecodingError, PixelPass

from conftest import (
    DEFAULT_MAX_DECOMPRESSED,
    DEFAULT_MAX_ENCODED,
    b64url,
    cbor_text,
    ref_b45decode,
    ref_b45encode,
    ref_encode_bytes,
)


# ----------------------------------------------------------------------------- configuration
@pytest.mark.parametrize("level", list(range(10)))
def test_ac12_compression_level_0_to_9_accepted(level):
    p = PixelPass(compression_level=level)
    assert p.decode(p.generate_qr_data('{"a":[1,2,3]}')) == '{"a":[1,2,3]}'


@pytest.mark.parametrize(
    "kwargs",
    [
        {"compression_level": -1},
        {"compression_level": 10},
        {"max_encoded_size": 0},
        {"max_encoded_size": -1},
        {"max_decompressed_size": 0},
        {"max_decompressed_size": -100},
    ],
)
def test_ac12_bad_config_raises_value_error(kwargs):
    with pytest.raises(ValueError):
        PixelPass(**kwargs)


def test_ac12_non_default_compression_level_breaks_js_parity_but_round_trips():
    text = '{"name":"Alice","name2":"Alice","name3":"Alice"}'
    p9, p0 = PixelPass(), PixelPass(compression_level=0)
    assert p0.generate_qr_data(text) != p9.generate_qr_data(text)
    assert p0.decode(p0.generate_qr_data(text)) == p9.decode(p9.generate_qr_data(text))


# ----------------------------------------------------------------------------- encoded-size limit: defaults
def _payload(text: str = "hello") -> str:
    return ref_encode_bytes(cbor_text(text))


def test_ac12_default_limit_exactly_65536_with_header_accepted(pp):
    body = _payload()
    header = "H" * (DEFAULT_MAX_ENCODED - len(body))
    assert len(header + body) == DEFAULT_MAX_ENCODED
    assert pp.decode(header + body, header=header) == '"hello"'
    assert pp.decode_to_object(header + body, header=header) == "hello"


def test_ac12_default_limit_65537_with_header_rejected(pp):
    body = _payload()
    header = "H" * (DEFAULT_MAX_ENCODED + 1 - len(body))
    with pytest.raises(DecodingError):
        pp.decode(header + body, header=header)
    with pytest.raises(DecodingError):
        pp.decode_to_object(header + body, header=header)


def test_ac12_default_limit_without_header():
    # a valid payload just over the default size is rejected before any work
    text = "x" * 200000
    big = ref_b45encode(zlib.compress(cbor_text(text), 0))
    assert len(big) > DEFAULT_MAX_ENCODED
    with pytest.raises(DecodingError):
        PixelPass(max_decompressed_size=10**6).decode(big)


# ----------------------------------------------------------------------------- encoded-size limit: exact boundary per decoder
@pytest.mark.parametrize("method", ["decode", "decode_to_object"])
def test_ac12_decode_boundary_header_counts(method):
    body = _payload("boundary")
    data = "HDR:" + body
    n = len(data)
    expected = {"decode": '"boundary"', "decode_to_object": "boundary"}[method]
    assert getattr(PixelPass(max_encoded_size=n), method)(data, header="HDR:") == expected
    with pytest.raises(DecodingError):
        getattr(PixelPass(max_encoded_size=n - 1), method)(data, header="HDR:")
    # the payload alone would fit n-1, so the header is what tips it over
    assert len(body) <= n - 1


def test_ac12_decode_binary_boundary():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("certificate.json", b"{}")
    data = buf.getvalue()
    assert PixelPass(max_encoded_size=len(data)).decode_binary(data) == "{}"
    with pytest.raises(DecodingError):
        PixelPass(max_encoded_size=len(data) - 1).decode_binary(data)


def test_ac12_to_json_boundary():
    s = b64url(cbor_text("a" * 73))  # 75 bytes -> 100 base64url characters
    assert len(s) == 100
    assert PixelPass(max_encoded_size=100).to_json(s) == "a" * 73
    with pytest.raises(DecodingError):
        PixelPass(max_encoded_size=99).to_json(s)


def test_ac12_to_json_padding_counts():
    s = b64url(cbor_text("abcd")) + "="  # 5 bytes: one '=' of canonical padding
    assert len(s) % 4 == 0
    assert PixelPass(max_encoded_size=len(s)).to_json(s) == "abcd"
    with pytest.raises(DecodingError):
        PixelPass(max_encoded_size=len(s) - 1).to_json(s)


def _json_item(n: int) -> str:
    """A JSON object string of exactly n characters that decode_mapped_data accepts."""
    base = '{"1":""}'
    s = '{"1":"' + "a" * (n - len(base)) + '"}'
    assert len(s) == n
    return s


def _hex_item(n_hex: int) -> str:
    """Valid hex CBOR (a text string) of exactly n_hex characters (n_hex even, >= 52)."""
    nbytes = n_hex // 2
    raw = cbor_text("a" * (nbytes - 2))
    assert len(raw) == nbytes
    return raw.hex()


@pytest.mark.parametrize("make", [_json_item, _hex_item], ids=["json", "hex"])
def test_ac12_decode_mapped_data_boundary(make):
    item = make(100)
    assert isinstance(PixelPass(max_encoded_size=100).decode_mapped_data(item), str)
    with pytest.raises(DecodingError):
        PixelPass(max_encoded_size=99).decode_mapped_data(item)


def test_ac12_decode_mapped_data_limit_applies_per_list_item():
    p = PixelPass(max_encoded_size=100)
    ok = [_json_item(100), _hex_item(100), _json_item(100)]
    assert sum(map(len, ok)) > 100
    assert len(p.decode_mapped_data(ok)) == 3
    with pytest.raises(DecodingError):
        p.decode_mapped_data([_json_item(100), _json_item(101)])


# ----------------------------------------------------------------------------- decompressed-size limit
def _text_len_for(n: int) -> int:
    """k such that the CBOR text string of k ASCII characters is exactly n bytes."""
    for head in (1, 2, 3, 5, 9):
        if len(cbor_text("a" * (n - head))) == n:
            return n - head
    raise AssertionError(n)


def _inflating_to(n: int) -> str:
    """Payload whose zlib stream inflates to exactly n bytes (a CBOR text string)."""
    raw = cbor_text("a" * _text_len_for(n))
    assert len(raw) == n
    return ref_encode_bytes(raw)


@pytest.mark.parametrize("method", ["decode", "decode_to_object"])
def test_ac12_decompressed_exact_boundary(method):
    data = _inflating_to(1000)
    out = getattr(PixelPass(max_decompressed_size=1000), method)(data)
    k = _text_len_for(1000)
    expected = {"decode": '"' + "a" * k + '"', "decode_to_object": "a" * k}[method]
    assert out == expected
    with pytest.raises(DecodingError):
        getattr(PixelPass(max_decompressed_size=999), method)(data)


@pytest.mark.parametrize("method", ["decode", "decode_to_object"])
def test_ac12_decompression_bomb_rejected_with_defaults(pp, method):
    bomb = ref_encode_bytes(b"\x00" * (DEFAULT_MAX_DECOMPRESSED + 1))
    assert len(bomb) <= DEFAULT_MAX_ENCODED
    with pytest.raises(DecodingError):
        getattr(pp, method)(bomb)


def test_ac12_payload_at_default_decompressed_limit_accepted(pp):
    data = _inflating_to(DEFAULT_MAX_DECOMPRESSED)
    assert len(data) <= DEFAULT_MAX_ENCODED
    assert len(pp.decode(data)) == _text_len_for(DEFAULT_MAX_DECOMPRESSED) + 2


BOMB_INFLATED = 64 * 1024 * 1024  # 64x the per-instance limit below
BOMB_LIMIT = 1024 * 1024
PEAK_BOUND = 16 * 1024 * 1024  # far below BOMB_INFLATED: inflation must stop near the limit
_CHUNK = b"\x00" * (1024 * 1024)


def _streamed_zlib_bomb() -> bytes:
    """zlib stream inflating to BOMB_INFLATED bytes, built chunk by chunk (about 1 MB of RAM, not 64 MB)."""
    c = zlib.compressobj(9)
    parts = [c.compress(_CHUNK) for _ in range(BOMB_INFLATED // len(_CHUNK))]
    parts.append(c.flush())
    return b"".join(parts)


def test_ac12_inflation_is_bounded_not_after_the_fact():
    """A bomb inflating to 64x max_decompressed_size is rejected without allocating anything near its inflated size."""
    bomb = ref_b45encode(_streamed_zlib_bomb())
    # the oracle really is a bomb: it inflates past the limit
    assert len(zlib.decompressobj().decompress(ref_b45decode(bomb), BOMB_LIMIT + 1)) == BOMB_LIMIT + 1
    p = PixelPass(max_encoded_size=len(bomb), max_decompressed_size=BOMB_LIMIT)
    tracemalloc.start()
    try:
        with pytest.raises(DecodingError):
            p.decode(bomb)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < PEAK_BOUND, f"peak {peak} bytes: inflation is not bounded"


def test_ac12_zip_entry_inflation_is_bounded():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with zf.open("certificate.json", "w") as entry:  # streamed: about 1 MB of RAM
            for _ in range(BOMB_INFLATED // len(_CHUNK)):
                entry.write(_CHUNK)
    data = buf.getvalue()
    p = PixelPass(max_encoded_size=len(data), max_decompressed_size=BOMB_LIMIT)
    tracemalloc.start()
    try:
        with pytest.raises(DecodingError):
            p.decode_binary(data)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < PEAK_BOUND, f"peak {peak} bytes: ZIP entry read is not bounded"
