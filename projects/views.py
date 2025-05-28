from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
import os
import json
import zipfile
import tempfile
import shutil
from urllib.parse import urlparse
import requests
from datetime import datetime, timedelta
from django.utils import timezone

from .models import Project, ScanData, GitHubInfo, ConversionResult, ProjectMonitoring
from .serializers import ProjectSerializer, ProjectDetailSerializer

# Create your views here.

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def project_list(request):
    """
    List user's projects or create a new project
    """
    if request.method == 'GET':
        projects = Project.objects.filter(user=request.user)
        serializer = ProjectSerializer(projects, many=True)
        return Response({
            'projects': serializer.data,
            'total_count': projects.count()
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        data = request.data
        project_name = data.get('project_name', '').strip()
        source_type = data.get('source_type', '').strip()
        github_repo_url = data.get('github_repo_url', '').strip()
        
        # Validation
        if not project_name:
            return Response({
                'error': 'Project name is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not source_type or source_type not in ['github', 'upload']:
            return Response({
                'error': 'Source type must be either "github" or "upload"'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if source_type == 'github' and not github_repo_url:
            return Response({
                'error': 'GitHub repository URL is required for GitHub projects'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate GitHub URL format
        if source_type == 'github':
            if not _is_valid_github_url(github_repo_url):
                return Response({
                    'error': 'Invalid GitHub repository URL format'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user already has a project with this name
        if Project.objects.filter(user=request.user, project_name=project_name).exists():
            return Response({
                'error': 'A project with this name already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create project
        project_data = {
            'user': request.user,
            'project_name': project_name,
            'source_type': source_type,
            'status': 'pending_scan'
        }
        
        if source_type == 'github':
            project_data['github_repo_url'] = github_repo_url
        
        project = Project.objects.create(**project_data)
        
        # If it's a GitHub project, we could trigger an immediate scan
        # For now, we'll just return the created project
        
        serializer = ProjectSerializer(project)
        return Response({
            'message': 'Project created successfully',
            'project': serializer.data
        }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def project_detail(request, project_id):
    """
    Get detailed information about a specific project
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    serializer = ProjectDetailSerializer(project)
    return Response({
        'project': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_code(request, project_id):
    """
    Upload code files for a project
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if this is an upload project
    if project.source_type != 'upload':
        return Response({
            'error': 'This endpoint is only for upload projects'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if file is provided
    if 'file' not in request.FILES:
        return Response({
            'error': 'No file provided'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    uploaded_file = request.FILES['file']
    
    # Validate file type (should be zip)
    if not uploaded_file.name.endswith('.zip'):
        return Response({
            'error': 'Only ZIP files are supported'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate file size (max 100MB)
    max_size = 100 * 1024 * 1024  # 100MB
    if uploaded_file.size > max_size:
        return Response({
            'error': 'File size exceeds 100MB limit'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Save file to storage
        file_path = f'uploads/{request.user.id}/{project.id}/{uploaded_file.name}'
        saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))
        
        # Update project
        project.uploaded_file_key = saved_path
        project.original_file_name = uploaded_file.name
        project.status = 'pending_scan'
        project.save()
        
        return Response({
            'message': 'File uploaded successfully',
            'file_name': uploaded_file.name,
            'file_size': uploaded_file.size,
            'project_status': project.status
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': f'Failed to upload file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_project(request, project_id):
    """
    Trigger a scan for a project
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if project can be scanned
    if not project.can_be_scanned():
        return Response({
            'error': f'Project cannot be scanned in current status: {project.status}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # For GitHub projects, check if URL is accessible
    if project.source_type == 'github':
        if not _validate_github_repo_access(project.github_repo_url):
            return Response({
                'error': 'GitHub repository is not accessible or does not exist'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # For upload projects, check if file exists
    elif project.source_type == 'upload':
        if not project.uploaded_file_key or not default_storage.exists(project.uploaded_file_key):
            return Response({
                'error': 'No uploaded file found for this project'
            }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update project status
    project.status = 'scanning'
    project.save()
    
    # Here you would typically trigger an async task to perform the actual scanning
    # For now, we'll simulate a quick scan
    try:
        _perform_mock_scan(project)
        return Response({
            'message': 'Scan completed successfully',
            'project_status': project.status
        }, status=status.HTTP_200_OK)
    except Exception as e:
        project.status = 'error'
        project.save()
        return Response({
            'error': f'Scan failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def convert_project(request, project_id):
    """
    Trigger conversion for a scanned project
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if project can be converted
    if not project.can_be_converted():
        return Response({
            'error': f'Project cannot be converted in current status: {project.status}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update project status
    project.status = 'converting'
    project.save()
    
    # Here you would typically trigger an async task to perform the actual conversion
    # For now, we'll simulate a quick conversion
    try:
        _perform_mock_conversion(project)
        return Response({
            'message': 'Conversion completed successfully',
            'project_status': project.status
        }, status=status.HTTP_200_OK)
    except Exception as e:
        project.status = 'error'
        project.save()
        return Response({
            'error': f'Conversion failed: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_project(request, project_id):
    """
    Download the converted project as a ZIP file
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if project has been converted
    if project.status != 'converted' and project.status != 'completed':
        return Response({
            'error': 'Project has not been converted yet'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if conversion result exists
    try:
        conversion_result = project.conversion_result
    except ConversionResult.DoesNotExist:
        return Response({
            'error': 'No conversion result found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if converted file exists
    if not conversion_result.converted_artifact_path or not os.path.exists(conversion_result.converted_artifact_path):
        return Response({
            'error': 'Converted file not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    try:
        # Read the file and return as response
        with open(conversion_result.converted_artifact_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{project.project_name}_converted.zip"'
            
            # Update download statistics
            conversion_result.increment_download_count()
            
            return response
            
    except Exception as e:
        return Response({
            'error': f'Failed to download file: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_to_drive(request, project_id):
    """
    Upload converted project to Google Drive
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if project has been converted
    if project.status != 'converted' and project.status != 'completed':
        return Response({
            'error': 'Project has not been converted yet'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if conversion result exists
    try:
        conversion_result = project.conversion_result
    except ConversionResult.DoesNotExist:
        return Response({
            'error': 'No conversion result found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if already uploaded to drive
    if conversion_result.google_drive_folder_id:
        return Response({
            'message': 'Project already uploaded to Google Drive',
            'drive_folder_link': conversion_result.google_drive_folder_link
        }, status=status.HTTP_200_OK)
    
    # Update project status
    project.status = 'uploading_to_drive'
    project.save()
    
    try:
        # Here you would implement actual Google Drive upload
        # For now, we'll simulate it
        _perform_mock_drive_upload(project, conversion_result)
        
        return Response({
            'message': 'Project uploaded to Google Drive successfully',
            'drive_folder_link': conversion_result.google_drive_folder_link
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        project.status = 'converted'  # Revert status
        project.save()
        return Response({
            'error': f'Failed to upload to Google Drive: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper functions

def _is_valid_github_url(url):
    """Validate GitHub repository URL format"""
    try:
        parsed = urlparse(url)
        if parsed.netloc != 'github.com':
            return False
        
        path_parts = parsed.path.strip('/').split('/')
        if len(path_parts) != 2:
            return False
        
        # Check if owner and repo name are valid
        owner, repo = path_parts
        if not owner or not repo:
            return False
        
        return True
    except:
        return False


def _validate_github_repo_access(url):
    """Check if GitHub repository is accessible"""
    try:
        # Convert to API URL
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        owner, repo = path_parts[0], path_parts[1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        response = requests.get(api_url, timeout=10)
        
        return response.status_code == 200
    except:
        return False


def _perform_mock_scan(project):
    """Perform a mock scan of the project"""
    # Create or update scan data
    scan_data, created = ScanData.objects.get_or_create(
        project=project,
        defaults={
            'languages_used': {'Python': '60%', 'JavaScript': '30%', 'HTML': '10%'},
            'total_files': 45,
            'total_size_bytes': 1024 * 1024 * 2  # 2MB
        }
    )
    
    if not created:
        scan_data.languages_used = {'Python': '60%', 'JavaScript': '30%', 'HTML': '10%'}
        scan_data.total_files = 45
        scan_data.total_size_bytes = 1024 * 1024 * 2
        scan_data.save()
    
    # If it's a GitHub project, create GitHub info
    if project.source_type == 'github':
        parsed = urlparse(project.github_repo_url)
        path_parts = parsed.path.strip('/').split('/')
        owner, repo_name = path_parts[0], path_parts[1]
        
        github_info, created = GitHubInfo.objects.get_or_create(
            scan_data=scan_data,
            defaults={
                'owner': owner,
                'repo_name': repo_name,
                'description': 'A sample repository for testing',
                'stars': 42,
                'forks': 7,
                'open_issues_count': 3,
                'default_branch': 'main'
            }
        )
    
    # Update project status
    project.status = 'scanned'
    project.last_scan_at = timezone.now()
    project.save()


def _perform_mock_conversion(project):
    """Perform a mock conversion of the project"""
    # Create a temporary zip file to simulate conversion
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, f"{project.project_name}_converted.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        # Add some mock converted files
        zipf.writestr('README.md', f'# {project.project_name}\n\nConverted project documentation.')
        zipf.writestr('code_summary.txt', 'This is a mock conversion result.')
        zipf.writestr('file_structure.json', json.dumps({
            'total_files': 45,
            'languages': ['Python', 'JavaScript', 'HTML'],
            'conversion_date': timezone.now().isoformat()
        }))
    
    # Create or update conversion result
    conversion_result, created = ConversionResult.objects.get_or_create(
        project=project,
        defaults={
            'converted_artifact_path': zip_path,
            'total_files_converted': 45,
            'conversion_size_bytes': os.path.getsize(zip_path),
            'conversion_duration_seconds': 2.5
        }
    )
    
    if not created:
        # Remove old file if exists
        if conversion_result.converted_artifact_path and os.path.exists(conversion_result.converted_artifact_path):
            os.remove(conversion_result.converted_artifact_path)
        
        conversion_result.converted_artifact_path = zip_path
        conversion_result.total_files_converted = 45
        conversion_result.conversion_size_bytes = os.path.getsize(zip_path)
        conversion_result.conversion_duration_seconds = 2.5
        conversion_result.save()
    
    # Update project status
    project.status = 'converted'
    project.last_conversion_at = timezone.now()
    project.save()


def _perform_mock_drive_upload(project, conversion_result):
    """Perform a mock Google Drive upload"""
    # Simulate Google Drive upload
    mock_folder_id = f"mock_folder_{project.id}_{int(timezone.now().timestamp())}"
    mock_folder_link = f"https://drive.google.com/drive/folders/{mock_folder_id}"
    
    # Update conversion result
    conversion_result.google_drive_folder_id = mock_folder_id
    conversion_result.google_drive_folder_link = mock_folder_link
    conversion_result.save()
    
    # Update project status
    project.status = 'completed'
    project.save()
