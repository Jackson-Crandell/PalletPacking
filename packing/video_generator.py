import os
import tempfile
import numpy as np
import trimesh
from trimesh.creation import box as make_box
from typing import List, Dict, Any, Optional
import traceback
import sys
import io
import platform

# Set up headless rendering environment
def setup_headless_rendering():
    """Configure environment for headless rendering on EC2/server environments"""
    if platform.system() == 'Linux':
        # Set environment variables for headless rendering
        os.environ['DISPLAY'] = os.environ.get('DISPLAY', ':99')
        os.environ['MESA_GL_VERSION_OVERRIDE'] = '3.3'
        os.environ['MESA_GLSL_VERSION_OVERRIDE'] = '330'
        os.environ['GALLIUM_DRIVER'] = 'llvmpipe'
        os.environ['LIBGL_ALWAYS_SOFTWARE'] = '1'

# Call setup immediately
setup_headless_rendering()

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt

try:
    import imageio
    IMAGEIO_AVAILABLE = True
except ImportError:
    IMAGEIO_AVAILABLE = False
    print("Warning: imageio not available. Install with: pip install imageio[ffmpeg]")

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    print("Warning: opencv-python not available. Install with: pip install opencv-python")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("Warning: Pillow not available. Install with: pip install Pillow")

try:
    from pyvirtualdisplay import Display
    PYVIRTUALDISPLAY_AVAILABLE = True
except ImportError:
    PYVIRTUALDISPLAY_AVAILABLE = False
    print("Warning: pyvirtualdisplay not available. Install with: pip install pyvirtualdisplay")

# Global virtual display instance
_virtual_display = None

def ensure_virtual_display():
    """Ensure virtual display is running for headless rendering"""
    global _virtual_display
    
    if platform.system() != 'Linux':
        return True  # Not needed on non-Linux systems
    
    if PYVIRTUALDISPLAY_AVAILABLE and _virtual_display is None:
        try:
            _virtual_display = Display(visible=0, size=(1024, 768))
            _virtual_display.start()
            print("Virtual display started successfully")
            return True
        except Exception as e:
            print(f"Failed to start virtual display: {e}")
            return False
    
    return True

# Add the project root to Python path to import existing modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from trimesh_visualizer import TrimeshPackingViewer
except ImportError as e:
    print(f"Import error for trimesh_visualizer: {e}")


