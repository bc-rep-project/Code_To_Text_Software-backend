from django.shortcuts import render
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
import requests
import json
import logging

from users.models import UserProfile

logger = logging.getLogger(__name__)

# Create your views here.

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_list(request):
    """
    List payment history and subscription information for the authenticated user
    """
    user = request.user
    
    return Response({
        'subscription_status': user.subscription_status,
        'trial_ends_at': user.trial_ends_at,
        'is_trial_expired': user.is_trial_expired(),
        'is_subscription_active': user.is_subscription_active(),
        'can_access_premium': user.can_access_premium_features(),
        'subscription_id': user.subscription_id,
        'available_plans': [
            {
                'name': 'Free Trial',
                'price': 0,
                'duration': '30 days',
                'features': [
                    'Up to 5 projects',
                    'Basic conversion',
                    'Email support'
                ]
            },
            {
                'name': 'Pro Monthly',
                'price': 9.99,
                'duration': 'monthly',
                'features': [
                    'Unlimited projects',
                    'Advanced conversion',
                    'GitHub monitoring',
                    'Google Drive integration',
                    'Priority support'
                ]
            }
        ]
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def paypal_subscribe(request):
    """
    Create a PayPal subscription for the user
    """
    plan_id = request.data.get('plan_id')
    
    if not plan_id:
        return Response({
            'error': 'Plan ID is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate plan ID
    valid_plans = ['monthly', 'yearly']
    if plan_id not in valid_plans:
        return Response({
            'error': 'Invalid plan ID. Must be "monthly" or "yearly"'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = request.user
    
    # Check if user already has an active subscription
    if user.is_subscription_active():
        return Response({
            'error': 'User already has an active subscription'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create mock PayPal subscription
        mock_subscription_id = f"I-{plan_id.upper()}-{request.user.id}-{int(timezone.now().timestamp())}"
        approval_url = f'https://www.sandbox.paypal.com/webapps/billing/subscriptions?ba_token={mock_subscription_id}'
        
        return Response({
            'message': 'Subscription created successfully',
            'subscription_id': mock_subscription_id,
            'status': 'APPROVAL_PENDING',
            'approval_url': approval_url
        }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        logger.error(f"PayPal subscription creation error: {str(e)}")
        return Response({
            'error': 'Failed to create subscription',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
