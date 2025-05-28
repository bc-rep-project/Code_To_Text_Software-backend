from rest_framework import serializers
from .models import (
    Project, ScanData, GitHubInfo, GitHubIssue, GitHubCommit, 
    ConversionResult, ProjectMonitoring
)


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
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'source_type', 'github_repo_url',
            'original_file_name', 'status', 'last_scan_at', 
            'last_conversion_at', 'created_at', 'updated_at'
        ]


class ProjectDetailSerializer(serializers.ModelSerializer):
    """Detailed project serializer with related data"""
    scan_data = ScanDataSerializer(read_only=True)
    conversion_result = ConversionResultSerializer(read_only=True)
    monitoring = ProjectMonitoringSerializer(read_only=True)
    
    class Meta:
        model = Project
        fields = [
            'id', 'project_name', 'source_type', 'github_repo_url',
            'uploaded_file_key', 'original_file_name', 'status',
            'last_scan_at', 'last_conversion_at', 'last_github_commit_hash',
            'created_at', 'updated_at', 'scan_data', 'conversion_result',
            'monitoring'
        ] 