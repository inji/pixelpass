"""PixelPass for Python: byte-compatible port of @injistack/pixelpass 1.0.0-rc.2 (upstream c9e2258).

Encode data into Base45(zlib(CBOR)) QR payloads and QR images, decode them back, read
``certificate.json`` from ZIP files and map Claim 169 identity data.
"""
from __future__ import annotations

from .client import PixelPass
from .constants import CLAIM_169_KEY_MAPPER, CLAIM_169_REVERSE_KEY_MAPPER, CLAIM_169_VALUE_MAPPER
from .exceptions import DecodingError, EncodingError, MappingError, PixelPassError
from .mapping import replace_values_for_claim169, reverse_mapper

__version__ = "0.1.0"

__all__ = [
    "PixelPass",
    "PixelPassError",
    "EncodingError",
    "DecodingError",
    "MappingError",
    "CLAIM_169_KEY_MAPPER",
    "CLAIM_169_VALUE_MAPPER",
    "CLAIM_169_REVERSE_KEY_MAPPER",
    "replace_values_for_claim169",
    "reverse_mapper",
    "__version__",
]
