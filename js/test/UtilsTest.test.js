const {
  decode,
  generateQRData,
  getMappedData,
  decodeMappedData,
} = require("../src");

const {
  translateToJson,
  replaceKeysAtDepth,
  replaceValuesForClaim169,
} = require("../src/utils/cborUtils");

const {
  toMapWithKeyAndValueMapper,
  toListWithKeyAndValueMapper,
} = require("../src/utils/mapperUtils");

/* ==================================================================
 * TESTS TO COVER REMAINING UNCOVERED LINES
 * ================================================================== */

/* ------------------------------------------------------------------
 * index.js - Line 69 (decode function - CBOR decode returns falsy)
 * ------------------------------------------------------------------ */

test("decode returns text when CBOR decode returns null/undefined", () => {
  // This covers the case where cbor.decode succeeds but returns falsy value
  // We need to trigger the path where decodedCBORData is falsy
  const plainText = "plain text without CBOR";
  const encoded = generateQRData(plainText);
  const result = decode(encoded);

  expect(result).toBe(plainText);
});

/* ------------------------------------------------------------------
 * cborUtils.js - Uncovered Lines
 * ------------------------------------------------------------------ */

// Line 36, 40 - translateToJson with Map containing nested Maps
test("translateToJson handles deeply nested Maps", () => {
  const innerMap = new Map([
    ["level2", "value2"],
    ["data", new Map([["level3", "value3"]])],
  ]);
  const outerMap = new Map([
    ["level1", "value1"],
    ["nested", innerMap],
  ]);

  const result = translateToJson(outerMap);

  expect(result.level1).toBe("value1");
  expect(result.nested.level2).toBe("value2");
  expect(result.nested.data.level3).toBe("value3");
});

// Line 65 - replaceKeysAtDepth with primitive value (not object/array)
test("replaceKeysAtDepth handles primitive values gracefully", () => {
  const primitiveValue = "string value";
  const result = replaceKeysAtDepth(primitiveValue, {}, 0);
  expect(result).toBe("string value");
});

test("replaceKeysAtDepth handles number values", () => {
  const numberValue = 123;
  const result = replaceKeysAtDepth(numberValue, {}, 0);
  expect(result).toBe(123);
});

// Line 79, 83 - replaceValuesForClaim169 with string format codes and edge cases
test("replaceValuesForClaim169 handles NaN from parseInt", () => {
  const input = {
    Face: {
      "Data format": "invalid-number",
      "Data sub format": "0",
      Data: "5249",
    },
  };

  const result = replaceValuesForClaim169(input);

  // Should not crash, format should remain unchanged
  expect(result.Face["Data format"]).toBe("invalid-number");
});

test("replaceValuesForClaim169 handles missing subformat mapping", () => {
  const input = {
    Face: {
      "Data format": 0, // Valid format (Image)
      "Data sub format": 999, // Invalid subformat code
      Data: "5249",
    },
  };

  const result = replaceValuesForClaim169(input);

  expect(result.Face["Data format"]).toBe("Image");
  // Subformat should remain unchanged since 999 is not mapped
  expect(result.Face["Data sub format"]).toBe(999);
});

test("replaceValuesForClaim169 handles null dataFormat value", () => {
  const input = {
    Face: {
      "Data format": null,
      "Data sub format": 0,
      Data: "5249",
    },
  };

  const result = replaceValuesForClaim169(input);

  // Should not crash, should handle null gracefully
  expect(result.Face["Data format"]).toBe(null);
});

// Line 119, 129 - replaceValuesForClaim169 biometric handling edge cases
test("replaceValuesForClaim169 handles non-object biometric values", () => {
  const input = {
    Face: "string instead of object",
    Voice: null,
    Fingerprint: ["array", "instead", "of", "object"],
  };

  const result = replaceValuesForClaim169(input);

  // Should not crash, should preserve values
  expect(result.Face).toBe("string instead of object");
  expect(result.Voice).toBe(null);
  expect(Array.isArray(result.Fingerprint)).toBe(true);
});

test("replaceValuesForClaim169 handles biometric object missing required keys", () => {
  const input = {
    Face: {
      Data: "5249",
      // Missing "Data format" and "Data sub format"
    },
  };

  const result = replaceValuesForClaim169(input);

  // Should not crash, object should remain unchanged
  expect(result.Face.Data).toBe("5249");
  expect(result.Face["Data format"]).toBeUndefined();
});

test("replaceValuesForClaim169 handles biometric with only format, no subformat", () => {
  const input = {
    Face: {
      "Data format": 0,
      // Missing "Data sub format"
      Data: "5249",
    },
  };

  const result = replaceValuesForClaim169(input);

  // Should not crash, should handle missing subformat
  expect(result.Face["Data format"]).toBe(0);
});

/* ------------------------------------------------------------------
 * mapperUtils.js - Lines 38, 42-47
 * ------------------------------------------------------------------ */

