"""Base45 (RFC 9285) codec, strict on decode.

Decoding rejects characters outside the alphabet, a length with ``len % 3 == 1``, a triplet above
65535 and a pair above 255 (base45-web accepts the last two; deliberate deviation, AC-14).
Error messages carry positions only, never the input.
"""
from __future__ import annotations

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}


class Base45Error(ValueError):
    """Malformed Base45 input. ``position`` is the offending character offset."""

    def __init__(self, reason: str, position: int) -> None:
        super().__init__(f"{reason} at position {position}")
        self.position = position


def encode(data: bytes) -> str:
    out = []
    append = out.append
    n_full = len(data) - (len(data) % 2)
    for i in range(0, n_full, 2):
        n = (data[i] << 8) | data[i + 1]
        e, n = divmod(n, 2025)
        d, c = divmod(n, 45)
        append(ALPHABET[c] + ALPHABET[d] + ALPHABET[e])
    if len(data) % 2:
        d, c = divmod(data[-1], 45)
        append(ALPHABET[c] + ALPHABET[d])
    return "".join(out)


def decode(text: str) -> bytes:
    if len(text) % 3 == 1:
        raise Base45Error("invalid Base45 length", len(text) - 1)
    values = []
    for pos, ch in enumerate(text):
        v = _INDEX.get(ch)
        if v is None:
            raise Base45Error("invalid Base45 character", pos)
        values.append(v)
    out = bytearray()
    full = len(values) - (len(values) % 3)
    for i in range(0, full, 3):
        n = values[i] + values[i + 1] * 45 + values[i + 2] * 2025
        if n > 0xFFFF:
            raise Base45Error("Base45 triplet above 65535", i)
        out.append(n >> 8)
        out.append(n & 0xFF)
    if len(values) % 3 == 2:
        n = values[full] + values[full + 1] * 45
        if n > 0xFF:
            raise Base45Error("Base45 pair above 255", full)
        out.append(n)
    return bytes(out)
