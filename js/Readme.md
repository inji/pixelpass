# PixelPass

Pixelpass is a library which can do multiple things which are listed below,

- Given a data → `generateQRCode` → returns a QR Code.

- Given a JSON String → `generateQRData` → Gives back CBOR-encoded data.

- Given a CBOR-encoded data as byte array → `decode` → Gives back JSON String.
- Given data as byteArray → `decodeBinary` → Gives back JSON String.
- Given a JSON and Mapper → `getMappedData` → Gives back CBOR-encoded data or mapped JSON.

- Given a CBOR-encoded data and Mapper → `decodeMappedData` → Gives back a JSON.

## 🚨 Breaking Changes (`0.8.0` and later)

Starting from version `0.8.0`, the following APIs have undergone changes
to support advanced key/value compression and depth-aware decoding.

These updates improve interoperability and reduce CBOR payload sizes.

## 🔄 API Contract Changes

### 1. `getMappedData` --- Signature Change

#### Old (Deprecated)

`getMappedData(jsonData, mapper, cborEnable?)`

#### New (Recommended)

`getMappedData(jsonData, keyMapper, valueMapper, cborEnable?)`

### 2. `decodeMappedData` --- Signature Change

#### Old (Deprecated)

`decodeMappedData(data, mapper)`

#### New (Recommended)

`decodeMappedData(data, keyMapper, valueMapper?)`.

## Features

- Compresses the data using zlib compression of level 9.

- Encodes/ Decodes the data using base45.

- When the Data is JSON, it does the CBOR encode/decode to reduce size further.

- When JSON and a Mapper is given, it maps the JSON with Mapper and then does the CBOR encode/decode which further reduces the size of the data.

## Usage

`npm i @injistack/pixelpass`

