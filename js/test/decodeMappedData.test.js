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

  test("decode CBOR hex string for claim-169 mapped full JSON", () => {
    const hex =
      "ac6249446a333931383539323433386756657273696f6e0a6946756c6c204e616d656c4a616e61726468616e2042536d44617465206f662042697274686a30342d31382d313938346647656e646572644d616c65674164647265737378294e657720486f7573652c204e656172204d6574726f204c696e652c2042656e67616c7572752c204b4168456d61696c204944756a616e61726468616e406578616d706c652e636f6d6c50686f6e65204e756d6265726d2b3931393837363534333231306b4e6174696f6e616c69747962494e6446616365a3644461746164353234396b4461746120666f726d617465496d6167656f446174612073756220666f726d617463504e4765566f696365a3644461746164353234396b4461746120666f726d617465536f756e646f446174612073756220666f726d6174635741566568656c6c6f65776f726c64";
    const decode = decodeMappedData(hex);
    const decodedData = JSON.parse(decode);
    const hexData = getMappedData(decodedData, [], [], true);
    expect(hexData).toBe(hex);
  });
});
