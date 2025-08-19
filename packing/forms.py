from django import forms
from django.core.exceptions import ValidationError
from .models import PackingSession, BoxData
import csv
import io


class PackingConfigurationForm(forms.ModelForm):
    """Form for configuring packing parameters"""
    
    class Meta:
        model = PackingSession
        fields = [
            'pallet_width', 'pallet_length', 'pallet_height',
            'rotation_setting', 'algorithm', 'csv_file'
        ]
        widgets = {
            'pallet_width': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1.0',
                'max': '100.0',
                'placeholder': '10.0'
            }),
            'pallet_length': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1.0',
                'max': '100.0',
                'placeholder': '10.0'
            }),
            'pallet_height': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '1.0',
                'max': '100.0',
                'placeholder': '10.0'
            }),
            'rotation_setting': forms.Select(attrs={
                'class': 'form-control'
            }),
            'algorithm': forms.Select(attrs={
                'class': 'form-control'
            }),
            'csv_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.csv'
            })
        }
        labels = {
            'pallet_width': 'Pallet Width (ft)',
            'pallet_length': 'Pallet Length (ft)',
            'pallet_height': 'Max Packing Height (ft)',
            'rotation_setting': 'Box Rotation',
            'algorithm': 'Packing Algorithm',
            'csv_file': 'Box Data CSV File (Optional)'
        }
        help_texts = {
            'pallet_width': 'Width of the pallet in units (1.0 - 100.0)',
            'pallet_length': 'Length of the pallet in units (1.0 - 100.0)',
            'pallet_height': 'Height of the pallet in units (1.0 - 100.0)',
            'rotation_setting': 'Choose whether boxes can be rotated during packing',
            'algorithm': 'Select the packing algorithm to use',
            'csv_file': 'Upload a CSV file with box dimensions (x,y,z columns). Leave empty to use default box set.'
        }
    
    def clean_csv_file(self):
        """Validate CSV file format and content"""
        csv_file = self.cleaned_data.get('csv_file')
        
        if not csv_file:
            return csv_file
        
        # Check file extension
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('File must be a CSV file (.csv extension)')
        
        # Check file size (max 5MB)
        if csv_file.size > 5 * 1024 * 1024:
            raise ValidationError('File size must be less than 5MB')
        
        # Validate CSV content
        try:
            # Read the file content
            csv_file.seek(0)
            content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset file pointer
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content))
            
            # Check for required columns
            required_columns = ['x', 'y', 'z']
            if not all(col in csv_reader.fieldnames for col in required_columns):
                raise ValidationError(
                    f'CSV file must contain columns: {", ".join(required_columns)}. '
                    f'Found columns: {", ".join(csv_reader.fieldnames or [])}'
                )
            
            # Validate data rows
            row_count = 0
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because of header
                row_count += 1
                
                # Limit number of boxes
                if row_count > 1000:
                    raise ValidationError('CSV file cannot contain more than 1000 boxes')
                
                # Validate each dimension
                for col in required_columns:
                    try:
                        value = float(row[col])
                        if value <= 0:
                            raise ValidationError(
                                f'Row {row_num}: {col} must be greater than 0, got {value}'
                            )
                        if value > 100:
                            raise ValidationError(
                                f'Row {row_num}: {col} must be less than 100, got {value}'
                            )
                    except (ValueError, TypeError):
                        raise ValidationError(
                            f'Row {row_num}: {col} must be a valid number, got "{row[col]}"'
                        )
            
            if row_count == 0:
                raise ValidationError('CSV file must contain at least one box')
                
        except UnicodeDecodeError:
            raise ValidationError('File must be a valid UTF-8 encoded CSV file')
        except csv.Error as e:
            raise ValidationError(f'Invalid CSV format: {e}')
        
        return csv_file
    
    def clean(self):
        """Additional form validation"""
        cleaned_data = super().clean()
        
        # Validate pallet dimensions make sense
        width = cleaned_data.get('pallet_width')
        length = cleaned_data.get('pallet_length')
        height = cleaned_data.get('pallet_height')
        
        if width and length and height:
            # Check minimum volume
            volume = width * length * height
            if volume < 1.0:
                raise ValidationError('Pallet volume must be at least 1.0 cubic units')
        
        return cleaned_data


class BoxDataForm(forms.ModelForm):
    """Form for manually adding individual box data"""
    
    class Meta:
        model = BoxData
        fields = ['x', 'y', 'z']
        widgets = {
            'x': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': '1.0'
            }),
            'y': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': '1.0'
            }),
            'z': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.1',
                'min': '0.1',
                'placeholder': '1.0'
            })
        }
        labels = {
            'x': 'Width (X)',
            'y': 'Length (Y)',
            'z': 'Height (Z)'
        }


# Formset for multiple box entries
BoxDataFormSet = forms.modelformset_factory(
    BoxData,
    form=BoxDataForm,
    extra=5,  # Show 5 empty forms by default
    can_delete=True,
    max_num=100  # Maximum 100 boxes via manual entry
)