class DjangoTrimeshViewer:
    """
    Modified trimesh viewer that works with Django session data instead of env
    """
    
    def __init__(self, session):
        self.session = session
        self.scene = trimesh.Scene()
        self.pallet_size = [session.pallet_width, session.pallet_length, session.pallet_height]
        self.packed_boxes = session.boxes.filter(is_packed=True).order_by('order')
        self._setup_scene()
    
    def _setup_scene(self):
        """Setup the scene with container and boxes"""
        self._draw_container()
        self._draw_boxes()
    
    def _draw_container(self):
        """Add container wireframe and translucent solid"""
        bx, by, bz = [float(v) for v in self.pallet_size]
        
        # Create container solid
        solid = make_box(extents=[bx, by, bz])
        solid.apply_translation([bx/2.0, by/2.0, bz/2.0])
        solid.visual.face_colors = [100, 100, 100, 50]  # semi-transparent gray container
        self.scene.add_geometry(solid, node_name="__container_solid__")
        
        # Create wireframe edges for better visibility
        # edges = self._create_wireframe_edges(bx, by, bz)
        # for i, edge in enumerate(edges):
        #     edge_mesh = trimesh.path.Path3D(entities=[trimesh.path.entities.Line([0, 1])],
        #                                   vertices=edge)
        #     edge_mesh.colors = [0, 0, 0, 255]  # black edges
        #     self.scene.add_geometry(edge_mesh, node_name=f"__container_edge_{i}__")
    
    def _create_wireframe_edges(self, bx, by, bz):
        """Create wireframe edges for the container"""
        # Define the 8 vertices of the container
        vertices = [
            [0, 0, 0], [bx, 0, 0], [bx, by, 0], [0, by, 0],  # bottom face
            [0, 0, bz], [bx, 0, bz], [bx, by, bz], [0, by, bz]  # top face
        ]
        
        # Define the 12 edges
        edges = [
            # Bottom face
            [vertices[0], vertices[1]], [vertices[1], vertices[2]], 
            [vertices[2], vertices[3]], [vertices[3], vertices[0]],
            # Top face
            [vertices[4], vertices[5]], [vertices[5], vertices[6]], 
            [vertices[6], vertices[7]], [vertices[7], vertices[4]],
            # Vertical edges
            [vertices[0], vertices[4]], [vertices[1], vertices[5]], 
            [vertices[2], vertices[6]], [vertices[3], vertices[7]]
        ]
        
        return edges
    
    def _draw_boxes(self):
        """Draw all packed boxes"""
        for i, box in enumerate(self.packed_boxes):
            if box.is_packed and box.position_x is not None:
                self._add_box(
                    size=(float(box.x), float(box.y), float(box.z)),
                    pos=(float(box.position_x), float(box.position_y), float(box.position_z)),
                    color=self._index_color(i)
                )
    
    def _add_box(self, size, pos, color):
        """Add a single box to the scene"""
        sx, sy, sz = size
        x0, y0, z0 = pos
        
        mesh = make_box(extents=[sx, sy, sz])
        # Translate to the box center: lower-min + half extents
        mesh.apply_translation([x0 + sx/2.0, y0 + sy/2.0, z0 + sz/2.0])
        mesh.visual.face_colors = color
        # Change edges to black for better definition
        mesh.visual.edge_color = [0, 0, 0, 255]  # black edges
        
        # Use a stable, unique name
        name = f"box_{x0}_{y0}_{z0}_{sx}_{sy}_{sz}"
        self.scene.add_geometry(mesh, node_name=name)
    
    def _index_color(self, i: int):
        """Generate distinct color per index (RGBA)"""
        rng = np.random.default_rng(i * 2654435761 % (2**32))
        r, g, b = (rng.integers(60, 220, size=3)).tolist()
        return [r, g, b, 255]
    
    def save_image(self, file_path, resolution=(1920, 1080)):
        """Save the scene as an image with headless rendering support"""
        try:
            # Ensure virtual display is running for headless environments
            if not ensure_virtual_display():
                print("Failed to ensure virtual display")
                return self._fallback_save_image(file_path, resolution)
            
            # Set up camera for good viewing angle
            self.scene.camera.resolution = resolution
            
            # Position camera for isometric view
            bounds = self.scene.bounds
            if bounds is not None:
                center = bounds.mean(axis=0)
                size = np.ptp(bounds,axis=0).max()
                
                # Position camera at an angle for good 3D view
                camera_distance = size * 2.5
                camera_pos = center + np.array([camera_distance, camera_distance, camera_distance * 0.7])
                
                self.scene.camera.look_at(
                    points=[center],
                    distance=camera_distance,
                    center=camera_pos
                )
            
            # Render and save
            png_data = self.scene.save_image(resolution=resolution)
            
            with open(file_path, 'wb') as f:
                f.write(png_data)
            
            return True
            
        except Exception as e:
            print(f"Error saving trimesh image: {e}")
            traceback.print_exc()
            # Try fallback method
            return self._fallback_save_image(file_path, resolution)
    
    def _fallback_save_image(self, file_path, resolution=(1920, 1080)):
        """Fallback method using matplotlib for basic visualization"""
        try:
            print("Attempting fallback image generation using matplotlib...")
            
            # Create a simple 3D plot using matplotlib
            fig = plt.figure(figsize=(resolution[0]/100, resolution[1]/100), dpi=100)
            ax = fig.add_subplot(111, projection='3d')
            
            # Draw container outline
            bx, by, bz = self.pallet_size
            
            # Draw container wireframe
            vertices = np.array([
                [0, 0, 0], [bx, 0, 0], [bx, by, 0], [0, by, 0],  # bottom
                [0, 0, bz], [bx, 0, bz], [bx, by, bz], [0, by, bz]  # top
            ])
            
            # Define edges for wireframe
            edges = [
                [0, 1], [1, 2], [2, 3], [3, 0],  # bottom
                [4, 5], [5, 6], [6, 7], [7, 4],  # top
                [0, 4], [1, 5], [2, 6], [3, 7]   # vertical
            ]
            
            for edge in edges:
                points = vertices[edge]
                ax.plot3D(*points.T, 'k-', alpha=0.6)
            
            # Draw boxes
            for i, box in enumerate(self.packed_boxes):
                if box.is_packed and box.position_x is not None:
                    x, y, z = float(box.position_x), float(box.position_y), float(box.position_z)
                    dx, dy, dz = float(box.x), float(box.y), float(box.z)
                    
                    # Create box vertices
                    box_vertices = np.array([
                        [x, y, z], [x+dx, y, z], [x+dx, y+dy, z], [x, y+dy, z],
                        [x, y, z+dz], [x+dx, y, z+dz], [x+dx, y+dy, z+dz], [x, y+dy, z+dz]
                    ])
                    
                    # Draw box edges
                    color = plt.cm.tab10(i % 10)
                    for edge in edges:
                        points = box_vertices[edge]
                        ax.plot3D(*points.T, color=color, linewidth=2)
            
            # Set equal aspect ratio and labels
            ax.set_xlabel('X')
            ax.set_ylabel('Y')
            ax.set_zlabel('Z')
            ax.set_title('Pallet Packing Visualization (Fallback)')
            
            # Set limits
            ax.set_xlim([0, bx])
            ax.set_ylim([0, by])
            ax.set_zlim([0, bz])
            
            # Save the figure
            plt.tight_layout()
            plt.savefig(file_path, dpi=100, bbox_inches='tight')
            plt.close(fig)
            
            print(f"Fallback image saved successfully: {file_path}")
            return True
            
        except Exception as e:
            print(f"Error in fallback image generation: {e}")
            traceback.print_exc()
            return False
    
    def export_scene(self, file_path):
        """Export the scene as a 3D file (GLB format for web viewing)"""
        try:
            # Export as GLB (binary GLTF) which is web-compatible
            self.scene.export(file_path)
            return True
        except Exception as e:
            print(f"Error exporting scene: {e}")
            return False


