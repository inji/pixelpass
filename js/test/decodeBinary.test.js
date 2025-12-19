const { decodeBinary } = require("../src");
const JSZip = require("jszip");

describe("decodeBinary", () => {
  test("decode ZIP binary data", async () => {
    const zip = new JSZip();
    zip.file("certificate.json", "Hello World!!");
    const data = await zip.generateAsync({ type: "string" });

    const result = await decodeBinary(new TextEncoder().encode(data));
    expect(result).toBe("Hello World!!");
  });

  test("decodeBinary throws for unsupported file", async () => {
    await expect(
      decodeBinary(new TextEncoder().encode("not-zip"))
    ).rejects.toThrow("Unsupported binary file type");
  });

  test("decode ZIP with multiple files", async () => {
    const zip = new JSZip();
    zip.file("certificate.json", "Cert");
    zip.file("other.txt", "Other");
    const data = await zip.generateAsync({ type: "string" });

    const result = await decodeBinary(new TextEncoder().encode(data));
    expect(result).toBe("Cert");
  });

  test("decode empty ZIP entry", async () => {
    const zip = new JSZip();
    zip.file("certificate.json", "");
    const data = await zip.generateAsync({ type: "string" });

    const result = await decodeBinary(new TextEncoder().encode(data));
    expect(result).toBe("");
  });
});
