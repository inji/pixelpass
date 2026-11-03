"""AC-3: generate_qr_code returns a PNG data URL that scans (zxing-cpp oracle) to exactly generate_qr_data."""
from __future__ import annotations

import base64
import hashlib
import io

import pytest

from pixelpass import EncodingError

zxingcpp = pytest.importorskip("zxingcpp")  # test extra; test_public_api::test_ac1_test_extras_available fails if missing
Image = pytest.importorskip("PIL.Image")

from conftest import golden

PREFIX = "data:image/png;base64,"
BORDER, SCALE = 3, 10


def _png(url: str):
    assert url.startswith(PREFIX)
    raw = base64.b64decode(url[len(PREFIX):], validate=True)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"
    return Image.open(io.BytesIO(raw))


def _scan(img) -> str:
    results = zxingcpp.read_barcodes(img.convert("L"))
    texts = [r.text for r in results if r.valid] if results and hasattr(results[0], "valid") else [r.text for r in results]
    assert len(texts) == 1, f"expected exactly one QR code, got {len(texts)}"
    return texts[0]


def _incompressible(n: int) -> str:
    """Deterministic high-entropy text (hex of a SHA-256 chain) of n characters; deflate gains little."""
    out, h = [], b"pixelpass"
    while sum(map(len, out)) < n:
        h = hashlib.sha256(h).digest()
        out.append(base64.b64encode(h).decode("ascii"))
    return "".join(out)[:n]


SAMPLES = [
    ('{"name":"Alice","age":30}', ""),
    ("hello world", ""),
    ('{"a":1}', "NCB:"),
    ("[1,2,3]", "mosip://"),
    ("", ""),
]


@pytest.mark.parametrize("ecc", ["L", "M", "Q", "H"])
@pytest.mark.parametrize("data, header", SAMPLES)
def test_ac3_qr_scans_to_generate_qr_data(pp, data, header, ecc):
    url = pp.generate_qr_code(data, ecc=ecc, header=header)
    assert _scan(_png(url)) == pp.generate_qr_data(data, header)


def test_ac3_default_ecc_is_l_and_scans_to_js_vector(pp):
    v = next(v for v in golden()["vectors"] if v["id"] == "generateQRData.json-object.credential-like")
    url = pp.generate_qr_code(v["input"])
    assert _scan(_png(url)) == v["expected"]
    results = zxingcpp.read_barcodes(_png(url).convert("L"))
    assert results[0].ec_level == "L"  # zxing-cpp >= 3.1.1 (test extra) reports the QR EC level


def test_ac3_png_geometry_border_3_scale_10_black_on_white(pp):
    img = _png(pp.generate_qr_code('{"a":1}')).convert("RGB")
    w, h = img.size
    assert w == h and w % SCALE == 0
    modules = w // SCALE - 2 * BORDER
    assert modules in {17 + 4 * v for v in range(1, 41)}, f"{modules} is not a QR version size"
    colours = {c for _, c in img.getcolors(maxcolors=1 << 16)}
    assert colours <= {(0, 0, 0), (255, 255, 255)}
    q = BORDER * SCALE
    # quiet zone (3 modules = 30 px) is white on every side
    for x in range(w):
        for y in list(range(q)) + list(range(h - q, h)):
            assert img.getpixel((x, y)) == (255, 255, 255)
            assert img.getpixel((y, x)) == (255, 255, 255)
    # finder pattern starts right after the quiet zone: one module = 10 px of black
    for d in range(SCALE):
        assert img.getpixel((q + d, q)) == (0, 0, 0)
    assert img.getpixel((q + 7 * SCALE, q)) == (255, 255, 255)  # separator after the 7-module finder


@pytest.mark.parametrize("ecc", ["X", "l", "m", "", "LOW", None, 1])
def test_ac3_invalid_ecc_raises_encoding_error(pp, ecc):
    with pytest.raises(EncodingError):
        pp.generate_qr_code('{"a":1}', ecc=ecc)


def test_ac3_overflow_raises_encoding_error(pp):
    with pytest.raises(EncodingError):
        pp.generate_qr_code(_incompressible(6000), ecc="L")


def test_ac3_overflow_depends_on_ecc(pp):
    data = _incompressible(1700)
    assert len(pp.generate_qr_data(data)) > 1852  # above QR v40-H alphanumeric capacity, below v40-L (4296)
    assert len(pp.generate_qr_data(data)) < 4296
    assert _scan(_png(pp.generate_qr_code(data, ecc="L"))) == pp.generate_qr_data(data)
    with pytest.raises(EncodingError):
        pp.generate_qr_code(data, ecc="H")
