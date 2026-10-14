using System.Numerics;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace DinoPlanet.Core.Data;

/// <summary>Shared JSON settings for every data file (asset registry, tuning, levels).</summary>
public static class Json
{
    public static readonly JsonSerializerOptions Options = Create();

    private static JsonSerializerOptions Create()
    {
        var o = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,
            WriteIndented = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        };
        o.Converters.Add(new Vector3ArrayConverter());
        o.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.CamelCase));
        return o;
    }

    public static T Parse<T>(string json) =>
        JsonSerializer.Deserialize<T>(json, Options)
        ?? throw new JsonException($"Could not parse {typeof(T).Name}: document was empty.");
}

/// <summary>Reads and writes <see cref="Vector3"/> as a compact [x, y, z] array.</summary>
public sealed class Vector3ArrayConverter : JsonConverter<Vector3>
{
    public override Vector3 Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
        if (reader.TokenType != JsonTokenType.StartArray)
            throw new JsonException("Expected a vector as [x, y, z].");

        Span<float> v = stackalloc float[3];
        int i = 0;
        while (reader.Read() && reader.TokenType != JsonTokenType.EndArray)
        {
            if (i >= 3) throw new JsonException("A vector has at most 3 numbers.");
            v[i++] = reader.GetSingle();
        }
        if (i != 3) throw new JsonException("A vector needs exactly 3 numbers.");
        return new Vector3(v[0], v[1], v[2]);
    }

    public override void Write(Utf8JsonWriter writer, Vector3 value, JsonSerializerOptions options)
    {
        writer.WriteStartArray();
        writer.WriteNumberValue(value.X);
        writer.WriteNumberValue(value.Y);
        writer.WriteNumberValue(value.Z);
        writer.WriteEndArray();
    }
}
