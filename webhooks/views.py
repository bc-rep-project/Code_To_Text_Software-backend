from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
import json
import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)

# Create your views here.

# Placeholder views for webhooks app
# These will be implemented later

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def webhook_list(request):
    """
    List webhook configurations for the authenticated user
    """
    return Response({
        'message': 'Webhooks endpoint - coming soon',
        'available_webhooks': [
            {
                'name': 'GitHub',
                'endpoint': '/api/webhooks/github/',
                'description': 'Receives GitHub repository events'
            },
            {
                'name': 'PayPal',
                'endpoint': '/api/webhooks/paypal/',
                'description': 'Receives PayPal payment notifications'
            }
        ]
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def github_webhook(request):
    """
    Handle GitHub webhook events
    """
    try:
        # Get the event type from headers
        event_type = request.META.get('HTTP_X_GITHUB_EVENT')
        delivery_id = request.META.get('HTTP_X_GITHUB_DELIVERY')
        signature = request.META.get('HTTP_X_HUB_SIGNATURE_256')
        
        if not event_type:
            return Response({
                'error': 'Missing X-GitHub-Event header'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Parse the payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return Response({
                'error': 'Invalid JSON payload'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log the webhook event
        logger.info(f"GitHub webhook received: {event_type} (delivery: {delivery_id})")
        
        # Handle different event types
        if event_type == 'push':
            return _handle_github_push(payload)
        elif event_type == 'pull_request':
            return _handle_github_pull_request(payload)
        elif event_type == 'issues':
            return _handle_github_issues(payload)
        elif event_type == 'ping':
            return Response({
                'message': 'GitHub webhook ping received successfully',
                'zen': payload.get('zen', 'GitHub is awesome!')
            }, status=status.HTTP_200_OK)
        else:
            logger.info(f"Unhandled GitHub event type: {event_type}")
            return Response({
                'message': f'Event type {event_type} received but not processed'
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"GitHub webhook error: {str(e)}")
        return Response({
            'error': 'Internal server error processing webhook'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def paypal_webhook(request):
    """
    Handle PayPal webhook events
    """
    try:
        # Get PayPal headers
        event_type = request.META.get('HTTP_PAYPAL_TRANSMISSION_ID')
        auth_algo = request.META.get('HTTP_PAYPAL_AUTH_ALGO')
        cert_id = request.META.get('HTTP_PAYPAL_CERT_ID')
        transmission_sig = request.META.get('HTTP_PAYPAL_TRANSMISSION_SIG')
        transmission_time = request.META.get('HTTP_PAYPAL_TRANSMISSION_TIME')
        
        # Parse the payload
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except json.JSONDecodeError:
            return Response({
                'error': 'Invalid JSON payload'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        event_type = payload.get('event_type')
        
        if not event_type:
            return Response({
                'error': 'Missing event_type in payload'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Log the webhook event
        logger.info(f"PayPal webhook received: {event_type}")
        
        # Handle different event types
        if event_type == 'BILLING.SUBSCRIPTION.CREATED':
            return _handle_paypal_subscription_created(payload)
        elif event_type == 'BILLING.SUBSCRIPTION.ACTIVATED':
            return _handle_paypal_subscription_activated(payload)
        elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
            return _handle_paypal_subscription_cancelled(payload)
        elif event_type == 'PAYMENT.SALE.COMPLETED':
            return _handle_paypal_payment_completed(payload)
        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")
            return Response({
                'message': f'Event type {event_type} received but not processed'
            }, status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"PayPal webhook error: {str(e)}")
        return Response({
            'error': 'Internal server error processing webhook'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# GitHub webhook handlers

def _handle_github_push(payload):
    """Handle GitHub push events"""
    repository = payload.get('repository', {})
    repo_full_name = repository.get('full_name')
    commits = payload.get('commits', [])
    
    logger.info(f"GitHub push to {repo_full_name} with {len(commits)} commits")
    
    # Here you would:
    # 1. Find projects that monitor this repository
    # 2. Check if auto-conversion is enabled
    # 3. Trigger re-scan and conversion if needed
    
    return Response({
        'message': 'GitHub push event processed',
        'repository': repo_full_name,
        'commits_count': len(commits)
    }, status=status.HTTP_200_OK)


def _handle_github_pull_request(payload):
    """Handle GitHub pull request events"""
    action = payload.get('action')
    pull_request = payload.get('pull_request', {})
    repository = payload.get('repository', {})
    
    logger.info(f"GitHub PR {action} in {repository.get('full_name')}")
    
    return Response({
        'message': 'GitHub pull request event processed',
        'action': action,
        'pr_number': pull_request.get('number')
    }, status=status.HTTP_200_OK)


def _handle_github_issues(payload):
    """Handle GitHub issues events"""
    action = payload.get('action')
    issue = payload.get('issue', {})
    repository = payload.get('repository', {})
    
    logger.info(f"GitHub issue {action} in {repository.get('full_name')}")
    
    return Response({
        'message': 'GitHub issues event processed',
        'action': action,
        'issue_number': issue.get('number')
    }, status=status.HTTP_200_OK)


# PayPal webhook handlers

def _handle_paypal_subscription_created(payload):
    """Handle PayPal subscription created events"""
    resource = payload.get('resource', {})
    subscription_id = resource.get('id')
    
    logger.info(f"PayPal subscription created: {subscription_id}")
    
    # Here you would:
    # 1. Find the user associated with this subscription
    # 2. Update their subscription status
    # 3. Send confirmation email
    
    return Response({
        'message': 'PayPal subscription created event processed',
        'subscription_id': subscription_id
    }, status=status.HTTP_200_OK)


def _handle_paypal_subscription_activated(payload):
    """Handle PayPal subscription activated events"""
    resource = payload.get('resource', {})
    subscription_id = resource.get('id')
    
    logger.info(f"PayPal subscription activated: {subscription_id}")
    
    return Response({
        'message': 'PayPal subscription activated event processed',
        'subscription_id': subscription_id
    }, status=status.HTTP_200_OK)


def _handle_paypal_subscription_cancelled(payload):
    """Handle PayPal subscription cancelled events"""
    resource = payload.get('resource', {})
    subscription_id = resource.get('id')
    
    logger.info(f"PayPal subscription cancelled: {subscription_id}")
    
    return Response({
        'message': 'PayPal subscription cancelled event processed',
        'subscription_id': subscription_id
    }, status=status.HTTP_200_OK)


def _handle_paypal_payment_completed(payload):
    """Handle PayPal payment completed events"""
    resource = payload.get('resource', {})
    payment_id = resource.get('id')
    
    logger.info(f"PayPal payment completed: {payment_id}")
    
    return Response({
        'message': 'PayPal payment completed event processed',
        'payment_id': payment_id
    }, status=status.HTTP_200_OK)
