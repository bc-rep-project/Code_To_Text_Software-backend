from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class Project(models.Model):
    """
    Project model based on the JSON structure provided.
    Represents a codebase project that can be scanned and converted.
    """
    
    # Basic project information
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects')
    project_name = models.CharField(max_length=255)
    
    # Source type and related fields
    SOURCE_TYPE_CHOICES = [
        ('github', 'GitHub Repository'),
        ('upload', 'Uploaded File'),
    ]
    
    source_type = models.CharField(max_length=10, choices=SOURCE_TYPE_CHOICES)
    github_repo_url = models.URLField(null=True, blank=True)  # if source_type is "github"
    uploaded_file_key = models.CharField(max_length=500, null=True, blank=True)  # storage path
    original_file_name = models.CharField(max_length=255, null=True, blank=True)  # if source_type is "upload"
    
    # Project status
    STATUS_CHOICES = [
        ('pending_scan', 'Pending Scan'),
        ('scanning', 'Scanning'),
        ('scanned', 'Scanned'),
        ('conversion_pending', 'Conversion Pending'),
        ('converting', 'Converting'),
        ('converted', 'Converted'),
        ('uploading_to_drive', 'Uploading to Drive'),
        ('completed', 'Completed'),
        ('error', 'Error'),
        ('monitoring_github', 'Monitoring GitHub'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_scan')
    
    # Timestamps for tracking
    last_scan_at = models.DateTimeField(null=True, blank=True)
    last_conversion_at = models.DateTimeField(null=True, blank=True)
    last_github_commit_hash = models.CharField(max_length=40, null=True, blank=True)  # For GitHub projects
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'projects'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.project_name} ({self.user.email})"
    
    def is_github_project(self):
        """Check if this is a GitHub project"""
        return self.source_type == 'github'
    
    def is_upload_project(self):
        """Check if this is an uploaded project"""
        return self.source_type == 'upload'
    
    def can_be_scanned(self):
        """Check if project can be scanned"""
        return self.status in ['pending_scan', 'error']
    
    def can_be_converted(self):
        """Check if project can be converted"""
        return self.status in ['scanned', 'error']
    
    def is_processing(self):
        """Check if project is currently being processed"""
        return self.status in ['scanning', 'converting', 'uploading_to_drive']


class ScanData(models.Model):
    """
    Stores scan results for a project
    """
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='scan_data')
    
    # Languages used (stored as JSON)
    languages_used = models.JSONField(default=dict)  # e.g., {"Python": "60%", "JavaScript": "30%"}
    
    # Error message if scanning failed
    error_message = models.TextField(null=True, blank=True)
    
    # File statistics
    total_files = models.IntegerField(default=0)
    total_size_bytes = models.BigIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'scan_data'
    
    def __str__(self):
        return f"Scan data for {self.project.project_name}"


class GitHubInfo(models.Model):
    """
    Stores GitHub-specific information for GitHub projects
    """
    scan_data = models.OneToOneField(ScanData, on_delete=models.CASCADE, related_name='github_info')
    
    # Repository metadata
    description = models.TextField(null=True, blank=True)
    stars = models.IntegerField(default=0)
    forks = models.IntegerField(default=0)
    open_issues_count = models.IntegerField(default=0)
    
    # Repository owner and name (extracted from URL)
    owner = models.CharField(max_length=255)
    repo_name = models.CharField(max_length=255)
    
    # Default branch
    default_branch = models.CharField(max_length=100, default='main')
    
    # Repository creation and update dates
    repo_created_at = models.DateTimeField(null=True, blank=True)
    repo_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'github_info'
    
    def __str__(self):
        return f"GitHub info for {self.owner}/{self.repo_name}"


class GitHubIssue(models.Model):
    """
    Stores simplified GitHub issue objects
    """
    github_info = models.ForeignKey(GitHubInfo, on_delete=models.CASCADE, related_name='issues')
    
    # Issue details
    github_issue_id = models.IntegerField()
    title = models.CharField(max_length=500)
    url = models.URLField()
    state = models.CharField(max_length=20)  # 'open', 'closed'
    
    # Issue metadata
    author = models.CharField(max_length=255, null=True, blank=True)
    labels = models.JSONField(default=list)  # List of label names
    
    # Timestamps
    issue_created_at = models.DateTimeField()
    issue_updated_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'github_issues'
        unique_together = ['github_info', 'github_issue_id']
        ordering = ['-issue_created_at']
    
    def __str__(self):
        return f"Issue #{self.github_issue_id}: {self.title}"


class GitHubCommit(models.Model):
    """
    Stores simplified GitHub commit objects
    """
    github_info = models.ForeignKey(GitHubInfo, on_delete=models.CASCADE, related_name='commits')
    
    # Commit details
    sha = models.CharField(max_length=40, unique=True)
    message = models.TextField()
    author_name = models.CharField(max_length=255)
    author_email = models.EmailField(null=True, blank=True)
    
    # Commit metadata
    additions = models.IntegerField(default=0)
    deletions = models.IntegerField(default=0)
    changed_files = models.IntegerField(default=0)
    
    # Timestamp
    commit_date = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'github_commits'
        ordering = ['-commit_date']
    
    def __str__(self):
        return f"Commit {self.sha[:8]}: {self.message[:50]}"


class ConversionResult(models.Model):
    """
    Stores conversion results for a project
    """
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='conversion_result')
    
    # Conversion artifact paths
    converted_artifact_path = models.CharField(max_length=500, null=True, blank=True)  # Temporary path on server
    
    # Google Drive integration
    google_drive_folder_id = models.CharField(max_length=255, null=True, blank=True)
    google_drive_folder_link = models.URLField(null=True, blank=True)
    
    # Conversion statistics
    total_files_converted = models.IntegerField(default=0)
    conversion_size_bytes = models.BigIntegerField(default=0)
    conversion_duration_seconds = models.FloatField(default=0.0)
    
    # Error message if conversion failed
    error_message = models.TextField(null=True, blank=True)
    
    # Download tracking
    download_count = models.IntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'conversion_results'
    
    def __str__(self):
        return f"Conversion result for {self.project.project_name}"
    
    def increment_download_count(self):
        """Increment download count and update timestamp"""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.save()


class ProjectMonitoring(models.Model):
    """
    Tracks GitHub repository monitoring for automatic re-conversion
    """
    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name='monitoring')
    
    # Monitoring settings
    is_active = models.BooleanField(default=False)
    check_frequency_hours = models.IntegerField(default=24)  # How often to check for updates
    
    # Monitoring status
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_known_commit_hash = models.CharField(max_length=40, null=True, blank=True)
    
    # Notification settings
    notify_on_update = models.BooleanField(default=True)
    auto_convert_on_update = models.BooleanField(default=False)
    
    # Statistics
    total_updates_detected = models.IntegerField(default=0)
    last_update_detected_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'project_monitoring'
    
    def __str__(self):
        return f"Monitoring for {self.project.project_name}"
    
    def should_check_for_updates(self):
        """Check if it's time to check for updates"""
        if not self.is_active:
            return False
        
        if not self.last_checked_at:
            return True
        
        from datetime import timedelta
        next_check = self.last_checked_at + timedelta(hours=self.check_frequency_hours)
        return timezone.now() >= next_check
    
    def record_update_check(self, new_commit_hash=None):
        """Record that we checked for updates"""
        self.last_checked_at = timezone.now()
        
        if new_commit_hash and new_commit_hash != self.last_known_commit_hash:
            self.last_known_commit_hash = new_commit_hash
            self.total_updates_detected += 1
            self.last_update_detected_at = timezone.now()
        
        self.save()
