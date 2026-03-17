"""
Technical Direction Assignment: Radiance Field & Character Batch Renderer
1. Imports Point Clouds (.ply) and applies RadianceField Geometry Nodes.
2. Imports FBX Characters and sets up TikTok-style (9:16) camera tracking.
3. Batch renders 20 combinations (4 point clouds x 5 characters).
"""

import bpy
import typer
import os
from pathlib import Path
from typing import Optional
from mathutils import Vector
from typing_extensions import Annotated

app = typer.Typer(help="Batch render characters in radiance field point clouds.")

# --- Configuration & Constants ---
SAVE_NAME = "td_assignment_output.blend"
FRAME_STEP = 5
CAMERA_DISTANCE = 3.0
CAMERA_HEIGHT_OFFSET = 1.5
TARGET_BONE_NAME = "mixamorig:Hips"
RADIANCE_BLEND_FILE = "radiance_field.blend" # Ensure this file is in your project root

def reset_scene() -> None:
    """Clear the scene and set TikTok resolutions."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Use Cycles for better point cloud rendering (or EEVEE if preferred)
    bpy.context.scene.render.engine = "CYCLES" 
    
    # TikTok aspect ratio: 9:16
    bpy.context.scene.render.resolution_x = 1080
    bpy.context.scene.render.resolution_y = 1920
    bpy.context.scene.render.resolution_percentage = 100

def import_point_cloud(ply_path: Path) -> bpy.types.Object:
    """Import a PLY file and rename it to 'Pointcloud'."""
    if not ply_path.exists():
        typer.secho(f"Error: Pointcloud not found: {ply_path}", fg=typer.colors.RED)
        return None
    
    bpy.ops.wm.ply_import(filepath=str(ply_path))
    obj = bpy.context.selected_objects[0]
    obj.name = "Pointcloud"
    return obj

def apply_radiance_nodes(pc_obj: bpy.types.Object, blend_path: Path):
    """Append the RadianceField node group and apply it to the object."""
    node_group_name = "RadianceField"
    
    # Path to the node group inside the external blend file
    append_directory = str(blend_path / "NodeTree")
    
    # Append the node group if it doesn't exist in the current file
    if node_group_name not in bpy.data.node_groups:
        bpy.ops.wm.append(
            directory=append_directory,
            filename=node_group_name
        )
    
    # Add Geometry Nodes modifier
    modifier = pc_obj.modifiers.new(name="RadianceField", type='NODES')
    modifier.node_group = bpy.data.node_groups[node_group_name]
    
    # Requirement: Set bounding box bounds (Socket_3 is typically a Vector input)
    # Adjust these values as needed based on your specific point cloud scale
    try:
        modifier["Socket_3"] = (10.0, 10.0, 10.0) 
    except:
        pass 

    return modifier

def import_fbx(fbx_path: Path) -> list[bpy.types.Object]:
    """Import FBX and return the list of imported objects."""
    objects_before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    objects_after = set(bpy.data.objects)
    return list(objects_after - objects_before)

def find_armature(objects: list[bpy.types.Object]) -> Optional[bpy.types.Object]:
    for obj in objects:
        if obj.type == "ARMATURE":
            return obj
    return None

def create_tiktok_camera() -> bpy.types.Object:
    bpy.ops.object.camera_add()
    camera = bpy.context.active_object
    camera.name = "TikTokCamera"
    camera.data.lens = 35 # Wide angle often looks better in point clouds
    bpy.context.scene.camera = camera
    return camera

def setup_camera_tracking(camera, target, start, end):
    """Animate camera to follow the target."""
    for frame in range(start, end + 1, FRAME_STEP):
        bpy.context.scene.frame_set(frame)
        target_loc = target.matrix_world.translation
        
        camera.location = (
            target_loc.x, 
            target_loc.y - CAMERA_DISTANCE, 
            target_loc.z + CAMERA_HEIGHT_OFFSET
        )
        
        # Point at target
        direction = target_loc - camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)

@app.command()
def render_batch(
    pc_dir: Annotated[Path, typer.Option("--pc", help="Folder containing .ply files")] = Path("point_clouds"),
    char_dir: Annotated[Path, typer.Option("--char", help="Folder containing .fbx files")] = Path("characters"),
    output_dir: Annotated[Path, typer.Option("--out", help="Render output folder")] = Path("render_output"),
    test: bool = typer.Option(False, "--test", help="Render only one frame for testing"),
    limit: int = typer.Option(0, "--limit", help="Limit number of renders for debugging")
):
    """The main batch processing loop."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Gather all assets
    ply_files = sorted(list(pc_dir.glob("*.ply")))
    fbx_files = sorted(list(char_dir.glob("*.fbx")))
    
    typer.secho(f"Found {len(ply_files)} pointclouds and {len(fbx_files)} characters.", fg=typer.colors.CYAN)
    
    count = 0
    # 2. Start Nested Loop
    for ply in ply_files:
        for fbx in fbx_files:
            if limit > 0 and count >= limit:
                break
            
            typer.echo(f"Processing: {ply.stem} + {fbx.stem}")
            reset_scene()
            
            # --- Setup Point Cloud ---
            pc_obj = import_point_cloud(ply)
            blend_path = Path.cwd() / RADIANCE_BLEND_FILE
            apply_radiance_nodes(pc_obj, blend_path)
            
            # --- Setup Character ---
            imported_objs = import_fbx(fbx)
            armature = find_armature(imported_objs)
            
            if armature:
                # Basic alignment (as requested in Step D)
                armature.location = (0, 0, 0)
                armature.rotation_euler = (0, 0, 0)
                
                # --- Setup Camera ---
                cam = create_tiktok_camera()
                setup_camera_tracking(cam, armature, 1, 100)
            
            # --- Render ---
            render_filename = f"{ply.stem}_{fbx.stem}.mp4"
            bpy.context.scene.render.filepath = str(output_dir / render_filename)
            bpy.context.scene.render.image_settings.file_format = 'FFMPEG'
            bpy.context.scene.render.ffmpeg.format = 'MPEG4'

            if test:
                typer.echo("Running test render (last frame)...")
                bpy.context.scene.frame_set(100)
                bpy.ops.render.render(write_still=True)
            else:
                typer.echo("Running full animation render...")
                bpy.ops.render.render(animation=True)
            
            count += 1

if __name__ == "__main__":
    app()
