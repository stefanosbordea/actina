"""AquaShift symbolic 3D explanation. Run with Blender --background --python this_file -- ..."""
import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def material(name, color, metallic=0.0, roughness=.35, emission=0.0, alpha=1.0):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    result.diffuse_color = (*color, alpha)
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, alpha)
    shader.inputs["Metallic"].default_value = metallic
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Alpha"].default_value = alpha
    for key in ("Emission Color", "Emission"):
        if key in shader.inputs:
            shader.inputs[key].default_value = (*color, 1)
    if "Emission Strength" in shader.inputs:
        shader.inputs["Emission Strength"].default_value = emission
    if alpha < 1:
        if hasattr(result, "surface_render_method"):
            result.surface_render_method = "DITHERED"
        elif hasattr(result, "blend_method"):
            result.blend_method = "BLEND"
    return result


def finish(obj, name, surface, bevel=0):
    obj.name = name
    obj.data.materials.append(surface)
    if bevel:
        edge = obj.modifiers.new("Soft manufactured edges", "BEVEL")
        edge.width = bevel
        edge.segments = 3
    if obj.type == "MESH":
        for polygon in obj.data.polygons:
            polygon.use_smooth = len(polygon.vertices) > 4
    return obj


def box(name, location, dimensions, surface, bevel=.06):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, surface, bevel)


def cylinder(name, location, radius, depth, surface, rotation=(0, 0, 0), vertices=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location,
                                      rotation=rotation)
    obj = finish(bpy.context.object, name, surface, .025)
    for polygon in obj.data.polygons:
        polygon.use_smooth = len(polygon.vertices) == 4
    return obj


def sphere(name, location, radius, surface):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location)
    obj = finish(bpy.context.object, name, surface)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def ring(name, location, radius, thickness, surface, rotation=(0, 0, 0)):
    bpy.ops.mesh.primitive_torus_add(major_segments=64, minor_segments=12, location=location,
                                    major_radius=radius, minor_radius=thickness, rotation=rotation)
    obj = finish(bpy.context.object, name, surface)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    return obj


def pipe(name, points, surface, width=.065):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 12
    curve.bevel_depth = width
    curve.bevel_resolution = 4
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, coordinates in zip(spline.points, points):
        point.co = (*coordinates, 1)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(surface)
    return obj


def aim(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def light(name, location, target, energy, color, size=5):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    aim(obj, target)
    return obj


def path_position(points, progress):
    lengths = [(Vector(b) - Vector(a)).length for a, b in zip(points, points[1:])]
    distance = (progress % 1) * sum(lengths)
    for a, b, length in zip(points, points[1:], lengths):
        if distance <= length:
            direction = Vector(b) - Vector(a)
            return Vector(a) + direction * distance / length, direction.normalized()
        distance -= length
    return Vector(points[-1]), (Vector(points[-1]) - Vector(points[-2])).normalized()


def flow(name, points, surface, count, frames, cycles=3, active=True):
    for number in range(count):
        bpy.ops.object.empty_add(type="PLAIN_AXES")
        token = bpy.context.object
        token.name = f"{name} directional marker {number + 1}"
        shaft = cylinder(name + " arrow shaft", (0, 0, -.045), .028, .14, surface, vertices=16)
        shaft.parent = token
        bpy.ops.mesh.primitive_cone_add(vertices=20, radius1=.075, radius2=0, depth=.12, location=(0, 0, .075))
        tip = finish(bpy.context.object, name + " arrow head", surface)
        tip.parent = token
        if not active:
            token.scale = (0, 0, 0)
        for frame in range(1, frames + 1):
            progress = (frame - 1) * cycles / frames + number / count
            location, direction = path_position(points, progress)
            token.location = location
            token.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
            token.keyframe_insert("location", frame=frame)
            token.keyframe_insert("rotation_euler", frame=frame)
        if token.animation_data and token.animation_data.action:
            # Dense frames make the wrapped path explicit and keep both Blender4/5 animation APIs portable.
            action = token.animation_data.action
            if hasattr(action, "fcurves"):
                for curve in action.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation = "LINEAR"


def solar_panel(x, y, surfaces):
    tilt = math.radians(16)
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(x, y, .62), rotation=(tilt, 0, 0))
    assembly = bpy.context.object
    assembly.name = "Solar photovoltaic panel"
    frame = box("Panel aluminium frame", (0, 0, 0), (1.37, .91, .07), surfaces["silver"], .035)
    frame.parent = assembly
    face = box("Photovoltaic graphite glass", (0, 0, .046), (1.27, .81, .035), surfaces["panel"], .018)
    face.parent = assembly
    for xx in [-.42, -.21, 0, .21, .42]:
        line = box("Panel cell conductor", (xx, 0, .067), (.007, .79, .003), surfaces["cell"], 0)
        line.parent = assembly
    for yy in [-.27, 0, .27]:
        line = box("Panel cell row", (0, yy, .067), (1.25, .007, .003), surfaces["cell"], 0)
        line.parent = assembly
    for dx in [-.49, .49]:
        cylinder("Solar panel support", (x + dx, y, .32), .035, .56, surfaces["silver"], vertices=16)


