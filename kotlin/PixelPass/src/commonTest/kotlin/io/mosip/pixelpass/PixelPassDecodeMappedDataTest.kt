package io.mosip.pixelpass

import io.mosip.pixelpass.shared.*
import org.json.JSONObject
import kotlin.test.Test
import kotlin.test.assertEquals
import io.mosip.pixelpass.utils.toMapWithKeyAndValueMapper

class PixelPassDecodeMappedDataTest {

    private val pixelPass = PixelPass()

    @Test
    fun `decodeMappedData should restore claim 169 semantics`() {
        val input = JSONObject(
            """{
              "ID":"102030",
              "Full Name":"John",
              "Gender":"Male",
              "Left Middle Finger":{
                "Data":"9988",
                "Data format":"Template",
                "Data sub format":"Fingerprint Template NIST"
              }
            }"""
        )

        val encoded = pixelPass.getMappedData(input, cborEnable = true) as String
        val decoded = pixelPass.decodeMappedData(encoded)

        assertEquals(
            input.toMapWithKeyAndValueMapper(),
            JSONObject(decoded).toMapWithKeyAndValueMapper()
        )
    }

    @Test
    fun `decodeMappedData should handle array input`() {
        val json = JSONObject("""{"ID":"1"}""")
        val encoded = pixelPass.getMappedData(json, cborEnable = true) as String

        val result = pixelPass.decodeMappedData(arrayOf(encoded))
        assertEquals(1, result.size)
    }
}
