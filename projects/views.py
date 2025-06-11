import os
import json
import shutil
import tempfile
import zipfile
import requests
import logging
import random
import string
from urllib.parse import urlparse
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

# Add the import for our conversion utils
from .conversion_utils import perform_codebase_conversion

from .models import Project, ScanData, GitHubInfo, ConversionResult, ProjectMonitoring
from .serializers import ProjectSerializer, ScanDataSerializer

# Google Drive integration
from allauth.socialaccount.models import SocialToken
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

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
    
    serializer = ProjectSerializer(project)
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
    
    # For GitHub projects, validate and check accessibility
    if project.source_type == 'github':
        validation_result = _validate_github_repo_access_detailed(project.github_repo_url)
        if not validation_result['success']:
            logger.warning(f"GitHub repo validation failed for {project.github_repo_url}: {validation_result['error']}")
            return Response({
                'error': validation_result['error']
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log successful validation
        logger.info(f"GitHub repo validation successful for {project.github_repo_url}")
    
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
        logger.error(f"Scan failed for project {project_id}: {str(e)}", exc_info=True)
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
        _perform_real_conversion(project)
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


def generate_otp(length=6):
    """Generate a random OTP of specified length"""
    return ''.join(random.choices(string.digits, k=length))

def upload_to_google_drive_task(*args, **kwargs):
    """
    Placeholder for Celery task that handles actual Google Drive upload
    In production, this would be implemented as a proper Celery task
    """
    print(f"CELERY TASK (Placeholder): upload_to_google_drive_task called with args: {args}, kwargs: {kwargs}")
    
    # Extract parameters
    user_id = kwargs.get('user_id') or (args[0] if len(args) > 0 else None)
    project_id = kwargs.get('project_id') or (args[1] if len(args) > 1 else None)
    verified_email = kwargs.get('verified_email')
    
    if not project_id:
        print("ERROR: No project_id provided to upload task")
        return
    
    try:
        project = Project.objects.get(id=project_id)
        
        # Simulate Google Drive upload process
        print(f"Simulating Google Drive upload for project {project.project_name}")
        
        # Update project status
        project.status = "uploading_to_drive"
        project.save()
        
        # Simulate upload delay
        import time
        time.sleep(2)
        
        # Update conversion result with mock Google Drive data
        conversion_result = project.conversion_result
        conversion_result.google_drive_folder_id = f"mock_folder_{project_id}"
        conversion_result.google_drive_folder_link = f"https://drive.google.com/drive/folders/mock_folder_{project_id}"
        conversion_result.save()
        
        # Update project status to completed
        project.status = "completed"
        project.save()
        
        print(f"Project {project_id} Google Drive upload simulation completed")
        
    except Project.DoesNotExist:
        print(f"ERROR: Project {project_id} not found")
    except Exception as e:
        print(f"ERROR in upload task: {str(e)}")
        if project_id:
            try:
                project = Project.objects.get(id=project_id)
                project.status = "converted"  # Revert to previous status
                project.save()
            except:
                pass

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_to_drive(request, project_id):
    """
    Upload project to Google Drive using AllAuth stored tokens
    """
    try:
        project = Project.objects.get(id=project_id, user=request.user)
    except Project.DoesNotExist:
        return Response({
            'error': 'Project not found'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if project is converted
    if project.status != 'converted':
        return Response({
            'error': 'Project must be converted before uploading to Google Drive'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user has Google tokens
    social_token = SocialToken.objects.filter(
        account__user=request.user, 
        account__provider='google'
    ).first()
    
    if not social_token:
        # User needs to authenticate with Google
        google_auth_url = f"{request.build_absolute_uri('/accounts/google/login/')}?next=/api/projects/{project_id}/upload_to_drive/"
        return Response({
            'action_required': 'GOOGLE_OAUTH_REQUIRED',
            'message': 'Google authentication required',
            'auth_url': google_auth_url
        }, status=status.HTTP_200_OK)
    
    try:
        # Create credentials from stored tokens
        credentials = Credentials(
            token=social_token.token,
            refresh_token=social_token.token_secret,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET
        )
        
        # Refresh token if needed
        if credentials.expired:
            credentials.refresh(Request())
            # Update stored token
            social_token.token = credentials.token
            social_token.save()
        
        # Upload to Google Drive
        drive_folder_link = _upload_project_to_google_drive(project, credentials)
        
        # Update project with Google Drive info
        conversion_result = ConversionResult.objects.filter(project=project).first()
        if conversion_result:
            conversion_result.google_drive_folder_link = drive_folder_link
            conversion_result.google_drive_folder_id = drive_folder_link.split('/')[-1]
            conversion_result.save()
        
        return Response({
            'message': 'Project uploaded to Google Drive successfully',
            'status': 'uploaded',
            'drive_folder_link': drive_folder_link
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Google Drive upload error: {str(e)}")
        return Response({
            'error': f'Failed to upload to Google Drive: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _upload_project_to_google_drive(project, credentials):
    """
    Actual Google Drive upload implementation
    """
    try:
        service = build('drive', 'v3', credentials=credentials)
        
        # Create a folder for the project
        folder_metadata = {
            'name': f"Code2Text - {project.project_name}",
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder.get('id')
        
        # Get the converted file to upload
        conversion_result = ConversionResult.objects.filter(project=project).first()
        if conversion_result and conversion_result.output_file_key:
            # Upload the converted file
            file_content = default_storage.open(conversion_result.output_file_key).read()
            
            file_metadata = {
                'name': f"{project.project_name}_converted.txt",
                'parents': [folder_id]
            }
            
            from googleapiclient.http import MediaInMemoryUpload
            media = MediaInMemoryUpload(file_content, mimetype='text/plain')
            
            uploaded_file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            logger.info(f"Uploaded file {uploaded_file.get('id')} to Google Drive")
        
        # Return the shareable folder link
        folder_link = f"https://drive.google.com/drive/folders/{folder_id}"
        return folder_link
        
    except HttpError as error:
        logger.error(f"Google Drive API error: {error}")
        raise Exception(f"Google Drive API error: {error}")
    except Exception as error:
        logger.error(f"Google Drive upload error: {error}")
        raise Exception(f"Upload failed: {error}")


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


def _validate_github_repo_access_detailed(url):
    """
    Check if GitHub repository is accessible with detailed error reporting
    """
    try:
        # First validate URL format
        if not _is_valid_github_url(url):
            return {
                'success': False,
                'error': 'Invalid GitHub URL format. Please provide a valid GitHub repository URL (e.g., https://github.com/username/repository)'
            }
        
        # Convert to API URL
        parsed = urlparse(url)
        path_parts = parsed.path.strip('/').split('/')
        owner, repo = path_parts[0], path_parts[1]
        
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        logger.info(f"Checking GitHub API access for: {api_url}")
        
        # Make request with longer timeout and proper headers
        headers = {
            'User-Agent': 'CodeToTextSoftware/1.0',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Add GitHub token if available (for higher rate limits and private repos)
        github_token = os.environ.get('GITHUB_TOKEN')
        if github_token:
            headers['Authorization'] = f'token {github_token}'
            logger.info("Using GitHub token for API access")
        else:
            logger.warning("No GitHub token found - using unauthenticated requests (lower rate limits)")
        
        response = requests.get(api_url, headers=headers, timeout=15)
        
        logger.info(f"GitHub API response status: {response.status_code}")
        
        if response.status_code == 200:
            repo_data = response.json()
            # Check if repository is empty
            if repo_data.get('size', 0) == 0:
                logger.warning(f"Repository {owner}/{repo} appears to be empty")
            
            return {
                'success': True,
                'data': {
                    'owner': owner,
                    'repo': repo,
                    'private': repo_data.get('private', False),
                    'size': repo_data.get('size', 0),
                    'default_branch': repo_data.get('default_branch', 'main')
                }
            }
        elif response.status_code == 404:
            return {
                'success': False,
                'error': f'GitHub repository "{owner}/{repo}" not found or is private and requires authentication'
            }
        elif response.status_code == 403:
            # Check if it's rate limiting
            if 'rate limit' in response.text.lower():
                return {
                    'success': False,
                    'error': 'GitHub API rate limit exceeded. Please try again later or configure a GitHub token for higher limits'
                }
            else:
                return {
                    'success': False,
                    'error': 'Access forbidden. Repository might be private or requires different permissions'
                }
        else:
            return {
                'success': False,
                'error': f'GitHub API returned status {response.status_code}. Please check if the repository exists and is accessible'
            }
            
    except requests.exceptions.Timeout:
        logger.error(f"Timeout while checking GitHub repository: {url}")
        return {
            'success': False,
            'error': 'Timeout while checking GitHub repository. Please try again or check your internet connection'
        }
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error while checking GitHub repository: {url}")
        return {
            'success': False,
            'error': 'Unable to connect to GitHub. Please check your internet connection and try again'
        }
    except Exception as e:
        logger.error(f"Unexpected error while validating GitHub repo {url}: {str(e)}", exc_info=True)
        return {
            'success': False,
            'error': f'Unexpected error while checking repository: {str(e)}'
        }

def _validate_github_repo_access(url):
    """Check if GitHub repository is accessible (legacy function for backward compatibility)"""
    result = _validate_github_repo_access_detailed(url)
    return result['success']


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


def _perform_real_conversion(project):
    """Perform the actual conversion of the project"""
    try:
        # Determine source directory based on project type
        if project.source_type == 'github':
            # For GitHub projects, we'll need to clone the repository first
            source_directory = _clone_github_repository(project)
            if not source_directory:
                raise Exception("Failed to clone GitHub repository")
        else:
            # For uploaded projects, extract the ZIP file to a temporary directory
            source_directory = _extract_uploaded_file(project)
            if not source_directory:
                raise Exception("Failed to extract uploaded file")
        
        # Perform the actual conversion
        conversion_result = perform_codebase_conversion(project, source_directory)
        
        if not conversion_result['success']:
            raise Exception(conversion_result.get('error', 'Unknown conversion error'))
        
        # Get conversion statistics
        stats = conversion_result['stats']
        zip_path = conversion_result['zip_path']
        
        # Create or update conversion result in database
        db_conversion_result, created = ConversionResult.objects.get_or_create(
            project=project,
            defaults={
                'converted_artifact_path': zip_path,
                'total_files_converted': stats.get('files_converted', 0),
                'conversion_size_bytes': os.path.getsize(zip_path),
                'conversion_duration_seconds': stats.get('conversion_duration_seconds', 0)
            }
        )
        
        if not created:
            # Remove old file if exists
            if db_conversion_result.converted_artifact_path and os.path.exists(db_conversion_result.converted_artifact_path):
                os.remove(db_conversion_result.converted_artifact_path)
            
            # Update with new conversion data
            db_conversion_result.converted_artifact_path = zip_path
            db_conversion_result.total_files_converted = stats.get('files_converted', 0)
            db_conversion_result.conversion_size_bytes = os.path.getsize(zip_path)
            db_conversion_result.conversion_duration_seconds = stats.get('conversion_duration_seconds', 0)
            db_conversion_result.save()
        
        # Clean up temporary source directory
        if source_directory:
            try:
                shutil.rmtree(source_directory, ignore_errors=True)
            except Exception as e:
                logger.warning(f"Failed to cleanup temporary directory {source_directory}: {e}")
        
        # Update project status
        project.status = 'converted'
        project.last_conversion_at = timezone.now()
        project.save()
        
        logger.info(f"Successfully converted project {project.id}: {stats.get('files_converted', 0)} files converted")
        
    except Exception as e:
        logger.error(f"Conversion failed for project {project.id}: {str(e)}")
        project.status = 'error'
        project.save()
        raise


def _extract_uploaded_file(project):
    """Extract uploaded ZIP file to a temporary directory"""
    try:
        # Check if the uploaded file exists
        if not project.uploaded_file_key or not default_storage.exists(project.uploaded_file_key):
            logger.error(f"Uploaded file not found for project {project.id}: {project.uploaded_file_key}")
            return None
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"upload_{project.id}_")
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir, exist_ok=True)
        
        logger.info(f"Extracting uploaded file {project.uploaded_file_key} to {extract_dir}")
        
        # Read the uploaded file from storage
        with default_storage.open(project.uploaded_file_key, 'rb') as f:
            file_content = f.read()
        
        # Save to temporary location for extraction
        temp_zip_path = os.path.join(temp_dir, project.original_file_name or "upload.zip")
        with open(temp_zip_path, 'wb') as f:
            f.write(file_content)
        
        # Extract the ZIP file
        try:
            with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Remove the temporary ZIP file
            os.remove(temp_zip_path)
            
            # Verify extraction was successful
            if not os.listdir(extract_dir):
                logger.error(f"Extracted directory is empty for project {project.id}")
                return None
            
            logger.info(f"Successfully extracted uploaded file to {extract_dir}")
            return extract_dir
            
        except zipfile.BadZipFile:
            logger.error(f"Invalid ZIP file for project {project.id}: {project.uploaded_file_key}")
            return None
        except Exception as e:
            logger.error(f"Error extracting ZIP file for project {project.id}: {str(e)}")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting uploaded file for project {project.id}: {str(e)}")
        return None


def _clone_github_repository(project):
    """Clone a GitHub repository to a temporary directory"""
    try:
        import subprocess
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix=f"repo_{project.id}_")
        
        # Extract repository information
        parsed = urlparse(project.github_repo_url)
        path_parts = parsed.path.strip('/').split('/')
        owner, repo_name = path_parts[0], path_parts[1]
        
        # Clean repo name (remove .git suffix if present)
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        clone_url = f"https://github.com/{owner}/{repo_name}.git"
        target_dir = os.path.join(temp_dir, repo_name)
        
        logger.info(f"Cloning repository {clone_url} to {target_dir}")
        
        # Clone the repository with limited depth to save space and time
        cmd = [
            'git', 'clone',
            '--depth', '1',  # Shallow clone
            '--single-branch',  # Only default branch
            clone_url,
            target_dir
        ]
        
        # Execute clone command with timeout
        result = subprocess.run(
            cmd,
            timeout=300,  # 5 minute timeout
            capture_output=True,
            text=True,
            cwd=temp_dir
        )
        
        if result.returncode != 0:
            logger.error(f"Git clone failed for {clone_url}: {result.stderr}")
            return None
        
        # Verify the cloned directory exists and has content
        if not os.path.exists(target_dir) or not os.listdir(target_dir):
            logger.error(f"Cloned directory is empty or doesn't exist: {target_dir}")
            return None
        
        logger.info(f"Successfully cloned repository to {target_dir}")
        return target_dir
        
    except subprocess.TimeoutExpired:
        logger.error(f"Git clone timeout for repository {project.github_repo_url}")
        return None
    except Exception as e:
        logger.error(f"Error cloning repository {project.github_repo_url}: {str(e)}")
        return None


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
