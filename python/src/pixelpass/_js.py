"""JavaScript value model and the JS semantics the reference relies on (DESIGN ADR-2).

Internal value model (what the CBOR decoder and :func:`js_parse` produce):

* ``float`` is a JS number, ``int`` (never ``bool``) is a JS BigInt;
* ``str``, ``bool``, ``None`` (null) and :data:`UNDEFINED`;
* ``dict`` (str keys, kept in JS property order) and ``list``;
* :class:`JSMap`, :class:`Buffer`, :class:`Tagged`, :class:`Simple`, :class:`JSDate`,
  :class:`TypedArray`, :class:`JSSet`, :class:`JSRegExp`, :class:`JSURL` for the objects cbor-web creates.

Functions here emulate ``JSON.parse``, ``JSON.stringify``, ``String(x)``, ``Number(str)``,
``parseInt(str, 10)``, ES ``Number::toString``, object spread and the WHATWG ``TextDecoder``.
"""
from __future__ import annotations

import base64
import json
import math
import re
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

MAX_SAFE_INTEGER = 9007199254740991
_MAX_ARRAY_INDEX = 4294967294
_INDEX_RE = re.compile(r"0|[1-9][0-9]*")


class _Undefined:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNDEFINED"

    def __bool__(self) -> bool:
        return False


UNDEFINED = _Undefined()


class JSBigIntError(TypeError):
    """JSON.stringify met a BigInt ("Do not know how to serialize a BigInt")."""


class JSMap:
    """A JS Map (cbor-web uses one when a CBOR map has a non-text key)."""

    __slots__ = ("pairs",)

    def __init__(self, pairs: List[Tuple[Any, Any]]) -> None:
        self.pairs = pairs


class Buffer:
    """A Node Buffer (CBOR byte string). ``json_kind`` is set by tags 21/22/23 (toJSON override)."""

    __slots__ = ("data", "json_kind")

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.json_kind: Optional[str] = None


class Tagged:
    """cbor-web Tagged: ``{tag, value, err}``; ``json_kind`` is cbor-web's INTERNAL_JSON (tags 21/22/23)."""

    __slots__ = ("tag", "value", "err", "json_kind")

    def __init__(self, tag: float, value: Any, err: Any = UNDEFINED) -> None:
        self.tag = tag
        self.value = value
        self.err = err
        self.json_kind: Optional[str] = None


class Simple:
    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value


class JSDate:
    """A JS Date; ``ms`` is the time value (NaN for an invalid date)."""

    __slots__ = ("ms",)

    def __init__(self, ms: float) -> None:
        self.ms = ms


class TypedArray:
    """A JS typed array (tags 64..86). ``json_kind`` is set on Uint8 arrays by tags 21/22/23."""

    __slots__ = ("kind", "values", "raw", "json_kind")

    def __init__(self, kind: str, values: List[Any], raw: bytes) -> None:
        self.kind = kind
        self.values = values
        self.raw = raw
        self.json_kind: Optional[str] = None


class JSSet:
    __slots__ = ("items",)

    def __init__(self, items: List[Any]) -> None:
        self.items = items


class JSRegExp:
    __slots__ = ("source",)

    def __init__(self, source: str) -> None:
        self.source = source


class JSURL:
    __slots__ = ("href",)

    def __init__(self, href: str) -> None:
        self.href = href


# ----------------------------------------------------------------------------- strings
def _has_surrogate(s: str) -> bool:
    try:
        s.encode("utf-8")
    except UnicodeEncodeError:
        return True
    return False


def combine_surrogates(s: str) -> str:
    """Join surrogate pairs held as two code points; lone surrogates stay (JS UTF-16 view)."""
    if not _has_surrogate(s):
        return s
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "surrogatepass")


def well_formed(s: str) -> str:
    """TextEncoder / Buffer UTF-8 view of a JS string: pairs joined, lone surrogates become U+FFFD."""
    if not _has_surrogate(s):
        return s
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


