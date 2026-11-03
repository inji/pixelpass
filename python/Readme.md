# PixelPass for Python

PixelPass compresses data into a compact QR payload (CBOR, then zlib, then Base45), renders QR codes,
decodes payloads back, reads `certificate.json` from ZIP files and maps MOSIP Claim 169 identity data.

This package is a port of the JavaScript library `@injistack/pixelpass` in [`../js`](../js).

- Distribution name: `pixelpass-python`, import name: `pixelpass`, version 0.1.0
- Python 3.9 or later (tested on CPython 3.9 and 3.13)
- One runtime dependency: `qrcode[png]` (qrcode with the pure-Python `pypng` writer). Pillow is not
  needed at runtime. CBOR is implemented inside the package.

## Install

From a checkout of this repository:

```bash
pip install ./python
```

For development, with the test tools (`pytest`, plus `cbor2`, `zxing-cpp` and `pillow`, used only as
test oracles):

```bash
pip install -e "./python[test]"
```

## Usage

Every operation is a method of `PixelPass`. The Claim 169 tables (`CLAIM_169_KEY_MAPPER`,
`CLAIM_169_VALUE_MAPPER`, `CLAIM_169_REVERSE_KEY_MAPPER`), `replace_values_for_claim169` and
`reverse_mapper` are module-level.

```python
from pixelpass import PixelPass, replace_values_for_claim169, reverse_mapper

pp = PixelPass()
```

### generate_qr_data

Encodes `data` and prefixes `header`. A `str` is parsed with `JSON.parse` semantics. Valid JSON is
CBOR-encoded; any other text is compressed as UTF-8. A `dict`, `list`, `int`, `float` or `bool` is
serialised to JSON first.

```python
qr_text = pp.generate_qr_data('{"name":"Alice","age":30}')
qr_text = pp.generate_qr_data({"name": "Alice", "age": 30}, header="NCB:")
# 'NCB:NCF:PB.NI7DJDQJ:CJ*IJPOJADJUE5$*0B+83%0'
```

### generate_qr_code

Returns a `data:image/png;base64,...` URL of a QR code holding `generate_qr_data(data, header)`.
The image is black on white, with a 3-module border and 10 pixels per module. `ecc` is one of
`"L"` (default), `"M"`, `"Q"` or `"H"`.

```python
data_url = pp.generate_qr_code('{"name":"Alice"}', ecc="M", header="")
```

### decode

Strips `header` when the data starts with it, then reverses `generate_qr_data`. It returns the JSON
text of the CBOR payload, or the decoded text when the payload is not CBOR.

```python
pp.decode(qr_text, header="NCB:")   # '{"name":"Alice","age":30}'
```

### decode_to_object

Returns `json.loads(decode(...))` when that works, otherwise the decoded text.

```python
pp.decode_to_object(qr_text, header="NCB:")   # {'name': 'Alice', 'age': 30}
```

### decode_binary

Returns the text of the `certificate.json` entry of a ZIP archive, given as `bytes`.

```python
with open("credential.zip", "rb") as fh:
    certificate_json = pp.decode_binary(fh.read())
```

### get_mapped_data

Maps keys and values through the Claim 169 tables (or your own), case-insensitively and
recursively. Returns a `dict` with `str` keys. With `cbor_enable=True` it returns the CBOR encoding
as lowercase hex.

```python
pp.get_mapped_data({"ID": "1234", "Gender": "female"})                    # {'1': '1234', '9': 2}
pp.get_mapped_data({"ID": "1234", "Gender": "female"}, cbor_enable=True)  # 'a261316431323334613902'
pp.get_mapped_data({"Name": "x"}, key_mapper={"name": "n"}, value_mapper={}, strict=False)  # {'n': 'x'}
```

### decode_mapped_data

The reverse of `get_mapped_data`. It reads hex CBOR (or JSON), renames keys depth by depth with the
list `key_mapper`, applies `value_mapper` and returns compact JSON.

```python
pp.decode_mapped_data("a261316431323334613902")   # '{"ID":"1234","Gender":"Female"}'
pp.decode_mapped_data('{"1":"1234","9":2}')       # '{"ID":"1234","Gender":"Female"}'
```

### to_json

Decodes a base64url CBOR string into a `dict`, `list` or scalar with `str` keys.

```python
pp.to_json("oWFhAQ")   # {'a': 1}
```

### reverse_mapper and replace_values_for_claim169

```python
reverse_mapper({"ID": 1, "Gender": 9})       # {'1': 'ID', '9': 'Gender'}
replace_values_for_claim169({"Gender": 2})   # {'Gender': 'Female'}
```

### Errors

All errors are subclasses of `PixelPassError`:

- `EncodingError`: `None` or unsupported input, an invalid `ecc`, or data too large for a QR code.
- `DecodingError`: malformed Base45, zlib, ZIP, base64url, CBOR or JSON input, or a size limit hit.
- `MappingError`: `None` input to the mapping methods, a key collision, or a `key_mapper` that is not a list.

The original exception is replaced by a sanitized cause (`__cause__`) that holds no payload text.
`to_json` raises `TypeError` for non-`str` input. The constructor raises `ValueError` for an invalid
configuration.

## Compatibility

For well-formed input, `generate_qr_data`, `decode`, `get_mapped_data`, `decode_mapped_data` and
`to_json` are byte-compatible with `@injistack/pixelpass` 1.0.0-rc.2 at upstream develop commit
c9e2258 (cbor-web 9.0.2, pako 2.1.0, base45-web 1.0.2, as pinned in `js/package-lock.json`).
The JS decode quirks are kept on purpose:

- A falsy CBOR item (`false`, `0`, `null`, `""`, `-0`, `NaN`) is returned as decoded text.
- Text that happens to parse as CBOR (for example `" "` gives `-1`) is returned as CBOR.

Byte parity needs the default `compression_level=9`. A `compression_level` other than 9 still
round-trips, but its output differs byte for byte from the JS library.

The golden vectors in `tests/golden/vectors.json` come from the JS reference and are normative.

## Deviations

These differences from the JS library are deliberate:

- `decode_mapped_data` treats a string as hex CBOR only when it is non-empty, has even length and holds only hex digits. Any other string is parsed as JSON. JS hex-parses every string, so JSON input turns into garbage such as `{}`.
- `to_json` rejects malformed base64url (characters outside the base64url alphabet, or a `=` that is not trailing padding) with `DecodingError`. JS silently drops invalid characters.
- `generate_qr_data(None)` raises `EncodingError`. JS encodes `None` as CBOR null.
- `decode_binary` reads the raw ZIP bytes. JS first converts the archive to UTF-8 text, which corrupts bytes >= 0x80.
- No console or log output. JS writes `console.error` (non-JSON input to generateQRData) and `console.warn` (decodeMappedData fallback). This SDK writes nothing to stdout, stderr, `logging` or `warnings`.
- An empty or truncated zlib stream raises `DecodingError` (JS `decode` returns `''`). So do bytes after the end of the zlib stream.
- Out-of-range Base45 groups (a triplet above 65535 or a pair above 255) raise `DecodingError`. base45-web accepts them.
- Key collision check in `get_mapped_data`: two input keys that map to the same key (for example `Gender` and `gender`) raise `MappingError`. The message names the keys, never the values. `strict=False` keeps the JS overwrite.
- Size limits: every decoder rejects input longer than `max_encoded_size`, and inflation stops at `max_decompressed_size` (see Security). JS has no limits.
- Input keys that hit `Object.prototype` in JS (`constructor`, `toString`, `__proto__`) are treated as ordinary keys here.
- Kotlin differs from both JS and Python on scalar strings: the Kotlin `generateQRData` CBOR-encodes only JSON objects and arrays, so `'123'`, `'true'` and `'null'` take its text path. This SDK follows JS and CBOR-encodes them.
- Deeply nested JSON (JS encodes it): the depth limit is the Python stack (about 1000 levels) and depends on
  the interpreter. Text the JSON parser gives up on takes the UTF-8 text path, like any non-JSON text. JSON that
  parses but is too deep to CBOR-encode raises `EncodingError` in `generate_qr_data` and
  `get_mapped_data(cbor_enable=True)`; input too deep to map raises `MappingError` in `get_mapped_data`.
- Kotlin differs on QR scale: Kotlin renders 15 pixels per module. This SDK follows JS (scale 10, border 3).

## Security

- Encoding is not encryption. Anyone who can read the QR code can decode the data. Sign or encrypt the payload yourself if it needs protection.
- Decoded data is untrusted input. Validate it before you use it.
- Pillow is not a runtime dependency: QR images are written by the pure-Python `pypng` writer, so
  Pillow vulnerabilities do not apply to installs without the `test` extra.
- Size limits protect against oversized input and decompression bombs. Defaults: `max_encoded_size=65536` characters or bytes (64 KiB, header included) and `max_decompressed_size=10485760` bytes (10 MiB). Inflation and ZIP entry reads stop at the limit; they never inflate the whole payload first. To change the limits:

```python
pp = PixelPass(max_encoded_size=16384, max_decompressed_size=1048576)
```

## Development

Run the tests from `python/`:

```bash
python -m pytest
```

### Regenerating the golden vectors

The vectors come from the JS reference. When `js/src` or its dependencies change, regenerate them
from the repository root:

```bash
cd js && npm ci
cd ..
node python/tests/golden/generate_vectors.js
```

Commit `generate_vectors.js` and `vectors.json` together. `test_ac9_vectors_not_stale_against_js_src`
fails when `js/src` has changed since the vectors were generated.