def house(x, y, size, surfaces, evening):
    box("Mediterranean home", (x, y, .58 * size), (1.25 * size, .98 * size, 1.15 * size), surfaces["white"], .04)
    box("Home flat roof", (x, y, 1.19 * size), (1.34 * size, 1.08 * size, .15 * size), surfaces["roof"], .035)
    box("Roof solar water heater", (x + .25 * size, y, 1.35 * size), (.36 * size, .45 * size, .12 * size), surfaces["silver"], .02)
    for dx in [-.33, .33]:
        box("Home window", (x + dx * size, y - .497 * size, .68 * size), (.22 * size, .015, .30 * size),
            surfaces["windows_night"] if evening else surfaces["windows_day"], .018)
    box("Home front door", (x, y - .498 * size, .31 * size), (.24 * size, .02, .61 * size), surfaces["trim"], .018)
    box("Home front step", (x, y - .72 * size, .055), (.46 * size, .46 * size, .10), surfaces["white"], .035)


def tank_cutaway(x, y, surface):
    vertices, faces = [], []
    for step in range(65):
        angle = math.radians(2 + 230 * step / 64)
        for radius, z in [(1.32, .30), (1.32, 3.0), (1.28, .30), (1.28, 3.0)]:
            vertices.append((x + radius * math.cos(angle), y + radius * math.sin(angle), z))
    for step in range(64):
        a, b = step * 4, (step + 1) * 4
        faces.extend([(a, b, b + 1, a + 1), (a + 2, a + 3, b + 3, b + 2),
                      (a + 1, b + 1, b + 3, a + 3), (a, a + 2, b + 2, b)])
    faces.extend([(0, 1, 3, 2), (256, 258, 259, 257)])
    mesh = bpy.data.meshes.new("Industrial tank cutaway mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("Storage tank with explanatory cutaway", mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(surface)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return obj


def build_scene(args):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    frames = round(args.duration * args.fps)
    evening = args.act == "evening"
    fill_start, fill_end = {"overview": (.31, .82), "storage": (.82, .88), "evening": (.88, .39)}[args.act]
    surfaces = {
        "stage": material("Charcoal enamel", (.035,) * 3, .20, .35),
        "floor": material("Black studio", (.008,) * 3, 0, .55),
        "white": material("Mineral white", (.70,) * 3, .06, .3),
        "silver": material("Brushed aluminium", (.38,) * 3, .80, .22),
        "trim": material("Graphite trim", (.085,) * 3, .45, .23),
        "water": material("Water graphite reflection", (.15,) * 3, .32, .16),
        "sea": material("Sea intake reflection", (.055,) * 3, .35, .16),
        "panel": material("Photovoltaic black glass", (.018,) * 3, .67, .15),
        "cell": material("Panel conductors", (.25,) * 3, .50, .20),
        "energy": material("Solar electricity luminous white", (.95,) * 3, .15, .22, 3.0),
        "water_flow": material("Water flow luminous white", (.80,) * 3, .1, .2, 1.6),
        "roof": material("Graphite roof", (.12,) * 3, .3, .3),
        "windows_day": material("Dark window glass", (.02,) * 3, .6, .16),
        "windows_night": material("Inhabited windows white", (.8,) * 3, .05, .35, 3),
        "tank_wall": material("Tank ceramic coated wall", (.55,) * 3, .42, .27)}

    box("Floating infrastructure platform", (0, 0, -.31), (14.8, 8.4, .55), surfaces["stage"], .25)
    box("Graphite platform reveal", (0, 0, -.59), (14.35, 7.96, .10), surfaces["trim"], .17)
    box("Studio ground", (0, 0, -.84), (200, 200, .1), surfaces["floor"], 0)
    # The sea basin, plant, storage and homes are conceptual geometry, not a mapped real installation.
    box("Sea intake basin edge", (-5.15, 2.45, .075), (3.0, 1.9, .18), surfaces["silver"], .11)
    box("Sea water surface", (-5.15, 2.45, .174), (2.8, 1.7, .04), surfaces["sea"], .08)
    for number in range(4):
        ripple = ring("Intake surface ripple", (-5.4, 2.4, .198), .16 + number * .17, .008, surfaces["water"])
        ripple.scale.z = .2
    for xx in [-5.7, -4.05, -2.4]:
        for yy in [-2.9, -1.55]:
            solar_panel(xx, yy, surfaces)
    pipe("Solar collection cable", [(-5.7, -3.4, .12), (-2.1, -3.4, .12), (-2.1, -1.1, .12), (-1.1, -1.1, .40)], surfaces["silver"], .035)

    box("Desalination building", (-.55, .85, .68), (3.0, 2.3, 1.30), surfaces["white"], .10)
    box("Plant roof", (-.55, .85, 1.37), (3.2, 2.5, .18), surfaces["roof"], .055)
    box("Plant graphite front stripe", (-.55, -.307, .93), (2.83, .025, .12), surfaces["trim"], .015)
    for x in [-1.48, -.62, .24]:
        box("Plant glazed service window", (x, -.316, .55), (.59, .024, .42), surfaces["windows_day"], .025)
    for x in [-1.2, -.4, .4]:
        box("Plant roof vent", (x, 1.22, 1.56), (.42, .54, .22), surfaces["silver"], .025)
        for y in [1.02, 1.12, 1.22, 1.32, 1.42]:
            box("Vent louvre", (x, y, 1.678), (.34, .019, .018), surfaces["roof"], .005)
    box("Membrane equipment rack", (-.48, -.82, .19), (2.45, .57, .30), surfaces["silver"], .025)
    for z in [.36, .64]:
        cylinder("Reverse osmosis membrane housing", (-.48, -.83, z), .105, 2.10, surfaces["white"], (0, math.pi / 2, 0))
        for x in [-1.40, .43]:
            ring("Membrane housing end clamp", (x, -.83, z), .11, .026, surfaces["trim"], (0, math.pi / 2, 0))
    box("High pressure pump base", (-2.29, .02, .16), (.72, .66, .24), surfaces["silver"], .04)
    cylinder("Pump motor", (-2.29, -.04, .40), .17, .42, surfaces["trim"], (math.pi / 2, 0, 0))
    cylinder("Pump casing", (-2.29, .19, .40), .22, .16, surfaces["silver"], (math.pi / 2, 0, 0))
    box("Plant power cabinet", (-1.97, -1.13, .50), (.36, .28, .82), surfaces["roof"], .025)
    box("Cabinet energy indicator", (-1.97, -1.276, .71), (.14, .01, .11), surfaces["energy"], .01)

    tank_x, tank_y = 2.58, 1.04
    cylinder("Tank foundation", (tank_x, tank_y, .14), 1.43, .28, surfaces["silver"])
    tank_cutaway(tank_x, tank_y, surfaces["tank_wall"])
    for z in [.29, 1.71, 3.01]:
        ring("Tank stainless rim", (tank_x, tank_y, z), 1.34, .046, surfaces["silver"])
    for angle in [0, math.pi / 2, math.pi, 3 * math.pi / 2]:
        cylinder("Tank structural rail", (tank_x + 1.35 * math.cos(angle), tank_y + 1.35 * math.sin(angle), 1.65),
                 .031, 2.72, surfaces["silver"], vertices=16)
    water = cylinder("Illustrative stored drinking water", (tank_x, tank_y, 1.0), 1.27, 1.0, surfaces["water"])
    for frame, fraction in [(1, fill_start), (frames, fill_end)]:
        height = 2.66 * fraction
        water.scale.z = height
        water.location.z = .30 + height / 2
        water.keyframe_insert("scale", frame=frame)
        water.keyframe_insert("location", frame=frame)
    # A bright waterline helps viewers read filling without showing a fabricated volume number.
    waterline = ring("Stored water surface highlight", (tank_x, tank_y, 1.0), 1.22, .018, surfaces["water_flow"])
    for frame, fraction in [(1, fill_start), (frames, fill_end)]:
        waterline.location.z = .30 + 2.66 * fraction + .005
        waterline.keyframe_insert("location", frame=frame)
    box("Tank access ladder side", (tank_x - 1.3, tank_y + .48, 1.54), (.045, .05, 2.73), surfaces["silver"], .005)
    for z in [i * .22 + .32 for i in range(12)]:
        box("Tank ladder rung", (tank_x - 1.28, tank_y + .62, z), (.055, .34, .027), surfaces["silver"], .005)

    house(5.16, -1.58, 1.0, surfaces, evening)
    house(5.82, .01, .8, surfaces, evening)
    house(5.08, 2.1, .9, surfaces, evening)
    box("Water distribution manifold", (3.73, -2.77, .16), (.75, .34, .22), surfaces["silver"], .035)

    intake = [(-3.88, 2.45, .26), (-2.29, 2.45, .26), (-2.29, .18, .43)]
    produced = [(.63, -.83, .55), (1.01, -.83, .55), (1.01, -.15, .55), (1.18, .30, 2.80), (2.10, .30, 2.80)]
    delivered = [(2.58, -.32, .47), (2.58, -2.77, .31), (4.46, -2.77, .31), (5.16, -2.3, .31)]
    energy = [(-4.05, -2.23, .79), (-3.45, -2.23, .79), (-2.49, -1.84, .79), (-1.97, -1.13, .86)]
    for name, points in [("Seawater intake pipe", intake), ("Fresh water transfer pipe", produced), ("Town distribution pipe", delivered)]:
        pipe(name, points, surfaces["silver"], .078)
        pipe(name + " water indicator", [(x, y, z + .041) for x, y, z in points], surfaces["water"], .033)
    energy_path = pipe("Solar electricity illustration", energy, surfaces["energy"], .015)
    energy_path.hide_render = evening
    flow("Solar electricity", energy, surfaces["energy"], 5, frames, 3, not evening)
    flow("Intake water", [(x, y, z + .13) for x, y, z in intake], surfaces["water_flow"], 4, frames, 3, not evening)
    flow("Produced drinking water", [(x, y, z + .13) for x, y, z in produced], surfaces["water_flow"], 5, frames, 3, not evening)
    flow("Evening stored water delivery", [(x, y, z + .13) for x, y, z in delivered], surfaces["water_flow"], 6, frames, 3,
         evening or args.act == "overview")
    # Existing electrical/water infrastructure is represented conceptually, without claiming an installed connection.
    sun = sphere("Symbolic sun", (-5.75, .25, 3.45), .35, surfaces["energy"])
    if args.act != "overview":
        sun.hide_render = True

    light("Large soft key", (-5, -5, 10), (0, 0, 0), 1550 if not evening else 340, (1,) * 3, 6)
    light("White rim", (3, 5, 7), (0, 0, 1), 1100 if not evening else 800, (1,) * 3, 5)
    light("Camera side fill", (3, -6, 5), (0, 0, 1), 550 if not evening else 250, (1,) * 3, 7)
    if evening:
        light("Neighbourhood evening light", (6, -1, 3), (5, 0, 0), 170, (1,) * 3, 3)
    world = bpy.data.worlds.new("Charcoal studio ambience")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (.025, .025, .025, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .35 if not evening else .20
    bpy.context.scene.world = world

    camera_data = bpy.data.cameras.new("AquaShift cinematic orthographic camera")
    camera = bpy.data.objects.new(camera_data.name, camera_data)
    bpy.context.collection.objects.link(camera)
    camera_data.type = "ORTHO"
    if args.act == "storage":
        start, end, target, scale = (9, -13, 10), (8.3, -12.5, 9.5), (.7, .3, 1.25), 13.5
    elif evening:
        start, end, target, scale = (11, -14, 10.5), (10.2, -14.5, 10.4), (.35, -.05, .75), 18.5
    else:
        start, end, target, scale = (10, -14.5, 11), (10.6, -14, 10.7), (0, .0, .8), 18.7
    camera_data.ortho_scale = scale
    for frame, position in [(1, start), (frames, end)]:
        camera.location = position
        aim(camera, target)
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
    bpy.context.scene.camera = camera
    scene = bpy.context.scene
    for engine in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"]:
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 48
        scene.cycles.use_denoising = True
    if hasattr(scene, "eevee"):
        for attribute, value in [("taa_render_samples", args.samples), ("taa_samples", args.samples),
                                 ("use_gtao", True), ("gtao_distance", 3), ("gtao_factor", 1.3)]:
            if hasattr(scene.eevee, attribute):
                setattr(scene.eevee, attribute, value)
    scene.render.resolution_x, scene.render.resolution_y = args.width, args.height
    scene.render.resolution_percentage = 100
    scene.render.fps = args.fps
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.render.film_transparent = False
    scene.frame_start, scene.frame_end = 1, frames
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        pass
    scene.view_settings.exposure = .40
    compositor = bpy.data.node_groups.new("AquaShift glow finish", "CompositorNodeTree")
    compositor.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    scene.compositing_node_group = compositor
    nodes = compositor.nodes
    layers = nodes.new("CompositorNodeRLayers")
    glow = nodes.new("CompositorNodeGlare")
    glow.inputs["Type"].default_value = "Fog Glow"
    glow.inputs["Quality"].default_value = "High"
    glow.inputs["Threshold"].default_value = 1.2
    glow.inputs["Strength"].default_value = .15
    glow.inputs["Size"].default_value = .3
    composite = nodes.new("NodeGroupOutput")
    compositor.links.new(layers.outputs["Image"], glow.inputs["Image"])
    compositor.links.new(glow.outputs["Image"], composite.inputs["Image"])
    scene["AquaShift evidence status"] = "Symbolic concept visualization; not plant footage, measured curtailment or physical test results"
    scene["Original concept"] = "Loucas Louka: absorb otherwise curtailed solar in water production, store water for later"
    scene["Roadmap development"] = "Stefanos Bordea: AquaShift competition roadmap"
    scene["Visual style"] = "Monochrome: equal-channel charcoal, white and graphite materials and lighting"
    scene["Illustrated water fractions"] = f"Illustrative {fill_start}–{fill_end} for this act. No actual volumes represented."
    return scene


def main():
    arguments = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--act", choices=["overview", "storage", "evening"], required=True)
    parser.add_argument("--duration", type=float, default=9)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--frames", help="Comma-separated still frames; otherwise render full animation")
    args = parser.parse_args(arguments)
    if args.duration <= 0 or args.fps <= 0 or min(args.width, args.height) <= 0:
        raise ValueError("Positive duration, frame rate and resolution required")
    output = args.output.resolve()
    if str(output).startswith("/Volumes/"):
        volume = Path("/Volumes") / output.parts[2]
        if not os.path.ismount(volume):
            raise RuntimeError(f"Build volume is not mounted: {volume}")
    elif not output.parent.is_dir():
        raise RuntimeError("Output parent must already exist; no implicit mount-point creation")
    directory = output / args.act
    directory.mkdir(parents=True, exist_ok=True)
    scene = build_scene(args)
    scene.render.filepath = str(directory / "frame-")
    blend = directory / f"aquashift-{args.act}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    source = Path(__file__).read_bytes()
    (directory / "scene-source.py").write_bytes(source)
    metadata = {"blender_version": bpy.app.version_string, "engine": scene.render.engine,
                "act": args.act, "fps": args.fps, "duration_s": args.duration,
                "width": args.width, "height": args.height, "frames": scene.frame_end,
                "source_sha256": hashlib.sha256(source).hexdigest(),
                "blend_sha256": hashlib.sha256(blend.read_bytes()).hexdigest(),
                "evidence_status": scene["AquaShift evidence status"], "invocation": sys.argv}
    metadata["visual_style"] = scene["Visual style"]
    if args.frames:
        selected = [int(frame) for frame in args.frames.split(",")]
        if any(frame < 1 or frame > scene.frame_end for frame in selected):
            raise ValueError("Selected still frame outside animation range")
        for frame in selected:
            scene.frame_set(frame)
            scene.render.filepath = str(directory / f"frame-{frame:04d}.png")
            bpy.ops.render.render(write_still=True)
        metadata["rendered_frames"] = selected
    else:
        bpy.ops.render.render(animation=True)
        metadata["rendered_frames"] = list(range(1, scene.frame_end + 1))
    metadata["render_exit_status"] = "Blender returned from render operation successfully"
    (directory / "render-manifest.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"blend": str(blend), "engine": scene.render.engine,
                      "rendered_frames": len(metadata["rendered_frames"]), "output": str(directory)}))


if __name__ == "__main__":
    main()
