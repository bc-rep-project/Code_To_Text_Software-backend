"""
User models for the code2text application.
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings

class User(AbstractUser):
    """
    Custom user model for the code2text application.
    """
    email = models.EmailField(unique=True)
    trial_start_date = models.DateTimeField(null=True, blank=True)
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('free_trial', 'Free Trial'),
            ('subscribed', 'Subscribed'),
            ('expired', 'Expired'),
        ],
        default='free_trial'
    )
    subscription_end_date = models.DateTimeField(null=True, blank=True)
    
    # Payment processing fields
    paypal_customer_id = models.CharField(max_length=255, null=True, blank=True)
    
    # Google OAuth fields
    google_access_token = models.CharField(max_length=255, null=True, blank=True)
    google_refresh_token = models.CharField(max_length=255, null=True, blank=True)
    google_token_expiry = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def start_trial(self):
        """
        Start the free trial period for the user.
        """
        if not self.trial_start_date:
            self.trial_start_date = timezone.now()
            self.subscription_status = 'free_trial'
            self.subscription_end_date = self.trial_start_date + timezone.timedelta(days=settings.TRIAL_PERIOD_DAYS)
            self.save()
    
    def is_trial_active(self):
        """
        Check if the user's trial is still active.
        """
        if not self.trial_start_date:
            return False
        
        return timezone.now() < self.subscription_end_date
    
    def is_subscription_active(self):
        """
        Check if the user's subscription is active.
        """
        if self.subscription_status == 'subscribed':
            if self.subscription_end_date and timezone.now() < self.subscription_end_date:
                return True
        elif self.subscription_status == 'free_trial':
            return self.is_trial_active()
        return False 