# PixelPass

## Features

- Create QR Code for given data
- Uses zlib compression and base45 encoding
- Decode QR data encoded by PixelPass
- Convert CBOR encoded base64Url string to JSON

## Usage

The library is implemented in Kotlin and is compatible with both **Kotlin** and **Java** projects. It is published to Maven as two artifacts:

* **`pixelpass-aar`** – Android library (AAR)
* **`pixelpass-jar`** – JVM library (JAR)

Choose the artifact that best fits your project.

### Gradle

**Android (AAR)**

```gradle
implementation("io.inji:pixelpass-aar:1.0.0-alpha.1")
```

**JVM (JAR)**

```gradle
implementation("io.inji:pixelpass-jar:1.0.0-alpha.1")
```

### Maven

**Android (AAR)**

```xml
<dependency>
    <groupId>io.inji</groupId>
    <artifactId>pixelpass-aar</artifactId>
    <version>1.0.0-alpha.1</version>
</dependency>
```

**JVM (JAR)**

```xml
<dependency>
    <groupId>io.inji</groupId>
    <artifactId>pixelpass-jar</artifactId>
    <version>1.0.0-alpha.1</version>
</dependency>
```

## APIs

`generateQRCode( data, ecc, header )`

`data` - Data needs to be compressed and encoded

`ecc` - Error Correction Level for the QR generated. defaults to `"L"`

`header` - Data header need to be prepend to identify the encoded data. defaults to `""`

returns a Base64-encoded PNG string of the QR code image. If a header is provided, it's included in the data that gets encoded into the QR.


`generateQRData( data, header )`

`data` - Data needs to be compressed and encoded

`header` - Data header need to be prepend to identify the encoded data. defaults to `""`

returns compressed and encoded data for qrcode with header prepended if provided.

`decode(data)`

`data` - Data needs to be decoded and decompressed without header

returns a base45 decoded and zlib decompressed string

`decodeBinary(data)`

`data` - Data needs to be decompressed without header. Should be sent as a ByteArray. Currently only zip binary data is only supported.

returns a unzipped string


`getMappedData(jsonData: JSONObject, keyMapper: Map<String,Int>, valueMapper: Map<String, Map<Any, Int>>, cborEnable: Boolean = false)`

- `jsonData` - A JSON data. Which is a JSONObject.
- `keyMapper` - A Map which is used to map keys for the given JSON data. Which is a Map<String,Int>. It will default to the Claim-169 key mapper if nothing provided.
- `valueMapper` - A Map which is used to map values for the given JSON data. Which is a Map<String, Map<Any, Int>>. It will default to the Claim-169 value mapper if nothing provided.
- `cborEnable` - A Boolean which is used to enable or disable CBOR encoding on mapped data. Defaults to `false` if not provided.

return a hex string which is a CBOR encoded JSON with given mapper if `cborEnable` is set to true. Or returns a JSON remapped string.

`getMappedData(jsonData: JSONArray, keyMapper: Map<String,Int>, valueMapper: Map<String, Map<Any, Int>>, cborEnable: Boolean = false)`

- `jsonData` - An array of JSON data. Which is a JSONArray.
- `keyMapper` - A Map which is used to map keys for the given JSON data. Which is a Map<String,Int>. It will default to the Claim-169 key mapper if nothing provided.
- `valueMapper` - A Map which is used to map values for the given JSON data. Which is a Map<String, Map<Any, Int>>. It will default to the Claim-169 value mapper if nothing provided.
- `cborEnable` - A Boolean which is used to enable or disable CBOR encoding on mapped data. Defaults to `false` if not provided.

return an array hex string which is a CBOR encoded JSON with given mapper if `cborEnable` is set to true. Or returns an array of JSON remapped string.

`decodeMappedData(data: String, keyMapper: Array<Map<String, String>>, valueMapperFunction: (JSONObject) -> JSONObject)`

- `data` - A CBOR Encoded string or JSON string which needs to be re mapped.
- `keyMapper` - A array of map which is used to reverse map keys for the given data. Which is a Array<Map<String, String>>. The order of array is directly equals to the depth of JSON tree. As some of the keys are repeated at different depths of JSON this approach is needed. It will default to the Claim-169 reverse key mapper if nothing provided.
- `valueMapperFunction` - A function which is used to map values for the given data. Which is a (JSONObject) -> JSONObject. It will default to the Claim-169 value mapper function if nothing provided.

return a JSON remapped string.

`decodeMappedData(data: Array<String>, keyMapper: Array<Map<String, String>>, valueMapperFunction: (JSONObject) -> JSONObject)`

- `data` - An array of CBOR Encoded string or JSON string which needs to be re mapped.
- `keyMapper` - A array of map which is used to reverse map keys for the given data. Which is a Array<Map<String, String>>. The order of array is directly equals to the depth of JSON tree. As some of the keys are repeated at different depths of JSON this approach is needed. It will default to the Claim-169 reverse key mapper if nothing provided.
- `valueMapperFunction` - A function which is used to map values for the given data. Which is a (JSONObject) -> JSONObject. It will default to the Claim-169 value mapper function if nothing provided.

return an array JSON remapped string.

`toJson(base64UrlEncodedCborEncodedString)`

- `base64UrlEncodedCborEncodedString` - base64url-encoded representation of the CBOR-encoded data

returns decoded data in JSON format

## License
MPL-2.0
