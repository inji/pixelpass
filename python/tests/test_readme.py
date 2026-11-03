"""AC-14: python/Readme.md documents install, every public method, compatibility, deviations and security limits.

These are presence checks (the doc reviewer judges quality); each phrase maps to a clause of AC-14.
"""
from __future__ import annotations

import re

import pytest

from conftest import PYTHON_ROOT

README = PYTHON_ROOT / "Readme.md"


@pytest.fixture(scope="module")
def text() -> str:
    assert README.is_file(), "python/Readme.md is required (AC-14)"
    return README.read_text(encoding="utf-8")


def test_ac14_install(text):
    assert re.search(r"pip install\s+\S*python", text)


@pytest.mark.parametrize(
    "method",
    ["generate_qr_data", "generate_qr_code", "decode", "decode_to_object", "decode_binary", "get_mapped_data", "decode_mapped_data", "to_json", "reverse_mapper"],
)
def test_ac14_example_per_public_method(text, method):
    assert re.search(r"\b" + re.escape(method) + r"\(", text), f"no example call of {method}()"


def test_ac14_compatibility_statement(text):
    assert "@injistack/pixelpass" in text and "1.0.0-rc.2" in text
    assert "c9e2258" in text


@pytest.fixture(scope="module")
def deviations(text) -> str:
    """Body of the Readme section whose heading mentions deviations/differences (up to the next same-level heading)."""
    m = re.search(r"^(#+)[^\n]*(deviation|difference)[^\n]*\n", text, re.IGNORECASE | re.MULTILINE)
    assert m, "Readme needs a 'Deviations' (or 'Differences') section listing the deliberate deviations (AC-14)"
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(r"^#{1,%d}\s" % level, rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


# One deviation per line/bullet: each pattern ties the behaviour to its method within one paragraph (no blank line).
_P = r"[^\n]*(?:\n(?!\s*\n)[^\n]*)*?"  # same paragraph / bullet, possibly wrapped


@pytest.mark.parametrize(
    "pattern, clause",
    [
        (r"decode_mapped_data" + _P + r"JSON", "JSON-string input to decode_mapped_data parsed as JSON"),
        (r"to_json" + _P + r"base64url" + _P + r"(reject|strict|DecodingError)|to_json" + _P + r"(reject|strict|DecodingError)" + _P + r"base64url",
         "strict rejection of malformed base64url in to_json"),
        (r"generate_qr_data" + _P + r"\bNone\b|\bNone\b" + _P + r"generate_qr_data", "None rejected by generate_qr_data"),
        (r"decode_binary" + _P + r"(raw|bytes)", "decode_binary reads the raw ZIP bytes"),
        (r"console\.(error|warn)", "no console/log output (JS writes console.error/console.warn)"),
        (r"(empty|truncated)" + _P + r"zlib|zlib" + _P + r"(empty|truncated)", "empty or truncated zlib stream raises DecodingError"),
        (r"Base45" + _P + r"(range|65535|255)", "out-of-range Base45 groups raise DecodingError"),
        (r"(empty|truncated|Base45)" + _P + r"DecodingError|DecodingError" + _P + r"(empty|truncated|Base45)",
         "those inputs raise DecodingError (JS returns '' or accepts them)"),
        (r"collision", "collision check"),
        (r"size limit|max_encoded_size|max_decompressed_size", "size limits"),
        (r"__proto__|toString|constructor", "Object.prototype keys treated as ordinary keys"),
        (r"Kotlin" + _P + r"scalar", "differences from Kotlin on scalar strings"),
        (r"Kotlin" + _P + r"(QR|scale)|(QR|scale)" + _P + r"Kotlin", "differences from Kotlin on QR scale"),
    ],
)
def test_ac14_deviation_documented_in_deviations_section(deviations, pattern, clause):
    assert re.search(pattern, deviations, re.IGNORECASE), f"Deviations section must document: {clause}"


def test_ac14_compression_level_parity_note(text):
    assert re.search(r"compression_level" + _P + r"(parity|byte|JS)", text, re.IGNORECASE), (
        "Readme must say a compression_level other than 9 breaks byte parity with JS (AC-12)"
    )


@pytest.mark.parametrize(
    "pattern, clause",
    [
        (r"not\s+encryption", "encoding is not encryption"),
        (r"untrusted", "decoded data is untrusted"),
        (r"65536|64\s*KiB", "default encoded-size limit"),
        (r"10485760|10\s*MiB", "default decompressed-size limit"),
        (r"max_encoded_size", "how to change the limits"),
        (r"max_decompressed_size", "how to change the limits"),
    ],
)
def test_ac14_security_limits_documented(text, pattern, clause):
    assert re.search(pattern, text, re.IGNORECASE), f"Readme must document: {clause}"
