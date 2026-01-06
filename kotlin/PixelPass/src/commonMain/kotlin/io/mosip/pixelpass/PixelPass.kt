package io.mosip.pixelpass

import co.nstant.`in`.cbor.CborDecoder
import co.nstant.`in`.cbor.CborEncoder
import co.nstant.`in`.cbor.model.DataItem
import io.mosip.pixelpass.cbor.Utils
import io.mosip.pixelpass.common.decodeFromBase64UrlFormat
import io.mosip.pixelpass.exception.UnknownBinaryFileTypeException
import io.mosip.pixelpass.shared.CLAIM_169_KEY_MAPPER
import io.mosip.pixelpass.shared.CLAIM_169_REVERSE_KEY_MAPPER
import io.mosip.pixelpass.shared.CLAIM_169_VALUE_MAPPER
import io.mosip.pixelpass.shared.DEFAULT_ZIP_FILE_NAME
import io.mosip.pixelpass.shared.ZIP_HEADER
import io.mosip.pixelpass.shared.decodeHex
import io.mosip.pixelpass.types.ECC
import io.mosip.pixelpass.utils.toMapWithKeyAndValueMapper
import io.mosip.pixelpass.zlib.ZLib
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.logging.Logger
import nl.minvws.encoding.Base45
import org.json.JSONArray
import org.json.JSONObject
import org.zeroturnaround.zip.ZipUtil

class PixelPass {
  private val logger = Logger.getLogger(PixelPass::class.java.name)

  fun toJson(base64UrlEncodedCborEncodedString: String): Any {
    val decodedData: ByteArray = decodeFromBase64UrlFormat(base64UrlEncodedCborEncodedString)
    val cbor =
      CborDecoder(ByteArrayInputStream(decodedData)).decode().firstOrNull()
        ?: throw IllegalArgumentException("Failed to decode CBOR data")
    return Utils().toJson(cbor)
  }

  fun generateQRCode(data: String, ecc: ECC = ECC.L, header: String = ""): String {
    val dataWithHeader = generateQRData(data, header)
    val qrcodeImage = convertQRDataIntoBase64(dataWithHeader, ecc)
    return qrcodeImage
  }

  fun decode(data: String): String {
    val decodedBase45Data = Base45.getDecoder().decode(data)
    val decompressedData = ZLib().decode(decodedBase45Data)
    return try {
      val cborDecodedData = CborDecoder(ByteArrayInputStream(decompressedData)).decode()[0]

      val json = Utils().toJson(cborDecodedData)
      if (json.toString().startsWith('[') && json.toString().endsWith(']'))
        (json as JSONArray).toString().replace("\\", "")
      else (json as JSONObject).toString().replace("\\", "")
    } catch (_: Exception) {
      String(decompressedData)
    }
  }

  fun decodeBinary(data: ByteArray): String {
    if (String(data).startsWith(ZIP_HEADER)) {
      var tempFile: File? = null
      try {
        tempFile = File.createTempFile("temp", ".zip")
        tempFile.writeBytes(data)
        if (ZipUtil.containsEntry(tempFile, DEFAULT_ZIP_FILE_NAME))
          return String(ZipUtil.unpackEntry(tempFile, DEFAULT_ZIP_FILE_NAME))
      } catch (e: Exception) {
        throw e
      } finally {
        tempFile?.delete()
      }
    }
    throw UnknownBinaryFileTypeException()
  }

  fun generateQRData(data: String, header: String = ""): String {
    val parsedData: Any?
    var compressedData = byteArrayOf()
    val b45EncodedData: String
    try {
      parsedData =
        if (data.startsWith('[') && data.endsWith(']')) {
          JSONArray(data)
        } else {
          JSONObject(data)
        }
      val toDataItem = Utils().toDataItem(parsedData)

      val cborByteArrayOutputStream = ByteArrayOutputStream()
      CborEncoder(cborByteArrayOutputStream).nonCanonical().encode(toDataItem)
      compressedData = ZLib().encode(cborByteArrayOutputStream.toByteArray())
    } catch (e: Exception) {
      logger.severe(e.toString())
      compressedData = ZLib().encode(data.toByteArray())
    } finally {
      b45EncodedData = String(Base45.getEncoder().encode(compressedData))
    }

    return (header + b45EncodedData)
  }