class VideoGenerator:
    """Generate packing simulation videos using trimesh"""
    
    def __init__(self, session):
        self.session = session
        self.packed_boxes = list(session.boxes.filter(is_packed=True).order_by('order'))
        self.pallet_size = [session.pallet_width, session.pallet_length, session.pallet_height]
        
    def generate_video(self) -> Optional[str]:
        """Generate both video and static image, return the static image path"""
        try:
            # Generate animated video for download
            video_path = None
            if OPENCV_AVAILABLE:
                video_path = self.generate_animated_mp4()
                if video_path:
                    print(f"Video generated successfully: {video_path}")
            
            # Always generate static image for display
            image_path = self.generate_trimesh_visualization()
            if image_path:
                print(f"Static image generated successfully: {image_path}")
                return image_path
            
            # If static image fails, return video as fallback
            if video_path:
                print("Static image failed, returning video as fallback")
                return video_path
            
            print("Both video and image generation failed")
            return None
            
        except Exception as e:
            print(f"Error generating video: {e}")
            traceback.print_exc()
            return None
    
    def generate_both_outputs(self):
        """Generate both video and static image, return both paths"""
        try:
            # Generate animated video
            video_path = None
            if OPENCV_AVAILABLE:
                video_path = self.generate_animated_mp4()
                if video_path:
                    print(f"Video generated: {video_path}")
            
            # Generate static image
            image_path = self.generate_trimesh_visualization()
            if image_path:
                print(f"Image generated: {image_path}")
            
            return video_path, image_path
            
        except Exception as e:
            print(f"Error generating outputs: {e}")
            traceback.print_exc()
            return None, None
    
    def generate_animated_mp4(self) -> Optional[str]:
        """Generate an animated MP4 video showing step-by-step packing"""
        try:
            temp_dir = tempfile.mkdtemp()
            video_path = os.path.join(temp_dir, f'packing_visualization_{self.session.id}.avi')
            
            # Generate frames for animation
            frames = self._generate_animation_frames()
            
            if not frames:
                print("No frames generated for animation")
                return None
            
            # Render frames
            # for frame in frames:
            #     print(f"Rendering frame {len(frames)}")
            #     # Show frame
            #     plt.imshow(frame)
            #     plt.axis('off')
            #     plt.show()
            
            # Create MP4 video from frames
            if OPENCV_AVAILABLE:
                success = self._create_video_with_opencv(frames, video_path)
            else:
                print("No video creation library available")
                return None
            
            if success and os.path.exists(video_path):
                return video_path
            else:
                print("Failed to create MP4 video")
                return None
                
        except Exception as e:
            print(f"Error generating animated MP4: {e}")
            traceback.print_exc()
            return None
    
    def _generate_animation_frames(self) -> List[np.ndarray]:
        """Generate frames for step-by-step packing animation"""
        frames = []
        resolution = (640, 480)  # Lower resolution for faster processing
        
        try:
            # Generate frames showing boxes being added one by one
            for step in range(len(self.packed_boxes) + 1):
                # Create viewer with boxes up to current step
                viewer = self._create_step_viewer(step)
                
                # Render frame
                frame_data = self._render_frame(viewer, resolution)
                if frame_data is not None:
                    frames.append(frame_data)
                    
                    # Add multiple copies of each frame for slower animation
                    # (each step shows for about 1 second at 30fps)
                    for _ in range(29):  # 30 frames total per step
                        frames.append(frame_data)
            
            # Add final frames showing the complete result
            if frames:
                final_frame = frames[-1]
                for _ in range(90):  # Hold final result for 3 seconds
                    frames.append(final_frame)
            
            return frames
            
        except Exception as e:
            print(f"Error generating animation frames: {e}")
            traceback.print_exc()
            return []
    
    def _create_step_viewer(self, step):
        """Create a viewer showing boxes up to the given step"""
        viewer = DjangoTrimeshViewer.__new__(DjangoTrimeshViewer)
        viewer.session = self.session
        viewer.scene = trimesh.Scene()
        viewer.pallet_size = self.pallet_size
        viewer.packed_boxes = self.packed_boxes[:step]  # Only boxes up to this step
        viewer._setup_scene()
        return viewer
    
    def _render_frame(self, viewer, resolution) -> Optional[np.ndarray]:
        """Render a single frame from the viewer with headless support"""
        try:
            # Ensure virtual display is running
            if not ensure_virtual_display():
                print("Failed to ensure virtual display for frame rendering")
                return None
            
            # Set up camera for good viewing angle
            viewer.scene.camera.resolution = resolution
            
            # Position camera for isometric view
            bounds = viewer.scene.bounds
            if bounds is not None:
                center = bounds.mean(axis=0)
                size = np.ptp(bounds,axis=0).max()
                
                # Position camera at an angle for good 3D view
                camera_distance = size * 2.5
                camera_pos = center + np.array([camera_distance, camera_distance, camera_distance * 0.7])
                
                viewer.scene.camera.look_at(
                    points=[center],
                    distance=camera_distance,
                    center=camera_pos
                )
            
            # Render frame
            png_data = viewer.scene.save_image(resolution=resolution)
            
            # Convert PNG bytes to numpy array
            if not PIL_AVAILABLE:
                print("PIL not available for frame conversion")
                return None
                
            image = Image.open(io.BytesIO(png_data))
            frame = np.array(image)
            
            # Convert RGBA to RGB if needed
            if frame.shape[2] == 4:
                frame = frame[:, :, :3]
            
            return frame
            
        except Exception as e:
            print(f"Error rendering frame: {e}")
            return None
    
    def _create_video_with_imageio(self, frames: List[np.ndarray], output_path: str) -> bool:
        """Create MKV video using imageio"""
        if not frames:
            raise ValueError("No frames provided.")

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        h, w = frames[0].shape[:2]

        def to_uint8(img: np.ndarray) -> np.ndarray:
            """Convert array to uint8 without changing the intended values."""
            if img.dtype == np.uint8:
                return img
            arr = img.astype(np.float32, copy=False)
            # If in [0,1], scale to [0,255]; else clip to [0,255]
            if np.nanmax(arr) <= 1.0:
                arr = arr * 255.0
            arr = np.clip(arr, 0, 255)
            return arr.astype(np.uint8)

        # Open writer (H.264 + yuv420p for broad compatibility)
        writer = imageio.get_writer(
            output_path,
            quality=4,               # 0 (worst) .. 10 (best); adjust as needed
            pixelformat="yuv420p"    # ensures playback on most players
        )

        try:
            for idx, f in enumerate(frames):
                if not isinstance(f, np.ndarray):
                    raise TypeError(f"Frame {idx} is not a numpy array.")
                if f.shape[:2] != (h, w):
                    raise ValueError(f"All frames must have same size; frame {idx} is {f.shape[:2]}, expected {(h, w)}.")

                # Normalize channels: grayscale→RGB, RGBA→RGB, BGR→RGB if specified
                if f.ndim == 2:  # grayscale
                    f = np.repeat(f[..., None], 3, axis=2)
                elif f.ndim == 3:
                    if f.shape[2] == 4:       # RGBA -> RGB
                        f = f[..., :3]
                    elif f.shape[2] == 3 and False:
                        f = f[..., ::-1]      # BGR -> RGB
                else:
                    raise ValueError(f"Unsupported frame ndim={f.ndim} at index {idx}.")

                f8 = to_uint8(f)
                writer.append_data(f8)
        finally:
            writer.close()

        return output_path
    
    def _create_video_with_opencv(self, frames: List[np.ndarray], output_path: str) -> bool:
        """Create MP4 video using OpenCV"""
        try:
            if not frames:
                return False
            
            height, width = frames[0].shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            out = cv2.VideoWriter(output_path, fourcc, 30.0, (width, height))
            
            for frame in frames:
                # Show image
                #cv2.imshow('Frame', frame)
                #cv2.waitKey(1)  # Allow OpenCV to process the frame
                # Convert RGB to BGR for OpenCV
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                out.write(bgr_frame)
            
            out.release()
            return True
        except Exception as e:
            print(f"Error creating video with OpenCV: {e}")
            return False
    
    def generate_trimesh_visualization(self) -> Optional[str]:
        """Generate a high-quality 3D visualization using trimesh with headless support"""
        try:
            # Ensure virtual display is available
            if not ensure_virtual_display():
                print("Virtual display not available, using fallback method")
                return self._generate_fallback_visualization()
            
            temp_dir = tempfile.mkdtemp()
            image_path = os.path.join(temp_dir, f'packing_visualization_{self.session.id}.png')
            
            # Create the trimesh viewer
            viewer = DjangoTrimeshViewer(self.session)

            bounds = viewer.scene.bounds
            if bounds is None:
                print("No bounds available, using fallback")
                return self._generate_fallback_visualization()

            center = bounds.mean(axis=0)
            size = np.ptp(bounds,axis=0).max()

            # Position camera at an angle for good 3D view
            camera_distance = size * 1.5
            camera_pos = center + np.array([0, -camera_distance*0.3, camera_distance * 0.5])
            print(camera_pos)
            rotation_matrix = trimesh.transformations.rotation_matrix(
                angle=np.radians(45),  # Rotate 45 degrees around X-axis
                direction=[1, 0, 0],  # Rotate around X-axis
                point=center
            )

            T = viewer.scene.camera.look_at(
                points=[center],
                rotation=rotation_matrix,
                distance=camera_distance,
                center=camera_pos
            )

            viewer.scene.camera_transform = T

            # Save lower resolution image for faster processing
            success = viewer.save_image(image_path, resolution=(800, 600))

            if success and os.path.exists(image_path):
                return image_path
            else:
                print("Failed to generate trimesh visualization, trying fallback")
                return self._generate_fallback_visualization()

        except Exception as e:
            print(f"Error generating trimesh visualization: {e}")
            traceback.print_exc()
            return self._generate_fallback_visualization()
    
    def _generate_fallback_visualization(self) -> Optional[str]:
        """Generate a matplotlib-based fallback visualization"""
        try:
            temp_dir = tempfile.mkdtemp()
            image_path = os.path.join(temp_dir, f'packing_fallback_{self.session.id}.png')
            
            # Create fallback visualization using matplotlib
            viewer = DjangoTrimeshViewer(self.session)
            success = viewer._fallback_save_image(image_path, resolution=(800, 600))
            
            if success and os.path.exists(image_path):
                return image_path
            else:
                print("Failed to generate fallback visualization")
                return None
                
        except Exception as e:
            print(f"Error generating fallback visualization: {e}")
            return None
    
    def generate_3d_export(self) -> Optional[str]:
        """Generate a 3D file export for web viewing"""
        try:
            temp_dir = tempfile.mkdtemp()
            model_path = os.path.join(temp_dir, f'packing_model_{self.session.id}.glb')
            
            # Create the trimesh viewer
            viewer = DjangoTrimeshViewer(self.session)
            
            # Export 3D model
            success = viewer.export_scene(model_path)
            
            if success and os.path.exists(model_path):
                return model_path
            else:
                print("Failed to generate 3D export")
                return None
                
        except Exception as e:
            print(f"Error generating 3D export: {e}")
            traceback.print_exc()
            return None


