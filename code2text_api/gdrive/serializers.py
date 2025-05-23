"""
Serializers for the Google Drive integration app.
"""

from rest_framework import serializers
from .models import DriveFile

class DriveFileSerializer(serializers.ModelSerializer):
    """Serializer for DriveFile model"""
    class Meta:
        model = DriveFile
        fields = [
            'id', 'conversion', 'file_id', 'file_name', 
            'file_url', 'mime_type', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

class GoogleDriveUploadSerializer(serializers.Serializer):
    """Serializer for Google Drive upload request"""
    conversion_id = serializers.IntegerField(required=True)
    folder_name = serializers.CharField(required=False)

class GoogleAuthCallbackSerializer(serializers.Serializer):
    """Serializer for Google OAuth callback"""
    code = serializers.CharField(required=True)
    state = serializers.CharField(required=False) 