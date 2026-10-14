using System.Numerics;

namespace DinoPlanet.Core.Procgen;

/// <summary>One placed prop from a scatter pass.</summary>
public readonly record struct Placement(string AssetId, Vector3 Position, float Yaw);

/// <summary>A prop type and how much of it to scatter.</summary>
public sealed record ScatterLayer(string AssetId, float Weight = 1f);

/// <summary>
/// Seeded Poisson-disk scatter (Bridson's algorithm): fills an area with props that never overlap
/// and never clump, then picks a prop type for each point by weight. Same seed, same layout.
/// This is the starter for level generation; biomes, paths and clearings build on top of it.
/// </summary>
public static class Scatter
{
    public static List<Placement> Generate(
        int seed,
        float halfSize,
        IReadOnlyList<ScatterLayer> layers,
        float minSpacing,
        Func<Vector2, bool>? keepOut = null,
        int attemptsPerPoint = 20)
    {
        if (layers.Count == 0) return new List<Placement>();
        if (minSpacing <= 0f) throw new ArgumentOutOfRangeException(nameof(minSpacing));

        var rng = new Random(seed);
        float size = halfSize * 2f;
        float cell = minSpacing / MathF.Sqrt(2f);
        int gridW = (int)MathF.Ceiling(size / cell);
        var grid = new int[gridW * gridW];
        Array.Fill(grid, -1);

        var points = new List<Vector2>();
        var active = new List<int>();

        int CellIndex(Vector2 p)
        {
            int gx = Math.Clamp((int)((p.X + halfSize) / cell), 0, gridW - 1);
            int gy = Math.Clamp((int)((p.Y + halfSize) / cell), 0, gridW - 1);
            return gy * gridW + gx;
        }

        bool Fits(Vector2 p)
        {
            if (p.X < -halfSize || p.X >= halfSize || p.Y < -halfSize || p.Y >= halfSize) return false;
            int gx = (int)((p.X + halfSize) / cell), gy = (int)((p.Y + halfSize) / cell);
            for (int y = Math.Max(0, gy - 2); y <= Math.Min(gridW - 1, gy + 2); y++)
            for (int x = Math.Max(0, gx - 2); x <= Math.Min(gridW - 1, gx + 2); x++)
            {
                int idx = grid[y * gridW + x];
                if (idx >= 0 && Vector2.DistanceSquared(points[idx], p) < minSpacing * minSpacing) return false;
            }
            return true;
        }

        void Add(Vector2 p)
        {
            points.Add(p);
            grid[CellIndex(p)] = points.Count - 1;
            active.Add(points.Count - 1);
        }

        Add(new Vector2((float)(rng.NextDouble() * size - halfSize), (float)(rng.NextDouble() * size - halfSize)));

        while (active.Count > 0)
        {
            int ai = rng.Next(active.Count);
            var origin = points[active[ai]];
            bool placed = false;
            for (int k = 0; k < attemptsPerPoint; k++)
            {
                float angle = (float)(rng.NextDouble() * Math.PI * 2);
                float r = minSpacing * (1f + (float)rng.NextDouble());
                var candidate = origin + new Vector2(MathF.Cos(angle) * r, MathF.Sin(angle) * r);
                if (!Fits(candidate)) continue;
                Add(candidate);
                placed = true;
                break;
            }
            if (!placed) active.RemoveAt(ai);
        }

        float totalWeight = layers.Sum(l => l.Weight);
        var result = new List<Placement>(points.Count);
        foreach (var p in points)
        {
            if (keepOut?.Invoke(p) == true) continue;
            float pick = (float)rng.NextDouble() * totalWeight;
            var layer = layers[^1];
            foreach (var l in layers)
            {
                pick -= l.Weight;
                if (pick <= 0f) { layer = l; break; }
            }
            float yaw = (float)(rng.NextDouble() * Math.PI * 2 - Math.PI);
            result.Add(new Placement(layer.AssetId, new Vector3(p.X, 0f, p.Y), yaw));
        }
        return result;
    }
}
