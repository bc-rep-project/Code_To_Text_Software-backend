from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta
from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os

class User(AbstractUser):
    """
    Custom User model based on the JSON structure provided.
    Extends Django's AbstractUser to include Google OAuth and subscription fields.
    """
    
    # Google OAuth fields
    google_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    google_access_token = models.TextField(null=True, blank=True)  # Will be encrypted
    google_refresh_token = models.TextField(null=True, blank=True)  # Will be encrypted
    
    # Subscription fields
    SUBSCRIPTION_STATUS_CHOICES = [
        ('free_trial', 'Free Trial'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]
    
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='free_trial'
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    subscription_id = models.CharField(max_length=255, null=True, blank=True)  # PayPal subscription ID
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'users'
    
    def save(self, *args, **kwargs):
        # Set trial end date for new users
        if not self.trial_ends_at and self.subscription_status == 'free_trial':
            self.trial_ends_at = timezone.now() + timedelta(days=settings.FREE_TRIAL_DAYS)
        
        # Encrypt tokens before saving
        if self.google_access_token and not self.google_access_token.startswith('gAAAAAB'):
            self.google_access_token = self._encrypt_token(self.google_access_token)
        if self.google_refresh_token and not self.google_refresh_token.startswith('gAAAAAB'):
            self.google_refresh_token = self._encrypt_token(self.google_refresh_token)
        
        super().save(*args, **kwargs)
    
    def _get_encryption_key(self):
        """Get or create encryption key for tokens"""
        key = getattr(settings, 'TOKEN_ENCRYPTION_KEY', None)
        if not key:
            # Generate a key if not provided in settings
            key = Fernet.generate_key()
        elif isinstance(key, str):
            key = key.encode()
        return key
    
    def _encrypt_token(self, token):
        """Encrypt a token for secure storage"""
        if not token:
            return token
        
        try:
            f = Fernet(self._get_encryption_key())
            encrypted_token = f.encrypt(token.encode())
            return base64.urlsafe_b64encode(encrypted_token).decode()
        except Exception:
            # If encryption fails, return the token as-is (for development)
            return token
    
    def _decrypt_token(self, encrypted_token):
        """Decrypt a token for use"""
        if not encrypted_token or not encrypted_token.startswith('gAAAAAB'):
            return encrypted_token
        
        try:
            f = Fernet(self._get_encryption_key())
            decoded_token = base64.urlsafe_b64decode(encrypted_token.encode())
            return f.decrypt(decoded_token).decode()
        except Exception:
            # If decryption fails, return the token as-is
            return encrypted_token
    
    def get_google_access_token(self):
        """Get decrypted Google access token"""
        return self._decrypt_token(self.google_access_token)
    
    def get_google_refresh_token(self):
        """Get decrypted Google refresh token"""
        return self._decrypt_token(self.google_refresh_token)
    
    def is_trial_expired(self):
        """Check if the user's trial period has expired"""
        if self.subscription_status != 'free_trial':
            return False
        return self.trial_ends_at and timezone.now() > self.trial_ends_at
    
    def is_subscription_active(self):
        """Check if the user has an active subscription"""
        return self.subscription_status == 'active'
    
    def can_access_premium_features(self):
        """Check if user can access premium features"""
        if self.subscription_status == 'active':
            return True
        if self.subscription_status == 'free_trial' and not self.is_trial_expired():
            return True
        return False
    
    def start_trial(self):
        """Start the free trial period"""
        self.subscription_status = 'free_trial'
        self.trial_ends_at = timezone.now() + timedelta(days=settings.FREE_TRIAL_DAYS)
        self.save()
    
    def activate_subscription(self, subscription_id):
        """Activate paid subscription"""
        self.subscription_status = 'active'
        self.subscription_id = subscription_id
        self.save()
    
    def cancel_subscription(self):
        """Cancel subscription"""
        self.subscription_status = 'cancelled'
        self.save()
    
    def expire_subscription(self):
        """Mark subscription as expired"""
        self.subscription_status = 'expired'
        self.save()
    
    def __str__(self):
        return f"{self.email} ({self.subscription_status})"


class UserProfile(models.Model):
    """
    Extended user profile information
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Additional profile fields
    avatar_url = models.URLField(null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    github_monitoring_notifications = models.BooleanField(default=True)
    conversion_completion_notifications = models.BooleanField(default=True)
    
    # Usage statistics
    total_repositories_processed = models.IntegerField(default=0)
    total_conversions = models.IntegerField(default=0)
    storage_used_mb = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"Profile for {self.user.email}"
