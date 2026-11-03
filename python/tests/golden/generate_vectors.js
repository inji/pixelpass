#!/usr/bin/env node
/*
 * Golden-vector generator for the PixelPass Python SDK (task PP-PYSDK, AC-9 / AC-10).
 *
 * The JS reference in js/src is the source of truth. This script calls it (and, for decode-only
 * vectors, the exact dependency versions it uses: cbor-web, pako, base45-web) and writes
 * python/tests/golden/vectors.json. The output is deterministic: 2-space JSON, LF, vectors sorted
 * by id, no timestamps.
 *
 * Usage (from the repo root, after `npm ci` in js/):
 *   node python/tests/golden/generate_vectors.js
 * Environment:
 *   PIXELPASS_JS_DIR           JS package dir (default: ../../../js relative to this file)
 *   PIXELPASS_UPSTREAM_COMMIT  commit to record (default: `git rev-parse HEAD` in the JS dir)
 *   PIXELPASS_VECTORS_OUT      output path (default: vectors.json beside this file)
 *
 * Vector schema (schema_version 1):
 *   id, category, function (JS name), input | input_json | input_value, header?, args?,
 *   expected (string; JSON.stringify of the JS result for object results), expected_value?
 *   (typed tree, only when compare == "value"), expect_error? (JS error message), compare
 *   ("exact" | "value"), deviation? (note; Python behaviour differs deliberately),
 *   python_error? (exception class the Python SDK must raise), value_input? (generateQRData:
 *   the parsed JSON value may be passed to Python as dict/list/int/float/bool), encode_parity?
 *   (AC-10), source_cbor_hex? (decode-only vectors built from raw CBOR / raw bytes).
 * Typed values: {"$float": "NaN" | "Infinity" | "-Infinity" | "-0"} and {"$int": "<digits>"}.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { execFileSync } = require("child_process");

const JS_DIR = path.resolve(
  process.env.PIXELPASS_JS_DIR || path.resolve(__dirname, "../../../js")
);
const OUT =
  process.env.PIXELPASS_VECTORS_OUT || path.join(__dirname, "vectors.json");

const req = (name) => require(path.join(JS_DIR, "node_modules", name));
const P = require(path.join(JS_DIR, "src"));
const C = require(path.join(JS_DIR, "src", "shared", "Constants"));
const cbor = req("cbor-web");
const pako = req("pako");
const b45 = req("base45-web");

// The reference writes console.error / console.warn on fallback paths; keep the run quiet.
console.error = () => {};
console.warn = () => {};

// ---------------------------------------------------------------- provenance
function upstreamCommit() {
  if (process.env.PIXELPASS_UPSTREAM_COMMIT) return process.env.PIXELPASS_UPSTREAM_COMMIT;
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], { cwd: JS_DIR, encoding: "utf8" }).trim();
  } catch (e) {
    return "unknown";
  }
}
function depVersion(name) {
  return JSON.parse(fs.readFileSync(path.join(JS_DIR, "node_modules", name, "package.json"), "utf8")).version;
}
function srcDigest() {
  const files = [];
  const walk = (d) => {
    for (const f of fs.readdirSync(d).sort()) {
      const p = path.join(d, f);
      if (fs.statSync(p).isDirectory()) walk(p);
      else files.push(p);
    }
  };
  walk(path.join(JS_DIR, "src"));
  const h = crypto.createHash("sha256");
  for (const f of files) {
    h.update(path.relative(JS_DIR, f).split(path.sep).join("/"));
    h.update("\0");
    h.update(fs.readFileSync(f).toString("utf8").replace(/\r\n/g, "\n"));
    h.update("\0");
  }
  return h.digest("hex");
}

// ---------------------------------------------------------------- helpers
const hex = (b) => Buffer.from(b).toString("hex");
const b45OfBytes = (bytes) => b45.encode(pako.deflate(Uint8Array.from(bytes), { level: 9 })).toString();
const b64url = (h) => Buffer.from(cborHex(h), "hex").toString("base64url");
// Hex of a CBOR map with typed (non-string) keys, built from [key, value] pairs (values may be nested M()).
const M = (entries) => new Map(entries);
const cborHex = (x) => (typeof x === "string" ? x : hex(cbor.encode(x)));

function stringifyBig(v) {
  // JSON.stringify, but BigInt rendered as bare digits (what Python json.dumps prints for int).
  const s = JSON.stringify(v, (k, x) => (typeof x === "bigint" ? "\u0000BIG" + x.toString() : x));
  return s === undefined ? undefined : s.replace(/"\\u0000BIG(-?\d+)"/g, "$1");
}
function typed(v) {
  return JSON.parse(
    JSON.stringify(v, (k, x) => {
      if (typeof x === "bigint") return { $int: x.toString() };
      if (typeof x === "number" && !Number.isFinite(x)) return { $float: String(x) };
      return x;
    })
  );
}
// True when compact json.dumps of the Python value cannot equal JSON.stringify (oracle note in
// ACCEPTANCE_REVIEW round 4): non-finite, |x| < 1e-4 non-integral (Python exponent form) or
// integral |x| >= 1e21 (JS exponent form).
function needsValueCompare(v) {
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return true;
    if (!Number.isInteger(v) && v !== 0 && Math.abs(v) < 1e-4) return true;
    if (Number.isInteger(v) && Math.abs(v) >= 1e21) return true;
    return false;
  }
  if (Array.isArray(v)) return v.some(needsValueCompare);
  if (v && typeof v === "object") return Object.values(v).some(needsValueCompare);
  return false;
}
function hasNegZeroOrNonFinite(v) {
  if (typeof v === "number") return Object.is(v, -0) || !Number.isFinite(v);
  if (Array.isArray(v)) return v.some(hasNegZeroOrNonFinite);
  if (v && typeof v === "object") return Object.values(v).some(hasNegZeroOrNonFinite);
  return false;
}
function fromTyped(v) {
  if (Array.isArray(v)) return v.map(fromTyped);
  if (v && typeof v === "object") {
    if (Object.keys(v).length === 1 && "$float" in v) return v.$float === "-0" ? -0 : Number(v.$float);
    const o = {};
    for (const [k, x] of Object.entries(v)) o[k] = fromTyped(x);
    return o;
  }
  return v;
}
function attempt(fn) {
  try {
    return { ok: true, value: fn() };
  } catch (e) {
    return { ok: false, error: String((e && e.message) || e) };
  }
}

const vectors = [];
const ids = new Set();
function add(v) {
  if (ids.has(v.id)) throw new Error("duplicate vector id " + v.id);
  ids.add(v.id);
  vectors.push(v);
}

// ---------------------------------------------------------------- generateQRData (+ round-trip decode)
// [category, name, input string, header]
const S23 = "a".repeat(23), S24 = "b".repeat(24), S255 = "c".repeat(255), S256 = "d".repeat(256);
const ENCODE = [
  ["json-object", "simple", '{"name":"Alice","age":30,"active":true,"tags":null}', ""],
  ["json-object", "whitespace", ' { "a" : 1 ,\n "b" : [ 1 , 2 ] } ', ""],
  ["json-object", "empty", "{}", ""],
  ["json-object", "duplicate-keys", '{"a":1,"b":2,"a":3}', ""],
  ["json-object", "escapes", '{"q":"\\"x\\"\\\\ \\/ \\b\\f\\n\\r\\t \\u0041 \\u00e9","c":"\\u0001\\u001f\\u007f"}', ""],
  ["json-object", "map-24-entries", JSON.stringify(Object.fromEntries(Array.from({ length: 24 }, (_, i) => ["k" + i, i]))), ""],
  ["json-object", "credential-like", '{"@context":["https://www.w3.org/2018/credentials/v1"],"type":["VerifiableCredential"],"issuer":"did:web:example.com","credentialSubject":{"id":"did:jwk:abc","fullName":"Test User","dateOfBirth":"1990/01/01","gender":[{"language":"eng","value":"Male"}]},"proof":{"type":"Ed25519Signature2020","jws":"eyJhbGciOiJFZERTQSJ9..sig"}}', ""],
  ["json-array", "mixed", '[1,"two",3.5,false,null,{"x":[]}]', ""],
  ["json-array", "empty", "[]", ""],
  ["json-array", "len-23", JSON.stringify(Array.from({ length: 23 }, (_, i) => i)), ""],
  ["json-array", "len-24", JSON.stringify(Array.from({ length: 24 }, (_, i) => i)), ""],
  ["json-array", "nested", "[[[[1]]],[{}],[[]]]", ""],
  ["scalar-string", "int-123", "123", ""],
  ["scalar-string", "true", "true", ""],
  ["scalar-string", "false", "false", ""],
  ["scalar-string", "null", "null", ""],
  ["scalar-string", "zero", "0", ""],
  ["scalar-string", "json-string", '"hello"', ""],
  ["scalar-string", "json-empty-string", '""', ""],
  ["scalar-string", "quoted-digits", '"123"', ""],
  ["integer-like-keys", "order", '{"b":1,"10":2,"2":3,"a":4,"01":5,"4294967295":6,"4294967294":7,"-1":8,"1.0":9,"0":10}', ""],
  ["integer-like-keys", "nested-order", '{"z":{"3":"c","1":"a","x":"y","2":"b"},"1":[{"9":0,"8":0}]}', ""],
  ["nested-object", "deep", '{"a":{"b":{"c":{"d":{"e":[1,{"f":"g"}]}}}}}', ""],
  ["float", "single-1.5", "1.5", ""],
  ["float", "single-100000.5", "100000.5", ""],
  ["float", "single-max", "3.4028234663852886e38", ""],
  ["float", "double-0.1", "0.1", ""],
  ["float", "double-1e300", "1e300", ""],
  ["float", "double-min-subnormal", "5e-324", ""],
  ["float", "double-1e21", "1e21", ""],
  ["float", "double-1e-7", "1e-7", ""],
  ["float", "exponent-int", "1E2", ""],
  ["float", "zero-point-zero", "0.0", ""],
  ["float", "whole-2.0", "2.0", ""],
  ["float", "half-range-int-65504", "65504", ""],
  ["float", "overflow-1e400", "1e400", ""],
  ["float", "overflow-neg-1e400", "-1e400", ""],
  ["float", "in-object", '{"h":1.5,"s":0.1,"w":2.0,"n":-2.5,"big":1e300}', ""],
  ["negative-zero", "int", "-0", ""],
  ["negative-zero", "float", "-0.0", ""],
  ["negative-zero", "nested", '{"a":-0,"b":[-0.0]}', ""],
  ["integer-width", "boundaries", "[23,24,255,256,65535,65536,4294967295,4294967296,-1,-24,-25,-256,-257,-65536,-65537]", ""],
  ["integer-above-2^53", "max-safe", "9007199254740991", ""],
  ["integer-above-2^53", "neg-max-safe", "-9007199254740991", ""],
  ["integer-above-2^53", "2^53", "9007199254740992", ""],
  ["integer-above-2^53", "2^53+1", "9007199254740993", ""],
  ["integer-above-2^53", "2^53+2", "9007199254740994", ""],
  ["integer-above-2^53", "neg-2^53+1", "-9007199254740993", ""],
  ["integer-above-2^53", "30-digits", "123456789012345678901234567890", ""],
  ["integer-above-2^53", "2^64", "18446744073709551616", ""],
  ["unicode", "json-emoji", '{"name":"J\u00f6rg \ud83d\ude00","city":"\u0928\u092e\u0938\u094d\u0924\u0947","\u00e9":"\u4e2d\u6587"}', ""],
  ["unicode", "json-string-emoji", '"h\u00e9llo \ud83d\ude00"', ""],
  ["unicode", "plain-text-emoji", "h\u00e9llo \ud83d\ude00 \u0928\u092e\u0938\u094d\u0924\u0947", ""],
  ["unicode", "json-lone-surrogate-escape", '"a\\ud800b"', ""],
  ["unicode", "text-lone-surrogate", "abc\ud800def", ""],
  ["text-length", "23", JSON.stringify(S23), ""],
  ["text-length", "24", JSON.stringify(S24), ""],
  ["text-length", "255", JSON.stringify(S255), ""],
  ["text-length", "256", JSON.stringify(S256), ""],
  ["plain-text", "hello", "hello world", ""],
  ["plain-text", "nan-literal", "NaN", ""],
  ["plain-text", "infinity-literal", "Infinity", ""],
  ["plain-text", "json-with-nan", '{"a":NaN}', ""],
  ["plain-text", "invalid-json", '{"a":1', ""],
  ["plain-text", "single-quotes", "{'a':1}", ""],
  ["plain-text", "multiline", "line1\nline2\r\nline3\ttab", ""],
  ["plain-text", "long", "The quick brown fox jumps over the lazy dog. ".repeat(20), ""],
  ["text-parses-as-cbor", "space-is-minus-1", " ", ""],
  ["text-parses-as-cbor", "bang-is-minus-2", "!", ""],
  ["text-parses-as-cbor", "at-is-empty-bytes", "@", ""],
  ["text-parses-as-cbor", "aa-is-text-a", "aa", ""],
  ["text-parses-as-cbor", "nul-is-zero-falsy", "\u0000", ""],
  ["text-parses-as-cbor", "backtick-is-empty-text-falsy", "`", ""],
  ["text-parses-as-cbor", "x-insufficient", "x", ""],
  ["text-parses-as-cbor", "two-spaces-trailing", "  ", ""],
  ["empty-string", "empty", "", ""],
  ["text-with-bom", "bom-json", "\ufeff{\"a\":1}", ""],
  ["text-with-bom", "bom-text", "\ufeffhello", ""],
  ["header-prefix", "ncb", '{"a":1}', "NCB:"],
  ["header-prefix", "uri", "hello world", "mosip://"],
  ["header-prefix", "unicode-header", "[1,2,3]", "h\u00e9\ud83d\ude00:"],
  ["header-prefix", "header-only-empty-data", "", "HDR"],
];

for (const [category, name, input, header] of ENCODE) {
  const idBase = `${category}.${name}`;
  const qr = P.generateQRData(input, header);
  const parsed = attempt(() => JSON.parse(input));
  const v = {
    id: `generateQRData.${idBase}`,
    category,
    function: "generateQRData",
    input,
    header,
    expected: qr,
    compare: "exact",
    encode_parity: true,
  };
  if (parsed.ok && parsed.value !== null && typeof parsed.value !== "string" && !hasNegZeroOrNonFinite(parsed.value)) {
    // Python dict/list/int/float/bool input is serialised to JSON (AC-2) and must give the same string.
    // (A parsed JSON string is excluded: a Python str is input text, not a value.)
    if (P.generateQRData(JSON.stringify(parsed.value), header) !== qr) throw new Error("value_input mismatch " + idBase);
    v.value_input = true;
  }
  add(v);
  const d = attempt(() => P.decode(qr.slice(header.length)));
  const dv = { id: `decode.${idBase}`, category, function: "decode", input: qr, header, compare: "exact" };
  if (d.ok) dv.expected = d.value;
  else dv.expect_error = d.error;
  add(dv);
}

// ---------------------------------------------------------------- decode-only vectors from raw CBOR / raw bytes
// [category, name, hex]
const RAW = [
  ["falsy-cbor", "false", "f4"],
  ["falsy-cbor", "zero", "00"],
  ["falsy-cbor", "null", "f6"],
  ["falsy-cbor", "undefined", "f7"],
  ["falsy-cbor", "empty-text", "60"],
  ["falsy-cbor", "neg-zero-half", "f98000"],
  ["falsy-cbor", "neg-zero-double", "fb8000000000000000"],
  ["falsy-cbor", "nan-half", "f97e00"],
  ["falsy-cbor", "nan-single", "fa7fc00000"],
  ["falsy-cbor", "nan-double", "fb7ff8000000000000"],
  ["truthy-cbor", "true", "f5"],
  ["truthy-cbor", "empty-array", "80"],
  ["truthy-cbor", "empty-map", "a0"],
  ["truthy-cbor", "infinity", "f97c00"],
  ["truthy-cbor", "neg-infinity", "f9fc00"],
  ["float", "half-1.5", "f93e00"],
  ["float", "half-max-65504", "f97bff"],
  ["float", "half-subnormal", "f90001"],
  ["float", "single-1.5", "fa3fc00000"],
  ["float", "single-100000.5", "fa47c35040"],
  ["float", "double-0.1", "fb3fb999999999999a"],
  ["float", "double-whole-1", "fb3ff0000000000000"],
  ["float", "double-1e20", "fb4415af1d78b58c40"],
  ["float", "double-1e21", "fb444b1ae4d6e2ef50"],
  ["float", "double-1e-7", "fb3e7ad7f29abcaf48"],
  ["float", "double-0.000001", "fb3eb0c6f7a0b5ed8d"],
  ["float", "double-min-subnormal", "fb0000000000000001"],
  ["float", "double-max", "fb7fefffffffffffff"],
  ["float", "array-of-specials", "86f98000f97e00f97c00f9fc00fb8000000000000000fa7f800000"],
  ["negative-zero", "in-map", "a16161f98000"],
  ["integer-above-2^53", "uint64-max-safe", "1b001fffffffffffff"],
  ["integer-above-2^53", "uint64-2^53+1-bigint", "1b0020000000000001"],
  ["integer-above-2^53", "uint64-max-bigint", "1bffffffffffffffff"],
  ["integer-above-2^53", "nint64-bigint", "3bffffffffffffffff"],
  ["integer-above-2^53", "nested-bigint", "a161611b0020000000000001"],
  ["integer-width", "uint64-encoded-small", "1b0000000000000001"],
  ["integer-like-keys", "text-map-reordered", "a5616201623130026132036161046130 05".replace(/ /g, "")],
  ["integer-like-keys", "index-boundary", "a36a343239343936373239350161780264313233340a".replace(/ /g, "")],
  ["integer-like-keys", "duplicate-key-last-wins", "a3616101616202616103"],
  ["map-non-string-keys", "int-keys", "a2016178026179"],
  ["map-non-string-keys", "mixed-keys", "a46162010261626161030100"],
  ["map-non-string-keys", "nested-int-key-map", "a1616ba10102"],
  ["map-non-string-keys", "neg-int-key", "a12001"],
  ["map-non-string-keys", "bool-null-float-keys", "a3f501f602f93e0003"],
  ["map-non-string-keys", "array-key", "a18201020a"],
  ["map-non-string-keys", "bytes-key", "a1426869 01".replace(/ /g, "")],
  ["map-non-string-keys", "int-and-text-same-string", "a201616161316162"],
  ["byte-string", "top-level", "43010203"],
  ["byte-string", "empty", "40"],
  ["byte-string", "indefinite", "5f41014102ff"],
  ["byte-string", "in-map", "a1616443deadbe"],
  ["tagged", "tag0-date-string", "c074323031332d30332d32315432303a30343a30305a"],
  ["tagged", "tag1-epoch-int", "c11a514b67b0"],
  ["tagged", "tag1-epoch-float", "c1fb41d452d9ec200000"],
  ["tagged", "tag1-epoch-out-of-range", "c1fb7ff0000000000000"],
  ["tagged", "tag2-bignum", "c249010000000000000000"],
  ["tagged", "tag3-neg-bignum", "c349010000000000000000"],
  ["tagged", "tag4-decimal-fraction", "c482212a"],
  ["tagged", "tag5-bigfloat", "c5822003"],
  ["tagged", "tag21-base64url-expected", "d81543010203"],
  ["tagged", "tag24-embedded-cbor", "d81843a10102"],
  ["tagged", "tag30-unassigned", "d81e820103"],
  ["tagged", "tag33-base64url-text", "d8216459574531"],
  ["tagged", "tag35-regexp", "d82343666f6f"],
  ["tagged", "tag37-uuid-text", "d8256b68656c6c6f20776f726c64"],
  ["tagged", "tag64-uint8-typed-array", "d84043010203"],
  ["tagged", "tag65-uint16be-typed-array", "d8414400010002"],
  ["tagged", "tag85-float32le-typed-array", "d855440000c03f"],
  ["tagged", "tag258-set", "d9010283010203"],
  ["tagged", "tag1000-unknown-in-map", "a16174d903e8a10101"],
  ["tagged", "tag55799-self-describe", "d9d9f7a16161 01".replace(/ /g, "")],
  ["simple-value", "simple-16", "f0"],
  ["simple-value", "simple-255", "f8ff"],
  ["simple-value", "undefined-in-array", "82f701"],
  ["simple-value", "undefined-in-map", "a26161f7616202"],
  ["indefinite", "text", "7f61616162ff"],
  ["indefinite", "array", "9f0102ff"],
  ["indefinite", "map", "bf616101ff"],
  ["indefinite", "empty-map", "bfff"],
  ["trailing-bytes", "int-then-int", "0102"],
  ["trailing-bytes", "map-then-byte", "a1616101 00".replace(/ /g, "")],
  ["unicode", "text-emoji", "6af09f9880c3a9e4b8ad20"],
  ["unicode", "control-and-separators", "6d0001081f227f5ce280a8e280a9"],
  ["invalid-utf8", "in-cbor-text-string", "6261ff"],
  ["text-with-bom", "raw-bom-text", "efbbbf68656c6c6f"],
  ["text-with-bom", "raw-double-bom", "efbbbfefbbbf6869"],
  ["invalid-utf8", "ff-fe", "fffe41c328"],
  ["invalid-utf8", "overlong", "ffc080e080af41"],
  ["invalid-utf8", "surrogate-encoded", "ffeda080eda0bd41"],
  ["invalid-utf8", "truncated-multibyte-mid", "ffe28241f09f98"],
  ["invalid-utf8", "out-of-range", "fff4908080f5f8"],
  ["invalid-utf8", "lone-continuation", "ff8080bf41"],
];
for (const [category, name, h] of RAW) {
  const input = b45OfBytes(Buffer.from(h, "hex"));
  const d = attempt(() => P.decode(input));
  const v = { id: `decode.raw.${category}.${name}`, category, function: "decode", input, header: "", source_cbor_hex: h, compare: "exact" };
  if (d.ok) v.expected = d.value;
  else v.expect_error = d.error;
  add(v);
  // the same CBOR through toJson (AC-8) where JSON.stringify(toJson(x)) is defined
  const t = attempt(() => P.toJson(b64url(h)));
  if (t.ok && t.value !== undefined) {
    const tv = { id: `toJson.raw.${category}.${name}`, category, function: "toJson", input: b64url(h), source_cbor_hex: h };
    tv.expected = stringifyBig(t.value);
    if (needsValueCompare(t.value)) {
      tv.compare = "value";
      tv.expected_value = typed(t.value);
    } else tv.compare = "exact";
    add(tv);
  }
}

// ---------------------------------------------------------------- toJson-specific
const TOJSON = [
  ["base64url", "padding-2", "oWFhAQ=="],
  ["base64url", "padding-1", "oWFhAQ="],
  ["base64url", "padding-3", "oWFhAQ==="],
  ["base64url", "url-alphabet", b64url("a1617e43fbffbf")],
  ["base64url", "map-int-keys", b64url("a3016178026179f5f6")],
  ["base64url", "claim169-like", b64url(M([[1, "1234567890"], [4, "Test"], [9, 1], [62, M([[0, Buffer.from([0xff, 0xd8, 0xff])], [1, 0], [2, 0]])]]))],
  ["base64url", "string", b64url("63616263")],
  ["base64url", "null", b64url("f6")],
  ["base64url", "false", b64url("f4")],
  ["base64url", "neg-zero-whole", b64url("82f98000fb4000000000000000")],
];
for (const [category, name, input] of TOJSON) {
  const t = attempt(() => P.toJson(input));
  const v = { id: `toJson.${category}.${name}`, category, function: "toJson", input };
  if (!t.ok) {
    v.expect_error = t.error;
    v.compare = "exact";
  } else {
    v.expected = stringifyBig(t.value);
    v.compare = needsValueCompare(t.value) ? "value" : "exact";
    if (v.compare === "value") v.expected_value = typed(t.value);
  }
  add(v);
}
// errors in both JS and Python
for (const [name, input] of [["empty", ""], ["trailing-bytes", b64url("0102")], ["truncated-map", b64url("a2616101")]]) {
  const t = attempt(() => P.toJson(input));
  if (t.ok) throw new Error("expected toJson error " + name);
  add({ id: `toJson.error.${name}`, category: "malformed", function: "toJson", input, expect_error: t.error, python_error: "DecodingError", compare: "exact" });
}

// ---------------------------------------------------------------- getMappedData
const CLAIM = {
  ID: "1234567890", Version: "1.0", Language: "eng", "Full Name": "Test User", "Date of Birth": "19900101",
  Gender: "male", Address: "1 Main St", "Email ID": "t@example.com", "Phone Number": "+10000000000",
  Nationality: "IN", "Marital Status": "MARRIED", "Binary Image Format": "jpeg", "Best Quality Fingers": [1, 2, 3],
  Face: { Data: "AAEC", "Data format": "image", "Data sub format": "png", "Data issuer": "VendorX" },
  "Right Thumb": [{ Data: "q83v", "Data format": "Template", "Data sub format": "Fingerprint Template ISO 19794-2" }],
  Voice: { Data: "UklG", "Data format": "sound", "Data sub format": "wav" },
  unknownField: "kept", "zz": null,
};
const MAPPED = [
  ["claim169-mapped", "full", CLAIM],
  ["claim169-mapped", "case-insensitive-keys-and-values", { "full name": "A", GENDER: "FEMALE", "marital STATUS": "divorced", face: { "DATA FORMAT": "IMAGE", "data sub FORMAT": "JpEg" } }],
  ["claim169-mapped", "unmapped-value-kept", { Gender: "unknown", "Marital Status": 2, "Binary Image Format": true }],
  ["claim169-mapped", "nested-dict-keys", { Guardian: { ID: "g1", "Full Name": "G", inner: { Gender: "Others" } } }],
  ["claim169-mapped", "list-of-dicts-nested", { list: [{ ID: 1 }, [{ Gender: "Male" }], "s", 5, null] }],
  ["claim169-mapped", "unmapped-key-order", { zz: 1, ID: "x", "5x": 2, "100": 3, Gender: "Male", abc: 4, ABC: 5 }],
  ["claim169-mapped", "data-maps-to-zero", { Data: "d", "Data format": "Bio Hash" }],
  ["claim169-mapped", "empty-object", {}],
  ["claim169-mapped", "value-mapper-not-for-unmapped-field", { gender2: "male", Language: "male" }],
  ["claim169-mapped", "unicode", { "Full Name": "J\u00f6rg \ud83d\ude00", "\u00e9": "x" }],
  ["claim169-mapped", "numbers", { ID: 12, Version: 2.5, "Phone Number": -3, big: 9007199254740991 }],
];
for (const [category, name, obj] of MAPPED) {
  const input_json = JSON.stringify(obj);
  for (const cborEnable of [false, true]) {
    const r = P.getMappedData(JSON.parse(input_json), undefined, undefined, cborEnable);
    add({
      id: `getMappedData.${category}.${name}.cbor-${cborEnable ? "on" : "off"}`,
      category, function: "getMappedData", input_json, args: { cbor_enable: cborEnable },
      expected: cborEnable ? r : JSON.stringify(r), compare: "exact", encode_parity: cborEnable,
    });
  }
}
// list input
{
  const input_json = JSON.stringify([{ ID: "a", Gender: "Male" }, { "Full Name": "b" }, []]);
  for (const cborEnable of [false, true]) {
    const r = P.getMappedData(JSON.parse(input_json), undefined, undefined, cborEnable);
    add({ id: `getMappedData.list-input.three-items.cbor-${cborEnable ? "on" : "off"}`, category: "list-input", function: "getMappedData", input_json, args: { cbor_enable: cborEnable }, expected: JSON.stringify(r), compare: "exact", encode_parity: cborEnable });
  }
}
// custom mappers
{
  const km = { name: "n", Colour: 7 };
  const vm = { colour: { Red: "r", GREEN: 2 } };
  const input_json = JSON.stringify({ NAME: "x", colour: "red", other: "Green", Colour2: "red" });
  for (const cborEnable of [false, true]) {
    const r = P.getMappedData(JSON.parse(input_json), km, vm, cborEnable);
    add({ id: `getMappedData.custom-mappers.basic.cbor-${cborEnable ? "on" : "off"}`, category: "custom-mappers", function: "getMappedData", input_json, args: { cbor_enable: cborEnable, key_mapper: km, value_mapper: vm }, expected: cborEnable ? r : JSON.stringify(r), compare: "exact", encode_parity: cborEnable });
  }
}
// scalars (typed input values) - AC-6 scalar rule and the cbor-web encoder rules (test_cbor)
const SCALARS = [
  ["string", "abc"], ["string-empty", ""], ["string-23", S23], ["string-24", S24], ["string-256", S256],
  ["string-emoji", "\ud83d\ude00"], ["string-lone-surrogate", "a\ud800b"],
  ["int-0", 0], ["int-23", 23], ["int-24", 24], ["int-255", 255], ["int-256", 256], ["int-65535", 65535], ["int-65536", 65536],
  ["int-2^32-1", 4294967295], ["int-2^32", 4294967296], ["int-max-safe", 9007199254740991], ["int-neg-1", -1], ["int-neg-24", -24],
  ["int-neg-25", -25], ["int-neg-max-safe", -9007199254740991], ["float-2^53", 9007199254740992], ["float-neg-2^53", -9007199254740992],
  ["float-2^53+2", 9007199254740994], ["float-2^64", 18446744073709551616], ["float-1.5", 1.5], ["float-0.1", 0.1], ["float-neg-2.5", -2.5],
  ["float-100000.5", 100000.5], ["float-single-max", 3.4028234663852886e38], ["float-1e300", 1e300], ["float-5e-324", 5e-324],
  ["float-whole-2.0", 2.0], ["float-1e21", 1e21], ["float-neg-zero", -0], ["float-nan", NaN], ["float-inf", Infinity], ["float-neg-inf", -Infinity],
  ["bool-true", true], ["bool-false", false],
];
for (const [name, value] of SCALARS) {
  for (const cborEnable of [false, true]) {
    const r = P.getMappedData(value, undefined, undefined, cborEnable);
    const v = { id: `getMappedData.scalar.${name}.cbor-${cborEnable ? "on" : "off"}`, category: "scalar", function: "getMappedData", input_value: Object.is(value, -0) ? { $float: "-0" } : typed(value), args: { cbor_enable: cborEnable }, compare: "exact", encode_parity: cborEnable };
    if (cborEnable) v.expected = r;
    else {
      // cbor off: the scalar is returned unchanged (identity); expected_value holds it.
      v.expected_value = v.input_value;
      v.compare = "value";
    }
    add(v);
  }
}
// collisions (AC-13): JS overwrites; Python strict=True raises MappingError, strict=False == JS
const COLLIDE = [
  ["gender-case", { Gender: "Male", gender: "Female" }, ["Gender", "gender"], "9"],
  ["mapped-1-and-literal-1", { ID: "x", "1": "y" }, ["ID", "1"], "1"],
  ["literal-1-then-mapped", { "1": "y", id: "x" }, ["1", "id"], "1"],
  ["two-keys-to-1", { ID: "x", "Data format": "Image" }, ["ID", "Data format"], "1"],
  ["nested-level", { Face: { Data: "a", data: "b" } }, ["Data", "data"], "0"],
];
for (const [name, obj, keys, mappedKey] of COLLIDE) {
  const input_json = JSON.stringify(obj);
  for (const cborEnable of [false, true]) {
    const r = P.getMappedData(JSON.parse(input_json), undefined, undefined, cborEnable);
    add({
      id: `getMappedData.mapping-collision.${name}.cbor-${cborEnable ? "on" : "off"}`, category: "mapping-collision", function: "getMappedData",
      input_json, args: { cbor_enable: cborEnable }, expected: cborEnable ? r : JSON.stringify(r), compare: "exact",
      deviation: "AC-13: Python raises MappingError by default; strict=False must equal this JS result",
      python_error: "MappingError", collision_keys: keys, collision_mapped_key: mappedKey, encode_parity: false,
    });
  }
}
// unmapped keys differing only by case stay separate (no collision)
{
  const input_json = JSON.stringify({ abc: 1, ABC: 2, Abc: 3 });
  add({ id: "getMappedData.no-collision.unmapped-case.cbor-off", category: "mapping-collision", function: "getMappedData", input_json, args: { cbor_enable: false }, expected: JSON.stringify(P.getMappedData(JSON.parse(input_json))), compare: "exact", encode_parity: false });
}

// ---------------------------------------------------------------- decodeMappedData
const DMD_HEX = [
  ["claim169-roundtrip", "full", P.getMappedData(CLAIM, undefined, undefined, true)],
  ["claim169-roundtrip", "case-insensitive", P.getMappedData(MAPPED[1][2], undefined, undefined, true)],
  ["claim169-int-keys", "kotlin-style", M([[1, "1234567890"], [4, "Test User"], [8, "19900101"], [9, 1], [10, "Address 1"], [14, 2], [17, 1], [18, [1, 2, 3]]])],
  ["claim169-int-keys", "biometric-face", M([[1, "x"], [62, M([[0, Buffer.from([1, 2, 3])], [1, 0], [2, 1], [3, "VendorX"]])]])],
  ["claim169-int-keys", "biometric-format-only", M([[62, M([[1, 3]])]])],
  ["claim169-int-keys", "biometric-bio-hash-with-subformat", M([[62, M([[1, 3], [2, 0]])]])],
  ["claim169-int-keys", "biometric-unknown-subformat", M([[62, M([[0, Buffer.alloc(0)], [1, 1], [2, 9]])]])],
  ["claim169-int-keys", "biometric-string-codes", M([[62, M([[1, "1"], [2, "1x"]])]])],
  ["claim169-int-keys", "biometric-nan-string-code", M([[62, M([[1, "x"], [2, 0]])]])],
  ["claim169-int-keys", "biometric-array", M([[50, [M([[0, Buffer.alloc(0)], [1, 1], [2, 2]])]]])],
  ["claim169-int-keys", "depth1-key-in-non-biometric", M([[10, M([[1, "a"], [2, "b"]])]])],
  ["claim169-int-keys", "gender-float-whole", "a109fb3ff0000000000000"],
  ["claim169-int-keys", "gender-string-2", "a1096132"],
  ["claim169-int-keys", "gender-array-coercion", "a1098101"],
  ["claim169-int-keys", "gender-unmapped-7", "a10907"],
  ["claim169-int-keys", "mixed-int-text-keys", M([["b", 1], [9, 2], ["1", "x"], [10, "a"]])],
  ["claim169-int-keys", "unknown-int-keys", M([[99, 1], [256, 2]])],
  ["claim169-int-keys", "int-and-text-key-collide", M([[1, "a"], ["1", "b"]])],
  ["claim169-int-keys", "null-and-bool-values", "a301f609f50ef4"],
  ["top-level-array", "ints", "83010203"],
  ["top-level-array", "maps", hex(cbor.encode([new Map([[1, "a"]]), new Map([[9, "1"]])]))],
  ["top-level-scalar", "text-spread", "63616263"],
  ["top-level-scalar", "int", "182a"],
  ["top-level-scalar", "null", "f6"],
  ["top-level-scalar", "empty-map", "a0"],
  ["byte-string", "value-bytes", "a1104401020304"],
  ["tagged", "date-value", "a108c074323031332d30332d32315432303a30343a30305a"],
  ["tagged", "unknown-tag-value", "a101d81e820103"],
  ["float", "values", M([[1, 1.5], [2, 0.1], [3, 1e21], [4, -0]])],
  ["map-non-string-keys", "bool-key", M([[true, 1], ["x", null]])],
  ["uppercase-hex", "upper", "A2016178096131"],
];
const DMD_JSON = [
  ["json-input", "object", '{"1":"x","9":1,"62":{"1":0,"2":1}}'],
  ["json-input", "array", '[{"1":"a"},{"4":"b"}]'],
  ["json-input", "nested-whitespace", ' { "10" : { "1" : "y" } } '],
];
for (const [category, name, rawInput] of DMD_HEX.concat(DMD_JSON)) {
  const input = cborHex(rawInput);
  const r = attempt(() => P.decodeMappedData(input));
  const v = { id: `decodeMappedData.${category}.${name}`, category, function: "decodeMappedData", input, compare: "exact" };
  if (r.ok) v.expected = r.value;
  else v.expect_error = r.error;
  add(v);
}
// custom key mapper with an identity value mapper (args.value_mapper == "identity")
{
  const km = [{ "1": "one", "2": "two" }, { "1": "inner-one" }, null];
  const input = "a201a101f502820304";
  const r = P.decodeMappedData(input, km, (d) => d);
  add({ id: "decodeMappedData.custom-mappers.identity-value", category: "custom-mappers", function: "decodeMappedData", input, args: { key_mapper: km, value_mapper: "identity" }, expected: r, compare: "exact" });
  const r2 = P.decodeMappedData("a201a101f502820304", [], (d) => d);
  add({ id: "decodeMappedData.custom-mappers.empty-key-mapper", category: "custom-mappers", function: "decodeMappedData", input, args: { key_mapper: [], value_mapper: "identity" }, expected: r2, compare: "exact" });
}
// errors in JS and Python
for (const [name, input] of [["odd-hex-not-json", "abc"], ["empty", ""], ["valid-hex-bad-cbor", "a1"], ["odd-hex-bad-cbor", "a1b"]]) {
  const r = attempt(() => P.decodeMappedData(input));
  if (r.ok) throw new Error("expected decodeMappedData error " + name);
  add({ id: `decodeMappedData.error.${name}`, category: "malformed", function: "decodeMappedData", input, expect_error: r.error, python_error: "DecodingError", compare: "exact" });
}

// ---------------------------------------------------------------- replaceValuesForClaim169 (public helper)
const { replaceValuesForClaim169 } = require(path.join(JS_DIR, "src", "utils", "cborUtils.js"));
const RV = [
  ["root-values", { Gender: 2, "Marital Status": "3", "Binary Image Format": 4, "Data format": 1, other: 1 }],
  ["root-unmapped", { Gender: 9, "Marital Status": "x" }],
  ["biometric", { Face: { "Data format": 0, "Data sub format": 4, Data: "x" }, "Left Iris": { "Data format": "2", "Data sub format": "1" } }],
  ["biometric-missing-subformat", { Face: { "Data format": 0 } }],
  ["biometric-not-object", { Face: "abc", Voice: [1, 2] }],
  ["empty", {}],
];
for (const [name, obj] of RV) {
  const input_json = JSON.stringify(obj);
  add({ id: `replaceValuesForClaim169.${name}`, category: "claim169-value-mapper", function: "replaceValuesForClaim169", input_json, expected: JSON.stringify(replaceValuesForClaim169(JSON.parse(input_json))), compare: "exact" });
}

// ---------------------------------------------------------------- deviation vectors (JS result recorded; Python raises)
{
  const dev = (id, fn, input, extra, note, pyErr) => {
    const r = attempt(fn);
    const v = Object.assign({ id, category: "deviation", function: id.split(".")[0], input }, extra, { compare: "exact", deviation: note, python_error: pyErr });
    if (r.ok) v.js_result = r.value === undefined ? null : r.value;
    else v.expect_error = r.error;
    add(v);
  };
  dev("generateQRData.deviation.null-input", () => P.generateQRData(null), null, { header: "" }, "AC-2/R3-2: JS encodes CBOR null; Python generate_qr_data(None) raises EncodingError", "EncodingError");
  dev("decode.deviation.base45-triplet-above-65535", () => P.decode("GGW"), "GGW", { header: "" }, "AC-14/R2-2 (out-of-range Base45 group), AC-11: base45-web accepts a triplet > 65535 (pako then fails); Python raises DecodingError", "DecodingError");
  dev("decode.deviation.base45-pair-above-255", () => P.decode(":Z"), ":Z", { header: "" }, "AC-14/R2-2 (out-of-range Base45 group): base45-web keeps 1619 and Uint8Array truncates it, JS returns ''; Python raises DecodingError", "DecodingError");
  const z = pako.deflate(cbor.encode({ a: "hello world hello world" }), { level: 9 });
  const trunc = b45.encode(z.slice(0, z.length - 3)).toString();
  dev("decode.deviation.truncated-zlib", () => P.decode(trunc), trunc, { header: "" }, "AC-14/R2-2 (truncated zlib stream), AC-11: pako.inflate returns undefined on a truncated stream and JS decode returns ''; Python raises DecodingError", "DecodingError");
  const trail = b45.encode(Uint8Array.from([...z, 1, 2, 3])).toString();
  dev("decode.deviation.zlib-trailing-garbage", () => P.decode(trail), trail, { header: "" }, "AC-11 (corrupt zlib stream): pako throws on bytes after the zlib stream; Python raises DecodingError too", "DecodingError");
  dev("decode.deviation.empty-input", () => P.decode(""), "", { header: "" }, "AC-14/R2-2 (empty zlib stream): JS decode('') returns '' (pako returns undefined for an empty stream); Python raises DecodingError", "DecodingError");
  dev("toJson.deviation.invalid-char-dropped", () => P.toJson("oW!FhAQ"), "oW!FhAQ", {}, "AC-8: Node drops invalid base64url characters; Python raises DecodingError", "DecodingError");
  dev("toJson.deviation.space-dropped", () => P.toJson("oWFh AQ"), "oWFh AQ", {}, "AC-8: Node drops whitespace; Python raises DecodingError", "DecodingError");
  dev("toJson.deviation.standard-base64-plus", () => P.toJson("oW+hAQ"), "oW+hAQ", {}, "AC-8: '+' is outside the base64url alphabet; Python raises DecodingError", "DecodingError");
  dev("decodeMappedData.deviation.non-hex-non-json", () => P.decodeMappedData("zz"), "zz", {}, "AC-7: JS hex-parses any string (parseInt('zz',16) -> NaN -> byte 0) and returns garbage; Python treats non-hex as JSON and raises DecodingError", "DecodingError");
  dev("decode.deviation.invalid-base45-char", () => P.decode("AB#"), "AB#", { header: "" }, "AC-11: both raise; Python raises DecodingError", "DecodingError");
  dev("decode.deviation.invalid-base45-length", () => P.decode("AAAA"), "AAAA", { header: "" }, "AC-11: both raise; Python raises DecodingError", "DecodingError");
  dev("decode.deviation.corrupt-zlib", () => P.decode(b45.encode(Uint8Array.from([1, 2, 3])).toString()), b45.encode(Uint8Array.from([1, 2, 3])).toString(), { header: "" }, "AC-11: both raise; Python raises DecodingError", "DecodingError");
}

// ---------------------------------------------------------------- output
vectors.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
const counts = {};
for (const v of vectors) {
  const k = `${v.function}/${v.category}`;
  counts[k] = (counts[k] || 0) + 1;
}
const sortedCounts = Object.fromEntries(Object.keys(counts).sort().map((k) => [k, counts[k]]));
const out = {
  schema_version: 1,
  generator: "python/tests/golden/generate_vectors.js",
  upstream_commit: upstreamCommit(),
  js_src_sha256: srcDigest(),
  package: { name: require(path.join(JS_DIR, "package.json")).name, version: require(path.join(JS_DIR, "package.json")).version },
  node_version: process.version,
  dependencies: { "base45-web": depVersion("base45-web"), "cbor-web": depVersion("cbor-web"), jszip: depVersion("jszip"), pako: depVersion("pako"), qrcode: depVersion("qrcode") },
  constants: {
    CLAIM_169_KEY_MAPPER: C.CLAIM_169_KEY_MAPPER,
    CLAIM_169_VALUE_MAPPER: C.CLAIM_169_VALUE_MAPPER,
    CLAIM_169_REVERSE_KEY_MAPPER: C.CLAIM_169_REVERSE_KEY_MAPPER,
    DEFAULT_ZLIB_COMPRESSION_LEVEL: C.DEFAULT_ZLIB_COMPRESSION_LEVEL,
    DEFAULT_ECC_LEVEL: C.DEFAULT_ECC_LEVEL,
    DEFAULT_QR_BORDER: C.DEFAULT_QR_BORDER,
    DEFAULT_QR_SCALE: C.DEFAULT_QR_SCALE,
    DEFAULT_ZIP_FILE_NAME: C.DEFAULT_ZIP_FILE_NAME,
  },
  counts: sortedCounts,
  vector_count: vectors.length,
  vectors,
};
fs.writeFileSync(OUT, JSON.stringify(out, null, 2) + "\n", { encoding: "utf8" });
process.stdout.write(`wrote ${vectors.length} vectors to ${path.basename(OUT)}\n`);
for (const [k, n] of Object.entries(sortedCounts)) process.stdout.write(`  ${k}: ${n}\n`);
