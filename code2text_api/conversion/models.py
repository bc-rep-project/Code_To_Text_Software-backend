"""
Conversion models for the code2text application.
"""

from django.db import models
from django.conf import settings
from repository.models import Repository

class Conversion(models.Model):
    """
    Model to store information about code conversions.
    """
    repository = models.ForeignKey(
        Repository, 
        on_delete=models.CASCADE, 
        related_name='conversions'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='conversions'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    result_path = models.CharField(max_length=255, null=True, blank=True)
    download_count = models.IntegerField(default=0)
    uploaded_to_drive = models.BooleanField(default=False)
    drive_file_id = models.CharField(max_length=255, null=True, blank=True)
    drive_file_url = models.URLField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'conversion'
        verbose_name = 'Conversion'
        verbose_name_plural = 'Conversions'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"Conversion of {self.repository.name} ({self.status})"
    
    @property
    def is_complete(self):
        """Check if the conversion is complete."""
        return self.status == 'completed'
    
    @property
    def is_failed(self):
        """Check if the conversion failed."""
        return self.status == 'failed'
    
    @property
    def duration(self):
        """Calculate the duration of the conversion."""
        if not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds() 