package io.mosip.pixelpass.utils

import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

fun JSONObject.toMapWithKeyAndValueMapper(
  keyMapper: Map<String, Any> = emptyMap(),
  valueMapper: Map<String, Map<Any, Any>> = emptyMap()
): Map<Any, Any?> {

  val normalizedKeyMapper: Map<String, Any> = keyMapper.mapKeys { it.key.toLowerCase(Locale.ROOT) }

  val normalizedValueMapper: Map<String, Map<Any, Any>> =
    valueMapper
      .mapKeys { it.key.toLowerCase(Locale.ROOT) }
      .mapValues { (_, mapper) ->
        mapper.mapKeys { entry ->
          val key = entry.key
          if (key is String) key.toLowerCase(Locale.ROOT) else key
        }
      }

  val map = mutableMapOf<Any, Any?>()
  val keys = this.keys()

  while (keys.hasNext()) {
    val originalKey = keys.next() as String
    val normalizedKey = originalKey.toLowerCase(Locale.ROOT)

    val newKey: Any = normalizedKeyMapper[normalizedKey] ?: originalKey

    val originalValue = this.get(originalKey)

    val fieldValueMapper = normalizedValueMapper[normalizedKey]

    var processedValue: Any? =
      if (originalValue != JSONObject.NULL && fieldValueMapper != null) {
        val lookupValue =
          if (originalValue is String) originalValue.toLowerCase(Locale.ROOT) else originalValue

        fieldValueMapper[lookupValue] ?: originalValue
      } else {
        originalValue
      }

    processedValue =
      when (processedValue) {
        is JSONObject -> processedValue.toMapWithKeyAndValueMapper(keyMapper, valueMapper)

        is JSONArray -> processedValue.toListWithKeyAndValueMapper(keyMapper, valueMapper)

        JSONObject.NULL -> null
        else -> processedValue
      }

    map[newKey] = processedValue
  }

  return map
}

fun JSONArray.toListWithKeyAndValueMapper(
  keyMapper: Map<String, Any> = emptyMap(),
  valueMapper: Map<String, Map<Any, Any>> = emptyMap(),
): List<Any?> {

  val list = mutableListOf<Any?>()

  for (i in 0 until this.length()) {
    val processedValue: Any? =
      when (val value = this.get(i)) {
        is JSONObject -> value.toMapWithKeyAndValueMapper(keyMapper, valueMapper)
        is JSONArray -> value.toListWithKeyAndValueMapper(keyMapper, valueMapper)
        JSONObject.NULL -> null
        else -> value
      }
    list.add(processedValue)
  }

  return list
}