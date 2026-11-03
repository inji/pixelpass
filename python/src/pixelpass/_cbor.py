"""CBOR codec compatible with cbor-web 9.0.2 as used by the JS reference (DESIGN ADR-1 option A).

Encoder (``cbor.encode``): an integral number with ``|x| <= 2^53-1`` (``-2^53+1`` on the negative
side) is a CBOR integer; any other finite number is float32 when exact, else float64; -0, NaN and
+/-Infinity are the half-precision specials; strings are UTF-8 (lone surrogates become U+FFFD);
objects are maps with text keys in property order.

Decoder (``cbor.decodeFirstSync``): the whole input must be exactly one item. Text-key maps become
objects (JS order, last duplicate wins); any other key makes a :class:`JSMap`. 64-bit integers above
2^53-1 are BigInts (Python ``int``). Tags are converted as cbor-web's default tag table does.
"""
from __future__ import annotations

import math
import re
import struct
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import _js
from ._js import (
    UNDEFINED,
    Buffer,
    JSDate,
    JSMap,
    JSRegExp,
    JSSet,
    JSURL,
    Simple,
    Tagged,
    TypedArray,
)

_MAX_SAFE = _js.MAX_SAFE_INTEGER
MAX_BIGNUM_BYTES = 1024  # tag 2/3 bignums: about 2467 decimal digits, under CPython's 4300-digit str() limit


class CborError(ValueError):
    """Undecodable or unencodable CBOR. The message holds positions only, never payload."""

    def __init__(self, reason: str, pos: int = 0) -> None:
        super().__init__(f"{reason} at pos {pos}")
        self.pos = pos


class BignumTooLargeError(CborError):
    """A tag 2/3 bignum longer than MAX_BIGNUM_BYTES: valid CBOR, rejected by this decoder's cap."""


# ============================================================================= encoder
def _head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([(major << 5) | n])
    if n <= 0xFF:
        return bytes([(major << 5) | 24, n])
    if n <= 0xFFFF:
        return bytes([(major << 5) | 25]) + struct.pack(">H", n)
    if n <= 0xFFFFFFFF:
        return bytes([(major << 5) | 26]) + struct.pack(">I", n)
    return bytes([(major << 5) | 27]) + struct.pack(">Q", n)


def _float(x: float) -> bytes:
    try:
        single = struct.pack(">f", x)
    except OverflowError:
        single = b""
    if single and struct.unpack(">f", single)[0] == x:
        return b"\xfa" + single
    return b"\xfb" + struct.pack(">d", x)


def _number(x: float) -> bytes:
    if math.isnan(x):
        return b"\xf9\x7e\x00"
    if math.isinf(x):
        return b"\xf9\x7c\x00" if x > 0 else b"\xf9\xfc\x00"
    if x == math.floor(x):
        if x == 0:
            return b"\xf9\x80\x00" if math.copysign(1.0, x) < 0 else b"\x00"
        if x > 0:
            return _head(0, int(x)) if x <= _MAX_SAFE else _float(x)
        n = -x - 1
        return _head(1, int(n)) if n <= _MAX_SAFE - 1 else _float(x)
    return _float(x)


def _to_js_number(x: int) -> float:
    try:
        return float(x)
    except OverflowError:
        return math.inf if x > 0 else -math.inf


def encode(value: Any) -> bytes:
    """``cbor.encode(value)`` for JSON-like values (Python ints are JS numbers here)."""
    out: List[bytes] = []
    try:
        _encode_into(value, out)
    except RecursionError:
        out = []  # nesting deeper than the interpreter stack; raised below, outside the handler
    else:
        return b"".join(out)
    raise CborError("nesting too deep", 0)


def _encode_into(value: Any, out: List[bytes]) -> None:
    if value is None:
        out.append(b"\xf6")
    elif value is UNDEFINED:
        out.append(b"\xf7")
    elif value is True:
        out.append(b"\xf5")
    elif value is False:
        out.append(b"\xf4")
    elif isinstance(value, float):
        out.append(_number(value))
    elif isinstance(value, int):
        out.append(_number(_to_js_number(value)))
    elif isinstance(value, str):
        raw = _js.utf8_encode(value)
        out.append(_head(3, len(raw)))
        out.append(raw)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        out.append(_head(2, len(raw)))
        out.append(raw)
    elif isinstance(value, (list, tuple)):
        out.append(_head(4, len(value)))
        for item in value:
            _encode_into(item, out)
    elif isinstance(value, dict):
        entries = _js.js_order({_js.js_string(k): v for k, v in value.items()})
        entries = {k: v for k, v in entries.items() if not callable(v)}
        out.append(_head(5, len(entries)))
        for k, v in entries.items():
            raw = _js.utf8_encode(k)
            out.append(_head(3, len(raw)))
            out.append(raw)
            _encode_into(v, out)
    else:
        raise CborError(f"unsupported value type {type(value).__name__}")


