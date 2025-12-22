package io.mosip.pixelpass

import io.mosip.pixelpass.types.ECC
import org.json.JSONArray
import org.json.JSONObject
import java.util.Base64
import kotlin.test.*

class PixelPassGenerateQRCodeTest {

    private val pixelPass = PixelPass()

    @Test
    fun `generateQRCode should return valid base64 image with default ECC`() {
        val json = """{"name":"Alice","age":30}"""
        val result = pixelPass.generateQRCode(json)

        assertTrue(result.isNotEmpty())
        // Verify it's valid base64
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with ECC level L`() {
        val json = """{"test":"data"}"""
        val result = pixelPass.generateQRCode(json, ECC.L)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with ECC level M`() {
        val json = """{"test":"data"}"""
        val result = pixelPass.generateQRCode(json, ECC.M)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with ECC level Q`() {
        val json = """{"test":"data"}"""
        val result = pixelPass.generateQRCode(json, ECC.Q)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with ECC level H`() {
        val json = """{"test":"data"}"""
        val result = pixelPass.generateQRCode(json, ECC.H)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with custom header`() {
        val json = """{"id":"123"}"""
        val header = "HC1:"
        val result = pixelPass.generateQRCode(json, ECC.L, header)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should work with empty header`() {
        val json = """{"id":"123"}"""
        val result = pixelPass.generateQRCode(json, ECC.L, "")

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should handle JSON array input`() {
        val jsonArray = """[{"name":"Alice"},{"name":"Bob"}]"""
        val result = pixelPass.generateQRCode(jsonArray)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should handle complex nested JSON`() {
        val complexJson = JSONObject().apply {
            put("ID", "123")
            put("Name", "John")
            put("Address", JSONObject().apply {
                put("Street", "Main St")
                put("City", "NYC")
            })
            put("Tags", JSONArray().apply {
                put("tag1")
                put("tag2")
            })
        }.toString()

        val result = pixelPass.generateQRCode(complexJson)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should handle invalid JSON with fallback`() {
        val invalidJson = "this is not json"
        val result = pixelPass.generateQRCode(invalidJson)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should produce different results for different ECC levels`() {
        val json = """{"test":"data"}"""
        
        val resultL = pixelPass.generateQRCode(json, ECC.L)
        val resultM = pixelPass.generateQRCode(json, ECC.M)
        val resultQ = pixelPass.generateQRCode(json, ECC.Q)
        val resultH = pixelPass.generateQRCode(json, ECC.H)

        // Different ECC levels should produce different QR codes
        val results = setOf(resultL, resultM, resultQ, resultH)
        assertTrue(results.size > 1, "Different ECC levels should produce different results")
    }

    @Test
    fun `generateQRCode with header should include header in encoded data`() {
        val json = """{"id":"123"}"""
        val header = "TEST:"
        
        val result = pixelPass.generateQRCode(json, ECC.L, header)
        
        assertTrue(result.isNotEmpty())
        // The QR code should encode data that starts with the header
        // We can verify this by checking the generateQRData includes it
        val qrData = pixelPass.generateQRData(json, header)
        assertTrue(qrData.startsWith(header))
    }

    @Test
    fun `generateQRCode should handle large JSON payload`() {
        val largeJson = JSONObject().apply {
            repeat(50) { i ->
                put("field$i", "value$i with some additional text to make it larger")
            }
        }.toString()

        val result = pixelPass.generateQRCode(largeJson)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }

    @Test
    fun `generateQRCode should handle special characters in JSON`() {
        val jsonWithSpecialChars = """{"name":"José María","text":"Hello 世界 🌍"}"""
        val result = pixelPass.generateQRCode(jsonWithSpecialChars)

        assertTrue(result.isNotEmpty())
        assertNotNull(Base64.getDecoder().decode(result))
    }
}