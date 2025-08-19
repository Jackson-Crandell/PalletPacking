from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
from django.conf import settings
import json
import csv
import io
import os
import tempfile
import threading
import time
import base64
import mimetypes
from .models import PackingSession, BoxData
from .forms import PackingConfigurationForm
from .packing_engine import PackingEngine
from .video_generator import VideoGenerator
from .scene_exporter import generate_web_scene


def index(request):
    """Main page with packing configuration form"""
    if request.method == 'POST':
        form = PackingConfigurationForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save()
            
            # Process CSV file if uploaded
            if session.csv_file:
                try:
                    process_csv_file(session)
                    messages.success(request, f'CSV file processed successfully. {session.boxes.count()} boxes loaded.')
                except Exception as e:
                    messages.error(request, f'Error processing CSV file: {str(e)}')
                    session.delete()
                    return render(request, 'packing/index.html', {'form': form})
            else:
                # Use default box set from givenData.py
                create_default_boxes(session)
                messages.info(request, f'Using default box set. {session.boxes.count()} boxes loaded.')
            
            return redirect('packing:configure', session_id=session.id)
    else:
        form = PackingConfigurationForm()
    
    return render(request, 'packing/index.html', {'form': form})


def configure(request, session_id):
    """Configuration page showing loaded boxes and allowing final adjustments"""
    session = get_object_or_404(PackingSession, id=session_id)
    boxes = session.boxes.all()
    
    context = {
        'session': session,
        'boxes': boxes,
        'total_boxes': boxes.count(),
        'total_volume': sum(box.volume for box in boxes),
        'pallet_volume': session.pallet_width * session.pallet_length * session.pallet_height,
    }
    
    return render(request, 'packing/configure.html', context)


def start_packing(request, session_id):
    """Start the packing simulation"""
    print(f'start_packing called with method: {request.method}, session_id: {session_id}')
    
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('packing:configure', session_id=session_id)
    
    session = get_object_or_404(PackingSession, id=session_id)
    print(f'Found session: {session.id}')
    
    if session.is_completed:
        messages.warning(request, 'This packing session has already been completed.')
        return redirect('packing:results', session_id=session.id)
    
    try:
        # Start packing in a background thread
        print('Starting background thread...')
        thread = threading.Thread(target=run_packing_simulation, args=(session.id,))
        thread.daemon = True
        thread.start()
        print('Background thread started')
        
        messages.success(request, 'Packing simulation started! You will be redirected to results when complete.')
        return redirect('packing:progress', session_id=session.id)
        
    except Exception as e:
        print(f'Error starting simulation: {e}')
        messages.error(request, f'Error starting simulation: {str(e)}')
        return redirect('packing:configure', session_id=session_id)


def progress(request, session_id):
    """Show packing progress"""
    session = get_object_or_404(PackingSession, id=session_id)
    
    context = {
        'session': session,
    }
    
    return render(request, 'packing/progress.html', context)


@require_http_methods(["GET"])
def progress_api(request, session_id):
    """API endpoint to check packing progress"""
    session = get_object_or_404(PackingSession, id=session_id)
    
    data = {
        'is_completed': session.is_completed,
        'utilization_rate': session.utilization_rate,
        'packed_boxes_count': session.packed_boxes_count,
        'total_boxes': session.boxes.count(),
    }
    
    return JsonResponse(data)


def results(request, session_id):
    """Show packing results and video"""
    session = get_object_or_404(PackingSession, id=session_id)
    
    if not session.is_completed:
        messages.warning(request, 'Packing simulation is not yet complete.')
        return redirect('packing:progress', session_id=session.id)
    
    packed_boxes = session.boxes.filter(is_packed=True)
    unpacked_boxes = session.boxes.filter(is_packed=False)
    
    # Convert utilization rate from decimal to percentage
    utilization_percentage = (session.utilization_rate * 100) if session.utilization_rate else 0.0
    
    # Generate 3D scene data for interactive viewer
    scene_data_json = None
    try:
        # Try to use saved scene data first, otherwise generate from database
        if session.scene_data:
            with session.scene_data.open('r') as f:
                scene_data_json = f.read()
        else:
            scene_data_json = generate_web_scene(session)
    except Exception as e:
        print(f"Error loading 3D scene data: {e}")
        # Fallback to generating from database
        try:
            scene_data_json = generate_web_scene(session)
        except Exception as e2:
            print(f"Error generating fallback 3D scene data: {e2}")
    
    context = {
        'session': session,
        'packed_boxes': packed_boxes,
        'unpacked_boxes': unpacked_boxes,
        'total_boxes': session.boxes.count(),
        'pallet_volume': session.pallet_width * session.pallet_length * session.pallet_height,
        'packed_volume': sum(box.volume for box in packed_boxes),
        'utilization_percentage': utilization_percentage,
        'scene_data_json': scene_data_json,
    }
    
    return render(request, 'packing/results.html', context)