def utf8_encode(s: str) -> bytes:
    return well_formed(s).encode("utf-8")


def utf16_units(s: str) -> List[str]:
    """The UTF-16 code units of a JS string (what string spread / indexing sees)."""
    out: List[str] = []
    for ch in combine_surrogates(s):
        cp = ord(ch)
        if cp > 0xFFFF:
            cp -= 0x10000
            out.append(chr(0xD800 + (cp >> 10)))
            out.append(chr(0xDC00 + (cp & 0x3FF)))
        else:
            out.append(ch)
    return out


def text_decode(raw: bytes) -> str:
    """WHATWG ``new TextDecoder().decode(raw)``: UTF-8, U+FFFD replacement, one leading BOM stripped."""
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("utf-8", "replace")


# ----------------------------------------------------------------------------- property order
def is_array_index(key: str) -> bool:
    return _INDEX_RE.fullmatch(key) is not None and int(key) <= _MAX_ARRAY_INDEX


def js_order(d: Dict[str, Any]) -> Dict[str, Any]:
    """Reorder like a JS object: array-index keys ascending first, then insertion order."""
    index_keys = [k for k in d if isinstance(k, str) and is_array_index(k)]
    if not index_keys:
        return d
    out = {k: d[k] for k in sorted(index_keys, key=int)}
    for k, v in d.items():
        if k not in out:
            out[k] = v
    return out


# ----------------------------------------------------------------------------- numbers
def number_to_string(x: float) -> str:
    """ES ``Number::toString(10)`` for a JS number."""
    if math.isnan(x):
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0"
    if x < 0:
        return "-" + number_to_string(-x)
    sign, digits_t, exp = Decimal(repr(float(x))).as_tuple()
    digits = "".join(map(str, digits_t)).rstrip("0") or "0"
    stripped = len("".join(map(str, digits_t))) - len(digits)
    k = len(digits)
    n = k + int(exp) + stripped
    if k <= n <= 21:
        return digits + "0" * (n - k)
    if 0 < n <= 21:
        return digits[:n] + "." + digits[n:]
    if -6 < n <= 0:
        return "0." + "0" * (-n) + digits
    e = n - 1
    e_str = ("+" if e >= 0 else "-") + str(abs(e))
    if k == 1:
        return digits + "e" + e_str
    return digits[0] + "." + digits[1:] + "e" + e_str


_JS_WS = "\t\n\x0b\x0c\r \xa0                　﻿"
_DEC_LITERAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_NON_DEC = re.compile(r"0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+")
_PARSE_INT = re.compile(r"[+-]?[0-9]+")


def to_number(s: str) -> float:
    """ES ``Number(string)`` (StringToNumber)."""
    t = s.strip(_JS_WS)
    if t == "":
        return 0.0
    if t in ("Infinity", "+Infinity"):
        return math.inf
    if t == "-Infinity":
        return -math.inf
    if _NON_DEC.fullmatch(t):
        return float(int(t, 0))
    if _DEC_LITERAL.fullmatch(t):
        return float(t)
    return math.nan


def parse_int10(s: str) -> float:
    """ES ``parseInt(string, 10)``."""
    m = _PARSE_INT.match(s.lstrip(_JS_WS))
    if not m:
        return math.nan
    return float(m.group(0))


def is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


# ----------------------------------------------------------------------------- String(x)
def js_string(x: Any) -> str:
    """ES ``String(x)`` / ToPropertyKey for the value model (and plain Python values)."""
    if isinstance(x, str):
        return x
    if x is None:
        return "null"
    if x is UNDEFINED:
        return "undefined"
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return number_to_string(x)
    if isinstance(x, (list, tuple)):
        return ",".join("" if (i is None or i is UNDEFINED) else js_string(i) for i in x)
    if isinstance(x, Buffer):
        return x.data.decode("utf-8", "replace")
    if isinstance(x, (bytes, bytearray)):
        return bytes(x).decode("utf-8", "replace")
    if isinstance(x, TypedArray):
        return ",".join(js_string(v) for v in x.values)
    if isinstance(x, Simple):
        return f"simple({x.value})"
    if isinstance(x, Tagged):
        try:
            inner = stringify(x.value)
        except JSBigIntError:
            inner = "undefined"
        return f"{number_to_string(float(x.tag))}({inner if inner is not None else 'undefined'})"
    if isinstance(x, JSDate):
        return date_to_string(x.ms)
    if isinstance(x, JSMap):
        return "[object Map]"
    if isinstance(x, JSSet):
        return "[object Set]"
    if isinstance(x, JSRegExp):
        return "/" + x.source + "/"
    if isinstance(x, JSURL):
        return x.href
    return "[object Object]"


