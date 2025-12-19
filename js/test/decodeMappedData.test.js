const { decodeMappedData, getMappedData } = require("../src");

describe("decodeMappedData", () => {
  test("decodeMappedData from CBOR", () => {
    const data = "a302644a686f6e01633230370365486f6e6179";
    const map = [{ 1: "id", 2: "name", 3: "l_name" }];

    const result = JSON.parse(decodeMappedData(data, map));
    expect(result).toStrictEqual({
      name: "Jhon",
      id: "207",
      l_name: "Honay",
    });
  });

  test("supports array input", () => {
    const data = [
      "a302644a686f6e01633230370365486f6e6179",
      "a302654a6d69746801633130320363446f65",
    ];

    const map = [{ 1: "id", 2: "name", 3: "l_name" }];
    const result = decodeMappedData(data, map).map(JSON.parse);

    expect(result[1].name).toBe("Jmith");
  });

  test("depth-based key remapping", () => {
    const input = { 1: { 0: "5249", 1: 0, 2: 0 } };
    const mapper = [
      { 1: "Face" },
      { 0: "Data", 1: "Data format", 2: "Data sub format" },
    ];

    const result = JSON.parse(decodeMappedData(JSON.stringify(input), mapper));
    expect(result.Face["Data sub format"]).toBe("PNG");
  });

  test("round-trip inverse operation", () => {
    const input = { id: "123", name: "Test" };
    const encoded = getMappedData(input, { id: "1", name: "2" }, {}, true);
    const decoded = JSON.parse(
      decodeMappedData(encoded, [{ 1: "id", 2: "name" }])
    );

    expect(decoded).toStrictEqual(input);
  });

  test("throws on invalid JSON", () => {
    expect(() => decodeMappedData("{bad")).toThrow();
  });
});
