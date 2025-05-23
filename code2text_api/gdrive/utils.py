"""
Utility functions for Google Drive integration.
"""

import os
import logging
import json
import requests
import mimetypes
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)

def check_google_credentials(access_token):
    """
    Check if Google credentials are valid.
    
    Args:
        access_token: Google OAuth access token.
    
    Returns:
        bool: True if credentials are valid, False otherwise.
    """
    url = 'https://www.googleapis.com/oauth2/v1/tokeninfo'
    params = {'access_token': access_token}
    
    try:
        response = requests.get(url, params=params)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error checking Google credentials: {str(e)}")
        return False


def refresh_google_token_if_needed(user):
    """
    Refresh Google token if it's expired or about to expire.
    
    Args:
        user: User object with Google tokens.
    
    Returns:
        str: Valid access token.
    """
    # Import here to avoid circular imports
    from users.utils import refresh_google_token
    
    # Check if token is valid
    if not user.google_access_token:
        raise Exception("No Google access token available")
    
    # Check if token is expired or about to expire (within 5 minutes)
    if user.google_token_expiry and user.google_token_expiry <= timezone.now() + timezone.timedelta(minutes=5):
        # Refresh token
        if not user.google_refresh_token:
            raise Exception("No refresh token available")
        
        token_info = refresh_google_token(user)
        return token_info['access_token']
    
    return user.google_access_token


def create_drive_folder(access_token, folder_name):
    """
    Create a folder in Google Drive.
    
    Args:
        access_token: Google OAuth access token.
        folder_name: Name of the folder to create.
    
    Returns:
        str: Folder ID.
    """
    url = 'https://www.googleapis.com/drive/v3/files'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    response = requests.post(url, headers=headers, json=metadata)
    
    if response.status_code != 200 and response.status_code != 201:
        logger.error(f"Error creating Google Drive folder: {response.status_code} - {response.text}")
        raise Exception(f"Failed to create Google Drive folder: {response.text}")
    
    folder_info = response.json()
    return folder_info['id']


def upload_file_to_drive(access_token, file_path, file_name=None, parent_folder_id=None):
    """
    Upload a file to Google Drive.
    
    Args:
        access_token: Google OAuth access token.
        file_path: Path to the file to upload.
        file_name: Name to use for the uploaded file (default: basename of file_path).
        parent_folder_id: ID of the parent folder (optional).
    
    Returns:
        dict: File information.
    """
    if not os.path.exists(file_path):
        raise Exception(f"File not found: {file_path}")
    
    # Use basename if file_name not provided
    if not file_name:
        file_name = os.path.basename(file_path)
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    
    # Metadata for the file
    metadata = {
        'name': file_name,
    }
    
    # Add parent folder if specified
    if parent_folder_id:
        metadata['parents'] = [parent_folder_id]
    
    # API endpoints
    create_url = 'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable'
    
    # Headers for creating the upload session
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json; charset=UTF-8',
        'X-Upload-Content-Type': mime_type,
        'X-Upload-Content-Length': str(file_size)
    }
    
    # Create the upload session
    response = requests.post(create_url, headers=headers, json=metadata)
    
    if response.status_code != 200:
        logger.error(f"Error creating upload session: {response.status_code} - {response.text}")
        raise Exception(f"Failed to create upload session: {response.text}")
    
    # Get the upload URL from the Location header
    upload_url = response.headers.get('Location')
    
    # Upload the file
    with open(file_path, 'rb') as f:
        headers = {
            'Content-Type': mime_type
        }
        response = requests.put(
            upload_url,
            headers=headers,
            data=f
        )
    
    if response.status_code != 200 and response.status_code != 201:
        logger.error(f"Error uploading file: {response.status_code} - {response.text}")
        raise Exception(f"Failed to upload file: {response.text}")
    
    # Get file ID and other information
    file_info = response.json()
    
    # Get additional file information
    file_id = file_info['id']
    get_url = f'https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,mimeType,webViewLink'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    response = requests.get(get_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Error getting file information: {response.status_code} - {response.text}")
        return file_info  # Return basic info if we can't get detailed info
    
    return response.json() 