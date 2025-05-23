"""
Repository models for the code2text application.
"""

from django.db import models
from django.conf import settings

class Repository(models.Model):
    """
    Model to store information about repositories.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='repositories')
    name = models.CharField(max_length=255)
    source = models.CharField(
        max_length=20,
        choices=[
            ('github', 'GitHub'),
            ('upload', 'Upload'),
        ]
    )
    github_url = models.URLField(null=True, blank=True)
    latest_commit_hash = models.CharField(max_length=40, null=True, blank=True)
    languages = models.JSONField(default=list)
    file_count = models.IntegerField(default=0)
    size = models.BigIntegerField(default=0)  # Size in bytes
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('analyzing', 'Analyzing'),
            ('ready', 'Ready'),
            ('error', 'Error'),
        ],
        default='pending'
    )
    is_monitored = models.BooleanField(default=False)
    storage_path = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'repository'
        verbose_name = 'Repository'
        verbose_name_plural = 'Repositories'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name


class MonitoringJob(models.Model):
    """
    Model to store repository monitoring job information.
    """
    repository = models.OneToOneField(Repository, on_delete=models.CASCADE, related_name='monitoring_job')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='monitoring_jobs')
    last_checked = models.DateTimeField(auto_now_add=True)
    last_commit_hash = models.CharField(max_length=40)
    frequency = models.IntegerField(default=60)  # Check frequency in minutes
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'monitoring_job'
        verbose_name = 'Monitoring Job'
        verbose_name_plural = 'Monitoring Jobs'
    
    def __str__(self):
        return f"Monitoring for {self.repository.name}" 