# ----------------------------------------------------------------------------- spread {...x}
def spread(x: Any) -> Dict[str, Any]:
    """ES object spread ``{...x}`` (own enumerable string-keyed properties)."""
    if isinstance(x, dict):
        return js_order({js_string(k): v for k, v in x.items()})
    if isinstance(x, (list, tuple)):
        return {str(i): v for i, v in enumerate(x)}
    if isinstance(x, str):
        return {str(i): u for i, u in enumerate(utf16_units(x))}
    return {}


# ----------------------------------------------------------------------------- dates
_ISO_RE = re.compile(
    r"([+-]\d{6}|\d{4})(?:-(\d{2})(?:-(\d{2}))?)?"
    r"(?:T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(Z|[+-]\d{2}:\d{2})?)?"
)
_MS_PER_DAY = 86400000
_DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _days_from_civil(y: int, m: int, d: int) -> int:
    y -= m <= 2
    era = y // 400  # floor division (the C original truncates and adjusts)
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def _civil_from_days(z: int) -> Tuple[int, int, int]:
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return y + (m <= 2), m, d


def _days_in_month(y: int, m: int) -> int:
    if m == 2:
        return 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28
    return 30 if m in (4, 6, 9, 11) else 31


def time_clip(t: float) -> float:
    if math.isnan(t) or math.isinf(t) or abs(t) > 8.64e15:
        return math.nan
    return float(math.trunc(t)) + 0.0


def parse_date(s: str) -> float:
    """``Date.parse`` for the ES Date Time String Format (other formats give NaN; local time is UTC)."""
    m = _ISO_RE.fullmatch(s)
    if not m:
        return math.nan
    ys, mo, da, hh, mi, ss, frac, tz = m.groups()
    if ys == "-000000":
        return math.nan
    y = int(ys)
    month = int(mo) if mo else 1
    day = int(da) if da else 1
    hour = int(hh) if hh else 0
    minute = int(mi) if mi else 0
    sec = int(ss) if ss else 0
    ms = int((frac or "0")[:3].ljust(3, "0"))
    if not (1 <= month <= 12 and 1 <= day <= _days_in_month(y, month)):
        return math.nan
    if minute > 59 or sec > 59 or hour > 24 or (hour == 24 and (minute or sec or ms)):
        return math.nan
    t = float(_days_from_civil(y, month, day) * _MS_PER_DAY + ((hour * 60 + minute) * 60 + sec) * 1000 + ms)
    if tz and tz != "Z":
        oh, om = int(tz[1:3]), int(tz[4:6])
        if oh > 23 or om > 59:
            return math.nan
        off = (oh * 60 + om) * 60000
        t = t - off if tz[0] == "+" else t + off
    return time_clip(t)


def _split_time(ms: float) -> Tuple[int, int, int, int, int, int, int, int]:
    t = int(ms)
    days, rem = divmod(t, _MS_PER_DAY)
    y, m, d = _civil_from_days(days)
    hour, rem = divmod(rem, 3600000)
    minute, rem = divmod(rem, 60000)
    sec, milli = divmod(rem, 1000)
    weekday = (days + 4) % 7
    return y, m, d, hour, minute, sec, milli, weekday


