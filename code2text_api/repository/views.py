"""
API views for the repository app.
"""

import os
import tempfile
import shutil
import logging
import git
from django.conf import settings
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Repository, MonitoringJob
from .serializers import (
    RepositorySerializer, 
    RepositoryAnalyzeSerializer,
    MonitoringJobSerializer
)
from .utils import (
    analyze_repository,
    get_github_issues,
    get_github_commits,
    detect_languages,
    get_commit_hash
)

logger = logging.getLogger(__name__)

class RepositoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for repositories.
    """
    serializer_class = RepositorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Get repositories for the current user."""
        return Repository.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create a new repository and associate it with the user."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def analyze(self, request):
        """
        Analyze a repository from GitHub URL or uploaded file.
        """
        serializer = RepositoryAnalyzeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        github_url = data.get('github_url')
        repo_file = data.get('repo_file')
        
        # Create repository instance
        if github_url:
            # Extract repo name from GitHub URL
            repo_name = github_url.strip('/').split('/')[-1]
            if repo_name.endswith('.git'):
                repo_name = repo_name[:-4]
            
            # Create repository from GitHub URL
            repository = Repository.objects.create(
                user=request.user,
                name=repo_name,
                source='github',
                github_url=github_url,
                status='analyzing'
            )
            
            try:
                # Create a temp directory for cloning
                repo_dir = os.path.join(settings.REPO_STORAGE_PATH, f"{repository.id}")
                os.makedirs(repo_dir, exist_ok=True)
                
                # Clone the repository
                git_repo = git.Repo.clone_from(github_url, repo_dir)
                
                # Get the latest commit hash
                commit_hash = str(git_repo.head.commit)
                
                # Analyze repository
                result = analyze_repository(repo_dir)
                
                # Update repository with analysis results
                repository.latest_commit_hash = commit_hash
                repository.languages = result.get('languages', [])
                repository.file_count = result.get('file_count', 0)
                repository.size = result.get('size', 0)
                repository.status = 'ready'
                repository.storage_path = repo_dir
                repository.save()
                
                return Response(
                    RepositorySerializer(repository).data,
                    status=status.HTTP_201_CREATED
                )
            
            except Exception as e:
                logger.error(f"Error analyzing repository: {str(e)}")
                repository.status = 'error'
                repository.save()
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        elif repo_file:
            # Create temp directory
            temp_dir = tempfile.mkdtemp()
            
            try:
                # Save uploaded file
                file_path = os.path.join(temp_dir, repo_file.name)
                with open(file_path, 'wb') as f:
                    for chunk in repo_file.chunks():
                        f.write(chunk)
                
                # Extract file if it's a zip or tar
                repo_dir = os.path.join(settings.REPO_STORAGE_PATH, f"{request.user.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}")
                os.makedirs(repo_dir, exist_ok=True)
                
                # TODO: Extract zip/tar file to repo_dir
                
                # For now, just use the name of the uploaded file
                repo_name = os.path.splitext(repo_file.name)[0]
                
                # Create repository
                repository = Repository.objects.create(
                    user=request.user,
                    name=repo_name,
                    source='upload',
                    status='analyzing',
                    storage_path=repo_dir
                )
                
                # Analyze repository
                result = analyze_repository(repo_dir)
                
                # Update repository with analysis results
                repository.languages = result.get('languages', [])
                repository.file_count = result.get('file_count', 0)
                repository.size = result.get('size', 0)
                repository.status = 'ready'
                repository.save()
                
                return Response(
                    RepositorySerializer(repository).data,
                    status=status.HTTP_201_CREATED
                )
            
            except Exception as e:
                logger.error(f"Error processing uploaded repository: {str(e)}")
                if 'repository' in locals():
                    repository.status = 'error'
                    repository.save()
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            finally:
                # Clean up temp directory
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    @action(detail=True, methods=['get'])
    def languages(self, request, pk=None):
        """
        Get programming languages used in the repository.
        """
        repository = self.get_object()
        return Response({'languages': repository.languages})
    
    @action(detail=True, methods=['get'])
    def issues(self, request, pk=None):
        """
        Get GitHub issues for the repository.
        Only works for GitHub repositories.
        """
        repository = self.get_object()
        
        if repository.source != 'github' or not repository.github_url:
            return Response(
                {'error': 'Issues are only available for GitHub repositories'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            issues = get_github_issues(repository.github_url)
            return Response(issues)
        except Exception as e:
            logger.error(f"Error fetching GitHub issues: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def commits(self, request, pk=None):
        """
        Get GitHub commits for the repository.
        Only works for GitHub repositories.
        """
        repository = self.get_object()
        
        if repository.source != 'github' or not repository.github_url:
            return Response(
                {'error': 'Commits are only available for GitHub repositories'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            commits = get_github_commits(repository.github_url)
            return Response(commits)
        except Exception as e:
            logger.error(f"Error fetching GitHub commits: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MonitoringJobViewSet(viewsets.ModelViewSet):
    """
    API endpoint for repository monitoring jobs.
    """
    serializer_class = MonitoringJobSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get monitoring jobs for the current user."""
        return MonitoringJob.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        """Create a new monitoring job and associate it with the user."""
        repository = serializer.validated_data['repository']
        
        # Ensure the repository belongs to the user
        if repository.user != self.request.user:
            return Response(
                {'error': 'Repository does not belong to the user'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update repository monitoring status
        repository.is_monitored = True
        repository.save()
        
        serializer.save(
            user=self.request.user,
            last_commit_hash=repository.latest_commit_hash or ''
        )
    
    def perform_destroy(self, instance):
        """Delete a monitoring job and update repository monitoring status."""
        repository = instance.repository
        repository.is_monitored = False
        repository.save()
        instance.delete() 