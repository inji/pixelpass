"""AC-1 (exports, packaging, runtime dependency) and the documented signatures/defaults (AC-2..AC-8, AC-12)."""
from __future__ import annotations

import importlib
import importlib.metadata as md
import inspect
import subprocess
import sys

import pytest

import pixelpass

DIST_NAME = "pixelpass-python"

EXPORTS = [
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
]
METHODS = [
    "generate_qr_data",
    "generate_qr_code",
    "decode",
    "decode_to_object",
    "decode_binary",
    "get_mapped_data",
    "decode_mapped_data",
    "to_json",
]


@pytest.mark.parametrize("name", EXPORTS)
def test_ac1_export_present(name):
    assert hasattr(pixelpass, name), f"pixelpass must export {name}"


def test_ac1_all_lists_exports():
    exported = getattr(pixelpass, "__all__", None)
    if exported is not None:
        assert set(EXPORTS) <= set(exported)


@pytest.mark.parametrize("name", METHODS)
def test_ac1_operations_are_methods_of_pixelpass(name):
    assert callable(getattr(pixelpass.PixelPass, name, None)), f"PixelPass.{name} missing"
    assert not hasattr(pixelpass, name), f"{name} must be a PixelPass method, not a module function"


def test_ac1_exception_hierarchy():
    assert issubclass(pixelpass.PixelPassError, Exception)
    for name in ("EncodingError", "DecodingError", "MappingError"):
        assert issubclass(getattr(pixelpass, name), pixelpass.PixelPassError)
    assert len({pixelpass.EncodingError, pixelpass.DecodingError, pixelpass.MappingError}) == 3


def test_ac1_constants_equal_js_tables(golden_data):
    js = golden_data["constants"]
    assert pixelpass.CLAIM_169_KEY_MAPPER == js["CLAIM_169_KEY_MAPPER"]
    assert pixelpass.CLAIM_169_VALUE_MAPPER == js["CLAIM_169_VALUE_MAPPER"]
    assert list(pixelpass.CLAIM_169_REVERSE_KEY_MAPPER) == js["CLAIM_169_REVERSE_KEY_MAPPER"]


def test_ac1_helpers_callable():
    assert callable(pixelpass.replace_values_for_claim169)
    assert callable(pixelpass.reverse_mapper)


def test_ac7_reverse_mapper_inverts_with_str_keys():
    assert pixelpass.reverse_mapper({"a": 1, "b": "x", "c": 62}) == {"1": "a", "x": "b", "62": "c"}
    for k in pixelpass.reverse_mapper({"ID": 1, "Gender": 9}):
        assert isinstance(k, str)


def test_ac7_reverse_mapper_of_claim169_root_keys_matches_js_depth0(golden_data):
    root = {k: v for k, v in pixelpass.CLAIM_169_KEY_MAPPER.items() if v >= 1 and k not in ("Data format", "Data sub format", "Data issuer")}
    assert pixelpass.reverse_mapper(root) == golden_data["constants"]["CLAIM_169_REVERSE_KEY_MAPPER"][0]


# ----------------------------------------------------------------------------- signatures and defaults
def _params(func):
    return inspect.signature(func).parameters


def test_ac12_constructor_defaults():
    p = _params(pixelpass.PixelPass.__init__)
    assert p["compression_level"].default == 9
    assert p["max_encoded_size"].default == 65536
    assert p["max_decompressed_size"].default == 10485760


def test_ac2_generate_qr_data_signature():
    p = _params(pixelpass.PixelPass.generate_qr_data)
    assert list(p)[1:3] == ["data", "header"]
    assert p["header"].default == ""


def test_ac3_generate_qr_code_signature():
    p = _params(pixelpass.PixelPass.generate_qr_code)
    assert list(p)[1:4] == ["data", "ecc", "header"]
    assert p["ecc"].default == "L"
    assert p["header"].default == ""


@pytest.mark.parametrize("name", ["decode", "decode_to_object"])
def test_ac4_decode_header_is_keyword_only(name):
    p = _params(getattr(pixelpass.PixelPass, name))
    assert p["header"].kind is inspect.Parameter.KEYWORD_ONLY
    assert p["header"].default is None


def test_ac6_get_mapped_data_signature():
    p = _params(pixelpass.PixelPass.get_mapped_data)
    assert list(p)[1:6] == ["json_data", "key_mapper", "value_mapper", "cbor_enable", "strict"]
    assert p["key_mapper"].default is pixelpass.CLAIM_169_KEY_MAPPER or p["key_mapper"].default == pixelpass.CLAIM_169_KEY_MAPPER
    assert p["value_mapper"].default is pixelpass.CLAIM_169_VALUE_MAPPER or p["value_mapper"].default == pixelpass.CLAIM_169_VALUE_MAPPER
    assert p["cbor_enable"].default is False
    assert p["strict"].default is True


def test_ac7_decode_mapped_data_signature():
    p = _params(pixelpass.PixelPass.decode_mapped_data)
    assert list(p)[1:4] == ["data", "key_mapper", "value_mapper"]
    assert p["key_mapper"].default == pixelpass.CLAIM_169_REVERSE_KEY_MAPPER
    assert p["value_mapper"].default is pixelpass.replace_values_for_claim169


def test_ac5_ac8_single_argument_methods():
    assert list(_params(pixelpass.PixelPass.decode_binary))[1] == "data"
    assert len(_params(pixelpass.PixelPass.to_json)) == 2


# ----------------------------------------------------------------------------- packaging (AC-1)
def test_ac1_python_version_supported():
    assert sys.version_info >= (3, 9)


def test_ac1_installed_distribution_metadata():
    meta = md.metadata(DIST_NAME)
    assert ">=3.9" in (meta.get("Requires-Python") or "")


def test_ac1_only_runtime_dependency_is_qrcode_png():
    """AC-1 as amended by ADR-5: qrcode[png] (pure-Python PyPNG) is the only runtime dependency; Pillow and cbor2 are test-only."""
    reqs = md.requires(DIST_NAME) or []
    runtime = [r for r in reqs if ";" not in r or "extra" not in r.split(";", 1)[1]]
    names = sorted(r.split(";")[0].strip().replace(" ", "") for r in runtime)
    assert len(names) == 1, f"runtime deps must be only qrcode[png], got {names}"
    assert names[0].lower().startswith("qrcode[png]")


def test_ac1_generate_qr_code_does_not_import_pil():
    """ADR-5: the QR PNG is written without Pillow; generate_qr_code works with PIL imports blocked."""
    code = "; ".join(
        [
            "import sys",
            "sys.modules['PIL'] = None",  # any `import PIL...` now raises ImportError
            "import pixelpass",
            "url = pixelpass.PixelPass().generate_qr_code('x')",
            "print(url.startswith('data:image/png;base64,'))",
        ]
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, f"generate_qr_code needs PIL (exit {out.returncode})"
    assert out.stdout.strip() == "True"


def test_ac1_cbor2_not_imported_at_runtime():
    code = "import sys, pixelpass; p = pixelpass.PixelPass(); p.decode(p.generate_qr_data('{\"a\":1}')); print('cbor2' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
    assert out.stderr == ""


@pytest.mark.parametrize("module", ["cbor2", "zxingcpp", "PIL"])
def test_ac1_test_extras_available(module):
    """The test extra must provide the cross-check (cbor2) and QR scan (zxing-cpp) oracles; fail loudly, never skip."""
    importlib.import_module(module)
