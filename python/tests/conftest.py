"""Shared fixtures and test-side oracles for the PixelPass Python SDK acceptance tests (PP-PYSDK).

The tests are an independent oracle written from the acceptance criteria and the JS-generated golden
vectors, before the implementation. They import only the public API of ``pixelpass``.
Helpers here (Base45 reference codec, tiny CBOR builders) are test-side oracles; they never call SDK
internals.
"""
from __future__ import annotations

import base64
import functools
import json
import math
import pathlib
import struct
import zlib
from typing import Any, Callable, Iterable, List, Optional

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PYTHON_ROOT = TESTS_DIR.parent
SRC_PKG = PYTHON_ROOT / "src" / "pixelpass"
GOLDEN_DIR = TESTS_DIR / "golden"
GOLDEN_FILE = GOLDEN_DIR / "vectors.json"

UPSTREAM_COMMIT = "c9e2258d9ba66c1cd493fef3efb51f9abaa66501"
JS_PACKAGE_VERSION = "1.0.0-rc.2"
JS_DEPENDENCIES = {
    "base45-web": "1.0.2",
    "cbor-web": "9.0.2",
    "jszip": "3.10.1",
    "pako": "2.1.0",
    "qrcode": "1.5.3",
}

DEFAULT_MAX_ENCODED = 65536
DEFAULT_MAX_DECOMPRESSED = 10485760


# ----------------------------------------------------------------------------- golden vectors
@functools.lru_cache(maxsize=1)
def golden() -> dict:
    with GOLDEN_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def vectors(function: str, pred: Optional[Callable[[dict], bool]] = None) -> List[Any]:
    """pytest params for every golden vector of a JS function (optionally filtered)."""
    out = []
    for v in golden()["vectors"]:
        if v["function"] != function:
            continue
        if pred is not None and not pred(v):
            continue
        out.append(pytest.param(v, id=v["id"]))
    return out


def from_typed(x: Any) -> Any:
    """Decode the typed JSON used in vectors: {"$float": "NaN"|"Infinity"|"-Infinity"|"-0"}, {"$int": "..."}."""
    if isinstance(x, list):
        return [from_typed(i) for i in x]
    if isinstance(x, dict):
        if len(x) == 1 and "$float" in x:
            return {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf, "-0": -0.0}[x["$float"]]
        if len(x) == 1 and "$int" in x:
            return int(x["$int"])
        return {k: from_typed(v) for k, v in x.items()}
    return x


def same_value(a: Any, b: Any) -> bool:
    """Value equality: NaN equals NaN, int == float by value, bool distinct from numbers, dict key sets equal."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) and math.isnan(a):
            return isinstance(b, float) and math.isnan(b)
        if isinstance(b, float) and math.isnan(b):
            return False
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same_value(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same_value(x, y) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def js_compact(x: Any) -> str:
    """The AC-8 oracle form: json.dumps(x, separators=(',', ':'), ensure_ascii=False)."""
    return json.dumps(x, separators=(",", ":"), ensure_ascii=False)


def assert_str_keys(x: Any, path: str = "$") -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            assert isinstance(k, str), f"non-str key {k!r} at {path}"
            assert_str_keys(v, f"{path}.{k}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            assert_str_keys(v, f"{path}[{i}]")


def mapping_args(v: dict) -> dict:
    """kwargs for get_mapped_data / decode_mapped_data from a vector's args."""
    args = dict(v.get("args") or {})
    if args.get("value_mapper") == "identity":
        args["value_mapper"] = lambda d: d
    return args


def mapping_input(v: dict) -> Any:
    if "input_json" in v:
        return json.loads(v["input_json"])
    return from_typed(v["input_value"])


# ----------------------------------------------------------------------------- Base45 reference (RFC 9285)
B45_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"


def ref_b45encode(data: bytes) -> str:
    out = []
    for i in range(0, len(data) - 1, 2):
        n = data[i] * 256 + data[i + 1]
        e, n = divmod(n, 45 * 45)
        d, c = divmod(n, 45)
        out.append(B45_ALPHABET[c] + B45_ALPHABET[d] + B45_ALPHABET[e])
    if len(data) % 2:
        d, c = divmod(data[-1], 45)
        out.append(B45_ALPHABET[c] + B45_ALPHABET[d])
    return "".join(out)


def ref_b45decode(s: str) -> bytes:
    vals = [B45_ALPHABET.index(ch) for ch in s]
    out = bytearray()
    for i in range(0, len(vals), 3):
        chunk = vals[i : i + 3]
        if len(chunk) == 3:
            n = chunk[0] + chunk[1] * 45 + chunk[2] * 2025
            out += bytes([n >> 8, n & 0xFF])
        else:
            out.append(chunk[0] + chunk[1] * 45)
    return bytes(out)


def ref_encode_bytes(raw: bytes, level: int = 9) -> str:
    """Base45(zlib(raw)) - a valid PixelPass payload built without the SDK."""
    return ref_b45encode(zlib.compress(raw, level))


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# ----------------------------------------------------------------------------- tiny CBOR builders (test oracle)
def _cbor_head(major: int, n: int) -> bytes:
    if n < 24:
        return bytes([major << 5 | n])
    if n < 0x100:
        return bytes([major << 5 | 24, n])
    if n < 0x10000:
        return bytes([major << 5 | 25]) + struct.pack(">H", n)
    if n < 0x100000000:
        return bytes([major << 5 | 26]) + struct.pack(">I", n)
    return bytes([major << 5 | 27]) + struct.pack(">Q", n)


def cbor_text(s: str) -> bytes:
    b = s.encode("utf-8")
    return _cbor_head(3, len(b)) + b


def cbor_uint(n: int) -> bytes:
    return _cbor_head(0, n)


def cbor_double(x: float) -> bytes:
    return b"\xfb" + struct.pack(">d", x)


def cbor_map(pairs: Iterable[tuple]) -> bytes:
    """pairs of already-encoded (key_bytes, value_bytes)."""
    pairs = list(pairs)
    return _cbor_head(5, len(pairs)) + b"".join(k + v for k, v in pairs)


def cbor_array(items: Iterable[bytes]) -> bytes:
    items = list(items)
    return _cbor_head(4, len(items)) + b"".join(items)


# ----------------------------------------------------------------------------- fixtures
@pytest.fixture
def pp():
    from pixelpass import PixelPass

    return PixelPass()


@pytest.fixture(scope="session")
def golden_data() -> dict:
    return golden()
