"""
Google Drive integration models for the code2text application.
"""

from django.db import models
from django.conf import settings
from conversion.models import Conversion

class DriveFile(models.Model):
    """
    Model to store information about files uploaded to Google Drive.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='drive_files'
    )
    conversion = models.ForeignKey(
        Conversion, 
        on_delete=models.CASCADE, 
        related_name='drive_files'
    )
    file_id = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    file_url = models.URLField()
    mime_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'drive_file'
        verbose_name = 'Drive File'
        verbose_name_plural = 'Drive Files'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.file_name 