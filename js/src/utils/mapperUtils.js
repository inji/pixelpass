function toMapWithKeyAndValueMapper(data, keyMapper, valueMapper) {
  if (data === null || data === undefined || typeof data !== "object") {
    return data;
  }

  const result = {};

  const normalizedKeyMapper = Object.fromEntries(
    Object.entries(keyMapper || {}).map(([sourceKey, mappedKey]) => [
      sourceKey.toLowerCase(),
      mappedKey,
    ])
  );

  const normalizedValueMapper = Object.fromEntries(
    Object.entries(valueMapper || {}).map(([fieldName, fieldValueMappings]) => [
      fieldName.toLowerCase(),
      Object.fromEntries(
        Object.entries(fieldValueMappings).map(([sourceValue, mappedValue]) => [
          sourceValue.toLowerCase(),
          mappedValue,
        ])
      ),
    ])
  );

  for (const [originalKey, originalValue] of Object.entries(data)) {
    const normalizedKey = originalKey.toLowerCase();
    const mappedKey = normalizedKeyMapper[normalizedKey] ?? originalKey;

    let processedValue = originalValue;

    const fieldValueMapper = normalizedValueMapper[normalizedKey];

    if (
      originalValue !== null &&
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
