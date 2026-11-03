"""AC-6 (get_mapped_data), AC-7 (decode_mapped_data, reverse_mapper), AC-13 (collision check)."""
from __future__ import annotations

import json

import pytest

from pixelpass import (
    CLAIM_169_REVERSE_KEY_MAPPER,
    DecodingError,
    MappingError,
    replace_values_for_claim169,
)

from conftest import assert_str_keys, b64url, js_compact, mapping_args, mapping_input, vectors


# ----------------------------------------------------------------------------- AC-6 get_mapped_data
def test_ac6_maps_keys_and_values_case_insensitively(pp):
    result = pp.get_mapped_data({"gender": "FEMALE", "FULL NAME": "x", "Marital status": "married"})
    assert result == {"4": "x", "9": 2, "14": 2}
    assert list(result) == ["4", "9", "14"], "JS property order: integer-like keys ascending"


def test_ac6_mapped_keys_are_str(pp):
    result = pp.get_mapped_data({"ID": "a", "Face": {"Data": "d", "Data format": "Image"}})
    assert result == {"1": "a", "62": {"0": "d", "1": 0}}
    assert_str_keys(result)


def test_ac6_unmapped_keys_and_values_kept(pp):
    src = {"zz": "Male", "Gender": "Unknown", "Marital Status": 1, "keep": [1, "a", None]}
    assert pp.get_mapped_data(src) == {"9": "Unknown", "14": 1, "zz": "Male", "keep": [1, "a", None]}


def test_ac6_recurses_into_nested_dicts_and_lists(pp):
    src = {"Guardian": {"ID": "g", "list": [{"Gender": "Male"}, [{"Full Name": "n"}], 3]}}
    assert pp.get_mapped_data(src) == {"15": {"1": "g", "list": [{"9": 1}, [{"4": "n"}], 3]}}


def test_ac6_does_not_mutate_input(pp):
    src = {"Gender": "Male", "nested": {"ID": "x"}}
    snapshot = json.dumps(src)
    pp.get_mapped_data(src)
    pp.get_mapped_data(src, cbor_enable=True)
    assert json.dumps(src) == snapshot


def test_ac6_cbor_enable_returns_lowercase_hex(pp):
    out = pp.get_mapped_data({"ID": "x", "Gender": "male"}, cbor_enable=True)
    assert out == "a2613161786139 01".replace(" ", "")
    assert out == out.lower()


def test_ac6_list_input_returns_per_item_results(pp):
    assert pp.get_mapped_data([{"ID": "a"}, {"Gender": "Male"}]) == [{"1": "a"}, {"9": 1}]
    assert pp.get_mapped_data([{"ID": "a"}, "s"], cbor_enable=True) == ["a161316161", "6173"]


@pytest.mark.parametrize("value", ["abc", 5, 1.5, True, False, ""])
def test_ac6_scalar_unchanged_when_cbor_off(pp, value):
    result = pp.get_mapped_data(value)
    assert result == value and type(result) is type(value)


@pytest.mark.parametrize("value, hexstr", [("abc", "63616263"), (5, "05"), (1.5, "fa3fc00000"), (True, "f5"), ("", "60")])
def test_ac6_scalar_is_js_cbor_hex_when_cbor_on(pp, value, hexstr):
    assert pp.get_mapped_data(value, cbor_enable=True) == hexstr


@pytest.mark.parametrize("cbor_enable", [False, True])
def test_ac6_none_raises_mapping_error(pp, cbor_enable):
    with pytest.raises(MappingError):
        pp.get_mapped_data(None, cbor_enable=cbor_enable)


def test_ac6_custom_mappers(pp):
    result = pp.get_mapped_data({"NAME": "x", "colour": "RED"}, key_mapper={"name": "n", "Colour": 7}, value_mapper={"colour": {"Red": "r"}})
    assert result == {"7": "r", "n": "x"}


# ----------------------------------------------------------------------------- AC-13 collisions
@pytest.mark.parametrize("v", vectors("getMappedData", lambda v: v["category"] == "mapping-collision" and "python_error" in v))
def test_ac13_strict_false_keeps_js_overwrite(pp, v):
    result = pp.get_mapped_data(mapping_input(v), strict=False, **mapping_args(v))
    if v["args"]["cbor_enable"]:
        assert result == v["expected"]
    else:
        assert js_compact(result) == v["expected"]


@pytest.mark.parametrize("v", vectors("getMappedData", lambda v: v["category"] == "mapping-collision" and "python_error" in v))
def test_ac13_strict_default_raises_naming_keys_not_values(pp, v):
    src = mapping_input(v)
    with pytest.raises(MappingError) as ei:
        pp.get_mapped_data(src, **mapping_args(v))
    msg = str(ei.value)
    def named(k: str) -> bool:
        # quoted (repr or double quotes) so a bare digit such as "1" cannot match by accident
        return f"'{k}'" in msg or f'"{k}"' in msg

    for key in v["collision_keys"]:
        assert named(key), f"message must name input key {key!r} quoted: {msg!r}"
    mk = v["collision_mapped_key"]
    assert named(mk) or f"mapped key {mk}" in msg, f"message must name the mapped key {mk!r} quoted: {msg!r}"

    def leaf_values(x):
        if isinstance(x, dict):
            for val in x.values():
                yield from leaf_values(val)
        elif isinstance(x, list):
            for val in x:
                yield from leaf_values(val)
        elif isinstance(x, str):
            yield x

    for val in leaf_values(src):
        if val not in v["collision_keys"] and len(val) > 1:
            assert val not in msg, f"message must not contain value {val!r}"


