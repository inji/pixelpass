"""Exception hierarchy of the PixelPass SDK.

Every error raised for malformed input is a :class:`PixelPassError` subclass. The original low-level
exception is never chained as-is, because its message or arguments can quote the payload. Instead a
sanitized cause (type name and, when known, a position) is chained with ``raise ... from cause``.
The SDK raises it outside the ``except`` block, so ``__context__`` stays ``None`` (DESIGN ADR-4).
"""
from __future__ import annotations

from typing import Optional


class PixelPassError(Exception):
    """Base class of every error the SDK raises for bad input or configuration of an operation."""


class EncodingError(PixelPassError):
    """Raised when data cannot be encoded (unsupported input, invalid ECC level, QR overflow)."""


class DecodingError(PixelPassError):
    """Raised when data cannot be decoded (malformed Base45, zlib, ZIP, base64url, CBOR or JSON; size limits)."""


class MappingError(PixelPassError):
    """Raised by the mapping helpers (None input, key collisions, invalid key mapper)."""


class SanitizedCause(Exception):
    """Payload-free stand-in for a low-level exception: only its type name and an optional position."""


def _position(exc: BaseException) -> Optional[int]:
    for attr in ("pos", "start", "position"):
        value = getattr(exc, attr, None)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def sanitize(exc: BaseException) -> SanitizedCause:
    """Return a cause that names the exception type (and position) but carries no payload text."""
    pos = _position(exc)
    name = type(exc).__name__
    return SanitizedCause(name if pos is None else f"{name} at pos {pos}")


def cause(kind: str, detail: str = "") -> SanitizedCause:
    """Build a sanitized cause for a failure detected by the SDK itself (no underlying exception)."""
    return SanitizedCause(f"{kind}: {detail}" if detail else kind)
