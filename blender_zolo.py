"""Generate a whimsical abstract creature scene in Blender.

Run from Blender's Scripting workspace, or from a shell:
    blender --background --python blender_whimsical_creature.py

The script builds the model, assigns materials, sets up a studio camera and
lights, and renders ``whimsical_creature.png`` beside the .blend file (or in
the current directory when the file has not been saved).
"""

import bpy
import math
import os
from mathutils import Vector


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials,
                       bpy.data.cameras, bpy.data.lights):
        # Orphaned data from the default scene is safe to remove.
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def material(name, color, metallic=0.0, roughness=0.38):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Specular IOR Level"].default_value = 0.45
    return mat


def smooth(obj, bevel=0.0):
    if obj.type == "MESH":
        for poly in obj.data.polygons:
            poly.use_smooth = True
        if bevel:
            mod = obj.modifiers.new("Soft edges", "BEVEL")
            mod.width = bevel
            mod.segments = 3
    return obj


def uv_sphere(name, location, scale, mat, segments=48, rings=24):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=rings, location=location
    )
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return smooth(obj)


def cylinder_between(name, a, b, radius, mat, vertices=24):
    a, b = Vector(a), Vector(b)
    delta = b - a
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=delta.length,
        location=(a + b) * 0.5
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(delta)
    obj.data.materials.append(mat)
    return smooth(obj, radius * 0.12)


def curve_tube(name, points, radius, mat):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 10
    curve.bevel_depth = radius
    curve.bevel_resolution = 5
    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = co
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def look_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------------------
# Custom rounded meshes
# ---------------------------------------------------------------------------

