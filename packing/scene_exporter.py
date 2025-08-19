import json
import numpy as np
import trimesh
from trimesh.creation import box as make_box
from typing import List, Tuple, Dict, Any
import base64
import io


class WebSceneExporter:
    """
    Export trimesh scenes to web-compatible format for Three.js
    """
    
    def __init__(self, session, env=None):
        self.session = session
        self.env = env  # Packing environment with actual box data
        self.scene_data = {
            "geometries": [],
            "materials": [],
            "objects": [],
            "metadata": {
                "type": "Object",
                "version": 4.5,
                "generator": "PalletPacking WebSceneExporter"
            }
        }
        
    def generate_scene_data(self):
        """Generate 3D scene data from packing session"""
        # Add container wireframe
        self._add_container()
        
        # Add packed boxes - use environment data if available, otherwise database
        if self.env and hasattr(self.env, 'space') and hasattr(self.env.space, 'boxes'):
            # Use environment data (same as trimesh visualizer)
            placed_boxes = self._extract_environment_boxes()
            for i, (size, pos) in enumerate(placed_boxes):
                self._add_environment_box(size, pos, i)
        else:
            # Fallback to database data
            print("Using database box data as fallback")
            packed_boxes = self.session.boxes.filter(is_packed=True)
            for i, box in enumerate(packed_boxes):
                self._add_database_box(box, i)
            
        return self.scene_data
    
    def _add_container(self):
        """Add pallet container as wireframe"""
        width = float(self.session.pallet_width)
        length = float(self.session.pallet_length) 
        height = float(self.session.pallet_height)
        
        # Create wireframe geometry
        container_geometry = self._create_wireframe_geometry(width, length, height)
        geometry_id = f"container_geometry"
        
        self.scene_data["geometries"].append({
            "uuid": geometry_id,
            "type": "EdgesGeometry",
            "data": container_geometry
        })
        
        # Create material for container
        material_id = f"container_material"
        self.scene_data["materials"].append({
            "uuid": material_id,
            "type": "LineBasicMaterial",
            "color": 0x666666,
            "linewidth": 2
        })
        
        # Create container object (no translation - keep at origin like trimesh visualizer)
        self.scene_data["objects"].append({
            "uuid": f"container_object",
            "type": "LineSegments",
            "name": "Container",
            "geometry": geometry_id,
            "material": material_id,
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
        })
    
    def _add_environment_box(self, size, pos, index):
        """Add a packed box to the scene using environment data (with correct rotations)"""
        # Box dimensions (already rotated by environment)
        width, length, height = size
        
        # Box position (center position)
        pos_x = float(pos[0]) + width/2
        pos_y = float(pos[1]) + length/2
        pos_z = float(pos[2]) + height/2
        
        # Create box geometry
        box_geometry = self._create_box_geometry(width, length, height)
        geometry_id = f"box_geometry_{index}"
        
        self.scene_data["geometries"].append({
            "uuid": geometry_id,
            "type": "BoxGeometry",
            "data": box_geometry
        })
        
        # Create material with random color
        color = self._generate_color(index)
        material_id = f"box_material_{index}"
        
        self.scene_data["materials"].append({
            "uuid": material_id,
            "type": "MeshPhongMaterial",
            "color": color,
            "transparent": True,
            "opacity": 0.8,
            "side": 2  # DoubleSide
        })
        
        # Create box object
        self.scene_data["objects"].append({
            "uuid": f"box_object_{index}",
            "type": "Mesh",
            "name": f"Box {index + 1}",
            "geometry": geometry_id,
            "material": material_id,
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, pos_x, pos_y, pos_z, 1]
        })
    
    def _add_database_box(self, box, index):
        """Add a packed box to the scene using database data (fallback)"""
        # Box dimensions
        width = float(box.x)
        length = float(box.y)
        height = float(box.z)
        
        # Box position (center position)
        pos_x = float(box.position_x) + width/2
        pos_y = float(box.position_y) + length/2
        pos_z = float(box.position_z) + height/2
        
        # Create box geometry
        box_geometry = self._create_box_geometry(width, length, height)
        geometry_id = f"box_geometry_{index}"
        
        self.scene_data["geometries"].append({
            "uuid": geometry_id,
            "type": "BoxGeometry",
            "data": box_geometry
        })
        
        # Create material with random color
        color = self._generate_color(index)
        material_id = f"box_material_{index}"
        
        self.scene_data["materials"].append({
            "uuid": material_id,
            "type": "MeshPhongMaterial",
            "color": color,
            "transparent": True,
            "opacity": 0.8,
            "side": 2  # DoubleSide
        })
        
        # Create box object
        self.scene_data["objects"].append({
            "uuid": f"box_object_{index}",
            "type": "Mesh",
            "name": f"Box {index + 1}",
            "geometry": geometry_id,
            "material": material_id,
            "matrix": [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, pos_x, pos_y, pos_z, 1]
        })
    
    def _create_box_geometry(self, width, length, height):
        """Create box geometry data"""
        # Correct mapping: environment (x,y,z) -> Three.js (width,height,depth)
        # Environment: x=width, y=length, z=height
        # Three.js: width=X, height=Y, depth=Z
        return {
            "width": width,   # X dimension
            "height": length, # Y dimension
            "depth": height,  # Z dimension
            "widthSegments": 1,
            "heightSegments": 1,
            "depthSegments": 1
        }
    
    def _create_wireframe_geometry(self, width, length, height):
        """Create wireframe geometry for container"""
        # Define the 8 vertices of the box
        vertices = [
            [0, 0, 0], [width, 0, 0], [width, length, 0], [0, length, 0],  # bottom face
            [0, 0, height], [width, 0, height], [width, length, height], [0, length, height]  # top face
        ]
        
        # Define the 12 edges (lines) of the box
        edges = [
            # Bottom face edges
            [0, 1], [1, 2], [2, 3], [3, 0],
            # Top face edges  
            [4, 5], [5, 6], [6, 7], [7, 4],
            # Vertical edges
            [0, 4], [1, 5], [2, 6], [3, 7]
        ]
        
        return {
            "vertices": vertices,
            "edges": edges
        }
    
    def _generate_color(self, index):
        """Generate a distinct color for each box"""
        # Use a simple hash-based color generation
        np.random.seed(index * 2654435761 % (2**32))
        r = np.random.randint(60, 220)
        g = np.random.randint(60, 220) 
        b = np.random.randint(60, 220)
        
        # Convert RGB to hex color
        return (r << 16) | (g << 8) | b
    
    def _extract_environment_boxes(self):
        """Extract box data from environment (same logic as trimesh visualizer)"""
        from typing import List, Tuple
        
        def _tuple3(x) -> Tuple[float, float, float]:
            """Coerce x into a length-3 float tuple."""
            arr = list(x)
            if len(arr) != 3:
                raise ValueError(f"Expected length-3, got {x}")
            return (float(arr[0]), float(arr[1]), float(arr[2]))
        
        boxes_raw = getattr(self.env.space, "boxes", None)
        parsed: List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]] = []
        for b in boxes_raw:
            # Try several common shapes:

            # 1) dict with size/pos keys
            if isinstance(b, dict):
                size = b.get("size") or b.get("dims") or b.get("extent")
                pos  = b.get("pos")  or b.get("origin") or b.get("xyz")
                if size is not None and pos is not None:
                    size = _tuple3(size)
                    pos  = _tuple3(pos)
                    parsed.append((size, pos))
                    continue

            # 2) object with attributes
            if hasattr(b, "size") and hasattr(b, "pos"):
                parsed.append((_tuple3(b.size), _tuple3(b.pos)))
                continue
            if hasattr(b, "dims") and hasattr(b, "origin"):
                parsed.append((_tuple3(b.dims), _tuple3(b.origin)))
                continue
            
            # 2b) Handle the specific Box class from space.py
            if hasattr(b, "x") and hasattr(b, "y") and hasattr(b, "z") and hasattr(b, "lx") and hasattr(b, "ly") and hasattr(b, "lz"):
                #print(f"Parsing box from Box class: {b}")
                size = (b.x, b.y, b.z)
                pos = (b.lx, b.ly, b.lz)
                parsed.append((_tuple3(size), _tuple3(pos)))
                continue

            # 3) flat tuple/list: (x0, y0, z0, sx, sy, sz) or (sx,sy,sz,x0,y0,z0)
            if isinstance(b, (list, tuple)) and len(b) == 6:
                # Heuristic: if first three look like position (>=0, < bin size), treat so
                bx, by, bz = self.env.bin_size
                v = list(b)
                first_three_pos_like = all(0 <= v[k] <= max(bx, by, bz) for k in range(3))
                last_three_size_like = all(v[k] > 0 for k in range(3, 6))
                if first_three_pos_like and last_three_size_like:
                    pos  = _tuple3(v[0:3])
                    size = _tuple3(v[3:6])
                else:
                    size = _tuple3(v[0:3])
                    pos  = _tuple3(v[3:6])
                parsed.append((size, pos))
                continue

            # 4) Unknown shape -> try to infer common names inside objects
            if hasattr(b, "__dict__"):
                d: Dict[str, Any] = b.__dict__
                cand_size = None
                cand_pos = None
                # Try a few keys
                for k in ("size", "dims", "extent", "box", "whd"):
                    if k in d:
                        cand_size = d[k]
                        break
                for k in ("pos", "origin", "xyz", "lower", "corner"):
                    if k in d:
                        cand_pos = d[k]
                        break
                if cand_size is not None and cand_pos is not None:
                    parsed.append((_tuple3(cand_size), _tuple3(cand_pos)))
                    continue

            # If we get here, we couldn't parse this box
            raise ValueError(f"Unrecognized box record format: {type(b)} -> {b}")

        return parsed
    
    def export_to_json(self):
        """Export scene data as JSON string"""
        scene_data = self.generate_scene_data()
        return json.dumps(scene_data, indent=2)


def generate_web_scene(session, env=None):
    """Generate web-compatible 3D scene data for a packing session"""
    exporter = WebSceneExporter(session, env)
    return exporter.export_to_json()