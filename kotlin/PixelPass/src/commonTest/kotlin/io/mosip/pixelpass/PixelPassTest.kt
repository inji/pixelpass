package io.mosip.pixelpass

import io.mockk.*
import io.mosip.pixelpass.exception.UnknownBinaryFileTypeException
import io.mosip.pixelpass.zlib.ZLib
import junit.framework.TestCase.assertEquals
import nl.minvws.encoding.Base45
import org.json.JSONArray
import org.json.JSONObject
import org.zeroturnaround.zip.ZipUtil
import java.io.File
import java.io.FileOutputStream
import kotlin.test.*
import io.mosip.pixelpass.shared.*
import io.mosip.pixelpass.utils.toMapWithKeyAndValueMapper



class PixelPassTest {

    @AfterTest
    fun after() {
        clearAllMocks()
    }

    private val pixelPass = PixelPass()

    @Test
    fun `should return decoded data for given QR data`() {
        val data = "NCFKVPV0QSIP600GP5L0"
        val expected = "hello"

        val actual = PixelPass().decode(data)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return decoded data for given QR data in cbor`() {
        val data = "NCF3QBXJA5NJRCOC004 QN4"
        val expected = "{\"temp\":15}"

        val actual = PixelPass().decode(data)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return encoded QR data for given data with CBOR`() {
        val data =
            "{\"str\":\"stringtype\",\"intP\":10,\"intN\":-10,\"intL\":111111110,\"intLN\":111111110,\"float\":10.01,\"nulltype\":null,\"bool\":true,\"bool2\":false,\"arryE\":[],\"arryF\":[1,2,3,-4,\"hello\",{\"temp\":123}],\"objE\":{},\"objS\":{\"str\":\"stringtype\"}}"
        val expected =
            "NCF6QB2NJXTAGPTV30I-R.431DJENA2JA-NEO:2RZI.3TL69%5L+2T+BTR\$9M PHQUKSIEUJ4\$F W0XQ08LA-NEYJ25/FTELJTPC31L.R-PI+YQXDPV0Q0C5-Q5S2W5OIJWIQZNOLN*XKRK1OP65QQ-NKQVB%/JX1M%9IF+8U48+SB000Z2WWS7"

        val actual = PixelPass().generateQRData(data)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return decoded JSON data for given QR data with CBOR`() {
        val expected =
            "{\"arryE\":[],\"arryF\":[1,2,3,-4,\"hello\",{\"temp\":123}],\"bool\":true,\"intLN\":111111110,\"intL\":111111110,\"float\":10.01,\"intN\":-10,\"nulltype\":null,\"objS\":{\"str\":\"stringtype\"},\"str\":\"stringtype\",\"intP\":10,\"bool2\":false,\"objE\":{}}"
        val data =
            "NCF6QB2NJXTAGPTV30I-R.431DJENA2JA-NEO:2RZI.3TL69%5L+2T+BTR\$9M PHQUKSIEUJ4\$F W0XQ08LA-NEYJ25/FTELJTPC31L.R-PI+YQXDPV0Q0C5-Q5S2W5OIJWIQZNOLN*XKRK1OP65QQ-NKQVB%/JX1M%9IF+8U48+SB000Z2WWS7"

        val actual = PixelPass().decode(data)
        assertEquals(expected, actual)
    }

    @Test
    fun `encode in js decode in kotlin`() {
        val expected =
            "{\"arryE\":[],\"arryF\":[1,2,3,-4,\"hello\",{\"temp\":123}],\"bool\":true,\"intLN\":111111110,\"intL\":111111110,\"float\":10.01,\"intN\":-10,\"nulltype\":null,\"objS\":{\"str\":\"stringtype\"},\"str\":\"stringtype\",\"intP\":10,\"bool2\":false,\"objE\":{}}"
        val data =
            "NCF6QBJUBZJA W04IJFLTY\$IFHL4IJNU44TBJQQRJ2\$SVMLM:8QP/I2NC7D8RDDQOVXY4%V3WABH-EF3OU0Q8O5MIP.HDQ1JMZI.9K:V6JR8X\$F1Y9WH5FWE%109/D6XH1+P:GLVHL E7JJ1 H9LOEQS4PRAAUI+SBSCGCHSU7D00089AWS7"

        val actual = PixelPass().decode(data)
        assertEquals(expected, actual)
    }


    @Test
    fun `should return mapped CBOR data for given data with map`() {
        val expected = "a3016332303702644a686f6e0365486f6e6179"
        val data = JSONObject("{\"name\": \"Jhon\", \"id\": \"207\", \"l_name\": \"Honay\"}")
        val mapper = mapOf("id" to 1, "name" to 2, "l_name" to 3)

        val actual = PixelPass().getMappedData(data, mapper, emptyMap(), true)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return mapped data for given data with map`() {
        val expected = mapOf(3 to "Honay", 2 to "Jhon", 1 to "207")
        val data = JSONObject("{\"name\": \"Jhon\", \"id\": \"207\", \"l_name\": \"Honay\"}")
        val mapper = mapOf("id" to 1, "name" to 2, "l_name" to 3)

        val actual = PixelPass().getMappedData(data, mapper)
        assertEquals(expected, actual as Map<*, *>)
    }

    @Test
    fun `should return properly mapped JSON data for given CBOR`() {
        val expected =
            JSONObject("{\"name\": \"Jhon\", \"id\": \"207\", \"l_name\": \"Honay\"}").toString()
        val data = "a302644a686f6e01633230370365486f6e6179"
        val mapper = arrayOf(mapOf("1" to "id", "2" to "name", "3" to "l_name"))

        val actual = PixelPass().decodeMappedData(data, mapper)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return properly mapped JSON data for given data`() {
        val expected =
            JSONObject("{\"name\": \"Jhon\", \"id\": \"207\", \"l_name\": \"Honay\"}").toString()
        val data = "{ \"1\": \"207\", 2: Jhon, 3: Honay }"
        val mapper = arrayOf(mapOf("1" to "id", "2" to "name", "3" to "l_name"))

        val actual = PixelPass().decodeMappedData(data, mapper)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return decoded data for given QR data for zipped data`() {
        val expected = "Hello World!!"
        val createTempFile = File("certificate.json")
        val fos = FileOutputStream(createTempFile)
        fos.write(expected.toByteArray())
        fos.close()
        val tempZip = File.createTempFile("temp", ".zip")
        ZipUtil.packEntry(createTempFile, tempZip)

        val actual = PixelPass().decodeBinary(tempZip.readBytes())
        assertEquals(expected, actual)
        tempZip.deleteOnExit()
    }

    @Test
    fun `should throw error if binary data type not zip`() {
        val tempZip = File.createTempFile("temp", ".png")

        tempZip.writeBytes(byteArrayOf(0x00, 0x01, 0x02))

        assertFailsWith<UnknownBinaryFileTypeException> {
            PixelPass().decodeBinary(tempZip.readBytes())
        }

        tempZip.deleteOnExit()
    }

    @Test
    fun `should encode raw data when JSON parsing fails`() {
        val invalidJson = "this is not valid json"
        val result = PixelPass().generateQRData(invalidJson)
        assertTrue(result.isNotEmpty(), "Encoded result should not be empty")

        val decoded = Base45.getDecoder().decode(result)
        val decompressed = ZLib().decode(decoded)
        val original = String(decompressed)

        assertEquals(invalidJson, original)
    }

    @Test
    fun `should return encoded QR data for JSON array`() {
        val jsonArray = """[{"name":"Alice","age":30},{"name":"Bob","age":25}]"""

        val result = PixelPass().generateQRData(jsonArray)

        assertTrue(result.isNotEmpty(), "Result should not be empty")

        val decodedBytes = Base45.getDecoder().decode(result)
        val decompressedBytes = ZLib().decode(decodedBytes)

        assertNotNull(decompressedBytes)
    }

    @Test
    fun `should return claim 169 semantics mapped CBOR data for given data if no mapper is given`() {

        val data = JSONObject(
            """{
                          "ID": "3918592438",
                          "Version": 10,
                          "Full Name": "Janardhan BS",
                          "Date of Birth": "19840418",
                          "Gender": "Male",
                          "Address": "New House, Near Metro Line, Bengaluru, KA",
                          "Email ID": "janardhan@example.com",
                          "Phone Number": "+919876543210",
                          "Nationality": "IN",
                          "hello":"world",
                          "Face": {
                            "Data": "5249",
                            "Data format": "Image",
                            "Data sub format": "PNG"
                          },
                           "Voice": {
                            "Data": "5249",
                            "Data format": "Sound",
                            "Data sub format": "WAV"
                          }, 
                        }"""
        )
        val actual = PixelPass().getMappedData(data, cborEnable = true)
        val expected = "ac016a33393138353932343338020a046c4a616e61726468616e2042530868313938343034313809010a78294e657720486f7573652c204e656172204d6574726f204c696e652c2042656e67616c7572752c204b410b756a616e61726468616e406578616d706c652e636f6d0c6d2b3931393837363534333231300d62494e183ea3006435323439010002001841a3006435323439010202006568656c6c6f65776f726c64"
        assertEquals(expected, actual)
    }

    @Test
    fun `should return claim 169 semantics mapped CBOR data in an array for given array of data if no mapper is given`() {

        val data = JSONArray(
          """[{
                        "ID": "3918592438",
                        "Version": 10,
                        "Full Name": "Janardhan BS",
                        "Date of Birth": "19840418",
                        "Gender": "Male",
                        "Address": "New House, Near Metro Line, Bengaluru, KA",
                        "Email ID": "janardhan@example.com",
                        "Phone Number": "+919876543210",
                        "Nationality": "IN",
                        "hello":"world",
                        "Face": {
                          "Data": "5249",
                          "Data format": "Image",
                          "Data sub format": "PNG"
                        },
                        "Voice": {
                          "Data": "5249",
                          "Data format": "Sound",
                          "Data sub format": "WAV"
                        }, 
                      },
                      {
                        "ID": "102030",
                        "Full Name": "Jhon",
                        "Date of Birth": "19990102",
                        "Gender": "Male",
                        "Left Middle Finger": {
                          "Data": "9988776655332211",
                          "Data format": "Template",
                          "Data sub format": "Fingerprint Template NIST"
                        }, 
                      }
                    ]"""
                .trimIndent()
        )
        val actual = PixelPass().getMappedData(data, cborEnable = true)
        val expected =
            JSONArray(
                """["ac016a33393138353932343338020a046c4a616e61726468616e2042530868313938343034313809010a78294e657720486f7573652c204e656172204d6574726f204c696e652c2042656e67616c7572752c204b410b756a616e61726468616e406578616d706c652e636f6d0c6d2b3931393837363534333231300d62494e183ea3006435323439010002001841a3006435323439010202006568656c6c6f65776f726c64","a5016631303230333004644a686f6e0868313939393031303209011839a300703939383837373636353533333232313101010202"]"""
            )
        assertEquals(expected.toString(), actual.toString())
    }

    @Test
    fun `should return properly remapped data for given claim 169 semantics mapped if no mapper is given`() {

        val expected =
            "{\"Address\":\"New House, Near Metro Line, Bengaluru, KA\",\"Version\":10,\"Email ID\":\"janardhan@example.com\",\"Full Name\":\"Janardhan BS\",\"Date of Birth\":\"19840418\",\"ID\":\"3918592438\",\"Gender\":\"Male\",\"hello\":\"world\",\"Phone Number\":\"+919876543210\",\"Face\":{\"Data format\":\"Image\",\"Data sub format\":\"PNG\",\"Data\":\"5249\"},\"Voice\":{\"Data format\":\"Sound\",\"Data sub format\":\"WAV\",\"Data\":\"5249\"},\"Nationality\":\"IN\"}"
        val data =
            "ac016a33393138353932343338020a046c4a616e61726468616e2042530868313938343034313809010a78294e657720486f7573652c204e656172204d6574726f204c696e652c2042656e67616c7572752c204b410b756a616e61726468616e406578616d706c652e636f6d0c6d2b3931393837363534333231300d62494e183ea3006435323439010002001841a3006435323439010202006568656c6c6f65776f726c64"
        val actual = PixelPass().decodeMappedData(data)
        assertEquals(expected, actual)
    }

    @Test
    fun `should return properly remapped data for given array claim 169 semantics mapped CBOR data if no mapper is given`() {

        val expected =
            arrayOf(
                """{"Address":"New House, Near Metro Line, Bengaluru, KA","Version":10,"Email ID":"janardhan@example.com","Full Name":"Janardhan BS","Date of Birth":"19840418","ID":"3918592438","Gender":"Male","hello":"world","Phone Number":"+919876543210","Face":{"Data format":"Image","Data sub format":"PNG","Data":"5249"},"Voice":{"Data format":"Sound","Data sub format":"WAV","Data":"5249"},"Nationality":"IN"}""",
                """{"Left Middle Finger":{"Data format":"Template","Data sub format":"Fingerprint Template NIST","Data":"9988776655332211"},"Full Name":"Jhon","Date of Birth":"19990102","ID":"102030","Gender":"Male"}""",
            )
        val data =
            arrayOf(
                "ac016a33393138353932343338020a046c4a616e61726468616e2042530868313938343034313809010a78294e657720486f7573652c204e656172204d6574726f204c696e652c2042656e67616c7572752c204b410b756a616e61726468616e406578616d706c652e636f6d0c6d2b3931393837363534333231300d62494e183ea3006435323439010002001841a3006435323439010202006568656c6c6f65776f726c64",
                "a5016631303230333004644a686f6e0868313939393031303209011839a300703939383837373636353533333232313101010202",
            )
        val actual = PixelPass().decodeMappedData(data)
        assertContentEquals(expected, actual)
    }

    @Test
    fun `should round-trip JSON through getMappedData and decodeMappedData`() {
        val inputJson = JSONObject(
            """{"Address":"New House, Near Metro Line, Bengaluru, KA","Version":10,"Email ID":"janardhan@example.com","Full Name":"Janardhan BS","Date of Birth":"19840418","ID":"3918592438","Gender":"Male","hello":"world","Phone Number":"+919876543210","Face":{"Data format":"Image","Data sub format":"PNG","Data":"5249"},"Voice":{"Data format":"Sound","Data sub format":"WAV","Data":"5249"},"Nationality":"IN"}"""
        )

        val encoded = pixelPass.getMappedData(
            jsonData = inputJson,
            keyMapper = CLAIM_169_KEY_MAPPER,
            valueMapper = CLAIM_169_VALUE_MAPPER,
            cborEnable = true
        ) as String

        val decoded = pixelPass.decodeMappedData(
            data = encoded,
            keyMapper = CLAIM_169_REVERSE_KEY_MAPPER
        )

        val expectedElement = inputJson.toMapWithKeyAndValueMapper()
        val actualElement = JSONObject(decoded).toMapWithKeyAndValueMapper()
        assertEquals(
            expectedElement as Map<*, *>,
            actualElement as Map<*, *>
        )
    }

}