class AnimatedVideoGenerator:
    """Generate animated videos showing step-by-step packing"""
    
    def __init__(self, session):
        self.session = session
        self.packed_boxes = list(session.boxes.filter(is_packed=True).order_by('order'))
        self.pallet_size = [session.pallet_width, session.pallet_length, session.pallet_height]
    
    def generate_step_by_step_images(self) -> List[str]:
        """Generate a series of images showing boxes being added one by one"""
        try:
            temp_dir = tempfile.mkdtemp()
            image_paths = []
            
            # Generate images for each step
            for step in range(len(self.packed_boxes) + 1):
                image_path = os.path.join(temp_dir, f'step_{step:03d}.png')
                
                # Create viewer with boxes up to current step
                viewer = self._create_step_viewer(step)
                
                if viewer.save_image(image_path, resolution=(1280, 720)):
                    image_paths.append(image_path)
                else:
                    print(f"Failed to generate step {step}")
            
            return image_paths
            
        except Exception as e:
            print(f"Error generating step-by-step images: {e}")
            traceback.print_exc()
            return []
    
    def _create_step_viewer(self, step):
        """Create a viewer showing boxes up to the given step"""
        viewer = DjangoTrimeshViewer.__new__(DjangoTrimeshViewer)
        viewer.session = self.session
        viewer.scene = trimesh.Scene()
        viewer.pallet_size = self.pallet_size
        viewer.packed_boxes = self.packed_boxes[:step]  # Only boxes up to this step
        viewer._setup_scene()
        return viewer


