const {
  DEFAULT_QR_QUALITY,
  DEFAULT_QR_BORDER,
  DEFAULT_QR_SCALE,
  COLOR_BLACK,
  COLOR_WHITE,
  DEFAULT_ZLIB_COMPRESSION_LEVEL,
  DEFAULT_ECC_LEVEL,
  ZIP_HEADER,
  DEFAULT_ZIP_FILE_NAME,
  CLAIM_169_KEY_MAPPER,
  CLAIM_169_VALUE_MAPPER,
  CLAIM_169_REVERSE_KEY_MAPPER,
} = require("./shared/Constants");
const QRCode = require("qrcode");
const b45 = require("base45-web");
const pako = require("pako");
const cbor = require("cbor-web");
const JSZip = require("jszip");
const {
  translateToJson,
  replaceKeysAtDepth,
  replaceValuesForClaim169,
  decodeFromBase64UrlFormat,
} = require("./utils/cborUtils.js");
const { toMapWithKeyAndValueMapper } = require("./utils/mapperUtils.js");

function toJson(base64UrlEncodedCborEncodedString) {
  if (typeof base64UrlEncodedCborEncodedString !== "string") {
    throw new TypeError("Expected base64url-encoded CBOR string");
  }
  try {
    const decodedData = decodeFromBase64UrlFormat(
      base64UrlEncodedCborEncodedString
    );
    const cborDecoded = cbor.decodeFirstSync(decodedData);
    return translateToJson(cborDecoded);
  } catch (error) {
    throw new Error(`Failed to decode CBOR data: ${error.message}`);
  }
}

function generateQRData(data, header = "") {
  let parsedData = null;
  let compressedData, b45EncodedData;
  try {
    parsedData = JSON.parse(data);
    const cborEncodedData = cbor.encode(parsedData);
    compressedData = pako.deflate(cborEncodedData, {
      level: DEFAULT_ZLIB_COMPRESSION_LEVEL,
    });
  } catch (e) {
    console.error("Data is not JSON");
    compressedData = pako.deflate(data, {
      level: DEFAULT_ZLIB_COMPRESSION_LEVEL,
    });
  } finally {
    b45EncodedData = b45.encode(compressedData).toString();
  }
  return header + b45EncodedData;
}

async function generateQRCode(data, ecc = DEFAULT_ECC_LEVEL, header = "") {
  const base45Data = generateQRData(data, header);
  const opts = {
    errorCorrectionLevel: ecc,
    quality: DEFAULT_QR_QUALITY,
    margin: DEFAULT_QR_BORDER,
    scale: DEFAULT_QR_SCALE,
    color: {
      dark: COLOR_BLACK,
      light: COLOR_WHITE,
    },
  };
  return QRCode.toDataURL(base45Data, opts);
}

function decode(data) {
  const decodedBase45Data = b45.decode(data);
  // Base45 returns number[], convert it
  const binaryData = Uint8Array.from(decodedBase45Data);
  const decompressedData = pako.inflate(binaryData);
  const textData = new TextDecoder().decode(decompressedData);
  try {
    const decodedCBORData = cbor.decodeFirstSync(decompressedData);
    if (decodedCBORData) return JSON.stringify(decodedCBORData);
    return textData;
  } catch (e) {
    return textData;
  }
}

async function decodeBinary(data) {
  let decodedData = new TextDecoder("utf-8").decode(data);
  if (decodedData.startsWith(ZIP_HEADER)) {
    const zip = await JSZip.loadAsync(decodedData);
    const file = zip.file(DEFAULT_ZIP_FILE_NAME);
    if (!file) {
      throw new Error(
        `File '${DEFAULT_ZIP_FILE_NAME}' not found in ZIP archive`
      );
    }
    return file.async("text");
  } else {
    throw new Error("Unsupported binary file type");
  }
}

function getMappedData(
  jsonData,
  keyMapper = CLAIM_169_KEY_MAPPER,
  valueMapper = CLAIM_169_VALUE_MAPPER,
  cborEnable = false
) {
  if (jsonData == null) {
    throw new TypeError("jsonData must not be null or undefined");
  }

  if (Array.isArray(jsonData)) {
    return jsonData.map((item) =>
      getMappedData(item, keyMapper, valueMapper, cborEnable)
    );
  }

  const payload = toMapWithKeyAndValueMapper(jsonData, keyMapper, valueMapper);

  if (cborEnable) {
    return Buffer.from(cbor.encode(payload)).toString("hex");
  }

  return payload;
}

function decodeMappedData(
  data,
  keyMapper = CLAIM_169_REVERSE_KEY_MAPPER,
  valueMapper = replaceValuesForClaim169
) {
  if (data == null) {
    throw new TypeError("data must not be null or undefined");
  }

  if (Array.isArray(data)) {
    return data.map((item) => {
      return decodeMappedData(item, keyMapper, valueMapper);
    });
  }

  let jsonData;

  try {
    const bytes = Buffer.from(data, "hex");
    const decoded = cbor.decodeFirstSync(bytes);
    jsonData = translateToJson(decoded);
  } catch (error) {
    try {
      jsonData = JSON.parse(data);
    } catch (parseError) {
      throw new Error(`Failed to decode data as CBOR or JSON: ${parseError.message}`);
    }
  }

  if (keyMapper) {
    if (!Array.isArray(keyMapper)) {
      throw new TypeError(
        "keyMapper must be an array of mapper objects for depth-aware decoding"
      );
    }

    keyMapper.forEach((mapper, index) => {
      if (mapper && typeof mapper === "object") {
        jsonData = replaceKeysAtDepth(jsonData, mapper, index);
      }
    });
  }

  if (valueMapper && typeof valueMapper === "function") {
    jsonData = valueMapper(jsonData);
  }

  return JSON.stringify(jsonData);
}

module.exports = {
  toJson,
  generateQRData,
  generateQRCode,
  decode,
  decodeBinary,
  getMappedData,
  decodeMappedData,
};
