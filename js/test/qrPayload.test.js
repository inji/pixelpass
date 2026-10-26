const {generateQRData, decode} = require("../src");
const {toQrPayload} = require("../example/qrPayload");

describe("toQrPayload", () => {
  const vcJson = JSON.stringify({
    "@context": ["https://www.w3.org/2018/credentials/v1"],
    type: ["VerifiableCredential", "FarmerCredential"],
    credentialSubject: {fullName: "John Doe", farmerId: "9876543210"},
  });
  const sdJwt = "header.payload.signature~disclosure~";
  const jwt = "header.payload.signature";

  test.each([
    ["VC JSON", vcJson, JSON.parse(vcJson)],
    ["raw SD-JWT with trailing newline", `${sdJwt}\n`, sdJwt],
    ["quoted SD-JWT", JSON.stringify(sdJwt), sdJwt],
    ["plain JWT", jwt, jwt],
    ["empty string", "", {}],
    ["non-string request body", {}, {}],
  ])("round-trips %s as valid JSON", (_name, input, expected) => {
    const decoded = decode(generateQRData(toQrPayload(input)));

    expect(JSON.parse(decoded)).toEqual(expected);
  });
});
