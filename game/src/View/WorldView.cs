using System.Collections.Generic;
using DinoPlanet.Core.Sim;
using Godot;

namespace DinoPlanet.Game.View;

/// <summary>
/// Mirrors Core's entities as Godot nodes. Each frame: create nodes for new entities, copy
/// positions and yaw across, remove nodes for despawned ones, and turn events into effects.
/// All nodes live flat under one parent; Core already computes world transforms for attachments.
/// </summary>
public sealed class WorldView
{
    private readonly Node3D _root;
    private readonly AssetFactory _factory;
    private readonly Dictionary<EntityId, Node3D> _nodes = new();
    private readonly HashSet<EntityId> _diedThisFrame = new();
    private readonly Dictionary<EntityId, EntityId> _parentOf = new();

    public WorldView(Node3D parent, AssetFactory factory)
    {
        _factory = factory;
        _root = new Node3D { Name = "Entities" };
        parent.AddChild(_root);
    }

    public bool TryGetNode(EntityId id, out Node3D node) => _nodes.TryGetValue(id, out node!);

    public void Sync(World world)
    {
        _diedThisFrame.Clear();
        foreach (var evt in world.DrainEvents())
        {
            switch (evt)
            {
                case Spawned s when world.TryGet(s.Entity, out var e):
                    CreateNode(e);
                    break;
                case Died d:
                    _diedThisFrame.Add(d.Entity);
                    Effects.Burst(_root, d.At.ToGodot() + Vector3.Up, new Color(1f, 0.6f, 0.2f), 1.5f);
                    break;
                case Despawned d:
                    RemoveNode(d.Entity, animate: IsDying(d.Entity));
                    break;
                case Fired f:
                    Effects.MuzzleFlash(_root, f.Muzzle.ToGodot());
                    break;
                case Damaged dmg when _nodes.TryGetValue(dmg.Target, out var hitNode):
                    Effects.HitPunch(hitNode, world.TryGet(dmg.Target, out var hit) ? hit.Asset.Scale : 1f);
                    break;
            }
        }

        foreach (var e in world.Entities)
        {
            if (!_nodes.TryGetValue(e.Id, out var node)) node = CreateNode(e);
            node.Position = e.Position.ToGodot();
            node.Rotation = new Vector3(0f, e.Yaw, 0f);
        }
    }

    public void Clear()
    {
        foreach (var node in _nodes.Values) node.QueueFree();
        _nodes.Clear();
        _parentOf.Clear();
    }

    private Node3D CreateNode(Entity e)
    {
        if (_nodes.TryGetValue(e.Id, out var existing)) return existing;
        var node = _factory.Create(e.Asset);
        node.Name = $"{e.Asset.Id}_{e.Id.Value}";
        node.Position = e.Position.ToGodot();
        node.Rotation = new Vector3(0f, e.Yaw, 0f);
        _root.AddChild(node);
        _nodes[e.Id] = node;
        if (e.Parent is { } parent) _parentOf[e.Id] = parent;
        return node;
    }

    /// <summary>True if this entity, or anything it was bolted to, died this frame.</summary>
    private bool IsDying(EntityId id)
    {
        for (EntityId? current = id; current is { } c; current = _parentOf.TryGetValue(c, out var p) ? p : null)
        {
            if (_diedThisFrame.Contains(c)) return true;
        }
        return false;
    }

    private void RemoveNode(EntityId id, bool animate)
    {
        if (!_nodes.Remove(id, out var node)) return;
        _parentOf.Remove(id);
        if (!animate)
        {
            node.QueueFree();
            return;
        }

        var tween = node.CreateTween();
        tween.TweenProperty(node, "scale", Vector3.One * 0.01f, 0.35f)
            .SetTrans(Tween.TransitionType.Back).SetEase(Tween.EaseType.In);
        tween.TweenCallback(Callable.From(node.QueueFree));
    }
}
