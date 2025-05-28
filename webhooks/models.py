from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class GitHubWebhookEvent(models.Model):
    """
    Stores GitHub webhook events for debugging and processing repository updates
    """
    # Event identification
    github_delivery_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=50)  # 'push', 'pull_request', etc.
    
    # Repository information
    repository_full_name = models.CharField(max_length=255)  # e.g., 'user/repo'
    repository_url = models.URLField()
    
    # Event payload
    payload = models.JSONField()  # Raw GitHub webhook payload
    
    # Processing status
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('ignored', 'Ignored'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    
    # Related project (if applicable)
    project_id_affected = models.CharField(max_length=255, null=True, blank=True)
    
    # Processing details
    processing_error = models.TextField(null=True, blank=True)
    processing_attempts = models.IntegerField(default=0)
    last_processing_attempt = models.DateTimeField(null=True, blank=True)
    
    # Actions taken
    actions_taken = models.JSONField(default=list)  # List of actions like ['scan_triggered', 'conversion_triggered']
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'github_webhook_events'
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['repository_full_name', 'event_type']),
            models.Index(fields=['status']),
            models.Index(fields=['received_at']),
        ]
    
    def __str__(self):
        return f"GitHub {self.event_type} webhook for {self.repository_full_name}"
    
    def mark_processed(self, actions_taken=None):
        """Mark webhook event as processed"""
        self.status = 'processed'
        self.processed_at = timezone.now()
        if actions_taken:
            self.actions_taken = actions_taken
        self.save()
    
    def mark_failed(self, error_message):
        """Mark webhook event as failed"""
        self.status = 'failed'
        self.processing_error = error_message
        self.processing_attempts += 1
        self.last_processing_attempt = timezone.now()
        self.save()
    
    def mark_ignored(self, reason):
        """Mark webhook event as ignored"""
        self.status = 'ignored'
        self.processing_error = reason
        self.processed_at = timezone.now()
        self.save()
    
    def can_retry(self, max_attempts=3):
        """Check if webhook can be retried"""
        return self.processing_attempts < max_attempts and self.status == 'failed'
    
    def get_commit_sha(self):
        """Extract commit SHA from payload"""
        try:
            if self.event_type == 'push':
                return self.payload.get('after')
            elif self.event_type == 'pull_request':
                return self.payload.get('pull_request', {}).get('head', {}).get('sha')
        except (AttributeError, KeyError):
            pass
        return None
    
    def get_branch_name(self):
        """Extract branch name from payload"""
        try:
            if self.event_type == 'push':
                ref = self.payload.get('ref', '')
                if ref.startswith('refs/heads/'):
                    return ref.replace('refs/heads/', '')
            elif self.event_type == 'pull_request':
                return self.payload.get('pull_request', {}).get('head', {}).get('ref')
        except (AttributeError, KeyError):
            pass
        return None
    
    def is_main_branch_push(self):
        """Check if this is a push to main/master branch"""
        if self.event_type != 'push':
            return False
        
        branch = self.get_branch_name()
        return branch in ['main', 'master']
    
    def get_pusher_info(self):
        """Get information about who pushed the changes"""
        try:
            if self.event_type == 'push':
                pusher = self.payload.get('pusher', {})
                return {
                    'name': pusher.get('name'),
                    'email': pusher.get('email'),
                }
        except (AttributeError, KeyError):
            pass
        return {}


class WebhookDeliveryLog(models.Model):
    """
    Logs webhook delivery attempts and responses
    """
    # Webhook source
    SOURCE_CHOICES = [
        ('github', 'GitHub'),
        ('paypal', 'PayPal'),
    ]
    
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    
    # Delivery details
    webhook_id = models.CharField(max_length=255)  # ID from the webhook source
    endpoint_url = models.URLField()
    http_method = models.CharField(max_length=10, default='POST')
    
    # Request details
    headers = models.JSONField(default=dict)
    payload = models.JSONField()
    
    # Response details
    response_status_code = models.IntegerField(null=True, blank=True)
    response_headers = models.JSONField(default=dict)
    response_body = models.TextField(null=True, blank=True)
    
    # Timing
    request_timestamp = models.DateTimeField()
    response_timestamp = models.DateTimeField(null=True, blank=True)
    processing_duration_ms = models.IntegerField(null=True, blank=True)
    
    # Delivery status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('timeout', 'Timeout'),
    ]
    
    delivery_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Error details
    error_message = models.TextField(null=True, blank=True)
    
    # Retry information
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_delivery_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'delivery_status']),
            models.Index(fields=['webhook_id']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.source} webhook {self.webhook_id} - {self.delivery_status}"
    
    def mark_delivered(self, response_status, response_headers=None, response_body=None):
        """Mark webhook as successfully delivered"""
        self.delivery_status = 'delivered'
        self.response_status_code = response_status
        self.response_timestamp = timezone.now()
        
        if response_headers:
            self.response_headers = response_headers
        if response_body:
            self.response_body = response_body
        
        # Calculate processing duration
        if self.request_timestamp and self.response_timestamp:
            duration = self.response_timestamp - self.request_timestamp
            self.processing_duration_ms = int(duration.total_seconds() * 1000)
        
        self.save()
    
    def mark_failed(self, error_message, schedule_retry=True):
        """Mark webhook delivery as failed"""
        self.delivery_status = 'failed'
        self.error_message = error_message
        self.response_timestamp = timezone.now()
        
        if schedule_retry and self.retry_count < self.max_retries:
            # Schedule next retry with exponential backoff
            from datetime import timedelta
            retry_delay_minutes = 2 ** self.retry_count  # 1, 2, 4, 8 minutes
            self.next_retry_at = timezone.now() + timedelta(minutes=retry_delay_minutes)
        
        self.save()
    
    def can_retry(self):
        """Check if webhook delivery can be retried"""
        return (
            self.delivery_status == 'failed' and 
            self.retry_count < self.max_retries and
            self.next_retry_at and
            timezone.now() >= self.next_retry_at
        )
    
    def increment_retry_count(self):
        """Increment retry count"""
        self.retry_count += 1
        self.save()


class WebhookSubscription(models.Model):
    """
    Manages webhook subscriptions for external services
    """
    # Subscription details
    service_name = models.CharField(max_length=50)  # 'github', 'paypal'
    webhook_url = models.URLField()
    secret_token = models.CharField(max_length=255, null=True, blank=True)
    
    # Event types to subscribe to
    event_types = models.JSONField(default=list)  # e.g., ['push', 'pull_request'] for GitHub
    
    # Subscription status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('failed', 'Failed'),
        ('pending', 'Pending'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # External service details
    external_webhook_id = models.CharField(max_length=255, null=True, blank=True)
    external_subscription_data = models.JSONField(default=dict)
    
    # Statistics
    total_events_received = models.IntegerField(default=0)
    last_event_received_at = models.DateTimeField(null=True, blank=True)
    
    # Configuration
    is_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'webhook_subscriptions'
        unique_together = ['service_name', 'webhook_url']
    
    def __str__(self):
        return f"{self.service_name} webhook subscription - {self.status}"
    
    def increment_event_count(self):
        """Increment the event counter"""
        self.total_events_received += 1
        self.last_event_received_at = timezone.now()
        self.save()
    
    def activate(self):
        """Activate the webhook subscription"""
        self.status = 'active'
        self.is_enabled = True
        self.save()
    
    def deactivate(self):
        """Deactivate the webhook subscription"""
        self.status = 'inactive'
        self.is_enabled = False
        self.save()
