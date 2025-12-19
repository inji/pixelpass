const { generateQRCode } = require("../src");
const { ECC } = require("../src/types/ECC");

describe("generateQRCode", () => {
  test("generate base64 QR image", async () => {
    const img = await generateQRCode("hello", ECC.M);
    expect(img.startsWith("data:image/png;base64")).toBe(true);
  });

  test("generate QR image with header", async () => {
    const img = await generateQRCode("hello", ECC.M, "hdr://");
    expect(img.startsWith("data:image/png;base64")).toBe(true);
  });

  test("supports all ECC levels", async () => {
    for (const level of [ECC.L, ECC.M, ECC.Q, ECC.H]) {
      const img = await generateQRCode("test", level);
      expect(img.startsWith("data:image/png;base64")).toBe(true);
    }
  });

  test("handles empty string", async () => {
    const img = await generateQRCode("", ECC.M);
    expect(img.startsWith("data:image/png;base64")).toBe(true);
  });
});
