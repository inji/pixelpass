const { decode, generateQRData } = require("../src");

describe("decode", () => {
  test("decode simple base45 string", () => {
    expect(decode("NCFKVPV0QSIP600GP5L0")).toBe("hello");
  });

  test("decode CBOR encoded QR data", () => {
    expect(decode("NCF3QBXJA5NJRCOC004 QN4")).toBe('{"temp":15}');
  });

  test("decode CBOR array QR", () => {
    const data = '[{"a":1},{"b":2}]';
    const encoded = generateQRData(data);
    expect(decode(encoded)).toBe(data);
  });

  test("decode handles null values", () => {
    const encoded = generateQRData(JSON.stringify({ key: null }));
    expect(decode(encoded)).toBe('{"key":null}');
  });

  test("decode handles booleans", () => {
    const encoded = generateQRData(JSON.stringify({ a: true, b: false }));
    expect(JSON.parse(decode(encoded))).toStrictEqual({ a: true, b: false });
  });

  test("decode returns text when CBOR fails", () => {
    const encoded = generateQRData("hello");
    expect(decode(encoded)).toBe("hello");
  });

  test("decode throws on invalid base45", () => {
    expect(() => decode("^1")).toThrow();
  });
});
