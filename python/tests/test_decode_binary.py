"""AC-5 (decode_binary) and its AC-12 limits. ZIP archives are built in-test with zipfile."""
from __future__ import annotations

import io
import struct
import zipfile

import pytest

from pixelpass import DecodingError, PixelPass

from conftest import DEFAULT_MAX_DECOMPRESSED

ENTRY = "certificate.json"


def make_zip(entries: dict, compression: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.parametrize("compression", [zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED])
def test_ac5_returns_certificate_json_text(pp, compression):
    content = '{"credentialSubject":{"fullName":"Jörg \U0001F600"}}'
    data = make_zip({ENTRY: content.encode("utf-8")}, compression)
    assert data[:2] == b"PK"
    assert pp.decode_binary(data) == content


def test_ac5_reads_raw_bytes_not_utf8_text(pp):
    """Deviation from JS (which UTF-8-decodes the archive first): bytes >= 0x80 in the archive must survive."""
    content = ("é中" * 500).encode("utf-8")
    data = make_zip({ENTRY: content})
    assert any(b >= 0x80 for b in data)
    assert pp.decode_binary(data) == content.decode("utf-8")


def test_ac5_text_decoder_rules_bom_and_invalid_utf8(pp):
    data = make_zip({ENTRY: b'\xef\xbb\xbf{"a":"x\xffy"}'})
    assert pp.decode_binary(data) == '{"a":"x�y"}'


def test_ac5_other_entries_ignored(pp):
    data = make_zip({"a.txt": b"other", ENTRY: b'{"ok":true}', "z/b.json": b"{}"})
    assert pp.decode_binary(data) == '{"ok":true}'


def test_ac5_missing_entry_raises_naming_entry(pp):
    data = make_zip({"other.json": b"{}"})
    with pytest.raises(DecodingError) as ei:
        pp.decode_binary(data)
    assert ENTRY in str(ei.value)


def test_ac5_entry_name_is_case_sensitive_and_exact(pp):
    with pytest.raises(DecodingError):
        pp.decode_binary(make_zip({"Certificate.JSON": b"{}"}))
    with pytest.raises(DecodingError):
        pp.decode_binary(make_zip({"dir/certificate.json": b"{}"}))


@pytest.mark.parametrize(
    "data",
    [
        b"PK\x03\x04" + b"\x00" * 30 + b"garbage",
        b"PK",
        b"PK\x05\x06",
    ],
    ids=["garbage-after-local-header", "only-magic", "eocd-magic-only"],
)
def test_ac5_corrupt_archive_starting_with_pk_raises(pp, data):
    with pytest.raises(DecodingError):
        pp.decode_binary(data)


def test_ac5_truncated_archive_raises(pp):
    data = make_zip({ENTRY: b'{"a":1}' * 50})
    with pytest.raises(DecodingError):
        pp.decode_binary(data[: len(data) // 2])


def test_ac5_corrupted_entry_data_raises(pp):
    data = bytearray(make_zip({ENTRY: b'{"a":"' + b"x" * 2000 + b'"}'}))
    off = data.index(ENTRY.encode()) + len(ENTRY) + 5  # inside the compressed stream of the first local entry
    for i in range(off, off + 20):
        data[i] ^= 0xFF
    with pytest.raises(DecodingError):
        pp.decode_binary(bytes(data))


@pytest.mark.parametrize("data", [b'{"a":1}', b"", b"P", b"pk\x03\x04", b"\x1f\x8b\x08\x00", "PK".encode("utf-16-le")])
def test_ac5_non_zip_raises_unsupported(pp, data):
    with pytest.raises(DecodingError) as ei:
        pp.decode_binary(data)
    assert "Unsupported binary file type" in str(ei.value)


# ----------------------------------------------------------------------------- AC-12 limits
def test_ac12_input_size_limit_exact_boundary():
    data = make_zip({ENTRY: b'{"a":1}'})
    assert PixelPass(max_encoded_size=len(data)).decode_binary(data) == '{"a":1}'
    with pytest.raises(DecodingError):
        PixelPass(max_encoded_size=len(data) - 1).decode_binary(data)


def test_ac12_entry_size_exact_boundary():
    content = b"a" * 1000
    data = make_zip({ENTRY: content})
    assert PixelPass(max_decompressed_size=1000).decode_binary(data) == "a" * 1000
    with pytest.raises(DecodingError):
        PixelPass(max_decompressed_size=999).decode_binary(data)


def test_ac12_zip_bomb_rejected_with_default_limits(pp):
    data = make_zip({ENTRY: b"\x00" * (DEFAULT_MAX_DECOMPRESSED + 1)})
    assert len(data) <= 65536, "bomb must pass the encoded-size check so the decompressed limit is what rejects it"
    with pytest.raises(DecodingError):
        pp.decode_binary(data)


def test_ac12_entry_at_default_decompressed_limit_accepted(pp):
    data = make_zip({ENTRY: b"a" * DEFAULT_MAX_DECOMPRESSED})
    assert len(data) <= 65536
    assert len(pp.decode_binary(data)) == DEFAULT_MAX_DECOMPRESSED


def _patch_sizes(data: bytes, new_size: int) -> bytes:
    """Lie about the uncompressed size in both the local header and the central directory."""
    b = bytearray(data)
    lh = b.index(b"PK\x03\x04")
    struct.pack_into("<I", b, lh + 22, new_size)
    cd = b.index(b"PK\x01\x02")
    struct.pack_into("<I", b, cd + 24, new_size)
    return bytes(b)


def test_ac12_lying_size_header_does_not_bypass_limit():
    data = _patch_sizes(make_zip({ENTRY: b"a" * 50000}), 10)
    with pytest.raises(DecodingError):
        PixelPass(max_decompressed_size=1000).decode_binary(data)
