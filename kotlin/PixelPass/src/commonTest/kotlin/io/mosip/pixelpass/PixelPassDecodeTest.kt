package io.mosip.pixelpass

import org.json.JSONObject
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlin.test.assertEquals
import io.mosip.pixelpass.utils.toMapWithKeyAndValueMapper


class PixelPassDecodeTest {

    private val pixelPass = PixelPass()

    @Test
    fun `decode should round trip QR encoded JSON`() {
        val json = """{"hello":"world"}"""
        val encoded = pixelPass.generateQRData(json)
        val decoded = pixelPass.decode(encoded)

        assertEquals(
            JSONObject(json).toMapWithKeyAndValueMapper(),
            JSONObject(decoded).toMapWithKeyAndValueMapper()
        )
    }

    @Test
    fun `decode should handle data without CBOR encoding`() {
        val plainText = "plain text message"
        val encoded = pixelPass.generateQRData(plainText)
        val decoded = pixelPass.decode(encoded)
        
        assertEquals(plainText, decoded)
    }

    @Test
    fun `decode should handle empty JSON object`() {
        val emptyJson = "{}"
        val encoded = pixelPass.generateQRData(emptyJson)
        val decoded = pixelPass.decode(encoded)
        
        assertTrue(decoded.contains("{}"))
    }

    @Test
    fun `decode should handle empty JSON array`() {
        val emptyArray = "[]"
        val encoded = pixelPass.generateQRData(emptyArray)
        val decoded = pixelPass.decode(encoded)
        
        assertTrue(decoded.contains("[]"))
    }

    @Test
    fun `decode should handle JSON with unicode characters`() {
        val unicodeJson = """{"name":"José","city":"São Paulo","emoji":"🎉"}"""
        val encoded = pixelPass.generateQRData(unicodeJson)
        val decoded = pixelPass.decode(encoded)
        
        assertTrue(decoded.contains("José"))
        assertTrue(decoded.contains("São Paulo"))
    }

    @Test
    fun `decode should handle deeply nested JSON`() {
        val nestedJson = """{"level1":{"level2":{"level3":{"value":"deep"}}}}"""
        val encoded = pixelPass.generateQRData(nestedJson)
        val decoded = pixelPass.decode(encoded)
        
        assertTrue(decoded.contains("level1"))
        assertTrue(decoded.contains("deep"))
    }

}
