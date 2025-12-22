package io.mosip.pixelpass

import io.mosip.pixelpass.shared.*
import org.json.JSONArray
import org.json.JSONObject
import kotlin.test.*

class PixelPassGetMappedDataTest {

    private val pixelPass = PixelPass()

    @Test
    fun `getMappedData should map JSON object without CBOR`() {
        val json = JSONObject("""{"ID":"123","Gender":"Male"}""")
        val mapped = pixelPass.getMappedData(json) as Map<*, *>

        assertTrue(mapped.isNotEmpty())
    }

    @Test
    fun `getMappedData should return CBOR hex when enabled`() {
        val json = JSONObject("""{"ID":"123"}""")
        val result = pixelPass.getMappedData(json, cborEnable = true)

        assertTrue(result is String)
        assertTrue((result as String).isNotEmpty())
    }

    @Test
    fun `getMappedData should map array of objects`() {
        val array = JSONArray("""[{"ID":"1"},{"ID":"2"}]""")
        val result = pixelPass.getMappedData(array)

        assertEquals(2, result.length())
    }

    @Test
    fun `getMappedData should throw for non object array element`() {
        val array = JSONArray("""[{"ID":"1"},5]""")

        assertFailsWith<IllegalArgumentException> {
            pixelPass.getMappedData(array)
        }
    }

    @Test
    fun `getMappedData should work with custom key mapper`() {
        val json = JSONObject("""{"firstName":"John","lastName":"Doe","age":"30"}""")
        val customKeyMapper = mapOf(
            "firstName" to 1, "lastName" to 2, "age" to 3
        )

        val result = pixelPass.getMappedData(json, customKeyMapper, emptyMap(), false) as Map<*, *>

        assertEquals("John", result[1])
        assertEquals("Doe", result[2])
        assertEquals("30", result[3])
    }

    @Test
    fun `getMappedData should work with custom value mapper`() {
        val json = JSONObject("""{"status":"active","type":"user"}""")
        val customKeyMapper = mapOf(
            "status" to 1,
            "type" to 2
        )
        val customValueMapper = mapOf(
            "status" to mapOf<Any, Int>("active" to 1, "inactive" to 0),
            "type" to mapOf<Any, Int>("user" to 10, "admin" to 20)
        )

        val result = pixelPass.getMappedData(json, customKeyMapper, customValueMapper, false) as Map<*, *>

        assertEquals(1, result[1])
        assertEquals(10, result[2])
    }

    @Test
    fun `getMappedData should handle partial key mapping`() {
        val json = JSONObject("""{"mapped":"value1","unmapped":"value2"}""")
        val partialMapper = mapOf("mapped" to 1)

        val result = pixelPass.getMappedData(json, partialMapper, emptyMap(), false) as Map<*, *>

        assertTrue(result.containsKey(1))
        assertTrue(result.containsKey("unmapped"))
    }

    @Test
    fun `getMappedData with CBOR should return hex string`() {
        val json = JSONObject("""{"id":"123"}""")
        val result = pixelPass.getMappedData(json, emptyMap(), emptyMap(), true)

        assertTrue(result is String)
        // Verify it's a valid hex string
        assertTrue((result as String).matches(Regex("^[0-9a-f]+$")))
    }

    @Test
    fun `decodeMappedData should handle non-CBOR JSON string`() {
        val jsonString = """{"1":"value1","2":"value2"}"""
        val mapper = arrayOf(mapOf("1" to "key1", "2" to "key2"))

        val result = pixelPass.decodeMappedData(jsonString, mapper)

        assertTrue(result.contains("key1"))
        assertTrue(result.contains("key2"))
    }

    @Test
    fun `decodeMappedData should handle empty mapper array`() {
        val cborHex = "a1016131" // Simple CBOR: {1: "1"}

        val result = pixelPass.decodeMappedData(cborHex, emptyArray())

        assertTrue(result.isNotEmpty())
    }

    @Test
    fun `decodeMappedData array should preserve order`() {
        val data = arrayOf(
            "a1016131", // {1: "1"}
            "a1016132", // {1: "2"}
            "a1016133"  // {1: "3"}
        )

        val result = pixelPass.decodeMappedData(data)

        assertEquals(3, result.size)
        // Verify order is preserved
        assertTrue(result[0].contains("\"1\""))
        assertTrue(result[1].contains("\"2\""))
        assertTrue(result[2].contains("\"3\""))
    }

}
