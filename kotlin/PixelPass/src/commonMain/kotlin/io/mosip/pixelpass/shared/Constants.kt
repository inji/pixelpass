package io.mosip.pixelpass.shared

const val QR_SCALE = 15
const val QR_BORDER = 3
const val QR_QUALITY = 100

const val DEFAULT_ZLIB_COMPRESSION_LEVEL = 9
const val ZIP_HEADER = "PK"
const val DEFAULT_ZIP_FILE_NAME = "certificate.json"

val CLAIM_169_KEY_MAPPER =
  mapOf(
    "ID" to 1,
    "Version" to 2,
    "Language" to 3,
    "Full Name" to 4,
    "First Name" to 5,
    "Middle Name" to 6,
    "Last Name" to 7,
    "Date of Birth" to 8,
    "Gender" to 9,
    "Address" to 10,
    "Email ID" to 11,
    "Phone Number" to 12,
    "Nationality" to 13,
    "Marital Status" to 14,
    "Guardian" to 15,
    "Binary Image" to 16,
    "Binary Image Format" to 17,
    "Best Quality Fingers" to 18,
    "Right Thumb" to 50,
    "Right Pointer Finger" to 51,
    "Right Middle Finger" to 52,
    "Right Ring Finger" to 53,
    "Right Little Finger" to 54,
    "Left Thumb" to 55,
    "Left Pointer Finger" to 56,
    "Left Middle Finger" to 57,
    "Left Ring Finger" to 58,
    "Left Little Finger" to 59,
    "Right Iris" to 60,
    "Left Iris" to 61,
    "Face" to 62,
    "Right Palm Print" to 63,
    "Left Palm Print" to 64,
    "Voice" to 65,
    "Data" to 0,
    "Data format" to 1,
    "Data sub format" to 2,
    "Data issuer" to 3,
  )

val CLAIM_169_VALUE_MAPPER: Map<String, Map<Any, Int>> =
  mapOf(
    "Data format" to mapOf("Image" to 0, "Template" to 1, "Sound" to 2, "Bio Hash" to 3),
    "Data sub format" to
      mapOf(
        "PNG" to 0,
        "JPEG" to 1,
        "JPEG2000" to 2,
        "AVIF" to 3,
        "WEBP" to 4,
        "TIFF" to 5,
        "WSQ" to 6,
        "Fingerprint Template ANSI 378" to 0,
        "Fingerprint Template ISO 19794-2" to 1,
        "Fingerprint Template NIST" to 2,
        "WAV" to 0,
        "MP3" to 1,
      ),
    "Gender" to mapOf("Male" to 1, "Female" to 2, "Others" to 3),
    "Marital Status" to mapOf("Unmarried" to 1, "Married" to 2, "Divorced" to 3),
    "Binary Image Format" to mapOf("JPEG" to 1, "JPEG2" to 2, "AVIF" to 3, "WEBP" to 4),
  )

val CLAIM_169_REVERSE_KEY_MAPPER: Array<Map<String, String>> =
  arrayOf(
    mapOf(
      "1" to "ID",
      "2" to "Version",
      "3" to "Language",
      "4" to "Full Name",
      "5" to "First Name",
      "6" to "Middle Name",
      "7" to "Last Name",
      "8" to "Date of Birth",
      "9" to "Gender",
      "10" to "Address",
      "11" to "Email ID",
      "12" to "Phone Number",
      "13" to "Nationality",
      "14" to "Marital Status",
      "15" to "Guardian",
      "16" to "Binary Image",
      "17" to "Binary Image Format",
      "18" to "Best Quality Fingers",
      "50" to "Right Thumb",
      "51" to "Right Pointer Finger",
      "52" to "Right Middle Finger",
      "53" to "Right Ring Finger",
      "54" to "Right Little Finger",
      "55" to "Left Thumb",
      "56" to "Left Pointer Finger",
      "57" to "Left Middle Finger",
      "58" to "Left Ring Finger",
      "59" to "Left Little Finger",
      "60" to "Right Iris",
      "61" to "Left Iris",
      "62" to "Face",
      "63" to "Right Palm Print",
      "64" to "Left Palm Print",
      "65" to "Voice",
    ),
    mapOf("0" to "Data", "1" to "Data format", "2" to "Data sub format", "3" to "Data issuer"),
  )

val CLAIM_169_ROOT_REVERSE_VALUE_MAPPER: Map<String, Map<Any, String>> =
  mapOf(
    "Data format" to mapOf(0 to "Image", 1 to "Template", 2 to "Sound", 3 to "Bio Hash"),
    "Gender" to mapOf(1 to "Male", 2 to "Female", 3 to "Others"),
    "Binary Image Format" to mapOf(1 to "JPEG", 2 to "JPEG2", 3 to "AVIF", 4 to "WEBP"),
    "Marital Status" to mapOf(1 to "Unmarried", 2 to "Married", 3 to "Divorced"),
  )

val CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER: Map<Any, Any> =
  mapOf(0 to "Image", 1 to "Template", 2 to "Sound", 3 to "Bio Hash")

val CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER: Map<String, Map<Any, Any>> =
  mapOf(
    "Image" to
      mapOf(
        0 to "PNG",
        1 to "JPEG",
        2 to "JPEG2000",
        3 to "AVIF",
        4 to "WEBP",
        5 to "TIFF",
        6 to "WSQ",
      ),
    "Template" to
      mapOf(
        0 to "Fingerprint Template ANSI 378",
        1 to "Fingerprint Template ISO 19794-2",
        2 to "Fingerprint Template NIST",
      ),
    "Sound" to mapOf(0 to "WAV", 1 to "MP3"),
  )

val CLAIM_169_BIOMETRIC_KEYS =
  listOf(
    "Right Thumb",
    "Right Pointer Finger",
    "Right Middle Finger",
    "Right Ring Finger",
    "Right Little Finger",
    "Left Thumb",
    "Left Pointer Finger",
    "Left Middle Finger",
    "Left Ring Finger",
    "Left Little Finger",
    "Right Iris",
    "Left Iris",
    "Face",
    "Right Palm Print",
    "Left Palm Print",
    "Voice",
  )

const val CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY = "Data format"
const val CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY = "Data sub format"
