package io.mosip.pixelpass

import nl.minvws.encoding.Base45
import io.mosip.pixelpass.zlib.ZLib
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class PixelPassGenerateQRDataTest {

    private val pixelPass = PixelPass()

    @Test
    fun `generateQRData should encode valid JSON`() {
        val json = """{"name":"Alice","age":30}"""
        val result = pixelPass.generateQRData(json)

        assertTrue(result.isNotEmpty())
    }

    @Test
    fun `generateQRData should fallback to raw encoding for invalid JSON`() {
        val raw = "this is not json"
        val encoded = pixelPass.generateQRData(raw)

        val decoded = Base45.getDecoder().decode(encoded)
        val decompressed = ZLib().decode(decoded)

        assertEquals(raw, String(decompressed))
    }

     @Test
    fun `generateQRData should include header in output`() {
        val json = """{"id":"123"}"""
        val header = "HC1:"
        
        val result = pixelPass.generateQRData(json, header)
        
        assertTrue(result.startsWith(header))
        assertTrue(result.length > header.length)
    }

    @Test
    fun `generateQRData should work with various header formats`() {
        val json = """{"test":"value"}"""
        
        val headers = listOf("HC1:", "MOSIP:", "V1:", "PREFIX_", "")
        
        headers.forEach { header ->
            val result = pixelPass.generateQRData(json, header)
            assertTrue(result.startsWith(header))
        }
    }

    @Test
    fun `generateQRData with empty header should not prefix anything`() {
        val json = """{"id":"123"}"""
        
        val resultWithoutHeader = pixelPass.generateQRData(json)
        val resultWithEmptyHeader = pixelPass.generateQRData(json, "")
        
        assertEquals(resultWithoutHeader, resultWithEmptyHeader)
    }

}
