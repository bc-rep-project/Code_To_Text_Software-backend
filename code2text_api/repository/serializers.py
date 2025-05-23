"""
Serializers for the repository app.
"""

from rest_framework import serializers
from .models import Repository, MonitoringJob

class RepositorySerializer(serializers.ModelSerializer):
    """Serializer for Repository model"""
    class Meta:
        model = Repository
        fields = [
            'id', 'name', 'source', 'github_url', 'latest_commit_hash',
            'languages', 'file_count', 'size', 'status', 'is_monitored',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'latest_commit_hash', 'languages', 'file_count', 
            'size', 'status', 'created_at', 'updated_at'
        ]


class RepositoryAnalyzeSerializer(serializers.Serializer):
    """Serializer for repository analysis request"""
    github_url = serializers.URLField(required=False)
    repo_file = serializers.FileField(required=False)
    
    def validate(self, attrs):
        """Ensure either github_url or repo_file is provided"""
        if not attrs.get('github_url') and not attrs.get('repo_file'):
            raise serializers.ValidationError(
                "Either 'github_url' or 'repo_file' must be provided."
            )
        return attrs


class MonitoringJobSerializer(serializers.ModelSerializer):
    """Serializer for MonitoringJob model"""
    class Meta:
        model = MonitoringJob
        fields = [
            'id', 'repository', 'last_checked', 'last_commit_hash',
            'frequency', 'is_active'
        ]
        read_only_fields = ['id', 'last_checked', 'last_commit_hash']