  @OptIn(ExperimentalStdlibApi::class)
  fun getMappedData(
    jsonData: JSONObject,
    mapper: Map<String, String>,
    cborEnable: Boolean = false,
  ): String {
    val mappedJson = JSONObject()
    val iterator = jsonData.keys().iterator()
    while (iterator.hasNext()) {
      val next = iterator.next()
      val key = mapper[next] ?: next
      val value = jsonData.get(next.toString())
      mappedJson.put(key.toString(), value)
    }

    val payload = Utils().toDataItem(mappedJson)

    if (cborEnable) {
      val cborByteArrayOutputStream = ByteArrayOutputStream()
      CborEncoder(cborByteArrayOutputStream).encode(payload)
      return cborByteArrayOutputStream.toByteArray().toHexString()
    }
    return payload.toString()
  }

  @OptIn(ExperimentalStdlibApi::class)
  fun getMappedData(
    jsonData: JSONObject,
    keyMapper: Map<String, Int> = CLAIM_169_KEY_MAPPER,
    valueMapper: Map<String, Map<Any, Int>> = CLAIM_169_VALUE_MAPPER,
    cborEnable: Boolean = false,
  ): Any {
    val mappedJson = jsonData.toMapWithKeyAndValueMapper(keyMapper, valueMapper)

    if (cborEnable) {
      val payload = Utils().toDataItem(mappedJson)
      val cborByteArrayOutputStream = ByteArrayOutputStream()
      CborEncoder(cborByteArrayOutputStream).encode(payload)
      return cborByteArrayOutputStream.toByteArray().toHexString()
    }
    return mappedJson
  }

  fun getMappedData(
    jsonData: JSONArray,
    keyMapper: Map<String, Int> = CLAIM_169_KEY_MAPPER,
    valueMapper: Map<String, Map<Any, Int>> = CLAIM_169_VALUE_MAPPER,
    cborEnable: Boolean = false,
  ): JSONArray {
    val mappedJsonArray = JSONArray()
    (0 until jsonData.length()).forEach { i ->
      when (val item = jsonData.get(i)) {
        is JSONObject -> {
          val result = getMappedData(item, keyMapper, valueMapper, cborEnable)
          mappedJsonArray.put(result)
        }
        else ->
          throw IllegalArgumentException(
            "Invalid input: Expected JSONObject at index $i, but found ${item::class.simpleName}"
          )
      }
    }
    return mappedJsonArray
  }

  fun decodeMappedData(data: String, mapper: Map<String, String>): String {
    var jsonData: JSONObject =
      try {
        val cborDecodedData = CborDecoder(ByteArrayInputStream(data.decodeHex())).decode()[0]
        (Utils().toJson(cborDecodedData) as JSONObject)
      } catch (e: Exception) {
        logger.fine("Failed to decode as CBOR, treating as plain JSON: ${e.message}")
        JSONObject(data)
      }

    val payload = JSONObject()
    val iterator = jsonData.keys().iterator()
    while (iterator.hasNext()) {
      val next = iterator.next()
      val key = mapper[next] ?: next
      val value = jsonData.get(next.toString())
      payload.put(key.toString(), value)
    }
    return payload.toString()
  }

  fun decodeMappedData(
    data: String,
    keyMapper: Array<Map<String, String>> = CLAIM_169_REVERSE_KEY_MAPPER,
    valueMapperFunction: (JSONObject) -> JSONObject = Utils()::replaceValuesForClaim169,
  ): String {

    val initialJson: JSONObject =
      try {
        val decoded = CborDecoder(ByteArrayInputStream(data.decodeHex())).decode()[0]
        Utils().toJson(decoded) as JSONObject
      } catch (e: Exception) {
        logger.fine("Failed to decode as CBOR, treating as plain JSON: ${e.message}")
        JSONObject(data)
      }

    val finalJson: JSONObject =
      keyMapper.foldIndexed(initialJson) { index, acc: JSONObject, mapper ->
        Utils().replaceKeysAtDepth(acc, mapper, index)
      }

    return valueMapperFunction(finalJson).toString()
  }

  fun decodeMappedData(
    data: Array<String>,
    keyMapper: Array<Map<String, String>> = CLAIM_169_REVERSE_KEY_MAPPER,
    valueMapperFunction: (JSONObject) -> JSONObject = Utils()::replaceValuesForClaim169,
  ): Array<String> {
    val decodedJsonArray = mutableListOf<String>()
    data.forEach { item ->
      decodedJsonArray.add(decodeMappedData(item, keyMapper, valueMapperFunction))
    }
    return decodedJsonArray.toTypedArray()
  }
}
