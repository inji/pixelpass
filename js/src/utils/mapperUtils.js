function toMapWithKeyAndValueMapper(data, keyMapper, valueMapper) {
  if (data === null || data === undefined || typeof data !== "object")
    return data;

  const result = {};

  for (const [key, value] of Object.entries(data)) {
    const mappedKey = keyMapper[key] ?? key;

    let processedValue = value;
    const fieldValueMapper = valueMapper?.[key];
    if (
      value !== null &&
      fieldValueMapper &&
      fieldValueMapper[value] !== undefined
    ) {
      processedValue = fieldValueMapper[value];
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
