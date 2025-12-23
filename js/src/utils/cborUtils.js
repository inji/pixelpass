const {
  CLAIM_169_BIOMETRIC_KEYS,
  CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY,
  CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY,
  CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER,
  CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER,
  CLAIM_169_ROOT_REVERSE_VALUE_MAPPER,
} = require("../shared/Constants");

function translateToJson(value) {
  if (value instanceof Map) {
    const data = {};
    value.forEach((mapValue, mapKey) => {
      data[mapKey] = translateToJson(mapValue);
    });
    return data;
  }

  if (Array.isArray(value)) {
    return value.map(translateToJson);
  }

  if (typeof value === "object" && value !== null) {
    const data = {};
    for (const [key, val] of Object.entries(value)) {
      data[key] = translateToJson(val);
    }
    return data;
  }

  return value;
}

function replaceKeysAtDepth(obj, mapper, depth, currentDepth = 0) {
  if (Array.isArray(obj)) {
    return replaceKeysInArrayAtDepth(obj, mapper, depth, currentDepth);
  }

  if (typeof obj !== "object" || obj === null) {
    return obj;
  }

  const result = {};
  const nextDepth = currentDepth + 1;

  for (const [originalKey, value] of Object.entries(obj)) {
    const newKey =
      currentDepth === depth
        ? mapper[originalKey] ?? mapper[Number(originalKey)] ?? originalKey
        : originalKey;

    let processedValue;
    if (Array.isArray(value)) {
      processedValue = replaceKeysInArrayAtDepth(
        value,
        mapper,
        depth,
        nextDepth
      );
    } else if (typeof value === "object" && value !== null) {
      processedValue = replaceKeysAtDepth(value, mapper, depth, nextDepth);
    } else if (value === null) {
      processedValue = null;
    } else {
      processedValue = value;
    }

    result[newKey] = processedValue;
  }

  return result;
}

function replaceKeysInArrayAtDepth(arr, mapper, depth, currentDepth = 0) {
  return arr.map((item) => {
    if (Array.isArray(item)) {
      return replaceKeysInArrayAtDepth(item, mapper, depth, currentDepth);
    } else if (typeof item === "object" && item !== null) {
      return replaceKeysAtDepth(item, mapper, depth, currentDepth);
    } else {
      return item;
    }
  });
}

function replaceValuesForClaim169(jsonData) {
  const result = { ...jsonData };

  Object.entries(CLAIM_169_ROOT_REVERSE_VALUE_MAPPER).forEach(
    ([fieldName, reverseMap]) => {
      if (result[fieldName] !== undefined) {
        const originalValue = result[fieldName];
        const mappedValue = reverseMap[originalValue];
        if (mappedValue !== undefined) {
          result[fieldName] = mappedValue;
        }
      }
    }
  );

  CLAIM_169_BIOMETRIC_KEYS.forEach((nestedKey) => {
    if (result[nestedKey] === undefined) return;

    const nestedObject = { ...result[nestedKey] };

    if (
      typeof nestedObject !== "object" ||
      nestedObject === null ||
      Array.isArray(nestedObject)
    ) {
      return;
    }

    const formatKey = CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY;
    const subFormatKey = CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY;

    if (
      nestedObject[formatKey] === undefined ||
      nestedObject[subFormatKey] === undefined
    ) {
      return;
    }

    const dataFormatShortCode = nestedObject[formatKey];
    const subFormatShortCode = nestedObject[subFormatKey];

    const dataFormatInt =
      typeof dataFormatShortCode === "number"
        ? dataFormatShortCode
        : typeof dataFormatShortCode === "string"
        ? parseInt(dataFormatShortCode, 10)
        : null;

    const subFormatInt =
      typeof subFormatShortCode === "number"
        ? subFormatShortCode
        : typeof subFormatShortCode === "string"
        ? parseInt(subFormatShortCode, 10)
        : null;

    if (dataFormatInt === null || Number.isNaN(dataFormatInt)) return;

    if (subFormatInt !== null && Number.isNaN(subFormatInt)) return;

    const dataFormatValue =
      CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER[dataFormatInt];

    const subFormatValue =
      dataFormatValue !== undefined && subFormatInt !== null
        ? CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER?.[
            dataFormatValue
          ]?.[subFormatInt]
        : undefined;

    if (dataFormatValue !== undefined) {
      nestedObject[formatKey] = dataFormatValue;
    }

    if (subFormatValue !== undefined) {
      nestedObject[subFormatKey] = subFormatValue;
    }

    result[nestedKey] = nestedObject;
  });

  return result;
}

function decodeFromBase64UrlFormat(content) {
  return Buffer.from(content, 'base64url');
}

module.exports = {
  translateToJson,
  replaceKeysAtDepth,
  replaceValuesForClaim169,
  decodeFromBase64UrlFormat
};
