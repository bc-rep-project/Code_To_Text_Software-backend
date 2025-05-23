"""
Serializers for the conversion app.
"""

from rest_framework import serializers
from .models import Conversion

class ConversionSerializer(serializers.ModelSerializer):
    """Serializer for Conversion model"""
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversion
        fields = [
            'id', 'repository', 'status', 'start_time', 'end_time',
            'result_path', 'download_count', 'uploaded_to_drive',
            'drive_file_id', 'drive_file_url', 'error_message', 'duration'
        ]
        read_only_fields = [
            'id', 'status', 'start_time', 'end_time', 'result_path',
            'download_count', 'uploaded_to_drive', 'drive_file_id',
            'drive_file_url', 'error_message', 'duration'
        ]
    
    def get_duration(self, obj):
        """Get the duration of the conversion"""
        return obj.duration 