def make_body(mat):
    """A tapered, upturned sausage generated from elliptical cross-sections."""
    rings, sides = 28, 32
    verts, faces = [], []
    for i in range(rings):
        t = i / (rings - 1)
        x = -2.2 + 4.4 * t
        # Raised ends and a slightly asymmetric silhouette.
        zc = 3.55 + 0.48 * ((2.0 * t - 1.0) ** 2) + 0.06 * math.sin(t * math.pi)
        taper = 0.58 + 0.42 * math.sin(math.pi * t) ** 0.45
        ry = 0.62 * taper
        rz = 0.72 * taper
        for j in range(sides):
            a = 2.0 * math.pi * j / sides
            verts.append((x, ry * math.sin(a), zc + rz * math.cos(a)))
    for i in range(rings - 1):
        for j in range(sides):
            nj = (j + 1) % sides
            a = i * sides + j
            b = i * sides + nj
            c = (i + 1) * sides + nj
            d = (i + 1) * sides + j
            faces.append((a, b, c, d))
    faces.append(tuple(range(sides - 1, -1, -1)))
    start = (rings - 1) * sides
    faces.append(tuple(start + j for j in range(sides)))
    mesh = bpy.data.meshes.new("Curved body mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Curved red body", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return smooth(obj, 0.06)


def make_base(mat):
    """Low three-lobed dome, triangulated as concentric rings."""
    rings, sides = 10, 72
    verts = [(0, 0, 1.22)]
    faces = []
    for i in range(1, rings + 1):
        u = i / rings
        for j in range(sides):
            a = 2 * math.pi * j / sides
            r_edge = 1.48 + 0.23 * math.cos(3 * a)
            r = u * r_edge
            z = 0.22 + 1.0 * (1.0 - u ** 1.45)
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for j in range(sides):
        faces.append((0, 1 + j, 1 + (j + 1) % sides))
    for i in range(rings - 1):
        s0, s1 = 1 + i * sides, 1 + (i + 1) * sides
        for j in range(sides):
            nj = (j + 1) % sides
            faces.append((s0 + j, s1 + j, s1 + nj, s0 + nj))
    bottom_center = len(verts)
    verts.append((0, 0, 0.20))
    last = 1 + (rings - 1) * sides
    for j in range(sides):
        faces.append((bottom_center, last + (j + 1) % sides, last + j))
    mesh = bpy.data.meshes.new("Three lobed base mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Green three-lobed base", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return smooth(obj, 0.05)


def lathe_profile(name, profile, mat, segments=64):
    """Create a surface of revolution; profile is a sequence of (radius, z)."""
    verts, faces = [], []
    for radius, z in profile:
        for i in range(segments):
            a = 2 * math.pi * i / segments
            verts.append((radius * math.cos(a), radius * math.sin(a), z))
    rows = len(profile)
    for r in range(rows - 1):
        for i in range(segments):
            n = (i + 1) % segments
            faces.append((r * segments + i, r * segments + n,
                          (r + 1) * segments + n, (r + 1) * segments + i))
    mesh = bpy.data.meshes.new(name + " mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return smooth(obj)


# ---------------------------------------------------------------------------
# Build the creature
# ---------------------------------------------------------------------------

clear_scene()

red = material("Lacquer red", (0.88, 0.035, 0.015), roughness=0.25)
red2 = material("Nose red", (1.0, 0.015, 0.025), roughness=0.2)
purple = material("Lilac spots", (0.56, 0.25, 0.67), roughness=0.34)
green = material("Lime base", (0.38, 0.75, 0.015), roughness=0.28)
olive = material("Olive decoration", (0.43, 0.48, 0.02), roughness=0.42)
violet = material("Violet post", (0.31, 0.04, 0.48), roughness=0.3)
cyan = material("Blue handle", (0.00, 0.64, 0.86), metallic=0.05, roughness=0.25)
black = material("Glossy black", (0.006, 0.008, 0.010), roughness=0.19)
white = material("Warm white", (0.92, 0.94, 0.93), roughness=0.28)
gold = material("Brushed gold", (0.67, 0.43, 0.11), metallic=0.5, roughness=0.28)
gray = material("Hole gray", (0.23, 0.27, 0.27), roughness=0.4)

make_base(green)
make_body(red)
cylinder_between("Violet neck", (0, 0, 1.12), (0, 0, 3.12), 0.13, violet)

# Purple body markings, pressed into the visible/front side.
body_spots = [
    (-1.45, -0.57, 3.88, .38, .12, .28, -0.25),
    (-0.78, -0.66, 3.28, .43, .12, .25, 0.18),
    (0.20, -0.69, 3.88, .34, .11, .23, -0.1),
    (0.88, -0.66, 3.38, .40, .11, .28, 0.2),
    (1.55, -0.53, 3.95, .32, .10, .25, -0.3),
]
for i, (x, y, z, sx, sy, sz, rot) in enumerate(body_spots):
    spot = uv_sphere(f"Purple body spot {i+1}", (x, y, z), (sx, sy, sz), purple, 32, 16)
    spot.rotation_euler.y = rot

# Bulging eyes and pupils.
for side, pos in (("left", (-1.92, -0.51, 4.15)),
                  ("right", (1.63, -0.55, 4.12))):
    uv_sphere(f"{side} eye", pos, (0.37, 0.28, 0.37), white)
    pupil_pos = (pos[0] + (0.02 if side == "left" else 0.06), pos[1] - 0.275, pos[2] + 0.02)
    uv_sphere(f"{side} pupil", pupil_pos, (0.075, 0.045, 0.075), black, 24, 12)

uv_sphere("Round red nose", (-0.42, -0.92, 3.70), (0.43, 0.40, 0.49), red2)
uv_sphere("Tiny red pore", (-0.82, -0.68, 3.18), (0.09, 0.045, 0.07), red2, 24, 12)

# Decorative olive rings and dot on the green base.
for i, (x, y, z, sx, sz, rot) in enumerate([
    (-0.66, -1.05, .70, .22, .12, -.35),
    (0.16, -1.23, .87, .23, .12, .15),
    (0.72, -1.03, .55, .18, .10, -.25),
]):
    mark = uv_sphere(f"Base marking {i+1}", (x, y, z), (sx, .035, sz), olive, 28, 14)
    mark.rotation_euler.y = rot
uv_sphere("Base dark dot", (0.02, -1.29, .55), (.10, .04, .12), black, 24, 12)

# Left striped wand/arm.
wand_a, wand_b = Vector((-1.02, -0.08, 0.91)), Vector((-3.05, -0.30, 1.78))
segments = 9
for i in range(segments):
    p0 = wand_a.lerp(wand_b, i / segments)
    p1 = wand_a.lerp(wand_b, (i + 1) / segments)
    cylinder_between(f"Striped wand segment {i+1}", p0, p1, 0.095,
                     white if i % 2 == 0 else black, 20)

# Right blue handle and two-tone spherical mallet.
handle_a, handle_b = (0.90, -0.04, 0.90), (2.42, -0.20, 1.82)
cylinder_between("Blue mallet handle", handle_a, handle_b, 0.13, cyan, 24)
head_center = Vector((2.72, -0.20, 2.04))
uv_sphere("Black mallet head", head_center, (0.66, 0.56, 0.66), black)
# A flattened pale cap overlapping the top half gives the toy its two-tone head.
cap = uv_sphere("White mallet cap", head_center + Vector((0, 0, .42)),
                (0.665, 0.565, 0.31), white)
cap.rotation_euler.y = -0.16
for i, (dx, dy, dz, s) in enumerate([
    (-.30, -.52, -.10, .085), (.10, -.56, -.30, .11), (.38, -.46, .08, .08),
    (.30, -.43, .42, .09), (-.25, -.47, .48, .07)
]):
    uv_sphere(f"Mallet dot {i+1}", head_center + Vector((dx, dy, dz)),
              (s, .035, s), gray, 20, 10)

# Black trumpet/stalk rising from the creature.
trumpet = lathe_profile("Black trumpet", [
    (.09, 4.05), (.11, 4.55), (.18, 4.88), (.34, 5.20),
    (.72, 5.39), (.84, 5.47), (.62, 5.56), (.28, 5.56)
], black)

# Gold, slightly wandering stems and round buds.
stems = [
    [(-.35, 0, 5.48), (-.48, .02, 5.98), (-.72, .02, 6.52)],
    [(-.14, 0, 5.51), (-.20, .03, 6.20), (-.18, .02, 6.78)],
    [( .05, 0, 5.52), ( .16, .02, 6.20), ( .33, .02, 6.70)],
    [( .24, 0, 5.50), ( .36, .04, 6.03), ( .63, .02, 6.55)],
    [( .43, 0, 5.48), ( .52, .03, 5.91), ( .78, .02, 6.38)],
]
bud_scales = [(.22,.18,.18), (.28,.20,.19), (.25,.19,.18), (.24,.18,.19), (.18,.16,.20)]
for i, (pts, scl) in enumerate(zip(stems, bud_scales)):
    curve_tube(f"Gold stem {i+1}", pts, 0.045, gold)
    uv_sphere(f"Gold bud {i+1}", pts[-1], scl, gold, 32, 16)


# ---------------------------------------------------------------------------
# Studio, camera, and render
# ---------------------------------------------------------------------------

# Ground plane with softly rounded shadow-catching look.
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0.04))
ground = bpy.context.object
ground.name = "Studio floor"
ground.data.materials.append(material("Studio white", (0.94, 0.94, 0.92), roughness=0.72))

world = bpy.context.scene.world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.93, 0.94, 0.96, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.65

def area_light(name, location, energy, size, color):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0, 0, 3))
    return obj

