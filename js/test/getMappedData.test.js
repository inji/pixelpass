const { getMappedData } = require("../src");
const {
  CLAIM_169_KEY_MAPPER,
  CLAIM_169_VALUE_MAPPER,
} = require("../src/shared/Constants");

describe("getMappedData", () => {
  test("returns mapped object", () => {
    const data = { name: "Jhon", id: "207", l_name: "Honay" };
    const map = { id: "1", name: "2", l_name: "3" };

    expect(getMappedData(data, map)).toStrictEqual({
      2: "Jhon",
      1: "207",
      3: "Honay",
    });
  });

  test("returns CBOR hex when enabled", () => {
    const data = { name: "Jhon", id: "207", l_name: "Honay" };
    const map = { id: "1", name: "2", l_name: "3" };

    const result = getMappedData(data, map, undefined, true);
    expect(typeof result).toBe("string");
  });

  test("supports array input", () => {
    const data = [{ name: "A" }, { name: "B" }];
    const map = { name: "n" };

    const result = getMappedData(data, map);
    expect(result[0].n).toBe("A");
    expect(result[1].n).toBe("B");
  });

  test("handles nested objects and arrays", () => {
    const data = { users: [{ name: "A" }, { name: "B" }] };
    const map = { name: "n" };

    const result = getMappedData(data, map);
    expect(result.users[1].n).toBe("B");
  });

  test("preserves null values", () => {
    const result = getMappedData({ a: null });
    expect(result.a).toBeNull();
  });

  test("should return CBOR hex string for claim-169 mapped full JSON", () => {
    const jsonData = {
      "Address": "New House, Near Metro Line, Bengaluru, KA",
      "Version": 10,
      "Email ID": "janardhan@example.com",
      "Full Name": "Janardhan BS",
      "Date of Birth": "19840418",
      "ID": "3918592438",
      "Gender": "Male",
      "hello": "world",
      "Phone Number": "+919876543210",
      "Face": { "Data format": "Image", "Data sub format": "PNG", "Data": "5249" },
      "Voice": { "Data format": "Sound", "Data sub format": "WAV", "Data": "5249" },
      "Nationality": "IN",
    };
    const result = getMappedData(
      jsonData,
      CLAIM_169_KEY_MAPPER,
      CLAIM_169_VALUE_MAPPER,
      true
    );
    expect(typeof result).toBe("string");
  });

});
