#!/usr/bin/env python3
"""
Test script to validate headless rendering setup on EC2 instances.
This script tests both trimesh and matplotlib fallback rendering.
"""

import os
import sys
import tempfile
import traceback
import platform

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_environment():
    """Test the basic environment setup"""
    print("Testing Environment Setup...")
    print(f"Platform: {platform.system()}")
    print(f"DISPLAY: {os.environ.get('DISPLAY', 'Not set')}")
    print(f"MESA_GL_VERSION_OVERRIDE: {os.environ.get('MESA_GL_VERSION_OVERRIDE', 'Not set')}")
    print(f"LIBGL_ALWAYS_SOFTWARE: {os.environ.get('LIBGL_ALWAYS_SOFTWARE', 'Not set')}")
    print()

def test_basic_imports():
    """Test basic imports"""
    print("Testing Basic Imports...")
    
    try:
        import numpy as np
        print("✓ numpy imported successfully")
    except ImportError as e:
        print(f"✗ numpy import failed: {e}")
        return False
    
    try:
        import matplotlib
        import matplotlib.pyplot as plt
        print(f"✓ matplotlib imported successfully (backend: {matplotlib.get_backend()})")
    except ImportError as e:
        print(f"✗ matplotlib import failed: {e}")
        return False
    
    try:
        import trimesh
        print("✓ trimesh imported successfully")
    except ImportError as e:
        print(f"✗ trimesh import failed: {e}")
        return False
    
    try:
        from PIL import Image
        print("✓ PIL imported successfully")
    except ImportError as e:
        print(f"✗ PIL import failed: {e}")
        return False
    
    print()
    return True

def test_virtual_display():
    """Test virtual display setup"""
    print("Testing Virtual Display...")
    
    try:
        from pyvirtualdisplay import Display
        display = Display(visible=0, size=(800, 600))
        display.start()
        print("✓ Virtual display started successfully")
        
        # Test if display is working
        import subprocess
        result = subprocess.run(['xdpyinfo', '-display', ':99'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Display connection verified")
        else:
            print("⚠ Display connection could not be verified")
        
        display.stop()
        print("✓ Virtual display stopped successfully")
        return True
        
    except ImportError:
        print("⚠ pyvirtualdisplay not available, will use system display")
        return True
    except Exception as e:
        print(f"✗ Virtual display failed: {e}")
        return False

def test_matplotlib_rendering():
    """Test matplotlib 3D rendering"""
    print("Testing Matplotlib 3D Rendering...")
    
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from mpl_toolkits.mplot3d import Axes3D
        
        # Create a simple 3D plot
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')
        
        # Create test data
        x = np.random.randn(100)
        y = np.random.randn(100)
        z = np.random.randn(100)
        
        ax.scatter(x, y, z)
        ax.set_title('Test 3D Plot')
        
        # Save to temporary file
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, 'test_matplotlib.png')
        
        plt.savefig(test_file, dpi=100, bbox_inches='tight')
        plt.close(fig)
        
        if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            print(f"✓ Matplotlib 3D rendering successful: {test_file}")
            print(f"  File size: {os.path.getsize(test_file)} bytes")
            return True
        else:
            print("✗ Matplotlib rendering failed - no output file")
            return False
            
    except Exception as e:
        print(f"✗ Matplotlib rendering failed: {e}")
        traceback.print_exc()
        return False

def test_trimesh_rendering():
    """Test trimesh rendering"""
    print("Testing Trimesh Rendering...")
    
    try:
        import trimesh
        from trimesh.creation import box as make_box
        
        # Create a simple scene
        scene = trimesh.Scene()
        
        # Add a container
        container = make_box(extents=[10, 10, 5])
        container.apply_translation([5, 5, 2.5])
        container.visual.face_colors = [100, 100, 100, 50]
        scene.add_geometry(container, node_name="container")
        
        # Add some boxes
        for i in range(3):
            box = make_box(extents=[2, 2, 2])
            box.apply_translation([2 + i*3, 2, 1])
            box.visual.face_colors = [255-i*80, 100+i*50, 100+i*30, 255]
            scene.add_geometry(box, node_name=f"box_{i}")
        
        # Try to render
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, 'test_trimesh.png')
        
        png_data = scene.save_image(resolution=(800, 600))
        
        with open(test_file, 'wb') as f:
            f.write(png_data)
        
        if os.path.exists(test_file) and os.path.getsize(test_file) > 0:
            print(f"✓ Trimesh rendering successful: {test_file}")
            print(f"  File size: {os.path.getsize(test_file)} bytes")
            return True
        else:
            print("✗ Trimesh rendering failed - no output file")
            return False
            
    except Exception as e:
        print(f"✗ Trimesh rendering failed: {e}")
        traceback.print_exc()
        return False

def test_video_generator():
    """Test the video generator components"""
    print("Testing Video Generator Components...")
    
    try:
        # Import the video generator
        from packing.video_generator import ensure_virtual_display, setup_headless_rendering
        
        # Test setup function
        setup_headless_rendering()
        print("✓ Headless rendering setup completed")
        
        # Test virtual display function
        if ensure_virtual_display():
            print("✓ Virtual display ensured successfully")
        else:
            print("⚠ Virtual display could not be ensured (may use system display)")
        
        return True
        
    except Exception as e:
        print(f"✗ Video generator test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("EC2 Headless Rendering Test Suite")
    print("=" * 60)
    print()
    
    tests = [
        ("Environment", test_environment),
        ("Basic Imports", test_basic_imports),
        ("Virtual Display", test_virtual_display),
        ("Matplotlib Rendering", test_matplotlib_rendering),
        ("Trimesh Rendering", test_trimesh_rendering),
        ("Video Generator", test_video_generator),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"Running {test_name} Test...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"✗ {test_name} test crashed: {e}")
            traceback.print_exc()
            results.append((test_name, False))
        print()
    
    # Summary
    print("=" * 60)
    print("Test Summary:")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        icon = "✓" if result else "✗"
        print(f"{icon} {test_name}: {status}")
        if result:
            passed += 1
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Your EC2 instance is ready for headless rendering.")
        return True
    else:
        print("⚠ Some tests failed. Check the output above for issues.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)