area_light("Large softbox", (-4.5, -6.0, 9.0), 1100, 5.0, (1.0, .88, .72))
area_light("Cool fill", (5.0, -2.0, 6.0), 750, 4.0, (.70, .84, 1.0))
area_light("Rim light", (1.0, 5.0, 7.0), 950, 3.0, (1.0, .92, .78))

cam_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", cam_data)
bpy.context.collection.objects.link(camera)
camera.location = (8.4, -13.5, 7.0)
cam_data.lens = 57
look_at(camera, (0, 0, 3.3))
bpy.context.scene.camera = camera

scene = bpy.context.scene

# Blender has renamed Eevee's enum more than once.  In particular, official
# Blender 5.x builds expose it as BLENDER_EEVEE again, so checking the version
# number is less reliable than trying the identifiers supported by this build.
def set_first_supported_enum(owner, attribute, candidates):
    """Set the first accepted enum value and return it, or keep the current one."""
    for candidate in candidates:
        try:
            setattr(owner, attribute, candidate)
            return candidate
        except (TypeError, ValueError):
            pass
    return getattr(owner, attribute)


render_engine = set_first_supported_enum(
    scene.render,
    "engine",
    ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES", "BLENDER_WORKBENCH"),
)
scene.render.resolution_x = 700
scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.render.image_settings.color_mode = "RGBA"
color_look = set_first_supported_enum(
    scene.view_settings,
    "look",
    ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Medium High Contrast Punchy"),
)

# Contact shadows and a gentle depth of field make it feel like a small toy.
cam_data.dof.use_dof = True
cam_data.dof.focus_object = bpy.data.objects["Curved red body"]
cam_data.dof.aperture_fstop = 7.0

base_dir = bpy.path.abspath("//") if bpy.data.filepath else os.getcwd()
scene.render.filepath = os.path.join(base_dir, "whimsical_creature.png")

# Comment out this line when iterating interactively in the Blender UI.
bpy.ops.render.render(write_still=True)
print("Rendered:", scene.render.filepath)
print("Render engine:", render_engine, "| Color look:", color_look)
