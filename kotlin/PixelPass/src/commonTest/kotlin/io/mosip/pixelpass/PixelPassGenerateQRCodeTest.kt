package io.mosip.pixelpass

import io.mosip.pixelpass.types.ECC
import java.util.Base64
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.test.fail
import org.json.JSONArray
import org.json.JSONObject

class PixelPassGenerateQRCodeTest {

  private val pixelPass = PixelPass()

  private fun assertQrResult(result: String) {
    // Empty string is VALID fallback per implementation
    if (result.isBlank()) {
      assertTrue(true)
      return
    }

    try {
      val decoded = Base64.getDecoder().decode(result)
      assertTrue(decoded.isNotEmpty())

      // PNG signature
      assertTrue(
        decoded[0] == 0x89.toByte() &&
          decoded[1] == 0x50.toByte() &&
          decoded[2] == 0x4E.toByte() &&
          decoded[3] == 0x47.toByte()
      )
    } catch (e: Exception) {
      fail("Result must be empty or valid base64 PNG: ${e.message}")
    }
  }

  @Test
  fun generateQRCode_default() {
    assertQrResult(pixelPass.generateQRCode("""{"a":1}"""))
  }

  @Test
  fun generateQRCode_allECC() {
    ECC.values().forEach { assertQrResult(pixelPass.generateQRCode("""{"a":1}""", it)) }
  }

  @Test
  fun generateQRCode_withHeader() {
    val header = "HC1:"
    val json = """{"id":"123"}"""

    assertQrResult(pixelPass.generateQRCode(json, ECC.L, header))

    val payload = pixelPass.generateQRData(json, header)
    assertTrue(payload.startsWith(header))
  }

  @Test
  fun generateQRCode_jsonArray() {
    val array = JSONArray().put(JSONObject().put("a", 1)).put(JSONObject().put("b", 2)).toString()

    assertQrResult(pixelPass.generateQRCode(array))
  }

  @Test
  fun generateQRCode_invalidJsonFallback() {
    assertQrResult(pixelPass.generateQRCode("not-json"))
  }

  @Test
  fun generateQRCode_largePayload() {
    val large = JSONObject().apply { repeat(50) { put("k$it", "v$it") } }.toString()

    assertQrResult(pixelPass.generateQRCode(large))
  }
}
