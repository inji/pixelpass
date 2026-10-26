const { generateQRData, decode } = require("../src");
const {toQrPayload} = require("../example/qrPayload");

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

  test("round-trips example app QR payloads as valid JSON", () => {
    const vcJson = JSON.stringify({
      "@context": ["https://www.w3.org/2018/credentials/v1"],
      type: ["VerifiableCredential", "FarmerCredential"],
      credentialSubject: {fullName: "John Doe", farmerId: "9876543210"},
    });
    const sdJwt = "header.payload.signature~disclosure~";
    const quotedSdJwt = JSON.stringify(sdJwt);
    const jwt = "header.payload.signature";

    expect(JSON.parse(decode(generateQRData(toQrPayload(vcJson))))).toEqual(JSON.parse(vcJson));
    expect(JSON.parse(decode(generateQRData(toQrPayload(`${sdJwt}\n`))))).toBe(sdJwt);
    expect(JSON.parse(decode(generateQRData(toQrPayload(quotedSdJwt))))).toBe(sdJwt);
    expect(JSON.parse(decode(generateQRData(toQrPayload(jwt))))).toBe(jwt);
  });
});
