using System.Numerics;
using DinoPlanet.Core.Spatial;

namespace DinoPlanet.Core.Sim.Behaviors;

/// <summary>Steers from the player's stick / WASD input.</summary>
public sealed class PlayerControlled : IBehavior
{
    public void Update(Entity self, World world, float dt)
    {
        var move = world.Input.Move;
        float amount = MathF.Min(1f, move.Length());
        if (amount < 0.1f) return;
        self.TrySteer(new SteeringRequest(new Vector3(move.X, 0f, move.Y), amount));
    }
}

/// <summary>Heads for the nearest hostile dino it can see, stopping at a comfortable distance.</summary>
public sealed class ChaseNearestHostile : IBehavior
{
    public ChaseNearestHostile(float sightRange = 18f, float stopDistance = 6f)
    {
        SightRange = sightRange;
        StopDistance = stopDistance;
    }

    public float SightRange { get; set; }
    public float StopDistance { get; set; }

    /// <summary>Last target seen, for debugging overlays.</summary>
    public EntityId? Target { get; private set; }

    public void Update(Entity self, World world, float dt)
    {
        var target = world.NearestHostileDino(self.Position, self.Faction, SightRange);
        Target = target?.Id;
        if (target is null) return;

        var toTarget = target.Position - self.Position;
        float dist = MathUtil.DistanceXZ(self.Position, target.Position);
        if (dist <= StopDistance)
        {
            // Close enough: claim steering so lower behaviors don't wander off, but just turn to face.
            self.TrySteer(new SteeringRequest(toTarget, 0f));
            self.Yaw = MathUtil.TurnToward(self.Yaw, MathUtil.YawFromDirection(toTarget),
                MathUtil.DegToRad(world.Tuning.Mover(self.Asset.Id).TurnRateDegrees) * dt);
            return;
        }

        self.TrySteer(new SteeringRequest(toTarget, 1f));
    }
}

/// <summary>Ambles between random points near where it started. A good lowest-priority fallback.</summary>
public sealed class Wander : IBehavior
{
    private Vector3? _home;
    private Vector3? _goal;
    private float _pause;

    public Wander(float radius = 10f, float throttle = 0.4f, float maxPause = 2.5f)
    {
        Radius = radius;
        Throttle = throttle;
        MaxPause = maxPause;
    }

    public float Radius { get; set; }
    public float Throttle { get; set; }
    public float MaxPause { get; set; }

    public void Update(Entity self, World world, float dt)
    {
        _home ??= self.Position;
        if (self.HasSteering)
        {
            _goal = null; // something more important took over; pick a fresh spot afterwards
            return;
        }

        if (_pause > 0f)
        {
            _pause -= dt;
            return;
        }

        if (_goal is null)
        {
            float angle = (float)world.Rng.NextDouble() * MathUtil.Tau;
            float dist = MathF.Sqrt((float)world.Rng.NextDouble()) * Radius;
            _goal = _home.Value + new Vector3(MathF.Cos(angle) * dist, 0f, MathF.Sin(angle) * dist);
        }

        if (MathUtil.DistanceXZ(self.Position, _goal.Value) < 1f)
        {
            _goal = null;
            _pause = (float)world.Rng.NextDouble() * MaxPause;
            return;
        }

        self.TrySteer(new SteeringRequest(_goal.Value - self.Position, Throttle));
    }
}