# ============================================================================= decoder
_BREAK = object()


def _half(b: bytes) -> float:
    sign = -1.0 if b[0] & 0x80 else 1.0
    exp = (b[0] & 0x7C) >> 2
    mant = ((b[0] & 0x03) << 8) | b[1]
    if exp == 0:
        return 5.960464477539063e-8 * sign * mant
    if exp == 31:
        return sign * (math.nan if mant else math.inf)
    return sign * 2.0 ** (exp - 25) * (1024 + mant)


def _ident(key: Any) -> Tuple[Any, ...]:
    """SameValueZero identity of a Map key."""
    if isinstance(key, float):
        if math.isnan(key):
            return ("n", "NaN")
        return ("n", key + 0.0)
    if isinstance(key, bool):
        return ("bool", key)
    if isinstance(key, int):
        return ("big", key)
    if isinstance(key, str):
        return ("s", key)
    if key is None:
        return ("null",)
    if key is UNDEFINED:
        return ("undef",)
    return ("obj", id(key))


class _Decoder:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def read(self, n: int) -> bytes:
        end = self.pos + n
        if end > len(self.data):
            raise CborError("insufficient data", self.pos)
        chunk = self.data[self.pos : end]
        self.pos = end
        return chunk

    def item(self, in_indefinite: bool = False) -> Any:
        start = self.pos
        ib = self.read(1)[0]
        major, ai = ib >> 5, ib & 31
        arg: Any
        if ai < 24:
            arg = ai
        elif ai == 24:
            arg = self.read(1)[0]
        elif ai in (25, 26, 27):
            raw = self.read(1 << (ai - 24))
            if major == 7:
                return self._float(raw)
            arg = self._uint(ai, raw)
        elif ai in (28, 29, 30):
            raise CborError("additional info not implemented", start)
        else:
            if major in (0, 1, 6):
                raise CborError("invalid indefinite encoding", start)
            arg = -1

        if major == 0:
            return arg if isinstance(arg, int) and arg > _MAX_SAFE else float(arg)
        if major == 1:
            if arg > _MAX_SAFE or arg == _MAX_SAFE:
                return -1 - arg  # BigInt (cbor-web: NEG_MAX when n == 2^53-1)
            return float(-1 - arg)
        if major in (2, 3):
            if arg == -1:
                return self._indefinite_string(major, start)
            raw = self.read(arg)
            return self._text(raw, start) if major == 3 else Buffer(raw)
        if major == 4:
            return self._array(arg)
        if major == 5:
            return self._map(arg, start)
        if major == 6:
            if arg > _MAX_SAFE:
                raise CborError("invalid tag type", start)
            value = self.item()
            return _convert_tag(arg, value)
        # major 7, ai < 24 or ai == 24 or ai == 31
        if ai == 31:
            if not in_indefinite:
                raise CborError("invalid BREAK", start)
            return _BREAK
        if ai == 24 and arg < 32:
            raise CborError("invalid two-byte encoding of simple value", start)
        if arg == 20:
            return False
        if arg == 21:
            return True
        if arg == 22:
            return None
        if arg == 23:
            return UNDEFINED
        return Simple(arg)

    @staticmethod
    def _uint(ai: int, raw: bytes) -> int:
        if ai == 25:
            return struct.unpack(">H", raw)[0]
        if ai == 26:
            return struct.unpack(">I", raw)[0]
        return struct.unpack(">Q", raw)[0]

    @staticmethod
    def _float(raw: bytes) -> float:
        if len(raw) == 2:
            return _half(raw)
        if len(raw) == 4:
            return struct.unpack(">f", raw)[0]
        return struct.unpack(">d", raw)[0]

    @staticmethod
    def _text(raw: bytes, pos: int) -> str:
        """cbor-web decodes text with ``TextDecoder('utf8', {fatal: true, ignoreBOM: true})``."""
        text: Optional[str] = None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is None:
            raise CborError("invalid UTF-8 in text string", pos)
        return text

    def _indefinite_string(self, major: int, start: int) -> Any:
        chunks: List[Any] = []
        while True:
            at = self.pos
            if at >= len(self.data):
                raise CborError("insufficient data", at)
            if self.data[at] != 0xFF and (self.data[at] >> 5) != major:
                raise CborError("invalid major type in indefinite encoding", at)
            chunk = self.item(in_indefinite=True)
            if chunk is _BREAK:
                break
            chunks.append(chunk)
        if major == 3:
            return "".join(chunks)
        return Buffer(b"".join(c.data for c in chunks))

    def _array(self, n: int) -> List[Any]:
        out: List[Any] = []
        if n == -1:
            while True:
                v = self.item(in_indefinite=True)
                if v is _BREAK:
                    return out
                out.append(v)
        for _ in range(n):
            out.append(self.item())
        return out

    def _map(self, n: int, start: int) -> Any:
        flat: List[Any] = []
        if n == -1:
            while True:
                v = self.item(in_indefinite=True)
                if v is _BREAK:
                    break
                flat.append(v)
            if len(flat) % 2:
                raise CborError("invalid map length", start)
        else:
            for _ in range(2 * n):
                flat.append(self.item())
        keys = flat[0::2]
        values = flat[1::2]
        if all(isinstance(k, str) and k != "__proto__" for k in keys):
            obj: Dict[str, Any] = {}
            for k, v in zip(keys, values):
                obj[k] = v
            return _js.js_order(obj)
        index: Dict[Tuple[Any, ...], int] = {}
        pairs: List[Tuple[Any, Any]] = []
        for k, v in zip(keys, values):
            ident = _ident(k)
            if ident in index:
                pairs[index[ident]] = (pairs[index[ident]][0], v)
            else:
                index[ident] = len(pairs)
                pairs.append((k, v))
        return JSMap(pairs)


