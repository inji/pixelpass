"""The :class:`PixelPass` client: encode, decode, QR, ZIP and Claim 169 mapping (port of js/src/index.js)."""
from __future__ import annotations

import base64
import io
import json
import re
import struct
import zipfile
import zlib
from typing import Any, List, Optional, Union

from . import _cbor, _js, base45
from .constants import (
    CLAIM_169_KEY_MAPPER,
    CLAIM_169_REVERSE_KEY_MAPPER,
    CLAIM_169_VALUE_MAPPER,
    DEFAULT_MAX_DECOMPRESSED_SIZE,
    DEFAULT_MAX_ENCODED_SIZE,
    DEFAULT_QR_BORDER,
    DEFAULT_QR_SCALE,
    DEFAULT_ZIP_FILE_NAME,
    DEFAULT_ZLIB_COMPRESSION_LEVEL,
    ECC_LEVELS,
    ZIP_HEADER,
)
from .exceptions import DecodingError, EncodingError, MappingError, SanitizedCause, cause, sanitize
from .mapping import build_mappers, map_value, replace_keys_at_depth, replace_values_for_claim169

_HEX_RE = re.compile(r"(?:[0-9a-fA-F]{2})+")
_B64URL_RE = re.compile(r"[A-Za-z0-9_-]*")
_PNG_DATA_URL = "data:image/png;base64,"
# What zipfile can raise for a hostile archive that starts with PK. All are needed: dropping one lets a raw,
# unsanitized exception escape decode_binary instead of DecodingError (AC-5, AC-11).
_ZIP_ERRORS = (
    zipfile.BadZipFile,  # bad central directory, bad CRC, bad local header magic
    zipfile.LargeZipFile,  # ZIP64 record without allowZip64
    zlib.error,  # corrupt deflate data in the entry
    EOFError,  # entry data shorter than the declared compressed size
    NotImplementedError,  # unsupported compression method or encryption flag
    RuntimeError,  # encrypted entry opened without a password
    ValueError,  # negative or inconsistent sizes/offsets in the directory
    OSError,  # seek before the start of the buffer (bad header offset)
    struct.error,  # truncated fixed-size header or extra field
    IndexError,  # extra field shorter than its declared length
    OverflowError,  # huge size/offset values in ZIP64 extra fields
)
_READ_CHUNK = 65536


