function normalizeMappers(keyMapper = {}, valueMapper = {}) {
  return {
    normalizedKeyMapper: Object.fromEntries(
      Object.entries(keyMapper).map(([k, v]) => [k.toLowerCase(), v])
    ),
    normalizedValueMapper: Object.fromEntries(
      Object.entries(valueMapper).map(([field, mappings]) => [
        typeof field === "string" && field.toLowerCase(),
        Object.fromEntries(
          Object.entries(mappings).map(([src, mapped]) => [
            String(src).toLowerCase(),
            mapped,
          ])
        ),
      ])
    ),
  };
}

function toMapWithKeyAndValueMapper(data, keyMapper, valueMapper) {
  if (data === null || data === undefined) {
    return data;
  }

  if (Array.isArray(data)) {
    return toListWithKeyAndValueMapper(data, keyMapper, valueMapper);
  }

  if (typeof data !== "object") {
    return data;
  }

  const result = {};
  
  const normalizedMappers = normalizeMappers(keyMapper, valueMapper);

  const { normalizedKeyMapper, normalizedValueMapper } = normalizedMappers;

  for (const [originalKey, originalValue] of Object.entries(data)) {
    const normalizedKey = originalKey.toLowerCase();
    const mappedKey = normalizedKeyMapper[normalizedKey] ?? originalKey;

    let processedValue = originalValue;

    const fieldValueMapper = normalizedValueMapper[normalizedKey];

    if (
      originalValue !== null &&
      typeof originalValue === "string" &&
      fieldValueMapper &&
      fieldValueMapper[originalValue.toLowerCase()] !== undefined
    ) {
      processedValue = fieldValueMapper[originalValue.toLowerCase()];
    }

    if (processedValue === null) {
      result[mappedKey] = null;
    } else if (Array.isArray(processedValue)) {
      result[mappedKey] = toListWithKeyAndValueMapper(
        processedValue,
        keyMapper,
        valueMapper
      );
    } else if (typeof processedValue === "object") {
      result[mappedKey] = toMapWithKeyAndValueMapper(
        processedValue,
        keyMapper,
        valueMapper
      );
    } else {
      result[mappedKey] = processedValue;
    }
  }

  return result;
}

function toListWithKeyAndValueMapper(arr, keyMapper, valueMapper) {
  const result = [];

  for (let i = 0; i < arr.length; i++) {
    const value = arr[i];
    let processedValue;

    if (value === null) {
      processedValue = null;
    } else if (typeof value === "object" && !Array.isArray(value)) {
      processedValue = toMapWithKeyAndValueMapper(
        value,
        keyMapper,
        valueMapper
      );
    } else if (Array.isArray(value)) {
      processedValue = toListWithKeyAndValueMapper(
        value,
        keyMapper,
        valueMapper
      );
    } else {
      processedValue = value;
    }

    result.push(processedValue);
  }

  return result;
}

module.exports = {
  toMapWithKeyAndValueMapper,
  toListWithKeyAndValueMapper,
};
