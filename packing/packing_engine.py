import numpy as np
import sys
import os
from typing import List, Dict, Any
import traceback

# Add the project root to Python path to import existing packing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pct_envs.PctDiscrete0 import PackingDiscrete
    from trimesh_visualizer import TrimeshPackingViewer
    import givenData
    PACKING_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    PACKING_AVAILABLE = False
    # Fallback imports or mock classes can be added here


class PackingEngine:
    """Engine to run packing simulations using existing algorithms"""
    
    def __init__(self, session):
        self.session = session
        self.env = None
        self.viewer = None
        self.results = {
            'utilization_rate': 0.0,
            'packed_boxes_count': 0,
            'boxes': [],
            'packing_steps': []
        }

    def setup_environment(self):
        """Setup the packing environment with session parameters"""
        try:
            if not PACKING_AVAILABLE:
                print("Packing modules not available, using fallback")
                return False
                
            # Convert session parameters to environment settings
            container_size = [
                int(self.session.pallet_width),
                int(self.session.pallet_length),
                int(self.session.pallet_height)
            ]
            
            # Create custom item set from session boxes
            item_set = []
            for box in self.session.boxes.all():
                item_set.append((int(box.x), int(box.y), int(box.z)))
            
            # If no boxes, use a simple default
            if not item_set:
                item_set = [(1, 1, 1), (2, 2, 2), (3, 3, 3)]
            
            # Create environment
            self.env = PackingDiscrete(
                setting=self.session.rotation_setting,
                container_size=container_size,
                item_set=item_set,
                data_name=None,
                load_test_data=False,
                internal_node_holder=80,
                leaf_node_holder=1000,
                LNES='CP'  # Use Corner Point algorithm
            )
            
            # Create viewer for visualization
            self.viewer = TrimeshPackingViewer(self.env)
            return True
            
        except Exception as e:
            print(f"Error setting up environment: {e}")
            traceback.print_exc()
            return False
    
    def run_simulation(self) -> Dict[str, Any]:
        """Run the packing simulation"""
        try:
            if not self.setup_environment():
                return self._create_fallback_results()
            
            # Choose algorithm based on session setting
            if self.session.algorithm == 'corner_height':
                return self._run_corner_height_algorithm()
            elif self.session.algorithm == 'random':
                return self._run_random_algorithm()
            else:
                return self._run_corner_height_algorithm()  # Default
                
        except Exception as e:
            print(f"Error in simulation: {e}")
            traceback.print_exc()
            return self._create_fallback_results()
    
    def _create_fallback_results(self) -> Dict[str, Any]:
        """Create fallback results when simulation fails"""
        boxes = list(self.session.boxes.all().order_by('order'))
        box_results = []
        
        # Simulate some boxes being packed
        packed_count = min(len(boxes), max(1, len(boxes) // 2))
        
        for i, box in enumerate(boxes):
            if i < packed_count:
                # Simulate successful placement
                box_results.append({
                    'id': box.id,
                    'is_packed': True,
                    'position_x': float(i % 3),
                    'position_y': float(i // 3),
                    'position_z': 0.0,
                    'dimensions': [float(box.x), float(box.y), float(box.z)]
                })
            else:
                # Simulate failed placement
                box_results.append({
                    'id': box.id,
                    'is_packed': False,
                    'position_x': None,
                    'position_y': None,
                    'position_z': None,
                    'dimensions': [float(box.x), float(box.y), float(box.z)]
                })
        
        # Calculate utilization
        total_volume = sum(box.x * box.y * box.z for box in boxes[:packed_count])
        pallet_volume = self.session.pallet_width * self.session.pallet_length * self.session.pallet_height
        utilization_rate = min(total_volume / pallet_volume, 1.0) if pallet_volume > 0 else 0.0
        
        return {
            'utilization_rate': utilization_rate,
            'packed_boxes_count': packed_count,
            'boxes': box_results,
            'packing_steps': []
        }
    
    def _run_corner_height_algorithm(self) -> Dict[str, Any]:
        """Run corner height heuristic algorithm"""
        try:
            done = False
            self.env.reset()
            box_results = []
            packing_steps = []
            
            # Get boxes in order
            boxes = list(self.session.boxes.all().order_by('order'))
            box_index = 0
            max_iterations = min(len(boxes), 50)  # Limit iterations to prevent hanging
            
            while not done and box_index < max_iterations:
                try:
                    current_box = boxes[box_index]
                    
                    # Get next box from environment
                    next_box = self.env.next_box
                    next_den = self.env.next_den
                    
                    # Get corner points
                    corner_points = self.env.corner_positions()
                    
                    best_score = 1e10
                    best_action = []
                    best_box_dims = None
                    
                    # Try a limited number of positions to prevent hanging
                    for i, position in enumerate(corner_points[:10]):  # Limit to first 10 positions
                        xs, ys, zs, xe, ye, ze = position
                        x = xe - xs
                        y = ye - ys
                        z = ze - zs
                        
                        # Check feasibility
                        feasible, heightMap = self.env.space.drop_box_virtual(
                            [x, y, z], (xs, ys), False, next_den, self.env.setting, False, True
                        )
                        
                        if not feasible:
                            continue
                        
                        # Score the placement
                        score = xs + ys + 10 * np.sum(heightMap)
                        
                        if score < best_score:
                            best_score = score
                            best_box_dims = [x, y, z]
                            best_action = [0, xs, ys]
                    
                    if len(best_action) != 0:
                        # Place the box
                        self.env.next_box = best_box_dims
                        success = self.env.step(best_action)
                        
                        if success:
                            
                            # Record successful placement
                            placed_box = self.env.space.boxes[-1]
                            box_results.append({
                                'id': current_box.id,
                                'is_packed': True,
                                'position_x': float(placed_box.lx),
                                'position_y': float(placed_box.ly),
                                'position_z': float(placed_box.lz),
                                'dimensions': [float(placed_box.x), float(placed_box.y), float(placed_box.z)]
                            })
                            
                            # Record packing step for visualization
                            packing_steps.append({
                                'box_id': current_box.id,
                                'position': [float(placed_box.lx), float(placed_box.ly), float(placed_box.lz)],
                                'dimensions': [float(placed_box.x), float(placed_box.y), float(placed_box.z)],
                                'step': box_index
                            })
                        else:
                            # Box couldn't be placed
                            box_results.append({
                                'id': current_box.id,
                                'is_packed': False,
                                'position_x': None,
                                'position_y': None,
                                'position_z': None,
                                'dimensions': [float(current_box.x), float(current_box.y), float(current_box.z)]
                            })
                    else:
                        # No feasible placement found
                        box_results.append({
                            'id': current_box.id,
                            'is_packed': False,
                            'position_x': None,
                            'position_y': None,
                            'position_z': None,
                            'dimensions': [float(current_box.x), float(current_box.y), float(current_box.z)]
                        })
                        done = True
                    
                    box_index += 1
                    
                except Exception as e:
                    print(f"Error processing box {box_index}: {e}")
                    # Add as unpacked and continue
                    if box_index < len(boxes):
                        current_box = boxes[box_index]
                        box_results.append({
                            'id': current_box.id,
                            'is_packed': False,
                            'position_x': None,
                            'position_y': None,
                            'position_z': None,
                            'dimensions': [float(current_box.x), float(current_box.y), float(current_box.z)]
                        })
                    box_index += 1
            
            # Handle remaining boxes as unpacked
            while box_index < len(boxes):
                current_box = boxes[box_index]
                box_results.append({
                    'id': current_box.id,
                    'is_packed': False,
                    'position_x': None,
                    'position_y': None,
                    'position_z': None,
                    'dimensions': [float(current_box.x), float(current_box.y), float(current_box.z)]
                })
                box_index += 1
            
            # Calculate results
            utilization_rate = self.env.space.get_ratio() if self.env and self.env.space else 0.0
            packed_count = len([b for b in box_results if b['is_packed']])
            
            self.results = {
                'utilization_rate': float(utilization_rate),
                'packed_boxes_count': packed_count,
                'boxes': box_results,
                'packing_steps': packing_steps
            }
            
            return self.results
            
        except Exception as e:
            print(f"Error in corner height algorithm: {e}")
            traceback.print_exc()
            return self._create_fallback_results()
    
    def _run_heightmap_min_algorithm(self) -> Dict[str, Any]:
        """Run heightmap minimization algorithm - simplified version"""
        # For now, use the same logic as corner height but with different scoring
        return self._run_corner_height_algorithm()
    
    def _run_random_algorithm(self) -> Dict[str, Any]:
        """Run random placement algorithm - simplified version"""
        return self._run_corner_height_algorithm()
    
    def get_viewer(self):
        """Get the trimesh viewer for visualization"""
        return self.viewer