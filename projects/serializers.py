from rest_framework import serializers
from .models import (
    Project, ScanData, GitHubInfo, GitHubIssue, GitHubCommit, 
    ConversionResult, ProjectMonitoring
)


def format_file_size(size_bytes):
    """
    Convert bytes to human readable format
    """
    if size_bytes is None or size_bytes == 0:
        return "0 B"
    
    # Define the units
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    
    # Convert to appropriate unit
    size = float(size_bytes)
    unit_index = 0
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    # Format with appropriate decimal places
    if size >= 100:
        return f"{size:.0f} {units[unit_index]}"
    elif size >= 10:
        return f"{size:.1f} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


class GitHubIssueSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubIssue
        fields = [
            'github_issue_id', 'title', 'url', 'state', 'author', 
            'labels', 'issue_created_at', 'issue_updated_at'
        ]


class GitHubCommitSerializer(serializers.ModelSerializer):
    class Meta:
        model = GitHubCommit
        fields = [
            'sha', 'message', 'author_name', 'author_email',
            'additions', 'deletions', 'changed_files', 'commit_date'
        ]


class GitHubInfoSerializer(serializers.ModelSerializer):
    issues = GitHubIssueSerializer(many=True, read_only=True)
    commits = GitHubCommitSerializer(many=True, read_only=True)
    
    class Meta:
        model = GitHubInfo
        fields = [
            'description', 'stars', 'forks', 'open_issues_count',
            'owner', 'repo_name', 'default_branch', 'repo_created_at',
            'repo_updated_at', 'issues', 'commits'
        ]


class ScanDataSerializer(serializers.ModelSerializer):
    github_info = GitHubInfoSerializer(read_only=True)
    
    class Meta:
        model = ScanData
        fields = [
            'languages_used', 'error_message', 'total_files',
            'total_size_bytes', 'created_at', 'updated_at', 'github_info'
        ]


class ConversionResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversionResult
        fields = [
            'google_drive_folder_id', 'google_drive_folder_link',
            'total_files_converted', 'conversion_size_bytes',
            'conversion_duration_seconds', 'error_message',
            'download_count', 'last_downloaded_at', 'created_at', 'updated_at'
        ]


class ProjectMonitoringSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectMonitoring
        fields = [
            'is_active', 'check_frequency_hours', 'last_checked_at',
            'last_known_commit_hash', 'notify_on_update', 'auto_convert_on_update',
            'total_updates_detected', 'last_update_detected_at'
        ]


class ProjectSerializer(serializers.ModelSerializer):
    """Basic project serializer for list views"""
    file_count = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'source_type', 'github_repo_url',
            'original_file_name', 'status', 'last_scan_at', 
            'last_conversion_at', 'created_at', 'updated_at',
            'file_count', 'size'
        ]
    
    def get_file_count(self, obj):
        """Get the file count from scan data"""
        try:
            return obj.scan_data.total_files
        except (AttributeError, ScanData.DoesNotExist):
            return 0
    
    def get_size(self, obj):
        """Get the formatted size from scan data"""
        try:
            return format_file_size(obj.scan_data.total_size_bytes)
        except (AttributeError, ScanData.DoesNotExist):
            return "N/A"


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Detailed project serializer with related data"""
    scan_data = ScanDataSerializer(read_only=True)
    conversion_result = ConversionResultSerializer(read_only=True)
    monitoring = ProjectMonitoringSerializer(read_only=True)
    file_count = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'source_type', 'github_repo_url',
            'uploaded_file_key', 'original_file_name', 'status',
            'last_scan_at', 'last_conversion_at', 'last_github_commit_hash',
            'created_at', 'updated_at', 'scan_data', 'conversion_result',
            'monitoring', 'file_count', 'size'
        ]
    
    def get_file_count(self, obj):
        """Get the file count from scan data"""
        try:
            return obj.scan_data.total_files
        except (AttributeError, ScanData.DoesNotExist):
            return 0
    
    def get_size(self, obj):
        """Get the formatted size from scan data"""
        try:
            return format_file_size(obj.scan_data.total_size_bytes)
        except (AttributeError, ScanData.DoesNotExist):
            return "N/A" 