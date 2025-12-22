package io.mosip.pixelpass.cbor

import co.nstant.`in`.cbor.CborDecoder
import co.nstant.`in`.cbor.model.Array
import co.nstant.`in`.cbor.model.ByteString
import co.nstant.`in`.cbor.model.DataItem
import co.nstant.`in`.cbor.model.DoublePrecisionFloat
import co.nstant.`in`.cbor.model.MajorType
import co.nstant.`in`.cbor.model.Map
import co.nstant.`in`.cbor.model.NegativeInteger
import co.nstant.`in`.cbor.model.SimpleValue
import co.nstant.`in`.cbor.model.SimpleValueType
import co.nstant.`in`.cbor.model.UnicodeString
import co.nstant.`in`.cbor.model.UnsignedInteger
import io.mosip.pixelpass.shared.CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY
import io.mosip.pixelpass.shared.CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY
import io.mosip.pixelpass.shared.CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER
import io.mosip.pixelpass.shared.CLAIM_169_BIOMETRIC_KEYS
import io.mosip.pixelpass.shared.CLAIM_169_ROOT_REVERSE_VALUE_MAPPER
import io.mosip.pixelpass.shared.CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER
import io.mosip.pixelpass.shared.isNegative
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONObject.NULL
import java.io.ByteArrayInputStream
import java.math.BigDecimal
import java.util.Locale

class Utils {
    fun toJson(dataItem: DataItem): Any {
        return if (dataItem.majorType == MajorType.MAP)
            mapToJson(JSONObject(), dataItem as Map)
        else
            arrayToJson(JSONArray(), dataItem as Array)
    }

    fun toDataItem(data: Any): DataItem {
        return when (data) {
            is JSONObject -> mapToDataItem(Map(), data)
            is JSONArray -> arrayToDataItem(Array(), data)
            is kotlin.collections.Map<*, *> -> kotlinMapToDataItem(Map(), data)
            else -> throw IllegalArgumentException("Unsupported root data type: ${data::class.simpleName}")
        }
    }

    fun replaceKeysAtDepth(
        jsonObject: JSONObject,
        mapper: kotlin.collections.Map<String, String>,
        targetDepth: Int,
        currentDepth: Int = 0
    ): JSONObject {
        val newJsonObject = JSONObject()
        val nextDepth = currentDepth + 1

        jsonObject.keys().forEach { originalKey ->
            val value = jsonObject.get(originalKey.toString())
            val newKey = if (currentDepth == targetDepth) {
                mapper[originalKey] ?: originalKey
            } else {
                originalKey
            }
            val processedValue: Any? = when (value) {
                is JSONObject ->
                    replaceKeysAtDepth(value, mapper, targetDepth, nextDepth)

                is JSONArray ->
                    replaceKeysInArrayAtDepth(value, mapper, targetDepth, nextDepth)

                NULL ->
                    null

                else ->
                    value
            }

            newJsonObject.put(newKey.toString(), processedValue)
        }
        return newJsonObject
    }

    private fun kotlinMapToDataItem(
        accumulator: Map,
        jsonMap: kotlin.collections.Map<*, *>
    ): DataItem {
        val iterator = jsonMap.entries.iterator()
        while (iterator.hasNext()) {
            val entry = iterator.next()
            val key =
                if (entry.key is Int) UnsignedInteger((entry.key as Int).toLong()) else UnicodeString(
                    entry.key.toString()
                )
            processEntry(entry.value, accumulator, key)
        }
        return accumulator
    }

    private fun processEntry(
        entry: Any?,
        accumulator: Map,
        key: DataItem
    ) {
        when (entry) {
            is JSONObject -> accumulator.put(key, mapToDataItem(Map(), entry))
            is JSONArray -> accumulator.put(key, arrayToDataItem(Array(), entry))
            is kotlin.collections.Map<*, *> -> accumulator.put(
                key,
                kotlinMapToDataItem(Map(), entry)
            )

            is String -> accumulator.put(key, UnicodeString(entry))
            is Int -> {
                if (entry.isNegative())
                    accumulator.put(key, NegativeInteger(entry.toLong()))
                else
                    accumulator.put(key, UnsignedInteger(entry.toLong()))
            }

            is BigDecimal -> accumulator.put(key, DoublePrecisionFloat(entry.toDouble()))
            is Long -> accumulator.put(key, DoublePrecisionFloat(entry.toDouble()))
            is Double -> accumulator.put(key, DoublePrecisionFloat(entry))
            true -> accumulator.put(key, SimpleValue(SimpleValueType.TRUE))
            false -> accumulator.put(key, SimpleValue(SimpleValueType.FALSE))
            NULL -> accumulator.put(key, SimpleValue(SimpleValueType.NULL))
            else -> accumulator.put(key, SimpleValue(SimpleValueType.UNDEFINED))
        }
    }

    private fun mapToDataItem(accumulator: Map, jsonObject: JSONObject): Map {
        val iterator = jsonObject.keys().iterator()
        while (iterator.hasNext()) {
            val key = iterator.next().toString()
            val unicodeString = UnicodeString(key)
            processEntry(jsonObject.get(key), accumulator, unicodeString)
        }
        return accumulator
    }

