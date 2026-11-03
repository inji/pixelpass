"""Developer unit tests for PixelPass error paths and helpers not covered by the SDET oracle."""
from __future__ import annotations

import io
import math
import zipfile

import pytest

from pixelpass import DecodingError, EncodingError, MappingError, PixelPass, replace_values_for_claim169, reverse_mapper
from pixelpass import base45
from pixelpass.exceptions import SanitizedCause, cause, sanitize


@pytest.mark.parametrize(
    "kwargs, exc",
    [({"compression_level": True}, ValueError), ({"max_encoded_size": 1.5}, ValueError), ({"max_decompressed_size": "1"}, ValueError)],
)
def test_constructor_rejects_non_int(kwargs, exc):
    with pytest.raises(exc):
        PixelPass(**kwargs)


def test_generate_qr_data_rejects_bad_types_and_values():
    pp = PixelPass()
    for bad in ({1, 2}, b"x", {"a": math.nan}, {"a": object()}):
        with pytest.raises(EncodingError) as ei:
            pp.generate_qr_data(bad)
        assert isinstance(ei.value.__cause__, SanitizedCause)
    with pytest.raises(EncodingError):
        pp.generate_qr_data("x", header=None)
    assert pp.generate_qr_data((1, 2)) == pp.generate_qr_data("[1,2]")


def test_decode_type_errors():
    pp = PixelPass()
    with pytest.raises(DecodingError):
        pp.decode("BB8", header=5)
    with pytest.raises(DecodingError):
        pp.decode(b"BB8")


def test_decode_binary_type_and_bytearray():
    pp = PixelPass()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("certificate.json", "{}")
    assert pp.decode_binary(bytearray(buf.getvalue())) == "{}"
    assert pp.decode_binary(memoryview(buf.getvalue())) == "{}"
    with pytest.raises(DecodingError):
        pp.decode_binary("PK")


def test_decode_binary_entry_bigger_than_limit_by_header():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("certificate.json", b"a" * 5000)
    with pytest.raises(DecodingError) as ei:
        PixelPass(max_decompressed_size=100).decode_binary(buf.getvalue())
    assert "max_decompressed_size" in str(ei.value)


def test_get_mapped_data_unencodable_value():
    with pytest.raises(EncodingError):
        PixelPass().get_mapped_data({"a": {1, 2}}, cbor_enable=True)


def test_get_mapped_data_none_mappers_and_null_value_mapping():
    pp = PixelPass()
    assert pp.get_mapped_data({"a": None, "b": [None, (1,)]}, key_mapper=None, value_mapper=None) == {"a": None, "b": [None, [1]]}
    assert pp.get_mapped_data({"k": "X"}, key_mapper={}, value_mapper={"k": {"x": None}}) == {"k": None}
    assert pp.get_mapped_data(({"ID": 1},)) == [{"1": 1}]


def test_decode_mapped_data_branches():
    pp = PixelPass()
    with pytest.raises(DecodingError):
        pp.decode_mapped_data(123)
    assert pp.decode_mapped_data("a10102", key_mapper=None) == '{"1":2}'
    assert pp.decode_mapped_data("a10102", key_mapper=[None, {"1": "one"}], value_mapper=None) == '{"1":2}'
    assert pp.decode_mapped_data("a101a10102", key_mapper=[None, {"1": "one"}], value_mapper=None) == '{"1":{"one":2}}'
    assert pp.decode_mapped_data("1234") == "{}"  # valid hex, bad CBOR, valid JSON number -> spread {}
    with pytest.raises(MappingError):
        pp.decode_mapped_data("a10102", value_mapper=lambda d: object())


def test_decode_mapped_data_number_key_lookup():
    pp = PixelPass()
    assert pp.decode_mapped_data('{"01":"a","1e0":"b"}', value_mapper=None) == '{"ID":"b"}'


def test_to_json_bad_length_and_valid():
    pp = PixelPass()
    with pytest.raises(DecodingError):
        pp.to_json("A")
    assert pp.to_json("9g") is None
    assert pp.to_json("9w") is None  # undefined at top level


def test_replace_values_for_claim169_edge_cases():
    assert replace_values_for_claim169("ab") == {"0": "a", "1": "b"}
    assert replace_values_for_claim169([1]) == {"0": 1}
    assert replace_values_for_claim169(None) == {}
    assert replace_values_for_claim169({"Gender": [1]}) == {"Gender": "Male"}
    assert replace_values_for_claim169({"Gender": 1.0}) == {"Gender": "Male"}
    face = {"Face": {"Data format": "x", "Data sub format": 1}}
    assert replace_values_for_claim169(face) == face
    face = {"Face": {"Data format": 0, "Data sub format": "zz"}}
    assert replace_values_for_claim169(face) == face
    face = {"Face": {"Data format": 9, "Data sub format": 1}}
    assert replace_values_for_claim169(face) == face
    face = {"Face": {"Data format": 3, "Data sub format": 1}}
    assert replace_values_for_claim169(face) == {"Face": {"Data format": "Bio Hash", "Data sub format": 1}}
    face = {"Face": {"Data format": 1, "Data sub format": True}}
    assert replace_values_for_claim169(face) == {"Face": {"Data format": "Template", "Data sub format": True}}


def test_reverse_mapper_rejects_non_mapping():
    with pytest.raises(MappingError):
        reverse_mapper([("a", 1)])