// Line 38 - toMapWithKeyAndValueMapper with nested array
test("toMapWithKeyAndValueMapper handles arrays with nested objects", () => {
  const obj = {
    items: [
      { name: "Item1", value: 10 },
      { name: "Item2", value: 20 },
    ],
  };
  const keyMapper = { name: "n", value: "v" };

  const result = toMapWithKeyAndValueMapper(obj, keyMapper, {});

  expect(result.items[0].n).toBe("Item1");
  expect(result.items[0].v).toBe(10);
  expect(result.items[1].n).toBe("Item2");
  expect(result.items[1].v).toBe(20);
});

// Lines 42-47 - toListWithKeyAndValueMapper with nested structures
test("toListWithKeyAndValueMapper handles array with null values", () => {
  const arr = [{ name: "A" }, null, { name: "B" }];
  const keyMapper = { name: "n" };

  const result = toListWithKeyAndValueMapper(arr, keyMapper, {});

  expect(result[0].n).toBe("A");
  expect(result[1]).toBe(null);
  expect(result[2].n).toBe("B");
});

test("toListWithKeyAndValueMapper handles nested arrays of arrays", () => {
  const arr = [
    [
      [1, 2],
      [3, 4],
    ],
    [
      [5, 6],
      [7, 8],
    ],
  ];

  const result = toListWithKeyAndValueMapper(arr, {}, {});

  expect(result[0][0]).toStrictEqual([1, 2]);
  expect(result[0][1]).toStrictEqual([3, 4]);
  expect(result[1][0]).toStrictEqual([5, 6]);
  expect(result[1][1]).toStrictEqual([7, 8]);
});

test("toListWithKeyAndValueMapper handles mixed types in array", () => {
  const arr = [{ type: "object" }, "string", 123, true, null, [1, 2, 3]];
  const keyMapper = { type: "t" };

  const result = toListWithKeyAndValueMapper(arr, keyMapper, {});

  expect(result[0].t).toBe("object");
  expect(result[1]).toBe("string");
  expect(result[2]).toBe(123);
  expect(result[3]).toBe(true);
  expect(result[4]).toBe(null);
  expect(result[5]).toStrictEqual([1, 2, 3]);
});

test("toListWithKeyAndValueMapper handles deeply nested object structures in arrays", () => {
  const arr = [
    {
      level1: {
        level2: {
          name: "deep",
        },
      },
    },
  ];
  const keyMapper = { name: "n" };

  const result = toListWithKeyAndValueMapper(arr, keyMapper, {});

  expect(result[0].level1.level2.n).toBe("deep");
});

/* ------------------------------------------------------------------
 * INTEGRATION TESTS - Covering edge cases through public API
 * ------------------------------------------------------------------ */

test("getMappedData with arrays containing nulls throws error", () => {
  const data = [{ name: "A" }, null, { name: "B" }];
  const keyMapper = { name: "n" };

  expect(() => getMappedData(data, keyMapper)).toThrow(TypeError);
  expect(() => getMappedData(data, keyMapper)).toThrow(
    "jsonData must not be null or undefined"
  );
});

test("decodeMappedData with nested arrays at specific depth", () => {
  const input = {
    users: [
      { id: 1, name: "A" },
      { id: 2, name: "B" },
    ],
  };

  // The objects inside 'users' array are at depth 1
  const keyMapper = [
    { users: "people" }, // depth 0 - rename users to people
    { id: "identifier", name: "label" }, // depth 1 - rename keys inside array objects
  ];

  const result = JSON.parse(decodeMappedData(JSON.stringify(input), keyMapper));

  expect(result.people[0].identifier).toBe(1);
  expect(result.people[0].label).toBe("A");
  expect(result.people[1].identifier).toBe(2);
  expect(result.people[1].label).toBe("B");
});

test("replaceKeysAtDepth with arrays at target depth", () => {
  const obj = {
    data: [{ key: "value1" }, { key: "value2" }],
  };
  const mapper = { key: "newKey" };

  const result = replaceKeysAtDepth(obj, mapper, 1);

  expect(result.data[0].newKey).toBe("value1");
  expect(result.data[1].newKey).toBe("value2");
});

/* ------------------------------------------------------------------
 * EDGE CASES FOR COMPLETE BRANCH COVERAGE
 * ------------------------------------------------------------------ */

test("translateToJson handles empty Map", () => {
  const emptyMap = new Map();
  const result = translateToJson(emptyMap);
  expect(result).toStrictEqual({});
});

test("translateToJson handles empty array", () => {
  const emptyArray = [];
  const result = translateToJson(emptyArray);
  expect(result).toStrictEqual([]);
});

test("translateToJson handles Map with mixed value types", () => {
  const map = new Map([
    ["string", "value"],
    ["number", 123],
    ["boolean", true],
    ["null", null],
    ["array", [1, 2, 3]],
    ["object", { nested: "value" }],
  ]);

  const result = translateToJson(map);

  expect(result.string).toBe("value");
  expect(result.number).toBe(123);
  expect(result.boolean).toBe(true);
  expect(result.null).toBe(null);
  expect(result.array).toStrictEqual([1, 2, 3]);
  expect(result.object.nested).toBe("value");
});
