import sys
import os
import bpy
from pathlib import Path

# 1. Setup local library path (U: drive)
lib_path = "U:/tdspring26-main/lib"
if lib_path not in sys.path:
    sys.path.append(lib_path)

# --- Configuration & Constants ---
CHAR_Z_OFFSET = 0.1     
CAMERA_DISTANCE = 7.0   
CAMERA_HEIGHT_OFFSET = 2.0
RADIANCE_BLEND_FILE = Path("U:/tdspring26-main/radiance_field.blend")

print("LOG: Script initialized.")

def reset_scene():
    """Clear scene and ensure basic structure exists."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 32
    bpy.context.scene.render.resolution_x = 1080
    bpy.context.scene.render.resolution_y = 1920

def setup_lighting_and_world():
    """Add lights and handle World settings."""
    bpy.ops.object.light_add(type="AREA", location=(5, -5, 10))
    key = bpy.context.active_object
    key.data.energy = 5000
    key.data.size = 5

    if bpy.context.scene.world is None:
        new_world = bpy.data.worlds.new("World")
        bpy.context.scene.world = new_world

    bpy.context.scene.world.use_nodes = True
    bg_node = bpy.context.scene.world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[1].default_value = 0.3
    
    print("LOG: Lighting and World setup complete.")

def import_and_normalize_pc(ply_path):
    """Import PLY and center it at origin."""
    if not ply_path.exists():
        print(f"LOG ERROR: {ply_path} not found.")
        return None
    bpy.ops.wm.ply_import(filepath=str(ply_path))
    obj = bpy.context.selected_objects[0]
    obj.name = "Pointcloud"
    
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location = (0, 0, 0)
    
    max_dim = max(obj.dimensions)
    if max_dim > 0:
        scale_factor = 10.0 / max_dim
        obj.scale = (scale_factor, scale_factor, scale_factor)
        
    return obj

def apply_visibility_nodes(pc_obj):
    """Ensure points are visible in Cycles using Geometry Nodes."""
    mod = pc_obj.modifiers.new(name="CloudVisibility", type='NODES')
    group = bpy.data.node_groups.new("ForceVisible", "GeometryNodeTree")
    
    group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes = group.nodes
    in_n, out_n = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")
    out_n.location.x = 600

    inst_node = nodes.new("GeometryNodeInstanceOnPoints")
    inst_node.location.x = 200
    
    sphere_node = nodes.new("GeometryNodeMeshIcoSphere")
    sphere_node.inputs[0].default_value = 0.04 
    sphere_node.inputs[1].default_value = 1 

    group.links.new(in_n.outputs[0], inst_node.inputs[0])
    group.links.new(sphere_node.outputs[0], inst_node.inputs[2])
    group.links.new(inst_node.outputs[0], out_n.inputs[0])
    mod.node_group = group
    print("LOG: Applied visibility nodes.")

def run_batch():
    root = Path("U:/tdspring26-main")
    pc_path = root / "point_clouds"
    char_path = root / "characters"
    out_root = root / "render_output"
    out_root.mkdir(parents=True, exist_ok=True)

    ply_files = sorted(list(pc_path.glob("*.ply")))
    fbx_files = sorted(list(char_path.glob("*.fbx")))

    print(f"LOG: Found {len(ply_files)} clouds and {len(fbx_files)} characters.")

    for ply in ply_files:
        for fbx in fbx_files:
            pair_name = f"{ply.stem}_{fbx.stem}"
            pair_folder = out_root / pair_name
            pair_folder.mkdir(parents=True, exist_ok=True)
            
            print(f">>> STARTING BATCH: {pair_name}")
            reset_scene()
            setup_lighting_and_world()
            
            pc_obj = import_and_normalize_pc(ply)
            if pc_obj: apply_visibility_nodes(pc_obj)
            
            obs_before = set(bpy.data.objects)
            bpy.ops.import_scene.fbx(filepath=str(fbx))
            armature = next((o for o in (set(bpy.data.objects)-obs_before) if o.type=='ARMATURE'), None)
            
            if armature:
                armature.location = (0, 0, CHAR_Z_OFFSET)
                if armature.animation_data and armature.animation_data.action:
                    bpy.context.scene.frame_end = int(armature.animation_data.action.frame_range[1])
                else:
                    bpy.context.scene.frame_end = 50 
                
                bpy.ops.object.camera_add()
                cam = bpy.context.active_object
                bpy.context.scene.camera = cam
                cam.location = (0, -CAMERA_DISTANCE, CAMERA_HEIGHT_OFFSET)
                cam.rotation_euler = (1.57, 0, 0)

            bpy.context.scene.render.image_settings.file_format = 'PNG'
            bpy.context.scene.render.filepath = str(pair_folder / "frame_")
            bpy.ops.render.render(animation=True)
            print(f"LOG: Finished {pair_name}")

if __name__ == "__main__":
    run_batch()