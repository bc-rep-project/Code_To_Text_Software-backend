from django.shortcuts import render
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import timedelta
import requests
import jwt

from .models import User, UserProfile
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, 
    UserProfileSerializer, GoogleOAuthSerializer
)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Register a new user with email and password
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Create user profile
        UserProfile.objects.create(user=user)
        
        # Create token
        token, created = Token.objects.get_or_create(user=user)
        
        return Response({
            'message': 'User created successfully',
            'token': token.key,
            'user': {
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'subscription_status': user.subscription_status,
                'trial_ends_at': user.trial_ends_at,
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Login user with email/username and password
    """
    serializer = UserLoginSerializer(data=request.data)
    if serializer.is_valid():
        username_or_email = serializer.validated_data['username_or_email']
        password = serializer.validated_data['password']
        
        # Try to authenticate with username first, then email
        user = authenticate(username=username_or_email, password=password)
        if not user:
            # Try with email
            try:
                user_obj = User.objects.get(email=username_or_email)
                user = authenticate(username=user_obj.username, password=password)
            except User.DoesNotExist:
                pass
        
        if user and user.is_active:
            token, created = Token.objects.get_or_create(user=user)
            return Response({
                'message': 'Login successful',
                'token': token.key,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'subscription_status': user.subscription_status,
                    'trial_ends_at': user.trial_ends_at,
                    'can_access_premium': user.can_access_premium_features(),
                }
            }, status=status.HTTP_200_OK)
        
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout user by deleting their token
    """
    try:
        token = Token.objects.get(user=request.user)
        token.delete()
        return Response({
            'message': 'Logout successful'
        }, status=status.HTTP_200_OK)
    except Token.DoesNotExist:
        return Response({
            'error': 'No active session found'
        }, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def google_oauth(request):
    """
    Handle Google OAuth authentication
    """
    serializer = GoogleOAuthSerializer(data=request.data)
    if serializer.is_valid():
        access_token = serializer.validated_data['access_token']
        
        # Verify token with Google
        try:
            google_response = requests.get(
                f'https://www.googleapis.com/oauth2/v1/userinfo?access_token={access_token}'
            )
            
            if google_response.status_code != 200:
                return Response({
                    'error': 'Invalid Google access token'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            google_data = google_response.json()
            
            # Check if user exists
            user = None
            try:
                user = User.objects.get(google_id=google_data['id'])
            except User.DoesNotExist:
                try:
                    user = User.objects.get(email=google_data['email'])
                    # Link Google account to existing user
                    user.google_id = google_data['id']
                    user.save()
                except User.DoesNotExist:
                    # Create new user
                    user = User.objects.create_user(
                        username=google_data['email'],
                        email=google_data['email'],
                        first_name=google_data.get('given_name', ''),
                        last_name=google_data.get('family_name', ''),
                        google_id=google_data['id']
                    )
                    # Create user profile
                    UserProfile.objects.create(
                        user=user,
                        avatar_url=google_data.get('picture', '')
                    )
            
            # Update Google tokens
            user.google_access_token = access_token
            if 'refresh_token' in serializer.validated_data:
                user.google_refresh_token = serializer.validated_data['refresh_token']
            user.save()
            
            # Create or get token
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'message': 'Google OAuth successful',
                'token': token.key,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'subscription_status': user.subscription_status,
                    'trial_ends_at': user.trial_ends_at,
                    'can_access_premium': user.can_access_premium_features(),
                }
            }, status=status.HTTP_200_OK)
            
        except requests.RequestException:
            return Response({
                'error': 'Failed to verify Google token'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    """
    Get current user profile
    """
    try:
        profile = request.user.profile
        serializer = UserProfileSerializer(profile)
        return Response({
            'user': {
                'id': request.user.id,
                'email': request.user.email,
                'username': request.user.username,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'subscription_status': request.user.subscription_status,
                'trial_ends_at': request.user.trial_ends_at,
                'can_access_premium': request.user.can_access_premium_features(),
            },
            'profile': serializer.data
        }, status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        # Create profile if it doesn't exist
        profile = UserProfile.objects.create(user=request.user)
        serializer = UserProfileSerializer(profile)
        return Response({
            'user': {
                'id': request.user.id,
                'email': request.user.email,
                'username': request.user.username,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'subscription_status': request.user.subscription_status,
                'trial_ends_at': request.user.trial_ends_at,
                'can_access_premium': request.user.can_access_premium_features(),
            },
            'profile': serializer.data
        }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user profile
    """
    user = request.user
    
    # Update user fields
    if 'first_name' in request.data:
        user.first_name = request.data['first_name']
    if 'last_name' in request.data:
        user.last_name = request.data['last_name']
    if 'email' in request.data:
        user.email = request.data['email']
    
    user.save()
    
    # Update profile if it exists
    try:
        profile = user.profile
        profile_serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if profile_serializer.is_valid():
            profile_serializer.save()
    except UserProfile.DoesNotExist:
        pass
    
    return Response({
        'message': 'Profile updated successfully',
        'user': {
            'id': user.id,
            'email': user.email,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'subscription_status': user.subscription_status,
            'trial_ends_at': user.trial_ends_at,
            'can_access_premium': user.can_access_premium_features(),
        }
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """
    Get current user's subscription status
    """
    user = request.user
    
    return Response({
        'subscription_status': user.subscription_status,
        'trial_ends_at': user.trial_ends_at,
        'is_trial_expired': user.is_trial_expired(),
        'is_subscription_active': user.is_subscription_active(),
        'can_access_premium': user.can_access_premium_features(),
        'subscription_id': user.subscription_id,
        'days_left_in_trial': (
            (user.trial_ends_at - timezone.now()).days 
            if user.trial_ends_at and user.subscription_status == 'free_trial' 
            else None
        )
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_trial(request):
    """
    Start or restart user's free trial
    """
    user = request.user
    
    if user.subscription_status == 'active':
        return Response({
            'error': 'User already has an active subscription'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user.start_trial()
    
    return Response({
        'message': 'Free trial started successfully',
        'trial_ends_at': user.trial_ends_at,
        'subscription_status': user.subscription_status
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_details(request):
    """
    Get current user details (for getUserDetails frontend call)
    """
    return Response({
        'id': request.user.id,
        'email': request.user.email,
        'username': request.user.username,
        'first_name': request.user.first_name,
        'last_name': request.user.last_name,
        'subscription_status': request.user.subscription_status,
        'trial_ends_at': request.user.trial_ends_at,
        'can_access_premium': request.user.can_access_premium_features(),
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    """
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response({
            'error': 'Both old_password and new_password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not request.user.check_password(old_password):
        return Response({
            'error': 'Invalid old password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    request.user.set_password(new_password)
    request.user.save()
    
    return Response({
        'message': 'Password changed successfully'
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def request_password_reset(request):
    """
    Request password reset email
    """
    email = request.data.get('email')
    
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Implement email sending logic
    return Response({
        'message': 'Password reset email sent (if account exists)'
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def confirm_password_reset(request):
    """
    Confirm password reset with token
    """
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    if not token or not new_password:
        return Response({
            'error': 'Token and new_password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # TODO: Implement token validation and password reset
    return Response({
        'message': 'Password reset successful'
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_subscription(request):
    """
    Manage subscription - POST to subscribe, DELETE to cancel
    """
    if request.method == 'POST':
        payment_token = request.data.get('payment_token')
        
        if not payment_token:
            return Response({
                'error': 'payment_token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # TODO: Implement PayPal subscription validation
        # For now, just activate the subscription
        request.user.activate_subscription(payment_token)
        
        return Response({
            'message': 'Subscription activated successfully',
            'user': {
                'id': request.user.id,
                'subscription_status': request.user.subscription_status,
                'subscription_id': request.user.subscription_id,
                'can_access_premium': request.user.can_access_premium_features(),
            }
        }, status=status.HTTP_200_OK)
    
    elif request.method == 'DELETE':
        # Cancel subscription
        request.user.subscription_status = 'cancelled'
        request.user.subscription_id = None
        request.user.save()
        
        return Response({
            'message': 'Subscription cancelled successfully',
            'user': {
                'id': request.user.id,
                'subscription_status': request.user.subscription_status,
                'can_access_premium': request.user.can_access_premium_features(),
            }
        }, status=status.HTTP_200_OK)
