from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import os


class PackingSession(models.Model):
    """Model to store packing session configuration and results"""
    
    # Packing configuration
    pallet_width = models.FloatField(
        default=10.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(100.0)],
        help_text="Pallet width in units"
    )
    pallet_length = models.FloatField(
        default=10.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(100.0)],
        help_text="Pallet length in units"
    )
    pallet_height = models.FloatField(
        default=10.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(100.0)],
        help_text="Pallet height in units"
    )
    
    # Rotation settings
    ROTATION_CHOICES = [
        (1, 'No Rotation (XY only)'),
        (2, 'Full Rotation (All orientations)'),
    ]
    rotation_setting = models.IntegerField(
        choices=ROTATION_CHOICES,
        default=1,
        help_text="Box rotation setting"
    )
    
    # Algorithm settings
    ALGORITHM_CHOICES = [
        ('corner_height', 'Corner Height Heuristic'),
        ('random', 'Random Placement'),
    ]
    algorithm = models.CharField(
        max_length=20,
        choices=ALGORITHM_CHOICES,
        default='corner_height',
        help_text="Packing algorithm to use"
    )
    
    # CSV file upload
    csv_file = models.FileField(
        upload_to='csv_uploads/',
        blank=True,
        null=True,
        help_text="CSV file with box dimensions (x,y,z columns)"
    )
    
    # Results
    utilization_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Space utilization percentage"
    )
    packed_boxes_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of boxes successfully packed"
    )
    
    # Video output
    simulation_video = models.FileField(
        upload_to='simulation_videos/',
        blank=True,
        null=True,
        help_text="Generated packing simulation video"
    )
    
    # Static image output
    simulation_image = models.FileField(
        upload_to='simulation_images/',
        blank=True,
        null=True,
        help_text="Generated packing visualization image"
    )
    
    # 3D scene data for interactive viewer
    scene_data = models.FileField(
        upload_to='scene_data/',
        blank=True,
        null=True,
        help_text="3D scene data JSON for interactive viewer"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Packing Session {self.id} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def pallet_size(self):
        """Return pallet size as a list for compatibility with existing code"""
        return [self.pallet_width, self.pallet_length, self.pallet_height]
    
    def delete(self, *args, **kwargs):
        """Override delete to clean up uploaded files"""
        if self.csv_file:
            if os.path.isfile(self.csv_file.path):
                os.remove(self.csv_file.path)
        if self.simulation_video:
            if os.path.isfile(self.simulation_video.path):
                os.remove(self.simulation_video.path)
        if self.simulation_image:
            if os.path.isfile(self.simulation_image.path):
                os.remove(self.simulation_image.path)
        if self.scene_data:
            if os.path.isfile(self.scene_data.path):
                os.remove(self.scene_data.path)
        super().delete(*args, **kwargs)


class BoxData(models.Model):
    """Model to store individual box dimensions for a packing session"""
    
    session = models.ForeignKey(
        PackingSession,
        on_delete=models.CASCADE,
        related_name='boxes'
    )
    
    # Box dimensions
    x = models.FloatField(
        validators=[MinValueValidator(0.1)],
        help_text="Box width"
    )
    y = models.FloatField(
        validators=[MinValueValidator(0.1)],
        help_text="Box length"
    )
    z = models.FloatField(
        validators=[MinValueValidator(0.1)],
        help_text="Box height"
    )
    
    # Packing results (filled after simulation)
    is_packed = models.BooleanField(default=False)
    position_x = models.FloatField(null=True, blank=True)
    position_y = models.FloatField(null=True, blank=True)
    position_z = models.FloatField(null=True, blank=True)
    
    # Order in which box was processed
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Box {self.order}: {self.x}x{self.y}x{self.z}"
    
    @property
    def dimensions(self):
        """Return dimensions as a list for compatibility with existing code"""
        return [self.x, self.y, self.z]
    
    @property
    def volume(self):
        """Calculate box volume"""
        return self.x * self.y * self.z
