// Tunic-style toon shader for Godot 4.x
// Reads the flat vertex colors written by blender_cleanup.py.
// Put outline.gdshader in this material's "Next Pass" for ink outlines.
shader_type spatial;
render_mode cull_back, diffuse_toon, specular_disabled;

// Multiplied with the vertex color. Leave white to use the mesh colors as-is.
uniform vec4 tint : source_color = vec4(1.0);
// Set true if colors look washed out (glTF vertex colors can arrive linear vs sRGB).
uniform bool vertex_color_is_srgb = false;

// Where light turns to shadow, and how soft that edge is.
uniform float shade_threshold : hint_range(-1.0, 1.0) = 0.0;
uniform float shade_softness : hint_range(0.0, 0.5) = 0.04;
// Shadow side keeps this much of the light, tinted (cool shadows = the Tunic look).
uniform vec4 shadow_tint : source_color = vec4(0.45, 0.5, 0.75, 1.0);
uniform float shadow_strength : hint_range(0.0, 1.0) = 0.55;

// Bright edge on the lit side for a little pop.
uniform vec4 rim_color : source_color = vec4(1.0, 0.95, 0.85, 1.0);
uniform float rim_amount : hint_range(0.0, 1.0) = 0.25;
uniform float rim_width : hint_range(0.0, 1.0) = 0.6;

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void fragment() {
	vec3 vc = COLOR.rgb;
	if (vertex_color_is_srgb) {
		vc = srgb_to_linear(vc);
	}
	ALBEDO = vc * tint.rgb;
	ROUGHNESS = 1.0;
}

void light() {
	float ndotl = dot(NORMAL, LIGHT);
	float lit = smoothstep(shade_threshold - shade_softness, shade_threshold + shade_softness, ndotl);
	lit *= ATTENUATION; // shadows from other objects

	// Two flat bands: full light, or tinted shadow. No gradient in between.
	vec3 band = mix(shadow_tint.rgb * (1.0 - shadow_strength), vec3(1.0), lit);
	// Point/spot lights (muzzle flashes) must fade with distance, shadow band included.
	if (!LIGHT_IS_DIRECTIONAL) {
		band *= ATTENUATION;
	}
	DIFFUSE_LIGHT += band * LIGHT_COLOR / PI;

	// Rim only on the lit side.
	float rim = 1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	rim = smoothstep(1.0 - rim_width, 1.0, rim) * lit * rim_amount;
	DIFFUSE_LIGHT += rim * rim_color.rgb * LIGHT_COLOR / PI;
}