def _check_int(name: str, value: Any, low: int, high: Optional[int] = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an int")
    if value < low or (high is not None and value > high):
        bound = f"between {low} and {high}" if high is not None else f">= {low}"
        raise ValueError(f"{name} must be {bound}")
    return value


class PixelPass:
    """PixelPass SDK client.

    :param compression_level: zlib level 0-9. Only the default 9 gives byte parity with the JS library.
    :param max_encoded_size: largest input (characters or bytes, header included) any decoder accepts.
    :param max_decompressed_size: largest inflated payload (zlib stream or ZIP entry) in bytes.
    """

    def __init__(
        self,
        compression_level: int = DEFAULT_ZLIB_COMPRESSION_LEVEL,
        max_encoded_size: int = DEFAULT_MAX_ENCODED_SIZE,
        max_decompressed_size: int = DEFAULT_MAX_DECOMPRESSED_SIZE,
    ) -> None:
        self.compression_level = _check_int("compression_level", compression_level, 0, 9)
        self.max_encoded_size = _check_int("max_encoded_size", max_encoded_size, 1)
        self.max_decompressed_size = _check_int("max_decompressed_size", max_decompressed_size, 1)

    # ------------------------------------------------------------------------- encode
    def generate_qr_data(self, data: Union[str, dict, list, int, float, bool], header: str = "") -> str:
        """Return ``header + Base45(zlib(CBOR(JSON.parse(data))))``, or of the UTF-8 text when not JSON.

        dict, list, int, float and bool input is serialised to JSON first and takes the same path.
        """
        if data is None:
            raise EncodingError("generate_qr_data: data must not be None") from cause("TypeError", "data is None")
        if not isinstance(header, str):
            raise EncodingError("generate_qr_data: header must be a str") from cause("TypeError", type(header).__name__)
        text = self._as_text(data)
        try:
            value: Any = _js.js_parse(text)
        except _js.JSONParseError:
            return header + self._compress(_js.utf8_encode(text))  # JS: "Data is not JSON" -> UTF-8 text path
        err: Optional[SanitizedCause] = None
        payload = b""
        try:
            payload = _cbor.encode(value)
        except _cbor.CborError as exc:  # valid JSON nested deeper than the interpreter stack allows
            err = sanitize(exc)
        if err is not None:
            raise EncodingError("generate_qr_data: JSON nesting too deep to CBOR-encode") from err
        return header + self._compress(payload)

    def _compress(self, payload: bytes) -> str:
        return base45.encode(zlib.compress(payload, self.compression_level))

    @staticmethod
    def _as_text(data: Any) -> str:
        if isinstance(data, str):
            return data
        err: Optional[SanitizedCause] = None
        too_deep = False
        if isinstance(data, (dict, list, tuple, int, float)):
            try:
                return json.dumps(data, ensure_ascii=False, allow_nan=False)
            except RecursionError as exc:  # nested deeper than the interpreter stack allows
                err = sanitize(exc)
                too_deep = True
            except (TypeError, ValueError) as exc:
                err = sanitize(exc)
        else:
            err = cause("TypeError", type(data).__name__)
        if too_deep:
            raise EncodingError("generate_qr_data: data nesting too deep to serialise") from err
        raise EncodingError("generate_qr_data: data must be a str or a JSON-serialisable dict/list/number/bool") from err

    def generate_qr_code(self, data: Union[str, dict, list, int, float, bool], ecc: str = "L", header: str = "") -> str:
        """Return a ``data:image/png;base64,`` URL of a QR code (border 3, scale 10) holding generate_qr_data()."""
        if not isinstance(ecc, str) or ecc not in ECC_LEVELS:
            raise EncodingError("generate_qr_code: ecc must be one of 'L', 'M', 'Q', 'H'")
        text = self.generate_qr_data(data, header)

        import qrcode
        from qrcode.exceptions import DataOverflowError
        from qrcode.image.pure import PyPNGImage  # pure-Python PNG writer (pypng); Pillow is not used

        levels = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        qr = qrcode.QRCode(
            version=None,
            error_correction=levels[ecc],
            box_size=DEFAULT_QR_SCALE,
            border=DEFAULT_QR_BORDER,
            image_factory=PyPNGImage,
        )
        err: Optional[SanitizedCause] = None
        image: Any = None
        try:
            qr.add_data(text)
            qr.make(fit=True)
            image = qr.make_image()  # PyPNGImage: 1-bit greyscale PNG, black modules on white
        except (DataOverflowError, ValueError) as exc:
            err = sanitize(exc)
        if err is not None:
            raise EncodingError(f"generate_qr_code: data of {len(text)} characters does not fit a QR code at ecc {ecc}") from err
        buf = io.BytesIO()
        image.save(buf)
        return _PNG_DATA_URL + base64.b64encode(buf.getvalue()).decode("ascii")

    # ------------------------------------------------------------------------- decode
    def _check_size(self, op: str, size: int) -> None:
        if size > self.max_encoded_size:
            raise DecodingError(f"{op}: input of {size} exceeds max_encoded_size {self.max_encoded_size}")

    def _inflate(self, op: str, compressed: bytes) -> bytes:
        limit = self.max_decompressed_size
        inflater = zlib.decompressobj()
        err: Optional[SanitizedCause] = None
        out = b""
        try:
            out = inflater.decompress(compressed, limit + 1)
        except zlib.error as exc:
            err = sanitize(exc)
        if err is not None:
            raise DecodingError(f"{op}: corrupt zlib stream") from err
        if len(out) > limit:
            raise DecodingError(f"{op}: decompressed data exceeds max_decompressed_size {limit}")
        if not inflater.eof:
            raise DecodingError(f"{op}: empty or truncated zlib stream") from cause("ZlibStreamError", "stream not terminated")
        if inflater.unused_data:
            raise DecodingError(f"{op}: unexpected bytes after the zlib stream") from cause(
                "ZlibStreamError", f"{len(inflater.unused_data)} trailing bytes"
            )
        return out

    def _payload_bytes(self, op: str, data: Any, header: Optional[str]) -> bytes:
        if not isinstance(data, str):
            raise DecodingError(f"{op}: data must be a str") from cause("TypeError", type(data).__name__)
        if header is not None and not isinstance(header, str):
            raise DecodingError(f"{op}: header must be a str") from cause("TypeError", type(header).__name__)
        self._check_size(op, len(data))
        if header and data.startswith(header):
            data = data[len(header):]
        err: Optional[SanitizedCause] = None
        compressed = b""
        reason = ""
        try:
            compressed = base45.decode(data)
        except base45.Base45Error as exc:
            err = sanitize(exc)
            reason = str(exc)
        if err is not None:
            raise DecodingError(f"{op}: {reason}") from err
        return self._inflate(op, compressed)

    def decode(self, data: str, *, header: Optional[str] = None) -> str:
        """Decode a generate_qr_data() string; returns the JSON text of the CBOR payload, or the UTF-8 text."""
        raw = self._payload_bytes("decode", data, header)
        text = _js.text_decode(raw)
        try:
            value = _cbor.decode_first(raw)
        except _cbor.CborError:
            return text
        if not _js.is_truthy(value):
            return text
        try:
            result = _js.stringify(value)
        except _js.JSBigIntError:
            return text
        return text if result is None else result

    def decode_to_object(self, data: str, *, header: Optional[str] = None) -> Any:
        """``json.loads(decode(data))`` when that succeeds, else the decoded text."""
        text = self.decode(data, header=header)
        try:
            # AC-4 specifies json.loads as-is (the approved oracle expects NaN/Infinity text to load as float)
            return json.loads(text)
        except (ValueError, RecursionError):
            return text

    def decode_binary(self, data: bytes) -> str:
        """Return the text of ``certificate.json`` from a ZIP archive (raw bytes, bounded read)."""
        op = "decode_binary"
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise DecodingError(f"{op}: data must be bytes") from cause("TypeError", type(data).__name__)
        data = bytes(data)
        self._check_size(op, len(data))
        if not data.startswith(ZIP_HEADER):
            raise DecodingError(f"{op}: Unsupported binary file type")
        limit = self.max_decompressed_size
        err: Optional[SanitizedCause] = None
        status = "ok"
        content = b""
        try:
            status, content = self._read_zip_entry(data, limit)
        except _ZIP_ERRORS as exc:
            err = sanitize(exc)
        if err is not None:
            raise DecodingError(f"{op}: corrupt ZIP archive") from err
        if status == "missing":
            raise DecodingError(f"{op}: File '{DEFAULT_ZIP_FILE_NAME}' not found in ZIP archive")
        if status == "too-large":
            raise DecodingError(f"{op}: '{DEFAULT_ZIP_FILE_NAME}' exceeds max_decompressed_size {limit}")
        return _js.text_decode(content)

    @staticmethod
    def _read_zip_entry(data: bytes, limit: int) -> "tuple[str, bytes]":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if DEFAULT_ZIP_FILE_NAME not in archive.namelist():
                return "missing", b""
            info = archive.getinfo(DEFAULT_ZIP_FILE_NAME)
            if info.file_size > limit:
                return "too-large", b""
            chunks: List[bytes] = []
            total = 0
            with archive.open(info) as entry:
                while True:
                    chunk = entry.read(min(_READ_CHUNK, limit + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        return "too-large", b""
                    chunks.append(chunk)
            return "ok", b"".join(chunks)

    # ------------------------------------------------------------------------- mapping
    def get_mapped_data(
        self,
        json_data: Any,
        key_mapper: Any = CLAIM_169_KEY_MAPPER,
        value_mapper: Any = CLAIM_169_VALUE_MAPPER,
        cbor_enable: bool = False,
        strict: bool = True,
    ) -> Any:
        """Map keys and values (case-insensitive, recursive); with ``cbor_enable`` return the CBOR as lowercase hex."""
        if json_data is None:
            raise MappingError("get_mapped_data: json_data must not be None") from cause("TypeError", "json_data is None")
        err: Optional[SanitizedCause] = None
        if isinstance(json_data, (list, tuple)):
            mapped: List[Any] = []
            try:
                mapped = [self.get_mapped_data(item, key_mapper, value_mapper, cbor_enable, strict) for item in json_data]
            except RecursionError as exc:  # bare list nested deeper than the interpreter stack allows (AC-6/AC-11)
                err = sanitize(exc)
            if err is not None:
                raise MappingError("get_mapped_data: json_data nesting too deep") from err
            return mapped
        mappers = build_mappers(key_mapper, value_mapper)
        payload: Any = None
        try:
            payload = map_value(json_data, mappers, strict)
        except RecursionError as exc:
            err = sanitize(exc)
        if err is not None:
            raise MappingError("get_mapped_data: json_data nesting too deep") from err
        if not cbor_enable:
            return payload
        encoded = b""
        try:
            encoded = _cbor.encode(payload)
        except _cbor.CborError as exc:
            err = sanitize(exc)
        if err is not None:
            raise EncodingError("get_mapped_data: value cannot be CBOR-encoded") from err
        return encoded.hex()

    def _parse_mapped(self, data: str) -> Any:
        op = "decode_mapped_data"
        err: Optional[SanitizedCause] = None
        if _HEX_RE.fullmatch(data):
            try:
                return _cbor.decode_first(bytes.fromhex(data))
            except _cbor.BignumTooLargeError as exc:  # valid CBOR past our cap: say so, not "neither ... nor JSON"
                err = sanitize(exc)
            except _cbor.CborError:
                pass  # JS falls back to JSON.parse when CBOR decoding fails
            if err is not None:
                raise DecodingError(f"{op}: CBOR bignum longer than {_cbor.MAX_BIGNUM_BYTES} bytes") from err
        value: Any = None
        try:
            value = _js.js_parse(data)
        except _js.JSONParseError as exc:
            err = sanitize(exc)
        if err is not None:
            raise DecodingError(f"{op}: input is neither hex CBOR nor JSON") from err
        return value

    def decode_mapped_data(
        self,
        data: Union[str, List[str]],
        key_mapper: Any = CLAIM_169_REVERSE_KEY_MAPPER,
        value_mapper: Any = replace_values_for_claim169,
    ) -> Union[str, List[str]]:
        """Decode hex CBOR (or JSON) mapped data, rename keys per depth, map values; returns compact JSON."""
        op = "decode_mapped_data"
        if data is None:
            raise MappingError(f"{op}: data must not be None") from cause("TypeError", "data is None")
        if isinstance(data, (list, tuple)):
            return [self.decode_mapped_data(item, key_mapper, value_mapper) for item in data]  # type: ignore[misc]
        if not isinstance(data, str):
            raise DecodingError(f"{op}: data must be a str") from cause("TypeError", type(data).__name__)
        self._check_size(op, len(data))
        value = _js.to_python(self._parse_mapped(data))
        if key_mapper is not None:
            if not isinstance(key_mapper, list):
                raise MappingError(f"{op}: key_mapper must be a list of per-depth mapper dicts")
            for depth, mapper in enumerate(key_mapper):
                if isinstance(mapper, dict):
                    value = replace_keys_at_depth(value, mapper, depth)
        if callable(value_mapper):
            value = value_mapper(value)
        result = _js.stringify(value, bigint_error=False)
        if result is None:
            raise MappingError(f"{op}: value_mapper returned a value that is not JSON-serialisable")
        return result

    def to_json(self, b64url: str) -> Any:
        """Decode a base64url CBOR string to dict/list/scalar (str keys, JS number view)."""
        op = "to_json"
        if not isinstance(b64url, str):
            raise TypeError("to_json: expected a base64url-encoded CBOR string")
        self._check_size(op, len(b64url))
        body = b64url.rstrip("=")
        if not _B64URL_RE.fullmatch(body):
            bad = next(i for i, ch in enumerate(body) if not _B64URL_RE.fullmatch(ch))
            raise DecodingError(f"{op}: invalid base64url character at position {bad}") from cause(
                "ValueError", f"invalid base64url character at position {bad}"
            )
        if len(body) % 4 == 1:
            raise DecodingError(f"{op}: invalid base64url length") from cause("ValueError", "invalid base64url length")
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        err: Optional[SanitizedCause] = None
        value: Any = None
        try:
            value = _cbor.decode_first(raw)
        except _cbor.CborError as exc:
            err = sanitize(exc)
        if err is not None:
            raise DecodingError(f"{op}: invalid CBOR data") from err
        return _js.to_python(value)
