# trimesh_visualizer.py
# Minimal Trimesh viewer for PackingDiscrete
#
# Usage:
#   from trimesh_visualizer import TrimeshPackingViewer
#   viewer = TrimeshPackingViewer(env)
#   ...
#   # (Call this whenever you want to refresh, e.g., after each step or at episode end)
#   viewer.show(block=False)   # or block=True to keep the window open

import numpy as np
import trimesh
from trimesh.creation import box as make_box
from typing import List, Tuple, Any, Dict, Optional

class TrimeshPackingViewer:
    """
    Visualize a PackingDiscrete environment with trimesh.
    - Draws container as wireframe (axis-aligned, origin at (0,0,0)).
    - Draws placed items as solid boxes.
    Assumes units and coordinates match env.bin_size indexing.
    """

    def __init__(self, env, container_color=(50, 50, 50, 50)):
        self.env = env
        self.scene = trimesh.Scene()
        self.container_color = container_color
        self._draw_container()

    # ------------------------- Public API -------------------------

    def show(self, block: bool = True):
        """
        Rebuilds the item meshes from current env state and shows the scene.
        Call this after placements (or at the end of the episode).
        """
        self._clear_items()
        boxes = self._extract_boxes()
        for i, (size, pos) in enumerate(boxes):
            self._add_item(size=size, pos=pos, color=self._index_color(i))
        
        self._draw_container()  # Redraw container to ensure it's always visible
        
        # Ensure scene has valid bounds before showing
        self._ensure_valid_bounds()

        # Move camera
        bounds = self.scene.bounds
        if bounds is None:
            return
        
        center = bounds.mean(axis=0)
        size = bounds.ptp(axis=0).max()
        
        # Position camera at an angle for good 3D view
        camera_distance = size * 1.5
        camera_pos = center + np.array([0, -camera_distance*0.3, camera_distance * 0.5])
        print(camera_pos)
        rotation_matrix = trimesh.transformations.rotation_matrix(
            angle=np.radians(45),  # Rotate 30 degrees around Z-axis
            direction=[1, 0, 0],  # Rotate around Z-axis
            point=center
        )
        
        T = self.scene.camera.look_at(
            points=[center],
            rotation=rotation_matrix,
            distance=camera_distance,
            center=camera_pos
        )

        self.scene.camera_transform = T

        
        try:
            self.scene.show(smooth=True, block=block)
        except Exception as e:
            print(f"Warning: Could not show scene with OpenGL viewer: {e}")
            print("Falling back to basic viewer...")
            try:
                self.scene.show(smooth=False, block=block)
            except Exception as e2:
                print(f"Error: Could not show scene: {e2}")

    # ------------------------- Internals --------------------------

    def _draw_container(self):
        """Add wireframe + translucent solid so scene has valid bounds."""
        bx, by, bz = [float(v) for v in self.env.bin_size]
        solid = make_box(extents=[bx, by, bz])
        solid.apply_translation([bx/2.0, by/2.0, bz/2.0])
        solid.visual.face_colors = [100, 100, 100, 100]  # semi-transparent gray container
        self.scene.add_geometry(solid, node_name="__container_solid__")

    def _ensure_valid_bounds(self):
        """Ensure the scene has valid bounds for lighting calculations."""
        try:
            # Force bounds recalculation
            if hasattr(self.scene, '_bounds'):
                self.scene._bounds = None
            
            # Check if bounds are valid
            bounds = self.scene.bounds
            if bounds is None:
                # If still None, add a small invisible marker at origin to establish bounds
                marker = trimesh.creation.icosphere(radius=0.001)
                marker.visual.face_colors = [0, 0, 0, 0]  # completely transparent
                self.scene.add_geometry(marker, node_name="__bounds_marker__")
        except Exception:
            # If all else fails, create a minimal scene bounds
            pass


    def _clear_items(self):
        """Remove all non-container geometries safely."""
        keep = {getattr(self, "_container_wire_key", None), getattr(self, "_container_solid_key", None)}
        for key in list(self.scene.geometry.keys()):
            if key in keep:
                continue
            self.scene.delete_geometry(key)


    def _add_item(self, size: Tuple[int, int, int], pos: Tuple[int, int, int], color):
        """
        size: (sx, sy, sz) in grid units
        pos:  (x0, y0, z0) lower-min corner in same units
        """
        sx, sy, sz = size
        x0, y0, z0 = pos

        mesh = make_box(extents=[sx, sy, sz])
        # Translate to the box center: lower-min + half extents
        mesh.apply_translation([x0 + sx/2.0, y0 + sy/2.0, z0 + sz/2.0])
        mesh.visual.face_colors = color
        # Change edges to black
        mesh.visual.edges_color = [0, 0, 0, 255]  # black edges
        # Use a stable, unique name so we can re-render cleanly
        name = f"box_{x0}_{y0}_{z0}_{sx}_{sy}_{sz}"
        self.scene.add_geometry(mesh, node_name=name)

    def _index_color(self, i: int):
        # Distinct-ish color per index (RGBA)
        rng = np.random.default_rng(i * 2654435761 % (2**32))
        r, g, b = (rng.integers(60, 220, size=3)).tolist()
        return [r, g, b, 255]

    def _extract_boxes(self) -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
        """
        Returns a list of (size=(sx,sy,sz), pos=(x0,y0,z0)) for each placed box.
        This function handles a few common patterns seen in packing envs.

        If your env stores boxes differently, edit ONLY this method.
        """
        boxes_raw = getattr(self.env.space, "boxes", None)
        if boxes_raw is None:
            # Fallback: some envs expose a getter
            getter = getattr(self.env.space, "get_boxes", None)
            if callable(getter):
                boxes_raw = getter()
        if boxes_raw is None:
            raise RuntimeError("Could not find env.space.boxes or a getter. "
                               "Please expose placed boxes from the environment.")

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


def _tuple3(x) -> Tuple[float, float, float]:
    """Coerce x into a length-3 float tuple."""
    arr = list(x)
    if len(arr) != 3:
        raise ValueError(f"Expected length-3, got {x}")
    return (float(arr[0]), float(arr[1]), float(arr[2]))