def test_base45_error_positions():
    with pytest.raises(base45.Base45Error) as ei:
        base45.decode("AB#")
    assert ei.value.position == 2


def test_sanitize_and_cause():
    err = ValueError("SECRET")
    err.pos = 3
    assert str(sanitize(err)) == "ValueError at pos 3"
    assert str(sanitize(KeyError("SECRET"))) == "KeyError"
    assert str(cause("Kind")) == "Kind"


# ----------------------------------------------------------------------------- repair 3: nesting depth
def _nested_dict(depth):
    root = cur = {}
    for _ in range(depth - 1):
        cur["a"] = {}
        cur = cur["a"]
    return root


def _nested_list(depth):
    root = cur = []
    for _ in range(depth - 1):
        nxt = []
        cur.append(nxt)
        cur = nxt
    cur.append("SECRET")
    return root


def _assert_sanitized(exc):
    assert isinstance(exc.__cause__, SanitizedCause)
    assert exc.__context__ is None
    assert "SECRET" not in str(exc) and "SECRET" not in str(exc.__cause__)


def test_generate_qr_data_json_nested_1000_deep_never_leaks_recursion_error():
    """Accepts either outcome on purpose: on py39 the json parser gives up first, so the text is treated as
    not-JSON and round-trips on the UTF-8 text path; on py312+ it parses and the CBOR encoder raises EncodingError.
    The monkeypatched test below pins the encoder path on every interpreter. Either way no raw RecursionError
    escapes."""
    pp = PixelPass()
    deep = "[" * 1000 + '"SECRET"' + "]" * 1000
    try:
        qr = pp.generate_qr_data(deep)
    except EncodingError as exc:
        _assert_sanitized(exc)
        assert "nesting too deep" in str(exc)
    else:
        assert pp.decode(qr) == deep


def test_generate_qr_data_parsed_json_too_deep_for_cbor_raises_encoding_error(monkeypatch):
    from pixelpass import _js

    monkeypatch.setattr(_js, "js_parse", lambda text: _nested_list(1000))
    with pytest.raises(EncodingError) as ei:
        PixelPass().generate_qr_data("[]")
    _assert_sanitized(ei.value)
    assert "nesting too deep" in str(ei.value)


def test_generate_qr_data_unparseable_deep_text_takes_text_path():
    pp = PixelPass()
    deep = "[" * 1000  # not JSON -> JS "Data is not JSON" text path
    assert pp.decode(pp.generate_qr_data(deep)) == deep


def test_get_mapped_data_cbor_list_nested_1000_deep_raises_pixelpass_error():
    with pytest.raises((EncodingError, MappingError)) as ei:
        PixelPass().get_mapped_data({"a": _nested_list(1000)}, cbor_enable=True)
    _assert_sanitized(ei.value)


@pytest.mark.parametrize("cbor_enable", [False, True])
def test_get_mapped_data_dict_nested_1000_deep_raises_mapping_error(cbor_enable):
    with pytest.raises(MappingError) as ei:
        PixelPass().get_mapped_data(_nested_dict(1000), cbor_enable=cbor_enable)
    _assert_sanitized(ei.value)


def test_get_mapped_data_cbor_encode_depth_maps_to_encoding_error(monkeypatch):
    from pixelpass import client

    monkeypatch.setattr(client, "map_value", lambda data, mappers, strict: _nested_list(1000))
    with pytest.raises(EncodingError) as ei:
        PixelPass().get_mapped_data({"a": 1}, cbor_enable=True)
    _assert_sanitized(ei.value)


def test_cbor_encode_nested_1000_deep_raises_cbor_error():
    from pixelpass import _cbor

    with pytest.raises(_cbor.CborError) as ei:
        _cbor.encode(_nested_list(1000))
    assert "SECRET" not in str(ei.value)


# ----------------------------------------------------------------------------- repair 4: bare lists, object input
@pytest.mark.parametrize("depth", [1000, 5000])
@pytest.mark.parametrize("cbor_enable", [False, True])
def test_get_mapped_data_bare_nested_list_raises_mapping_error(depth, cbor_enable):
    with pytest.raises(MappingError) as ei:
        PixelPass().get_mapped_data(_nested_list(depth), cbor_enable=cbor_enable)
    _assert_sanitized(ei.value)
    assert "nesting too deep" in str(ei.value)


@pytest.mark.parametrize("depth", [1000, 50000])
def test_generate_qr_data_deep_dict_object_raises_nesting_too_deep(depth):
    # json.dumps gives up (py39) or, where the C encoder copes, the CBOR encoder does: both say "nesting too deep"
    root = _nested_dict(depth)
    leaf = root
    while leaf:
        leaf = leaf["a"]
    leaf["k"] = "SECRET"
    with pytest.raises(EncodingError) as ei:
        PixelPass().generate_qr_data(root)
    _assert_sanitized(ei.value)
    assert "nesting too deep" in str(ei.value)
    assert "JSON-serialisable" not in str(ei.value)


def test_as_text_recursion_error_gets_own_message(monkeypatch):
    from pixelpass import client

    def boom(*args, **kwargs):
        raise RecursionError("SECRET")

    monkeypatch.setattr(client.json, "dumps", boom)
    with pytest.raises(EncodingError) as ei:
        PixelPass().generate_qr_data({"a": 1})
    _assert_sanitized(ei.value)
    assert str(ei.value) == "generate_qr_data: data nesting too deep to serialise"
