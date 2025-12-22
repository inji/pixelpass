package io.mosip.pixelpass

import io.mosip.pixelpass.exception.UnknownBinaryFileTypeException
import io.mosip.pixelpass.shared.DEFAULT_ZIP_FILE_NAME
import org.zeroturnaround.zip.ZipUtil
import java.io.File
import kotlin.test.*

class PixelPassDecodeBinaryTest {

    private val pixelPass = PixelPass()

    @Test
    fun `decodeBinary should extract zip content`() {
        val expected = "Hello World!!"

        // Create a file WITH THE REQUIRED ENTRY NAME
        val contentFile = File.createTempFile("content", null)
        contentFile.writeText(expected)

        val zipFile = File.createTempFile("test", ".zip")

        // Pack entry with DEFAULT_ZIP_FILE_NAME
        ZipUtil.packEntry(
            contentFile,
            zipFile,
            DEFAULT_ZIP_FILE_NAME
        )

        val actual = PixelPass().decodeBinary(zipFile.readBytes())
        assertEquals(expected, actual)

        contentFile.deleteOnExit()
        zipFile.deleteOnExit()
    }

    @Test
    fun `decodeBinary should throw error for unsupported binary`() {
        assertFailsWith<UnknownBinaryFileTypeException> {
            PixelPass().decodeBinary(byteArrayOf(0x01, 0x02))
        }
    }

    @Test
    fun `decodeBinary should handle ZIP with multiple entries`() {
        val content = "Hello World"

        val tempZip = File.createTempFile("test", ".zip")
        val contentFile = File.createTempFile("content", null)
        val otherFile = File.createTempFile("other", null)

        contentFile.writeText(content)
        otherFile.writeText("Other content")

        // Create a proper directory structure
        val tempDir = File.createTempFile("temp", "dir")
        tempDir.delete()
        tempDir.mkdir()

        val file1 = File(tempDir, "certificate.json")
        val file2 = File(tempDir, "other.txt")
        file1.writeText(content)
        file2.writeText("Other content")

        // Pack directory
        ZipUtil.pack(tempDir, tempZip)

        val result = pixelPass.decodeBinary(tempZip.readBytes())
        assertEquals(content, result)

        tempZip.deleteOnExit()
        contentFile.deleteOnExit()
        otherFile.deleteOnExit()
        file1.deleteOnExit()
        file2.deleteOnExit()
        tempDir.deleteOnExit()
    }

    @Test
    fun `decodeBinary should throw error for empty byte array`() {
        assertFailsWith<UnknownBinaryFileTypeException> {
            pixelPass.decodeBinary(byteArrayOf())
        }
    }

    @Test
    fun `decodeBinary should throw error for corrupted ZIP header`() {
        val corruptedZip = "PK\u0003\u0004corrupted".toByteArray()

        assertFailsWith<Exception> {
            pixelPass.decodeBinary(corruptedZip)
        }
    }

    @Test
    fun `decodeBinary should handle ZIP with wrong entry name`() {
        val content = "Hello"
        val tempZip = File.createTempFile("test", ".zip")
        val contentFile = File.createTempFile("wrong", null)

        contentFile.writeText(content)

        ZipUtil.packEntry(contentFile, tempZip, "wrong_name.txt")
        
        assertFailsWith<Exception> {
            pixelPass.decodeBinary(tempZip.readBytes())
        }
        
        tempZip.deleteOnExit()
        contentFile.deleteOnExit()
    }

}