    private fun arrayToDataItem(accumulator: Array, jsonArray: JSONArray): Array {
        for (i in 0 until jsonArray.length()) {
            when (val value = jsonArray.get(i)) {
                is JSONObject -> accumulator.add(mapToDataItem(Map(), value))
                is JSONArray -> accumulator.add(arrayToDataItem(Array(), value))
                is kotlin.collections.Map<*, *> -> accumulator.add(
                    kotlinMapToDataItem(
                        Map(),
                        value
                    )
                )

                is String -> accumulator.add(UnicodeString(value))
                is Int -> {
                    if (value.isNegative())
                        accumulator.add(NegativeInteger(value.toBigInteger()))
                    else
                        accumulator.add(UnsignedInteger(value.toBigInteger()))
                }

                is BigDecimal -> accumulator.add(DoublePrecisionFloat(value.toDouble()))
                is Long -> accumulator.add(DoublePrecisionFloat(value.toDouble()))
                is Double -> accumulator.add(DoublePrecisionFloat(value))
                true -> accumulator.add(SimpleValue(SimpleValueType.TRUE))
                false -> accumulator.add(SimpleValue(SimpleValueType.FALSE))
                NULL -> accumulator.add(SimpleValue(SimpleValueType.NULL))

                else -> accumulator.add(SimpleValue(SimpleValueType.UNDEFINED))
            }
        }
        return accumulator
    }

    private fun mapToJson(accumulator: JSONObject, map: Map): JSONObject {
        val iterator: Iterator<DataItem> = map.keys.iterator()
        while (iterator.hasNext()) {
            val next = iterator.next()
            val key = next.toString()
            val dataItem = map.get(next)
            accumulator.put(key, parse(dataItem))
        }
        return accumulator
    }

    private fun arrayToJson(accumulator: JSONArray, array: Array): JSONArray {
        for (dataItem in array.dataItems) {
            accumulator.put(parse(dataItem))
        }
        return accumulator
    }

    private fun parse(dataItem: DataItem): Any? {
        return when (dataItem.majorType) {
            MajorType.MAP -> (mapToJson(JSONObject(), dataItem as Map))
            MajorType.ARRAY -> (arrayToJson(JSONArray(), dataItem as Array))
            MajorType.UNICODE_STRING -> ((dataItem as UnicodeString).string)
            MajorType.UNSIGNED_INTEGER,
            MajorType.NEGATIVE_INTEGER,
                -> ((dataItem.toString()).toInt())

            MajorType.BYTE_STRING -> {
                try {
                    val decoded =
                        CborDecoder(ByteArrayInputStream((dataItem as ByteString).bytes)).decode()

                    return parse(decoded[0])
                } catch (e: Exception) {
                    return (String((dataItem as ByteString).bytes))
                } catch (e: Error) {
                    return (String((dataItem as ByteString).bytes))
                }
            }

            MajorType.SPECIAL -> (getSpecial(dataItem.toString()))
            MajorType.INVALID -> (NULL)
            else -> (dataItem)
        }
    }

    private fun getSpecial(get: String): Any? {
        return try {
            get.toFloat()
        } catch (_: Exception) {
            try {
                if (get.lowercase(Locale.getDefault())
                        .toBooleanStrictOrNull() == null
                ) NULL else get.lowercase(Locale.getDefault()).toBooleanStrict()
            } catch (_: Exception) {
                return NULL
            }
        }
    }

    private fun replaceKeysInArrayAtDepth(
        jsonArray: JSONArray,
        mapper: kotlin.collections.Map<String, String>,
        targetDepth: Int,
        currentDepth: Int
    ): JSONArray {
        val newJsonArray = JSONArray()

        (0 until jsonArray.length()).forEach { i ->
            val processedItem: Any? = when (val item = jsonArray.get(i)) {
                is JSONObject ->
                    replaceKeysAtDepth(item, mapper, targetDepth, currentDepth)

                is JSONArray ->
                    replaceKeysInArrayAtDepth(item, mapper, targetDepth, currentDepth)

                NULL ->
                    null

                else ->
                    item
            }
            newJsonArray.put(processedItem)
        }
        return newJsonArray
    }

    fun replaceValuesForClaim169(jsonData: JSONObject): JSONObject {
        CLAIM_169_ROOT_REVERSE_VALUE_MAPPER.forEach { (fieldName, reverseMap) ->
        if (jsonData.has(fieldName)) {
            val originalValue = jsonData.get(fieldName)
            val mappedValue = reverseMap[originalValue]
            if (mappedValue != null) {
            jsonData.put(fieldName, mappedValue)
            }
        }
        }

        CLAIM_169_BIOMETRIC_KEYS.forEach { nestedKey ->
        if (!jsonData.has(nestedKey)) return@forEach

        val nestedObject = jsonData.optJSONObject(nestedKey) ?: return@forEach

        if (
            !nestedObject.has(CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY) ||
            !nestedObject.has(CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY)
        ) {
            return@forEach
        }

        val dataFormatShortCode = nestedObject.opt(CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY) ?: return@forEach

        val subFormatShortCodeValue =
            nestedObject.opt(CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY) ?: return@forEach

        val dataFormatValue =
            CLAIM_169_BIOMETRIC_FORMAT_REVERSE_VALUE_MAPPER[dataFormatShortCode] ?: dataFormatShortCode

        val subFormatValue =
            CLAIM_169_BIOMETRIC_SUB_FORMAT_REVERSE_VALUE_MAPPER[dataFormatValue]?.get(
            subFormatShortCodeValue
            ) ?: subFormatShortCodeValue

        nestedObject.put(CLAIM_169_BIOMETRIC_DATA_FORMAT_KEY, dataFormatValue)
        nestedObject.put(CLAIM_169_BIOMETRIC_DATA_SUB_FORMAT_KEY, subFormatValue)

        jsonData.put(nestedKey, nestedObject)
        }
        return jsonData
    }
}