[npm](https://www.npmjs.com/package/@injistack/pixelpass)

## Example

Prerequisites

- [nodejs](https://nodejs.org/en/learn/getting-started/how-to-install-nodejs)
- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

To run the example app copy the below command and paste it to your terminal.

```
git clone https://github.com/inji/pixelpass.git && cd pixelpass && git checkout develop && cd js && npm i && cd example && npm i && npm start
```

## APIs

### generateQRCode( data, ecc , header )

- `data` - Data needs to be compressed and encoded.

- `ecc` - Error Correction Level for the QR generated. defaults to `"L"`.

- `header` - Data header need to be prepend to identify the encoded data. defaults to `""`.

```javascript
import { generateQRCode } from "@injistack/pixelpass";

const data = "Hello";
const qrCode = generateQRCode(data, ecc, header);

// ecc is Error Correction Level for the QR generated. defaults to "L".
// header defaults to empty string if not passed.
```

The `generateQRCode` takes a data, ECC (Error correction level) which when not passed defaults to L and header which defaults to empty string if not passed.
Returns a base64 encoded PNG image.

### generateQRData( data, header )

- `data` - Data needs to be compressed and encoded.

- `header` - Data header need to be prepend to identify the encoded data. defaults to `""`.

```javascript
import { generateQRData } from "@injistack/pixelpass";

const jsonString = '{"name":"Steve","id":"1","l_name":"jobs"}';
const header = "jsonstring";

const encodedCBORData = generateQRData(jsonString, header);

// header defaults to empty string if not passed.
```

The `generateQRData` takes a valid JSON string and a header which when not passed defaults to an empty string.
This API will return a base45 encoded string which is `Compressed > CBOR Encoded > Base45 Encoded`.

### decode( data )

- `data` - Data needs to be decoded and decompressed without header.

```javascript
import { decode } from "@injistack/pixelpass";

const b45EncodedData =
  "NCFWTL$PPB$PN$AWGAE%5UW5A%ADFAHR9 IE:GG6ZJJCL2.AJKAMHA100+8S.1";
const jsonString = decode(b45EncodedData);
```

The `decode` will take a `string` as parameter and gives us decoded JSON string which is Base45 `Decoded > CBOR Decoded > Decompressed`.

### decodeBinary( data )

- `data` - Data needs to be decoded and decompressed without header.

```javascript
import { decodeBinary } from '@injistack/pixelpass';

const zipdata = <zip-byte-array>;
const decompressedData = decodeBinary(zipdata);
```

The `decodeBinary` will take a `UInt8ByteArray` as parameter and gives us unzipped string. Currently only zip binary data is supported.

### getMappedData( jsonData, keyMapper, valueMapper, cborEnable )

- `jsonData` - A JSON data or an array of JSON data.
- `keyMapper` - A Map which is used to map the keys of the JSON.
- `valueMapper` - A Map which is used to map the values of the JSON.
- `cborEnable` - A Boolean which is used to enable or disable CBOR encoding on mapped data. Defaults to `false` if not provided.

```javascript
import { getMappedData } from "@injistack/pixelpass";

const jsonData = { name: "Jhon", id: "207", l_name: "Honay" };
const keyMapper = { id: "1", name: "2", l_name: "3" };
const valueMapper = {}; // Optional value mapping

const result = getMappedData(jsonData, keyMapper, valueMapper, true);

// If cborEnable is true, result is a hex string of CBOR-encoded data
const cborEncodedString = result;

// If cborEnable is false, result is the mapped JSON object
const mappedJson = getMappedData(jsonData, keyMapper, valueMapper, false);
```

The `getMappedData` takes 4 arguments:

1. A JSON object or array of JSON objects
2. A key mapper to map JSON keys
3. A value mapper to map JSON values (can be empty object if no value mapping needed)
4. An optional boolean to enable or disable CBOR encoding on the mapped data (defaults to `false`)

The example of a converted map would look like, `{ "1": "207", "2": "Jhon", "3": "Honay"}`

When `cborEnable` is `true`, the function returns a hex string of the CBOR-encoded mapped data.
When `cborEnable` is `false`, the function returns the mapped JSON object directly.

**⚠️ DEPRECATION NOTICE**: The previous 3-argument signature `getMappedData(jsonData, mapper, cborEnable)` is deprecated. Please use the new 4-argument signature with separate `keyMapper` and `valueMapper` parameters.

### decodeMappedData( data, keyMapper, valueMapper )

- `data` - A CBOR-encoded hex string, a mapped JSON string, or an array of either.
- `keyMapper` - An array of mapper objects for depth-aware key decoding. Each mapper object handles keys at a specific depth level.
- `valueMapper` - A function to transform values in the decoded JSON. Optional.

```javascript
import { decodeMappedData } from "@injistack/pixelpass";

const cborEncodedString = "a302644a686f6e01633230370365486f6e6179";
const keyMapper = [
  { 1: "id", 2: "name", 3: "l_name" }, // Mapper for depth 0
];
const valueMapper = (jsonData) => {
  // Optional: transform values if needed
  return jsonData;
};

const jsonString = decodeMappedData(cborEncodedString, keyMapper, valueMapper);
const jsonData = JSON.parse(jsonString);
```

The `decodeMappedData` takes 3 arguments:

1. A CBOR-encoded hex string, a JSON string, or an array of either
2. An array of mapper objects for depth-aware key decoding (each index corresponds to a depth level)
3. An optional value mapper function to transform the decoded data

The function will:

- First attempt to decode the data as CBOR (if it's a hex string)
- If CBOR decoding fails, it will try to parse it as JSON
- Apply key mapping at each depth level using the provided keyMapper array
- Apply value transformation using the valueMapper function (if provided)
- Return a JSON string representation of the decoded and mapped data

Example with nested objects:

```javascript
const keyMapper = [
  { 1: "id", 2: "name" }, // Maps keys at depth 0
  { a: "street", b: "city" }, // Maps keys at depth 1 (nested objects)
];

const result = decodeMappedData(cborEncodedData, keyMapper);
```

The function also supports arrays of data:

```javascript
const dataArray = [encodedData1, encodedData2, encodedData3];
const results = decodeMappedData(dataArray, keyMapper, valueMapper);
// Returns an array of decoded JSON strings
```

**⚠️ BREAKING CHANGE**: The signature has been updated from the previous 2-argument version `decodeMappedData(data, mapper)` to the new 3-argument version `decodeMappedData(data, keyMapper, valueMapper)`. The `keyMapper` is now expected to be an array of mapper objects for depth-aware decoding, and an optional `valueMapper` function can be provided for value transformations.

#### Migration Guide from Old to New API

**Old API (Deprecated):**

```javascript
const mapper = { 1: "id", 2: "name", 3: "l_name" };
const jsonData = decodeMappedData(cborEncodedString, mapper);
```

**New API:**

```javascript
const keyMapper = [
  { 1: "id", 2: "name", 3: "l_name" }, // Wrap mapper in array
];
const valueMapper = null; // or a transformation function
const jsonString = decodeMappedData(cborEncodedString, keyMapper, valueMapper);
const jsonData = JSON.parse(jsonString); // Parse the returned JSON string
```

Key differences:

- `keyMapper` must now be an array (for depth-aware mapping)
- `valueMapper` is a new optional parameter for value transformations
- Returns a JSON string instead of an object (needs `JSON.parse()`)
- Supports arrays of data for batch processing

## Errors / Exceptions

- `Cannot read properties of null (reading 'length')` - thrown when the string passed to encode is null.

- `Cannot read properties of undefined (reading 'length')` - thrown when the string passed to encode is undefined.

- `byteArrayArg is null or undefined.` - thrown when the string passed to encode is null or undefined.

- `utf8StringArg is null or undefined.` - thrown when the string passed to decode is null or undefined.

- `utf8StringArg has incorrect length.` - thrown when the string passed to decode is of invalid length.

- `Invalid character at position X.` - thrown when the string passed to decode is invalid with an unknown character then base45 character set. Also denotes the invalid character position.

- `incorrect data check` - thrown when the string passed to decode is invalid.

- `jsonData must not be null or undefined` - thrown when null or undefined is passed to `getMappedData`.

## License
MPL-2.0
