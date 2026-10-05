"""Render the current AquaShift SVG as a five-second monochrome Blender symbol."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

import bpy
from mathutils import Vector


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def segments(data):
    tokens = re.findall(r"[MHCLZ]|-?\d+(?:\.\d+)?", data)
    result, cursor, start, i = [], None, None, 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        count = {"M": 2, "H": 1, "C": 6, "L": 2, "Z": 0}[command]
        values = list(map(float, tokens[i:i + count]))
        i += count
        if command == "M":
            cursor = start = tuple(values)
            continue
        if command == "C":
            c1, c2, end = tuple(values[:2]), tuple(values[2:4]), tuple(values[4:])
        else:
            end = (values[0], cursor[1]) if command == "H" else tuple(values) if command == "L" else start
            if end == cursor:
                continue
            c1 = tuple(a + (b - a) / 3 for a, b in zip(cursor, end))
            c2 = tuple(a + 2 * (b - a) / 3 for a, b in zip(cursor, end))
        result.append((cursor, c1, c2, end))
        cursor = end
    if not result or result[-1][3] != start:
        raise ValueError("The source mark must contain a closed path")
    return result


def make_symbol(svg, material, parent):
    paths = ET.parse(svg).getroot().findall("{http://www.w3.org/2000/svg}path")
    if len(paths) != 2 or paths[0].get("transform") != "translate(-4 -4)" or paths[1].get("transform") != "translate(4 4) rotate(180 64 64)":
        raise ValueError("Current mark transforms changed; review the geometry before rendering")
    for index, path in enumerate(paths):
        source = segments(path.attrib["d"])
        def point(p):
            x, y = (p[0] - 4, p[1] - 4) if index == 0 else (132 - p[0], 132 - p[1])
            return ((x - 64) / 24, (64 - y) / 24, 0)
        curve = bpy.data.curves.new(f"SVG counterform {index + 1}", "CURVE")
        curve.dimensions = "2D"
        curve.resolution_u = 64
        curve.fill_mode = "BOTH"
        curve.extrude = .075
        curve.bevel_depth = .012
        curve.bevel_resolution = 4
        spline = curve.splines.new("BEZIER")
        spline.bezier_points.add(len(source) - 1)
        spline.use_cyclic_u = True
        for n, segment in enumerate(source):
            p = spline.bezier_points[n]
            p.handle_left_type = p.handle_right_type = "FREE"
            p.co = point(segment[0])
            p.handle_left = point(source[n - 1][2])
            p.handle_right = point(segment[1])
        obj = bpy.data.objects.new(f"AquaShift counterform {index + 1}", curve)
        bpy.context.collection.objects.link(obj)
        obj.data.materials.append(material)
        obj.parent = parent


def light(name, location, power, size):
    data = bpy.data.lights.new(name, "AREA")
    data.energy, data.shape, data.size = power, "DISK", size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0)) - obj.location).to_track_quat("-Z", "Y").to_euler()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--frames", default="1,60,120", help="Comma-separated preview frames, or all")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    output, blend, svg = args.output.resolve(), args.blend.resolve(), args.svg.resolve()
    if str(output).startswith("/Volumes/") and not os.path.ismount(Path("/Volumes") / output.parts[2]):
        raise RuntimeError("Render volume is not mounted")
    output.mkdir(parents=True, exist_ok=True)
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    scene.render.threads_mode, scene.render.threads = "FIXED", 2
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start, scene.frame_end = 1, 120
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "BW"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.render.dither_intensity = 0
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0, 0, 0, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = 0
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = .4
    material = bpy.data.materials.new("Satin white metal")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (.72, .72, .72, 1)
    bsdf.inputs["Metallic"].default_value = .42
    bsdf.inputs["Roughness"].default_value = .32
    bsdf.inputs["Coat Weight"].default_value = .18
    parent = bpy.data.objects.new("AquaShift symbol", None)
    bpy.context.collection.objects.link(parent)
    make_symbol(svg, material, parent)
    for frame, degrees in ((1, -15), (120, 0)):
        parent.rotation_euler.y = math.radians(degrees)
        parent.keyframe_insert(data_path="rotation_euler", frame=frame)
    light("Broad upper left softbox", (-3, 5, 7), 1400, 7)
    light("Right fill", (4, -1, 6), 500, 6)
    light("Low edge rake", (-5, -4, 2), 400, 3)
    camera_data = bpy.data.cameras.new("Front orthographic camera")
    camera_data.type, camera_data.ortho_scale = "ORTHO", 22
    camera = bpy.data.objects.new("Front orthographic camera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0, -1.1, 20)
    camera.rotation_euler = (0, 0, 0)
    scene.camera = camera
    scene["Source mark SHA-256"] = digest(svg)
    scene["Geometry"] = "Source cubic Bézier curves with exact SVG transforms; shallow extrusion and bevel"
    scene["Evidence status"] = "Brand animation only; no physical or operational claims"
    scene.render.filepath = str(output / "frame-")
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    selected = list(range(1, 121)) if args.frames == "all" else [int(n) for n in args.frames.split(",")]
    if any(n < 1 or n > 120 for n in selected):
        raise ValueError("Frame outside 1–120")
    metadata = {"blender_version": bpy.app.version_string, "engine": scene.render.engine,
                "source_sha256": digest(Path(__file__)), "svg_sha256": digest(svg),
                "blend_sha256": digest(blend), "invocation": sys.argv, "width": 1920,
                "height": 1080, "fps": 24, "duration_seconds": 5, "threads": 2,
                "eevee_samples": 32, "dither_intensity": 0, "png_color_mode": "BW",
                "geometry": scene["Geometry"], "frames": []}
    for frame in selected:
        scene.frame_set(frame)
        target = output / f"frame-{frame:04d}.png"
        scene.render.filepath = str(target)
        bpy.ops.render.render(write_still=True)
        metadata["frames"].append({"frame": frame, "path": str(target), "sha256": digest(target)})
    metadata["render_status"] = "Blender returned successfully from every requested render"
    receipt = output / ("render-all.json" if args.frames == "all" else "render-previews.json")
    receipt.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"blend": str(blend), "receipt": str(receipt), "rendered_frames": selected}))


if __name__ == "__main__":
    main()