def date_to_iso(ms: float) -> Optional[str]:
    """``Date.prototype.toJSON``: ISO string, or None (JSON null) for an invalid date."""
    if math.isnan(ms):
        return None
    y, m, d, hour, minute, sec, milli, _ = _split_time(ms)
    ys = f"{y:04d}" if 0 <= y <= 9999 else ("+" if y > 0 else "-") + f"{abs(y):06d}"
    return f"{ys}-{m:02d}-{d:02d}T{hour:02d}:{minute:02d}:{sec:02d}.{milli:03d}Z"


def date_to_string(ms: float) -> str:
    if math.isnan(ms):
        return "Invalid Date"
    y, m, d, hour, minute, sec, _, wd = _split_time(ms)
    ys = f"{y:04d}" if y >= 0 else f"-{abs(y):06d}"
    return f"{_DAYS[wd]} {_MONTHS[m - 1]} {d:02d} {ys} {hour:02d}:{minute:02d}:{sec:02d} GMT+0000 (Coordinated Universal Time)"


# ----------------------------------------------------------------------------- JSON.parse
class JSONParseError(ValueError):
    """Text is not valid JSON under JSON.parse rules."""

    def __init__(self, pos: int) -> None:
        super().__init__(f"invalid JSON at pos {pos}")
        self.pos = pos


def _reject_constant(name: str) -> Any:
    raise ValueError("non-JSON constant")


