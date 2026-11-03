"""AC-15: the SDK writes nothing to logging, stdout or stderr (and emits no warnings), on success and failure paths."""
from __future__ import annotations

import ast
import io
import logging
import warnings
import zipfile

import pytest

from pixelpass import PixelPass, PixelPassError

from conftest import SRC_PKG, b64url, cbor_text, ref_b45encode


def _zip(entries: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for k, v in entries.items():
            zf.writestr(k, v)
    return buf.getvalue()


def _exercise_everything():
    pp = PixelPass()
    payload = '{"Gender":"Male","ID":"SECRET-1","nested":[1,{"a":"SECRET-2"}]}'
    ok = [
        lambda: pp.generate_qr_data(payload),
        lambda: pp.generate_qr_data("not json SECRET"),  # JS writes console.error here
        lambda: pp.generate_qr_data({"a": "SECRET"}, header="H:"),
        lambda: pp.generate_qr_code(payload, ecc="M"),
        lambda: pp.decode(pp.generate_qr_data(payload)),
        lambda: pp.decode(pp.generate_qr_data("SECRET text"), header="X"),
        lambda: pp.decode_to_object(pp.generate_qr_data(payload)),
        lambda: pp.decode_binary(_zip({"certificate.json": b'{"SECRET":1}'})),
        lambda: pp.get_mapped_data({"Gender": "Male", "x": "SECRET"}),
        lambda: pp.get_mapped_data({"Gender": "Male"}, cbor_enable=True),
        lambda: pp.get_mapped_data({"Gender": "Male", "gender": "SECRET"}, strict=False),
        lambda: pp.decode_mapped_data("a2016653454352455409 01".replace(" ", "")),
        lambda: pp.decode_mapped_data('{"1":"SECRET"}'),  # JS writes console.warn on this path
        lambda: pp.to_json(b64url(cbor_text("SECRET"))),
    ]
    bad = [
        lambda: pp.decode("SECRET#"),
        lambda: pp.decode(ref_b45encode(b"SECRET garbage")),
        lambda: pp.decode_binary(b"PK\x03\x04SECRET"),
        lambda: pp.decode_binary(b"SECRET"),
        lambda: pp.decode_binary(_zip({"other.json": b"SECRET"})),
        lambda: pp.decode_mapped_data("SECRET not json"),  # JS writes console.error here
        lambda: pp.to_json("SECRET!!"),
        lambda: pp.generate_qr_data(None),
        lambda: pp.generate_qr_code("x", ecc="Z"),
        lambda: pp.get_mapped_data({"Gender": "SECRET", "gender": "SECRET"}),
        lambda: pp.get_mapped_data(None),
        lambda: PixelPass(max_encoded_size=5).decode("SECRET-SECRET"),
    ]
    for f in ok:
        f()
    for f in bad:
        with pytest.raises(PixelPassError):
            f()


def test_ac15_no_stdout_stderr_logging_or_warnings(capsys, caplog):
    caplog.set_level(logging.DEBUG)
    root = logging.getLogger()
    old_level = root.level
    root.setLevel(logging.DEBUG)
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            _exercise_everything()
    finally:
        root.setLevel(old_level)
    out, err = capsys.readouterr()
    assert out == "" and err == "", "SDK must not print"
    sdk_records = [r for r in caplog.records if r.name.split(".")[0] == "pixelpass" or "SECRET" in r.getMessage()]
    assert sdk_records == [], [r.getMessage()[:80] for r in sdk_records]
    sdk_warnings = [x for x in w if "pixelpass" in (x.filename or "").replace("\\", "/")]
    assert sdk_warnings == [], [str(x.message)[:80] for x in sdk_warnings]


def test_ac15_no_pixelpass_logger_created():
    _ = PixelPass()
    assert not [n for n in logging.Logger.manager.loggerDict if n.split(".")[0] == "pixelpass"]


# ----------------------------------------------------------------------------- static scan of the package source
FORBIDDEN_MODULES = {"logging", "warnings", "traceback"}
FORBIDDEN_CALLS = {"print", "breakpoint", "input"}


@pytest.mark.parametrize("path", sorted(SRC_PKG.rglob("*.py")) or [None])
def test_ac15_source_has_no_print_logging_warnings(path):
    assert path is not None, f"no package sources under {SRC_PKG}"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            problems += [f"import {a.name}" for a in node.names if a.name.split(".")[0] in FORBIDDEN_MODULES]
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] in FORBIDDEN_MODULES:
            problems.append(f"from {node.module} import ...")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            problems.append(f"{node.func.id}() at line {node.lineno}")
        elif isinstance(node, ast.Attribute) and node.attr in {"stdout", "stderr", "__stdout__", "__stderr__"}:
            problems.append(f"sys.{node.attr} at line {node.lineno}")
    assert problems == [], f"{path.name}: {problems}"