# Fallback simple generator for compatibility
class SimpleVideoGenerator:
    """Simplified video generator that creates a basic representation"""
    
    def __init__(self, session):
        self.session = session
        self.packed_boxes = session.boxes.filter(is_packed=True).order_by('order')
        self.pallet_size = [session.pallet_width, session.pallet_length, session.pallet_height]
    
    def generate_simple_visualization(self) -> Optional[str]:
        """Generate a simple text-based visualization"""
        try:
            temp_dir = tempfile.mkdtemp()
            text_path = os.path.join(temp_dir, f'packing_summary_{self.session.id}.txt')
            
            with open(text_path, 'w') as f:
                f.write(f"Packing Results for Session {self.session.id}\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Pallet Size: {self.pallet_size[0]} x {self.pallet_size[1]} x {self.pallet_size[2]}\n")
                f.write(f"Algorithm: {self.session.get_algorithm_display()}\n")
                f.write(f"Rotation: {self.session.get_rotation_setting_display()}\n\n")
                
                f.write("Packed Boxes:\n")
                f.write("-" * 30 + "\n")
                
                for i, box in enumerate(self.packed_boxes, 1):
                    f.write(f"Box {i}: {box.x}x{box.y}x{box.z} at ({box.position_x}, {box.position_y}, {box.position_z})\n")
                
                f.write(f"\nTotal Boxes Packed: {len(self.packed_boxes)}\n")
                f.write(f"Utilization Rate: {(self.session.utilization_rate or 0) * 100:.1f}%\n")
            
            return text_path
            
        except Exception as e:
            print(f"Error generating simple visualization: {e}")
            return None