def decode_first(data: bytes) -> Any:
    """``cbor.decodeFirstSync(data)``: exactly one item, else :class:`CborError`."""
    dec = _Decoder(bytes(data))
    try:
        value = dec.item()
    except RecursionError:
        value = _BREAK
    if value is _BREAK:
        raise CborError("nesting too deep", 0)
    if dec.pos != len(dec.data):
        raise CborError("unexpected data after the first item", dec.pos)
    return value


# ============================================================================= tags (cbor-web Tagged.TAGS)
_B64URL_RE = re.compile(r"[a-zA-Z0-9_-]+")
_B64_RE = re.compile(r"[a-zA-Z0-9+/]+(={0,2})")

# tag -> (kind, element size, struct format char)
_TYPED: Dict[int, Tuple[str, int, str]] = {
    64: ("u8", 1, "B"),
    65: ("u16", 2, "H"),
    66: ("u32", 4, "I"),
    67: ("u64", 8, "Q"),
    68: ("u8c", 1, "B"),
    69: ("u16", 2, "H"),
    70: ("u32", 4, "I"),
    71: ("u64", 8, "Q"),
    72: ("i8", 1, "b"),
    73: ("i16", 2, "h"),
    74: ("i32", 4, "i"),
    75: ("i64", 8, "q"),
    77: ("i16", 2, "h"),
    78: ("i32", 4, "i"),
    79: ("i64", 8, "q"),
    81: ("f32", 4, "f"),
    82: ("f64", 8, "d"),
    85: ("f32", 4, "f"),
    86: ("f64", 8, "d"),
}


def _bufferish(value: Any) -> Optional[bytes]:
    if isinstance(value, Buffer):
        return value.data
    if isinstance(value, TypedArray) and value.kind in ("u8", "u8c"):
        return value.raw
    return None


def _set_json(value: Any, kind: str) -> None:
    """cbor-web ``s(e, t)``: give nested buffers a toJSON override (skips Tagged 21..23)."""
    if isinstance(value, (Buffer, TypedArray)):
        if _bufferish(value) is not None:
            value.json_kind = kind
    elif isinstance(value, list):
        for item in value:
            _set_json(item, kind)
    elif isinstance(value, dict):
        for item in value.values():
            _set_json(item, kind)
    elif isinstance(value, Tagged):
        if not 21 <= value.tag <= 23:
            _set_json(value.value, kind)
            _set_json(value.err, kind)


def _date_ms(value: Any) -> Optional[float]:
    """``new Date(value)`` time value; None when JS would throw."""
    if isinstance(value, float):
        return _js.time_clip(value)
    if isinstance(value, str):
        return _js.parse_date(value)
    if isinstance(value, bool):
        return float(value)
    if value is None:
        return 0.0
    if isinstance(value, int):
        return None
    if isinstance(value, (Buffer, list)):
        return _js.parse_date(_js.js_string(value))
    return math.nan


def _epoch_ms(value: Any) -> Optional[float]:
    """``new Date(1e3 * value)``; None when JS would throw (BigInt)."""
    if isinstance(value, float):
        return _js.time_clip(1000.0 * value)
    if isinstance(value, bool):
        return _js.time_clip(1000.0 * value)
    if value is None:
        return 0.0
    if isinstance(value, int):
        return None
    if isinstance(value, str):
        return _js.time_clip(1000.0 * _js.to_number(value))
    return math.nan


