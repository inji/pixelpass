const cbor = require("cbor-web");
const { toJson } = require("../src");

describe("toJson (Base64URL CBOR → JSON)", () => {
  test("decodes base64url encoded CBOR into JSON object", () => {
    // 🔹 Input JSON
    const input = {
      id: "123",
      name: "Alice",
      age: 30,
    };

    // 🔹 Encode to CBOR → Base64URL (same as Kotlin flow)
    const cborBytes = cbor.encode(input);
    const base64Url = Buffer.from(cborBytes).toString("base64url");

    // 🔹 Decode using toJson
    const result = toJson(base64Url);

    expect(result).toStrictEqual(input);
  });

  test("handles nested objects and arrays", () => {
    const input = {
      user: {
        name: "Bob",
        roles: ["admin", "user"],
        profile: {
          active: true,
          score: 99,
        },
      },
    };

    const cborBytes = cbor.encode(input);
    const base64Url = Buffer.from(cborBytes).toString("base64url");

    const result = toJson(base64Url);

    expect(result).toStrictEqual(input);
  });

  test("handles CBOR Map correctly", () => {
    // 🔹 Explicit Map to ensure translateToJson(Map) path is hit
    const map = new Map();
    map.set(1, "one");
    map.set(2, "two");

    const cborBytes = cbor.encode(map);
    const base64Url = Buffer.from(cborBytes).toString("base64url");

    const result = toJson(base64Url);

    expect(result).toStrictEqual({
      1: "one",
      2: "two",
    });
  });

  test("handles arrays at root level", () => {
    const input = [
      { id: 1, value: "A" },
      { id: 2, value: "B" },
    ];

    const cborBytes = cbor.encode(input);
    const base64Url = Buffer.from(cborBytes).toString("base64url");

    const result = toJson(base64Url);

    expect(result).toStrictEqual(input);
  });

  test("handles null and primitive values", () => {
    const input = {
      a: null,
      b: true,
      c: false,
      d: 42,
      e: "text",
    };

    const cborBytes = cbor.encode(input);
    const base64Url = Buffer.from(cborBytes).toString("base64url");

    const result = toJson(base64Url);

    expect(result).toStrictEqual(input);
  });

  test("throws error for invalid base64url input", () => {
    expect(() => toJson("%%%invalid%%%")).toThrow();
  });
});