def test_ac13_message_contains_no_values_with_marker(pp):
    with pytest.raises(MappingError) as ei:
        pp.get_mapped_data({"Gender": "SECRETVALUEONE", "gender": "SECRETVALUETWO"})
    msg = str(ei.value)
    assert "SECRETVALUE" not in msg
    assert ("'Gender'" in msg or '"Gender"' in msg) and ("'gender'" in msg or '"gender"' in msg)
    assert any(q in msg for q in ("'9'", '"9"', "mapped key 9")), msg
    assert ei.value.__cause__ is None or "SECRETVALUE" not in str(ei.value.__cause__)


def test_ac13_unmapped_keys_differing_by_case_stay_separate(pp):
    assert pp.get_mapped_data({"abc": 1, "ABC": 2, "Abc": 3}) == {"abc": 1, "ABC": 2, "Abc": 3}


def test_ac13_collision_detected_in_nested_level_and_lists(pp):
    with pytest.raises(MappingError):
        pp.get_mapped_data({"outer": [{"ID": 1, "id": 2}]})
    with pytest.raises(MappingError):
        pp.get_mapped_data([{"ok": 1}, {"Gender": "Male", "GENDER": "Male"}])


def test_ac13_collision_with_cbor_enabled_also_raises(pp):
    with pytest.raises(MappingError):
        pp.get_mapped_data({"ID": "x", "1": "y"}, cbor_enable=True)


def test_ac13_no_collision_when_mapped_keys_differ(pp):
    assert pp.get_mapped_data({"ID": "x", "2": "y"}) == {"1": "x", "2": "y"}


# ----------------------------------------------------------------------------- AC-7 decode_mapped_data
def test_ac7_hex_cbor_with_int_keys(pp):
    # {1: "x", 9: 1, 62: {1: 0, 2: 1}}
    assert pp.decode_mapped_data("a3016178090118" "3ea201000201") == '{"ID":"x","Gender":"Male","Face":{"Data format":"Image","Data sub format":"JPEG"}}'


def test_ac7_uppercase_hex_accepted(pp):
    assert pp.decode_mapped_data("A2016178096131") == '{"ID":"x","Gender":"Male"}'


def test_ac7_json_input_equals_equivalent_hex(pp):
    hexstr = "a3613161786139016236 32a2613100613201".replace(" ", "")  # {"1":"x","9":1,"62":{"1":0,"2":1}}
    as_json = '{"1":"x","9":1,"62":{"1":0,"2":1}}'
    assert pp.decode_mapped_data(as_json) == pp.decode_mapped_data(hexstr)
    assert pp.decode_mapped_data(hexstr) == '{"ID":"x","Gender":"Male","Face":{"Data format":"Image","Data sub format":"JPEG"}}'


@pytest.mark.parametrize("v", vectors("decodeMappedData", lambda v: v["category"] in ("claim169-roundtrip", "claim169-int-keys") and "expected" in v))
def test_ac7_json_input_equals_hex_for_vectors(pp, v):
    as_json = json.dumps(pp.to_json(b64url(bytes.fromhex(v["input"]))), ensure_ascii=False)
    assert pp.decode_mapped_data(as_json) == pp.decode_mapped_data(v["input"]) == v["expected"]


def test_ac7_top_level_array_spread_to_object(pp):
    assert pp.decode_mapped_data("83010203") == '{"0":1,"1":2,"2":3}'


def test_ac7_key_mapper_applied_per_depth(pp):
    # {1: {1: true}, 2: [3, 4]} with a depth-indexed mapper and identity value mapper
    out = pp.decode_mapped_data("a201a101f502820304", key_mapper=[{"1": "one", "2": "two"}, {"1": "inner-one"}], value_mapper=lambda d: d)
    assert out == '{"one":{"inner-one":true},"two":[3,4]}'


def test_ac7_value_mapper_receives_dict_and_result_is_compact_json(pp):
    seen = []

    def vm(d):
        seen.append(d)
        return {"wrapped": d}

    out = pp.decode_mapped_data("a2016178096131", value_mapper=vm)
    assert seen == [{"ID": "x", "Gender": "1"}]
    assert out == '{"wrapped":{"ID":"x","Gender":"1"}}'
    assert " " not in out


def test_ac7_list_input_returns_per_item_results(pp):
    assert pp.decode_mapped_data(["a10102", '{"9":2}']) == ['{"ID":2}', '{"Gender":"Female"}']


@pytest.mark.parametrize("bad", [{"0": {"1": "ID"}}, "not-a-list", ({"1": "ID"},)])
def test_ac7_key_mapper_not_a_list_raises_mapping_error(pp, bad):
    with pytest.raises(MappingError):
        pp.decode_mapped_data("a10102", key_mapper=bad)


def test_ac7_none_raises_mapping_error(pp):
    with pytest.raises(MappingError):
        pp.decode_mapped_data(None)


@pytest.mark.parametrize("bad", ["", "zz", "abc", "a1", "a1b", " a10102", "0x a1", "{bad json", "not hex or json"])
def test_ac7_neither_hex_cbor_nor_json_raises_decoding_error(pp, bad):
    with pytest.raises(DecodingError):
        pp.decode_mapped_data(bad)


def test_ac7_defaults_are_claim169(pp):
    assert pp.decode_mapped_data("a10902") == pp.decode_mapped_data("a10902", key_mapper=CLAIM_169_REVERSE_KEY_MAPPER, value_mapper=replace_values_for_claim169)
