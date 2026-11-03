"""Claim 169 key/value mapping (ports of js/src/utils/mapperUtils.js and cborUtils.js).

Keys are JS property keys (``str``) and objects keep JS property order. Unlike the JS reference,
two input keys that resolve to the same mapped key raise :class:`MappingError` unless
``strict=False`` (AC-13); the message names the keys, never the values.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

from . import _js
from .constants import (
    CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY,
    CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY,
    CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER,
    CLAIM_169_BIOMETRIC_KEYS,
    CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER,
    CLAIM_169_ROOT_REVERSE_VALUE_MAPPER,
)
from .exceptions import MappingError


# ----------------------------------------------------------------------------- forward mapping (getMappedData)
class _Mappers:
    """mapperUtils.normalizeMappers: lower-cased keys, lower-cased String() value sources."""

    __slots__ = ("keys", "values")

    def __init__(self, key_mapper: Any, value_mapper: Any) -> None:
        self.keys: Dict[str, Any] = {}
        for k, v in _js.spread(key_mapper if key_mapper is not None else {}).items():
            self.keys[k.lower()] = v
        self.values: Dict[str, Dict[str, Any]] = {}
        for field, mappings in _js.spread(value_mapper if value_mapper is not None else {}).items():
            self.values[field.lower()] = {
                _js.js_string(src).lower(): mapped for src, mapped in _js.spread(mappings).items()
            }


def map_value(data: Any, mappers: _Mappers, strict: bool) -> Any:
    """toMapWithKeyAndValueMapper: map one value (dict, list or scalar)."""
    if data is None:
        return None
    if isinstance(data, (list, tuple)):
        return _map_list(data, mappers, strict)
    if not isinstance(data, dict):
        return data
    result: Dict[str, Any] = {}
    origin: Dict[str, str] = {}
    for original_key, original_value in _js.spread(data).items():
        normalized_key = original_key.lower()
        mapped = mappers.keys.get(normalized_key)
        mapped_key = original_key if mapped is None else _js.js_string(mapped)

        processed = original_value
        field_mapper = mappers.values.get(normalized_key)
        if isinstance(original_value, str) and field_mapper is not None:
            lowered = original_value.lower()
            if lowered in field_mapper:
                processed = field_mapper[lowered]

        if processed is None:
            value: Any = None
        elif isinstance(processed, (list, tuple)):
            value = _map_list(processed, mappers, strict)
        elif isinstance(processed, dict):
            value = map_value(processed, mappers, strict)
        else:
            value = processed

        if mapped_key in origin and strict:
            raise MappingError(
                f"get_mapped_data: input keys '{origin[mapped_key]}' and '{original_key}' "
                f"both map to mapped key '{mapped_key}' (pass strict=False to keep the JS overwrite)"
            )
        origin.setdefault(mapped_key, original_key)
        result[mapped_key] = value
    return _js.js_order(result)


def _map_list(items: Any, mappers: _Mappers, strict: bool) -> List[Any]:
    """toListWithKeyAndValueMapper."""
    out: List[Any] = []
    for item in items:
        if item is None:
            out.append(None)
        elif isinstance(item, dict):
            out.append(map_value(item, mappers, strict))
        elif isinstance(item, (list, tuple)):
            out.append(_map_list(item, mappers, strict))
        else:
            out.append(item)
    return out


def build_mappers(key_mapper: Any, value_mapper: Any) -> _Mappers:
    return _Mappers(key_mapper, value_mapper)


# ----------------------------------------------------------------------------- reverse key mapping (decodeMappedData)
def _depth_lookup(mapper: Mapping[Any, Any]) -> Dict[str, Any]:
    return {_js.js_string(k): v for k, v in mapper.items()}


def _new_key(key: str, lookup: Dict[str, Any]) -> str:
    """``mapper[key] ?? mapper[Number(key)] ?? key``."""
    mapped = lookup.get(key)
    if mapped is None:
        mapped = lookup.get(_js.number_to_string(_js.to_number(key)))
    return key if mapped is None else _js.js_string(mapped)


def replace_keys_at_depth(obj: Any, mapper: Mapping[Any, Any], depth: int) -> Any:
    """cborUtils.replaceKeysAtDepth: rename the keys of objects found at ``depth``."""
    return _replace_keys(obj, _depth_lookup(mapper), depth, 0)


def _replace_keys(obj: Any, lookup: Dict[str, Any], depth: int, current: int) -> Any:
    if isinstance(obj, list):
        return _replace_keys_in_list(obj, lookup, depth, current)
    if not isinstance(obj, dict):
        return obj
    result: Dict[str, Any] = {}
    nxt = current + 1
    for original_key, value in _js.spread(obj).items():
        new_key = _new_key(original_key, lookup) if current == depth else original_key
        if isinstance(value, list):
            result[new_key] = _replace_keys_in_list(value, lookup, depth, nxt)
        elif isinstance(value, dict):
            result[new_key] = _replace_keys(value, lookup, depth, nxt)
        else:
            result[new_key] = value
    return _js.js_order(result)


def _replace_keys_in_list(items: List[Any], lookup: Dict[str, Any], depth: int, current: int) -> List[Any]:
    out: List[Any] = []
    for item in items:
        if isinstance(item, list):
            out.append(_replace_keys_in_list(item, lookup, depth, current))
        elif isinstance(item, dict):
            out.append(_replace_keys(item, lookup, depth, current))
        else:
            out.append(item)
    return out


# ----------------------------------------------------------------------------- public helpers
def _short_code(value: Any) -> Optional[float]:
    if _js.is_number(value):
        try:
            return float(value)
        except OverflowError:  # BigInt past the double range: JS Number() gives +/-Infinity
            return math.inf if value > 0 else -math.inf
    if isinstance(value, str):
        return _js.parse_int10(value)
    return None


def _code_key(value: float) -> str:
    return _js.number_to_string(value)


def replace_values_for_claim169(json_data: Any) -> Dict[str, Any]:
    """Map Claim 169 short codes back to names (port of cborUtils.replaceValuesForClaim169).

    Root fields (Gender, Marital Status, Binary Image Format, Data format) are looked up through
    ``String(value)``; biometric entries get their Data format / Data sub format names. A list or
    string input is spread into an object with index keys, as ``{...jsonData}`` does in JS.
    """
    result = _js.spread(json_data)

    for field_name, reverse_map in CLAIM_169_ROOT_REVERSE_VALUE_MAPPER.items():
        if field_name in result and result[field_name] is not _js.UNDEFINED:
            mapped = reverse_map.get(_js.js_string(result[field_name]))
            if mapped is not None:
                result[field_name] = mapped

    format_key = CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY
    sub_format_key = CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY
    for nested_key in CLAIM_169_BIOMETRIC_KEYS:
        if nested_key not in result or result[nested_key] is _js.UNDEFINED:
            continue
        nested = _js.spread(result[nested_key])
        if nested.get(format_key, _js.UNDEFINED) is _js.UNDEFINED:
            continue
        if nested.get(sub_format_key, _js.UNDEFINED) is _js.UNDEFINED:
            continue
        data_format = _short_code(nested[format_key])
        sub_format = _short_code(nested[sub_format_key])
        if data_format is None or math.isnan(data_format):
            continue
        if sub_format is not None and math.isnan(sub_format):
            continue
        format_value = CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER.get(_code_key(data_format))
        sub_format_value = None
        if format_value is not None and sub_format is not None:
            sub_format_value = CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER.get(format_value, {}).get(
                _code_key(sub_format)
            )
        if format_value is not None:
            nested[format_key] = format_value
        if sub_format_value is not None:
            nested[sub_format_key] = sub_format_value
        result[nested_key] = nested

    return result


def reverse_mapper(mapping: Mapping[Any, Any]) -> Dict[str, Any]:
    """Invert a mapping: ``{"ID": 1}`` becomes ``{"1": "ID"}`` (keys are ``String(value)``, JS order)."""
    if not isinstance(mapping, Mapping):
        raise MappingError("reverse_mapper: mapping must be a dict")
    out: Dict[str, Any] = {}
    for key, value in mapping.items():
        out[_js.js_string(value)] = key
    return _js.js_order(out)