def _validate_b64url(value: str) -> Optional[str]:
    if not _B64URL_RE.fullmatch(value):
        return "Invalid base64url characters"
    rem = len(value) % 4
    if rem == 1:
        return "Invalid base64url length"
    if rem == 2 and value[-1] not in "AQgw":
        return "Invalid base64 padding"
    if rem == 3 and value[-1] not in "AEIMQUYcgkosw048":
        return "Invalid base64 padding"
    return None


def _validate_b64(value: str) -> Optional[str]:
    m = _B64_RE.fullmatch(value)
    if not m:
        return "Invalid base64 characters"
    if len(value) % 4:
        return "Invalid base64 length"
    if m.group(1) == "=" and value[-2] not in "AQgw":
        return "Invalid base64 padding"
    if m.group(1) == "==" and value[-3] not in "AEIMQUYcgkosw048":
        return "Invalid base64 padding"
    return None


def _typed_array(tag: int, value: Any) -> Any:
    raw = _bufferish(value)
    if raw is None:
        return Tagged(tag, value, "val not a buffer")
    kind, size, fmt = _TYPED[tag]
    if len(raw) % size:
        return Tagged(tag, value, f"byte length should be a multiple of {size}")
    order = "<" if tag & 4 else ">"
    values: List[Any] = list(struct.unpack(f"{order}{len(raw) // size}{fmt}", raw)) if raw else []
    if kind in ("f32", "f64"):
        values = [float(v) for v in values]
    elif kind not in ("u64", "i64"):
        values = [float(v) for v in values]
    return TypedArray(kind, values, raw)


def _convert_tag(tag: int, value: Any) -> Any:
    converter: Optional[Callable[[int, Any], Any]] = _TAGS.get(tag)
    if tag in _TYPED:
        return _typed_array(tag, value)
    if converter is None:
        return Tagged(tag, value)
    return converter(tag, value)


def _tag_date_string(tag: int, value: Any) -> Any:
    ms = _date_ms(value)
    return Tagged(tag, value, "Cannot convert a BigInt value to a number") if ms is None else JSDate(ms)


def _tag_date_epoch(tag: int, value: Any) -> Any:
    ms = _epoch_ms(value)
    return Tagged(tag, value, "Cannot mix BigInt and other types, use explicit conversions") if ms is None else JSDate(ms)


def _tag_bignum(tag: int, value: Any) -> Any:
    if not isinstance(value, Buffer) or not value.data:
        return Tagged(tag, value, "Cannot convert value to a BigInt")
    if len(value.data) > MAX_BIGNUM_BYTES:
        # str() of a bigger int can hit CPython's 4300-digit limit (raw ValueError) and is quadratic on 3.9
        raise BignumTooLargeError("bignum too large", 0)
    n = int.from_bytes(value.data, "big")
    return n if tag == 2 else -1 - n


def _tag_expected(kind: str) -> Callable[[int, Any], Any]:
    def convert(tag: int, value: Any) -> Any:
        t = Tagged(tag, value)
        if _bufferish(value) is not None:
            t.json_kind = kind
        else:
            _set_json(value, kind)
        return t

    return convert


def _tag_uri(tag: int, value: Any) -> Any:
    if isinstance(value, str) and re.match(r"[A-Za-z][A-Za-z0-9+.-]*:", value):
        return JSURL(value)
    return Tagged(tag, value, "Invalid URL")


def _tag_b64url(tag: int, value: Any) -> Any:
    err = _validate_b64url(value) if isinstance(value, str) else "e.match is not a function"
    return Tagged(tag, value, err) if err else Tagged(tag, value)


def _tag_b64(tag: int, value: Any) -> Any:
    err = _validate_b64(value) if isinstance(value, str) else "e.match is not a function"
    return Tagged(tag, value, err) if err else Tagged(tag, value)


def _tag_regexp(tag: int, value: Any) -> Any:
    return JSRegExp(_js.js_string(value))


def _tag_set(tag: int, value: Any) -> Any:
    if isinstance(value, list):
        return JSSet(list(value))
    if isinstance(value, str):
        return JSSet(_js.utf16_units(value))
    if isinstance(value, (Buffer, TypedArray)):
        return JSSet([])
    return Tagged(tag, value, "object is not iterable")


_TAGS: Dict[int, Callable[[int, Any], Any]] = {
    0: _tag_date_string,
    1: _tag_date_epoch,
    2: _tag_bignum,
    3: _tag_bignum,
    21: _tag_expected("base64url"),
    22: _tag_expected("base64"),
    23: _tag_expected("hex"),
    32: _tag_uri,
    33: _tag_b64url,
    34: _tag_b64,
    35: _tag_regexp,
    258: _tag_set,
}