def _js_object(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for k, v in pairs:
        d[k] = v  # duplicate key: last value wins, first position kept (JSON.parse)
    return js_order(d)


def js_parse(text: str) -> Any:
    """``JSON.parse``: numbers as IEEE doubles, JS property order, NaN/Infinity rejected."""
    try:
        return json.loads(
            text,
            object_pairs_hook=_js_object,
            parse_int=float,
            parse_float=float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        pos = exc.pos
    except (ValueError, RecursionError):
        pos = 0
    raise JSONParseError(pos)


# ----------------------------------------------------------------------------- JSON.stringify
_ESCAPES = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
_ESC_RE = re.compile("[\\x00-\\x1f\"\\\\\ud800-\udfff]")


def _escape(m: "re.Match[str]") -> str:
    ch = m.group(0)
    return _ESCAPES.get(ch) or "\\u%04x" % ord(ch)


def quote(s: str) -> str:
    """``JSON.stringify(string)`` (well-formed: lone surrogates escaped as lowercase \\uXXXX)."""
    return '"' + _ESC_RE.sub(_escape, combine_surrogates(s)) + '"'


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _buffer_json(kind: str, data: bytes) -> str:
    if kind == "base64url":
        return _b64url(data)
    if kind == "base64":
        return base64.b64encode(data).decode("ascii")
    return data.hex()


def _to_json_value(x: Any, bigint_error: bool) -> Any:
    """Apply toJSON-like conversions; returns a value stringify can serialise directly."""
    if isinstance(x, Buffer):
        if x.json_kind:
            return _buffer_json(x.json_kind, x.data)
        return {"type": "Buffer", "data": [float(b) for b in x.data]}
    if isinstance(x, TypedArray):
        if x.json_kind:
            return _buffer_json(x.json_kind, x.raw)
        return {str(i): v for i, v in enumerate(x.values)}
    if isinstance(x, Tagged):
        if x.json_kind:
            value = x.value
            raw = value.data if isinstance(value, Buffer) else value.raw
            return _buffer_json(x.json_kind, raw)
        out: Dict[str, Any] = {"tag": float(x.tag), "value": x.value}
        if x.err is not UNDEFINED and x.err:
            out["err"] = x.err
        return out
    if isinstance(x, Simple):
        return {"value": float(x.value)}
    if isinstance(x, JSDate):
        return date_to_iso(x.ms)
    if isinstance(x, JSURL):
        return x.href
    if isinstance(x, (JSMap, JSSet, JSRegExp)):
        return {}
    return x


def stringify(x: Any, bigint_error: bool = True) -> Optional[str]:
    """``JSON.stringify(x)`` (compact). Returns None where JS returns undefined.

    With ``bigint_error`` a Python ``int`` is a JS BigInt and raises :class:`JSBigIntError`;
    otherwise it is printed as a decimal integer (plain Python values on the mapping path).
    """
    parts: List[str] = []
    if _stringify_into(x, parts, bigint_error, top=True) is False:
        return None
    return "".join(parts)


def _stringify_into(x: Any, out: List[str], bigint_error: bool, top: bool = False) -> bool:
    x = _to_json_value(x, bigint_error)
    if x is None:
        out.append("null")
    elif x is True:
        out.append("true")
    elif x is False:
        out.append("false")
    elif isinstance(x, str):
        out.append(quote(x))
    elif isinstance(x, float):
        out.append(number_to_string(x) if math.isfinite(x) else "null")
    elif isinstance(x, int):
        if bigint_error:
            raise JSBigIntError("BigInt")
        out.append(str(x))
    elif isinstance(x, (list, tuple)):
        out.append("[")
        first = True
        for item in x:
            if not first:
                out.append(",")
            first = False
            if not _stringify_into(item, out, bigint_error):
                out.append("null")
        out.append("]")
    elif isinstance(x, dict):
        out.append("{")
        first = True
        for k, v in js_order({js_string(k): v for k, v in x.items()}).items():
            if v is UNDEFINED or callable(v):
                continue
            mark = len(out)
            out.append(("" if first else ",") + quote(k) + ":")
            if not _stringify_into(v, out, bigint_error):
                del out[mark:]
                continue
            first = False
        out.append("}")
    else:
        return False  # undefined, functions and unknown objects are not serialisable
    return True


# ----------------------------------------------------------------------------- translateToJson + Python view
def to_python(x: Any) -> Any:
    """cborUtils.translateToJson, then the Python view of the result.

    Whole doubles below 1e21 (where JS prints plain digits) and -0 become ``int``; other numbers stay
    ``float``; BigInt stays ``int``. Map keys go through ``String()``. ``undefined`` is dropped from
    objects and becomes None in arrays and at the top level (as JSON.stringify would).
    """
    v = _translate(x)
    return None if v is UNDEFINED else v


def _num(x: float) -> Any:
    if math.isfinite(x) and x == math.floor(x) and abs(x) < 1e21:
        return int(x)
    return x


def _obj(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    d: Dict[str, Any] = {}
    for k, v in pairs:
        d[k] = v
    return {k: v for k, v in js_order(d).items() if v is not UNDEFINED}


def _translate(x: Any) -> Any:
    if isinstance(x, float):
        return _num(x)
    if x is None or isinstance(x, (str, bool, int)) or x is UNDEFINED:
        return x
    if isinstance(x, (list, tuple)):
        return _translate_list(x)
    if isinstance(x, dict):
        return _obj((js_string(k), _translate(v)) for k, v in x.items())
    if isinstance(x, JSMap):
        return _obj((js_string(k), _translate(v)) for k, v in x.pairs)
    if isinstance(x, Buffer):
        return {str(i): b for i, b in enumerate(x.data)}
    if isinstance(x, TypedArray):
        return {str(i): _translate(v) for i, v in enumerate(x.values)}
    if isinstance(x, Tagged):
        return _obj([("tag", _translate(float(x.tag))), ("value", _translate(x.value)), ("err", _translate(x.err))])
    if isinstance(x, Simple):
        return {"value": x.value}
    return {}


def _translate_list(x: Iterable[Any]) -> List[Any]:
    out = []
    for i in x:
        v = _translate(i)
        out.append(None if v is UNDEFINED else v)
    return out


def is_truthy(x: Any) -> bool:
    """JS ToBoolean for the value model."""
    if x is None or x is UNDEFINED or x is False:
        return False
    if isinstance(x, float):
        return not (x == 0 or math.isnan(x))
    if isinstance(x, int) and not isinstance(x, bool):
        return x != 0
    if isinstance(x, str):
        return x != ""
    return True
