"""AC-2, AC-4, AC-6, AC-7, AC-8, AC-9, AC-10: byte/string parity with the JS reference via golden vectors.

Vectors are produced by golden/generate_vectors.js from js/src at upstream c9e2258 and are normative.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

import pytest

import pixelpass
from pixelpass import PixelPass, replace_values_for_claim169

from conftest import (
    GOLDEN_DIR,
    GOLDEN_FILE,
    JS_DEPENDENCIES,
    JS_PACKAGE_VERSION,
    PYTHON_ROOT,
    UPSTREAM_COMMIT,
    assert_str_keys,
    from_typed,
    golden,
    js_compact,
    mapping_args,
    mapping_input,
    same_value,
    vectors,
)


def _ok(v: dict) -> bool:
    """Vectors where Python must reproduce the JS result (no deliberate deviation, no error)."""
    return "python_error" not in v and "expect_error" not in v


def _header(v: dict):
    return v.get("header") or None


# ----------------------------------------------------------------------------- AC-9 provenance
def test_ac9_generator_and_vectors_committed_together():
    assert (GOLDEN_DIR / "generate_vectors.js").is_file()
    assert GOLDEN_FILE.is_file()


def test_ac9_vectors_record_upstream_provenance(golden_data):
    assert golden_data["schema_version"] == 1
    assert golden_data["upstream_commit"] == UPSTREAM_COMMIT
    assert golden_data["package"] == {"name": "@injistack/pixelpass", "version": JS_PACKAGE_VERSION}
    assert golden_data["dependencies"] == JS_DEPENDENCIES
    assert golden_data["node_version"].startswith("v")
    assert len(golden_data["js_src_sha256"]) == 64


def _js_dir() -> pathlib.Path:
    """Same default as generate_vectors.js: $PIXELPASS_JS_DIR or <repo>/js beside python/."""
    env = os.environ.get("PIXELPASS_JS_DIR")
    return pathlib.Path(env) if env else PYTHON_ROOT.parent / "js"


def js_src_digest(js_dir: pathlib.Path) -> str:
    """Python port of srcDigest() in generate_vectors.js (per-directory sorted walk, '/' paths, CRLF -> LF)."""
    h = hashlib.sha256()

    def walk(d: pathlib.Path) -> None:
        for name in sorted(os.listdir(d)):
            p = d / name
            if p.is_dir():
                walk(p)
            else:
                h.update(p.relative_to(js_dir).as_posix().encode("utf-8"))
                h.update(b"\0")
                h.update(p.read_bytes().decode("utf-8").replace("\r\n", "\n").encode("utf-8"))
                h.update(b"\0")

    walk(js_dir / "src")
    return h.hexdigest()


def test_ac9_vectors_not_stale_against_js_src(golden_data):
    """If js/src is present (repo checkout), the vectors must have been generated from exactly that source."""
    js_dir = _js_dir()
    if not (js_dir / "src").is_dir():
        pytest.skip(f"JS reference not present at {js_dir}; staleness check needs the repo checkout")
    assert js_src_digest(js_dir) == golden_data["js_src_sha256"], (
        "js/src changed since vectors.json was generated: rerun python/tests/golden/generate_vectors.js"
    )


def test_ac9_vector_file_is_deterministic_form(golden_data):
    raw = GOLDEN_FILE.read_bytes()
    assert b"\r" not in raw, "vectors.json must use LF line endings"
    assert raw.endswith(b"}\n")
    ids = [v["id"] for v in golden_data["vectors"]]
    assert ids == sorted(ids), "vectors must be sorted by id"
    assert len(ids) == len(set(ids)), "vector ids must be unique"
    assert golden_data["vector_count"] == len(ids)
    assert raw.decode("utf-8").startswith('{\n  "schema_version": 1,\n'), "2-space indented JSON"
    assert b'"generated_at"' not in raw and b'"timestamp"' not in raw, "no timestamps"


# AC-9 minimum categories -> (function, category) pairs that must be present in the vector file
AC9_REQUIRED = {
    "JSON object": [("generateQRData", "json-object"), ("decode", "json-object")],
    "array": [("generateQRData", "json-array"), ("decode", "json-array")],
    "scalar strings '123','true','null'": [("generateQRData", "scalar-string")],
    "integer-like keys": [("decode", "integer-like-keys"), ("toJson", "integer-like-keys")],
    "nested objects": [("decode", "nested-object")],
    "half/single/double floats": [("decode", "float"), ("toJson", "float"), ("generateQRData", "float")],
    "-0": [("decode", "negative-zero"), ("generateQRData", "negative-zero")],
    "integer above 2^53": [("decode", "integer-above-2^53"), ("toJson", "integer-above-2^53")],
    "unicode/emoji text": [("decode", "unicode")],
    "plain text": [("decode", "plain-text")],
    "empty string": [("decode", "empty-string")],
    "text with BOM": [("decode", "text-with-bom")],
    "invalid UTF-8 bytes": [("decode", "invalid-utf8")],
    "falsy CBOR items": [("decode", "falsy-cbor")],
    "header prefix": [("decode", "header-prefix"), ("generateQRData", "header-prefix")],
    "CBOR map with non-string keys": [("decode", "map-non-string-keys"), ("toJson", "map-non-string-keys")],
    "byte strings": [("decode", "byte-string"), ("toJson", "byte-string"), ("decodeMappedData", "byte-string")],
    "tagged values": [("decode", "tagged"), ("toJson", "tagged")],
    "CLAIM_169 mapped data (cbor on/off)": [("getMappedData", "claim169-mapped"), ("decodeMappedData", "claim169-roundtrip")],
    "top-level CBOR array in decode_mapped_data": [("decodeMappedData", "top-level-array")],
    "base64url CBOR for to_json": [("toJson", "base64url")],
}


@pytest.mark.parametrize("label", sorted(AC9_REQUIRED))
def test_ac9_minimum_category_present(golden_data, label):
    present = {(v["function"], v["category"]) for v in golden_data["vectors"]}
    for pair in AC9_REQUIRED[label]:
        assert pair in present, f"AC-9 category {label!r} missing {pair}"
    if label.startswith("CLAIM_169"):
        cbor = {v["args"]["cbor_enable"] for v in golden_data["vectors"] if v["category"] == "claim169-mapped"}
        assert cbor == {True, False}


def test_ac9_scalar_strings_123_true_null_present(golden_data):
    inputs = {v["input"] for v in golden_data["vectors"] if v["function"] == "generateQRData"}
    assert {"123", "true", "null"} <= inputs


# ----------------------------------------------------------------------------- AC-2 / AC-10 encode parity
@pytest.mark.parametrize("v", vectors("generateQRData", lambda v: v.get("encode_parity") and _ok(v)))
def test_ac2_ac10_generate_qr_data_matches_js(pp, v):
    assert pp.generate_qr_data(v["input"], header=v["header"]) == v["expected"]


@pytest.mark.parametrize("v", vectors("generateQRData", lambda v: v.get("value_input") and _ok(v)))
def test_ac2_value_input_serialised_like_json(pp, v):
    """dict/list/int/float/bool input is serialised to JSON and takes the same path (AC-2)."""
    value = json.loads(v["input"])
    assert not isinstance(value, str) and value is not None
    assert pp.generate_qr_data(value, header=v["header"]) == v["expected"]


@pytest.mark.parametrize(
    "v", vectors("getMappedData", lambda v: v.get("encode_parity") and _ok(v) and v["args"]["cbor_enable"])
)
def test_ac6_ac10_get_mapped_data_cbor_matches_js(pp, v):
    result = pp.get_mapped_data(mapping_input(v), **mapping_args(v))
    if isinstance(result, list):
        assert js_compact(result) == v["expected"]
    else:
        assert result == v["expected"]


# ----------------------------------------------------------------------------- AC-4 / AC-9 decode parity
@pytest.mark.parametrize("v", vectors("decode", _ok))
def test_ac4_ac9_decode_matches_js(pp, v):
    assert pp.decode(v["input"], header=_header(v)) == v["expected"]


@pytest.mark.parametrize("v", vectors("decode", _ok))
def test_ac4_decode_to_object_matches_js(pp, v):
    try:
        expected = json.loads(v["expected"])
    except ValueError:
        expected = v["expected"]
    assert same_value(pp.decode_to_object(v["input"], header=_header(v)), expected)


# ----------------------------------------------------------------------------- AC-6 mapping parity (cbor off)
@pytest.mark.parametrize(
    "v", vectors("getMappedData", lambda v: _ok(v) and not v["args"]["cbor_enable"] and "expected" in v)
)
def test_ac6_get_mapped_data_dict_matches_js(pp, v):
    result = pp.get_mapped_data(mapping_input(v), **mapping_args(v))
    assert_str_keys(result)
    assert js_compact(result) == v["expected"]


@pytest.mark.parametrize(
    "v", vectors("getMappedData", lambda v: _ok(v) and not v["args"]["cbor_enable"] and "expected_value" in v)
)
def test_ac6_scalar_returned_unchanged_when_cbor_off(pp, v):
    value = mapping_input(v)
    result = pp.get_mapped_data(value, **mapping_args(v))
    assert type(result) is type(value)
    assert same_value(result, from_typed(v["expected_value"]))


# ----------------------------------------------------------------------------- AC-7 / AC-9 decode_mapped_data parity
@pytest.mark.parametrize("v", vectors("decodeMappedData", _ok))
def test_ac7_ac9_decode_mapped_data_matches_js(pp, v):
    assert pp.decode_mapped_data(v["input"], **mapping_args(v)) == v["expected"]


@pytest.mark.parametrize("v", vectors("replaceValuesForClaim169", _ok))
def test_ac7_replace_values_for_claim169_matches_js(v):
    assert js_compact(replace_values_for_claim169(json.loads(v["input_json"]))) == v["expected"]


# ----------------------------------------------------------------------------- AC-8 / AC-9 to_json parity
@pytest.mark.parametrize("v", vectors("toJson", _ok))
def test_ac8_ac9_to_json_matches_js(pp, v):
    result = pp.to_json(v["input"])
    assert_str_keys(result)
    if v["compare"] == "exact":
        assert js_compact(result) == v["expected"]
    else:
        assert same_value(result, from_typed(v["expected_value"]))


# ----------------------------------------------------------------------------- errors and deliberate deviations
_CALL = {
    "generateQRData": lambda p, v: p.generate_qr_data(v["input"], header=v.get("header", "")),
    "decode": lambda p, v: p.decode(v["input"], header=_header(v)),
    "decodeMappedData": lambda p, v: p.decode_mapped_data(v["input"]),
    "toJson": lambda p, v: p.to_json(v["input"]),
    "getMappedData": lambda p, v: p.get_mapped_data(mapping_input(v), **mapping_args(v)),
}


def _all_python_error_vectors():
    return [pytest.param(v, id=v["id"]) for v in golden()["vectors"] if "python_error" in v]


@pytest.mark.parametrize("v", _all_python_error_vectors())
def test_ac11_deviation_and_error_vectors_raise_typed_error(pp, v):
    exc = getattr(pixelpass, v["python_error"])
    with pytest.raises(exc):
        _CALL[v["function"]](pp, v)
