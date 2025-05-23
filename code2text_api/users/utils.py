"""
Utility functions for user authentication and Google OAuth integration.
"""

import logging
import requests
import json
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)

def get_google_token(auth_code):
    """
    Exchange an authorization code for a Google OAuth token.
    
    Args:
        auth_code: Google authorization code.
    
    Returns:
        dict: Token information including access_token and refresh_token.
    """
    token_url = 'https://oauth2.googleapis.com/token'
    
    data = {
        'code': auth_code,
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'redirect_uri': settings.GOOGLE_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code != 200:
        logger.error(f"Google token error: {response.status_code} - {response.text}")
        raise Exception(f"Failed to get Google token: {response.text}")
    
    token_info = response.json()
    
    # Add expiry time if available
    if 'expires_in' in token_info:
        token_info['expires_at'] = timezone.now() + timezone.timedelta(seconds=token_info['expires_in'])
    
    return token_info


def get_google_user_info(access_token):
    """
    Get user information from Google using an access token.
    
    Args:
        access_token: Google OAuth access token.
    
    Returns:
        dict: User information from Google.
    """
    user_info_url = 'https://www.googleapis.com/oauth2/v1/userinfo'
    headers = {'Authorization': f'Bearer {access_token}'}
    
    response = requests.get(user_info_url, headers=headers)
    
    if response.status_code != 200:
        logger.error(f"Google user info error: {response.status_code} - {response.text}")
        raise Exception(f"Failed to get Google user info: {response.text}")
    
    return response.json()


def create_or_update_user_from_google(user_info, access_token, refresh_token=None, expires_at=None):
    """
    Create or update a user based on Google user information.
    
    Args:
        user_info: User information from Google.
        access_token: Google OAuth access token.
        refresh_token: Google OAuth refresh token.
        expires_at: Token expiry time.
    
    Returns:
        tuple: (user, created) where created is True if a new user was created.
    """
    email = user_info.get('email')
    if not email:
        raise Exception("Email is required from Google")
    
    try:
        # Try to find the user by email
        user = User.objects.get(email=email)
        created = False
    except User.DoesNotExist:
        # Create a new user if not found
        username = email.split('@')[0]
        
        # Ensure username is unique
        base_username = username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=user_info.get('given_name', ''),
            last_name=user_info.get('family_name', '')
        )
        created = True
    
    # Update user with Google OAuth information
    user.google_access_token = access_token
    
    if refresh_token:
        user.google_refresh_token = refresh_token
    
    if expires_at:
        user.google_token_expiry = expires_at
    
    user.save()
    
    # Start trial if new user
    if created:
        user.start_trial()
    
    return user, created


def refresh_google_token(user):
    """
    Refresh a Google OAuth token.
    
    Args:
        user: User object with refresh token.
    
    Returns:
        dict: New token information.
    """
    if not user.google_refresh_token:
        raise Exception("No refresh token available")
    
    token_url = 'https://oauth2.googleapis.com/token'
    
    data = {
        'client_id': settings.GOOGLE_CLIENT_ID,
        'client_secret': settings.GOOGLE_CLIENT_SECRET,
        'refresh_token': user.google_refresh_token,
        'grant_type': 'refresh_token'
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code != 200:
        logger.error(f"Google token refresh error: {response.status_code} - {response.text}")
        raise Exception(f"Failed to refresh Google token: {response.text}")
    
    token_info = response.json()
    
    # Update user with new token information
    user.google_access_token = token_info['access_token']
    
    if 'expires_in' in token_info:
        user.google_token_expiry = timezone.now() + timezone.timedelta(seconds=token_info['expires_in'])
    
    user.save()
    
    return token_info 