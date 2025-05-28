from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class PayPalSubscription(models.Model):
    """
    Tracks PayPal subscription information
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='paypal_subscription')
    
    # PayPal subscription details
    paypal_subscription_id = models.CharField(max_length=255, unique=True)
    paypal_plan_id = models.CharField(max_length=255)
    
    # Subscription status
    STATUS_CHOICES = [
        ('approval_pending', 'Approval Pending'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='approval_pending')
    
    # Subscription details
    start_time = models.DateTimeField(null=True, blank=True)
    next_billing_time = models.DateTimeField(null=True, blank=True)
    
    # Pricing information
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=2.00)
    currency = models.CharField(max_length=3, default='USD')
    
    # PayPal URLs
    approval_url = models.URLField(null=True, blank=True)
    
    # Metadata
    paypal_response_data = models.JSONField(default=dict)  # Store full PayPal response
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paypal_subscriptions'
    
    def __str__(self):
        return f"PayPal subscription {self.paypal_subscription_id} for {self.user.email}"
    
    def is_active(self):
        """Check if subscription is active"""
        return self.status == 'active'
    
    def activate(self):
        """Activate the subscription"""
        self.status = 'active'
        self.start_time = timezone.now()
        self.save()
        
        # Update user subscription status
        self.user.activate_subscription(self.paypal_subscription_id)
    
    def cancel(self):
        """Cancel the subscription"""
        self.status = 'cancelled'
        self.save()
        
        # Update user subscription status
        self.user.cancel_subscription()
    
    def suspend(self):
        """Suspend the subscription"""
        self.status = 'suspended'
        self.save()


class PayPalPayment(models.Model):
    """
    Tracks individual PayPal payments
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='paypal_payments')
    subscription = models.ForeignKey(
        PayPalSubscription, 
        on_delete=models.CASCADE, 
        related_name='payments',
        null=True, 
        blank=True
    )
    
    # PayPal payment details
    paypal_payment_id = models.CharField(max_length=255, unique=True)
    paypal_order_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Payment information
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Payment status
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    
    # Payment type
    PAYMENT_TYPE_CHOICES = [
        ('subscription', 'Subscription Payment'),
        ('one_time', 'One-time Payment'),
    ]
    
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='subscription')
    
    # Timestamps
    payment_date = models.DateTimeField(null=True, blank=True)
    
    # PayPal response data
    paypal_response_data = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paypal_payments'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"PayPal payment {self.paypal_payment_id} - ${self.amount}"
    
    def mark_completed(self):
        """Mark payment as completed"""
        self.status = 'completed'
        self.payment_date = timezone.now()
        self.save()
    
    def mark_failed(self):
        """Mark payment as failed"""
        self.status = 'failed'
        self.save()


class PayPalWebhookEvent(models.Model):
    """
    Stores PayPal webhook events for debugging and processing
    """
    # Event identification
    paypal_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=100)
    
    # Event data
    event_data = models.JSONField()
    
    # Processing status
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('ignored', 'Ignored'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    
    # Related objects (if applicable)
    related_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    related_subscription = models.ForeignKey(
        PayPalSubscription, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    related_payment = models.ForeignKey(
        PayPalPayment, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    # Processing details
    processing_error = models.TextField(null=True, blank=True)
    processing_attempts = models.IntegerField(default=0)
    last_processing_attempt = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'paypal_webhook_events'
        ordering = ['-received_at']
    
    def __str__(self):
        return f"PayPal webhook {self.event_type} - {self.paypal_event_id}"
    
    def mark_processed(self):
        """Mark webhook event as processed"""
        self.status = 'processed'
        self.processed_at = timezone.now()
        self.save()
    
    def mark_failed(self, error_message):
        """Mark webhook event as failed"""
        self.status = 'failed'
        self.processing_error = error_message
        self.processing_attempts += 1
        self.last_processing_attempt = timezone.now()
        self.save()
    
    def can_retry(self, max_attempts=3):
        """Check if webhook can be retried"""
        return self.processing_attempts < max_attempts and self.status == 'failed'


class PayPalPlan(models.Model):
    """
    Stores PayPal subscription plan information
    """
    # Plan identification
    paypal_plan_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    # Plan status
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('inactive', 'Inactive'),
        ('active', 'Active'),
    ]
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    
    # Pricing
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Billing cycle
    INTERVAL_UNIT_CHOICES = [
        ('day', 'Day'),
        ('week', 'Week'),
        ('month', 'Month'),
        ('year', 'Year'),
    ]
    
    interval_unit = models.CharField(max_length=10, choices=INTERVAL_UNIT_CHOICES, default='month')
    interval_count = models.IntegerField(default=1)  # e.g., every 1 month
    
    # Plan metadata
    paypal_response_data = models.JSONField(default=dict)
    
    # Usage tracking
    total_subscriptions = models.IntegerField(default=0)
    active_subscriptions = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paypal_plans'
    
    def __str__(self):
        return f"PayPal plan {self.name} - ${self.amount}/{self.interval_count} {self.interval_unit}(s)"
    
    def is_active(self):
        """Check if plan is active"""
        return self.status == 'active'
    
    def increment_subscription_count(self):
        """Increment subscription counters"""
        self.total_subscriptions += 1
        self.active_subscriptions += 1
        self.save()
    
    def decrement_active_subscriptions(self):
        """Decrement active subscription counter"""
        if self.active_subscriptions > 0:
            self.active_subscriptions -= 1
            self.save()


class PaymentIntent(models.Model):
    """
    Tracks payment intents for one-time payments
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_intents')
    
    # Intent details
    intent_id = models.CharField(max_length=255, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Intent purpose
    PURPOSE_CHOICES = [
        ('subscription_setup', 'Subscription Setup'),
        ('one_time_payment', 'One-time Payment'),
        ('trial_extension', 'Trial Extension'),
    ]
    
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    
    # Status
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('requires_payment_method', 'Requires Payment Method'),
        ('requires_confirmation', 'Requires Confirmation'),
        ('requires_action', 'Requires Action'),
        ('processing', 'Processing'),
        ('succeeded', 'Succeeded'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Failed'),
    ]
    
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='created')
    
    # PayPal data
    paypal_response_data = models.JSONField(default=dict)
    
    # Metadata
    metadata = models.JSONField(default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_intents'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Payment intent {self.intent_id} - ${self.amount} ({self.purpose})"
