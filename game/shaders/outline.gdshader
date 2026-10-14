// Inverted-hull ink outline for Godot 4.x.
// Use as the "Next Pass" material of toon.gdshader.
// Works best on smooth-shaded meshes (blender_cleanup.py default); on --flat meshes
// the outline can split at hard edges.
shader_type spatial;
render_mode cull_front, unshaded;

uniform vec4 outline_color : source_color = vec4(0.08, 0.07, 0.1, 1.0);
// Thickness in world units (compensates for the node's scale).
uniform float outline_width : hint_range(0.0, 0.1) = 0.015;

void vertex() {
	VERTEX += NORMAL * outline_width / max(length(MODEL_MATRIX[0].xyz), 0.0001);
}

void fragment() {
	ALBEDO = outline_color.rgb;
}
