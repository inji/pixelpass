const { generateQRData, decode } = require("../src");

describe("generateQRData", () => {
  test("encode raw string to QR", () => {
    expect(generateQRData("hello")).toBe("NCFKVPV0QSIP600GP5L0");
  });

  test("encode JSON to CBOR QR", () => {
    expect(generateQRData('{"temp":15}')).toBe("NCF3QBXJA5NJRCOC004 QN4");
  });

  test("encode QR with header", () => {
    expect(generateQRData("hello", "hdr://"))
      .toBe("hdr://NCFKVPV0QSIP600GP5L0");
  });

  test("handles empty string", () => {
    const result = generateQRData("");
    expect(result.length).toBeGreaterThan(0);
  });

  test("handles complex nested JSON", () => {
    const data = JSON.stringify({ a: { b: { c: [1, 2, 3] } } });
    const encoded = generateQRData(data);
    expect(decode(encoded)).toBe(data);
  });

  test("handles non-JSON string with header", () => {
    const result = generateQRData("plain text", "PREFIX:");
    expect(result.startsWith("PREFIX:")).toBe(true);
  });
});