def session_list(request):
    """List all packing sessions"""
    sessions = PackingSession.objects.all()
    
    context = {
        'sessions': sessions,
    }
    
    return render(request, 'packing/session_list.html', context)


def delete_session(request, session_id):
    """Delete a packing session"""
    session = get_object_or_404(PackingSession, id=session_id)
    
    if request.method == 'POST':
        session.delete()
        messages.success(request, 'Packing session deleted successfully.')
        return redirect('packing:session_list')
    
    context = {
        'session': session,
    }
    
    return render(request, 'packing/delete_session.html', context)


# Helper functions

def process_csv_file(session):
    """Process uploaded CSV file and create BoxData objects"""
    if not session.csv_file:
        return
    
    session.csv_file.seek(0)
    content = session.csv_file.read().decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(content))
    
    boxes_to_create = []
    for order, row in enumerate(csv_reader):
        box_data = BoxData(
            session=session,
            x=float(row['x']),
            y=float(row['y']),
            z=float(row['z']),
            order=order
        )
        boxes_to_create.append(box_data)
    
    # Bulk create for efficiency
    BoxData.objects.bulk_create(boxes_to_create)


def create_default_boxes(session):
    """Create default box set from givenData.py"""
    # Import here to avoid circular imports
    import givenData
    
    boxes_to_create = []
    for order, (x, y, z) in enumerate(givenData.item_size_set[:50]):  # Limit to first 50 boxes
        box_data = BoxData(
            session=session,
            x=float(x),
            y=float(y),
            z=float(z),
            order=order
        )
        boxes_to_create.append(box_data)
    
    # Bulk create for efficiency
    BoxData.objects.bulk_create(boxes_to_create)


def run_packing_simulation(session_id):
    """Run the packing simulation in background thread"""
    print(f"Starting packing simulation for session {session_id}")
    try:
        session = PackingSession.objects.get(id=session_id)
        
        # Initialize packing engine
        engine = PackingEngine(session)
        
        # Run packing simulation
        results = engine.run_simulation()
        
        # Update session with results
        session.utilization_rate = results['utilization_rate']
        session.packed_boxes_count = results['packed_boxes_count']
        
        # Update box positions
        for box_result in results['boxes']:
            box = BoxData.objects.get(id=box_result['id'])
            box.is_packed = box_result['is_packed']
            if box_result['is_packed']:
                box.x = box_result['dimensions'][0]
                box.y = box_result['dimensions'][1]
                box.z = box_result['dimensions'][2]
                box.position_x = box_result['position_x']
                box.position_y = box_result['position_y']
                box.position_z = box_result['position_z']
            box.save()
        
        # Generate both video and image
        video_generator = VideoGenerator(session)
        video_path, image_path = video_generator.generate_both_outputs()
        
        # Save video file if generated
        if video_path and os.path.exists(video_path):
            video_ext = os.path.splitext(video_path)[1]
            video_filename = f'packing_video_{session.id}{video_ext}'
            
            with open(video_path, 'rb') as video_file:
                session.simulation_video.save(
                    video_filename,
                    ContentFile(video_file.read())
                )
            
            # Clean up temporary video file
            os.remove(video_path)
            print(f"Video saved: {video_filename}")
        
        # Save image file if generated
        if image_path and os.path.exists(image_path):
            image_ext = os.path.splitext(image_path)[1]
            image_filename = f'packing_image_{session.id}{image_ext}'
            
            with open(image_path, 'rb') as image_file:
                session.simulation_image.save(
                    image_filename,
                    ContentFile(image_file.read())
                )
            
            # Clean up temporary image file
            os.remove(image_path)
            print(f"Image saved: {image_filename}")
        
        # Generate and save 3D scene data using environment for correct orientations
        try:
            # Pass the environment to get accurate box orientations
            scene_data_json = generate_web_scene(session, engine.env if hasattr(engine, 'env') else None)
            if scene_data_json:
                scene_filename = f'scene_data_{session.id}.json'
                session.scene_data.save(
                    scene_filename,
                    ContentFile(scene_data_json.encode('utf-8'))
                )
                print(f"3D scene data saved: {scene_filename}")
        except Exception as e:
            print(f"Error generating 3D scene data: {e}")
        
        session.is_completed = True
        session.save()
        
    except Exception as e:
        print(f"Error in packing simulation: {e}")
        # Mark session as failed or handle error appropriately
        try:
            session = PackingSession.objects.get(id=session_id)
            session.is_completed = True  # Mark as completed even if failed
            session.save()
        except:
            pass

