#!/usr/bin/env python3

import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pallet_packing_web.settings')
django.setup()

from packing.models import PackingSession, BoxData
from packing.video_generator import VideoGenerator

def test_video_generation():
    """Test MP4 video generation"""
    print("Testing MP4 video generation...")
    
    # Create a test session
    session = PackingSession.objects.create(
        pallet_width=100,
        pallet_length=100,
        pallet_height=100,
        algorithm='first_fit',
        rotation_setting='none'
    )
    
    # Create some test boxes
    test_boxes = [
        (20, 20, 20, 10, 10, 10),
        (30, 30, 30, 40, 10, 10),
        (25, 25, 25, 70, 10, 10),
    ]
    
    for i, (x, y, z, px, py, pz) in enumerate(test_boxes):
        BoxData.objects.create(
            session=session,
            x=x, y=y, z=z,
            position_x=px, position_y=py, position_z=pz,
            is_packed=True,
            order=i
        )
    
    # Test video generation
    generator = VideoGenerator(session)
    video_path = generator.generate_video()
    
    if video_path and os.path.exists(video_path):
        file_ext = os.path.splitext(video_path)[1]
        print(f"✅ Video generated successfully: {video_path}")
        print(f"✅ File extension: {file_ext}")
        print(f"✅ File size: {os.path.getsize(video_path)} bytes")
        
        if file_ext.lower() == '.mp4':
            print("✅ SUCCESS: MP4 video generated!")
        else:
            print(f"⚠️  WARNING: Expected MP4 but got {file_ext}")
    else:
        print("❌ FAILED: No video generated")
    
    # Cleanup
    session.delete()
    if video_path and os.path.exists(video_path):
        os.remove(video_path)
    
    print("Test completed.")

if __name__ == "__main__":
    test_video_generation()