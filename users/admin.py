from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, UserProfile

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'subscription_status', 'is_trial_active', 'date_joined', 'is_staff')
    list_filter = ('subscription_status', 'is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'google_id')
    ordering = ('-date_joined',)
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Google OAuth', {
            'fields': ('google_id', 'google_access_token', 'google_refresh_token'),
        }),
        ('Subscription', {
            'fields': ('subscription_status', 'trial_ends_at', 'subscription_id'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login')
    
    def is_trial_active(self, obj):
        return obj.subscription_status == 'free_trial' and not obj.is_trial_expired()
    is_trial_active.boolean = True
    is_trial_active.short_description = 'Trial Active'

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'timezone', 'language', 'email_notifications', 'total_repositories_processed', 'total_conversions')
    list_filter = ('timezone', 'language', 'email_notifications', 'github_monitoring_notifications')
    search_fields = ('user__username', 'user__email')
    ordering = ('-user__date_joined',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'avatar_url'),
        }),
        ('Preferences', {
            'fields': ('timezone', 'language', 'email_notifications', 'github_monitoring_notifications', 'conversion_completion_notifications'),
        }),
        ('Usage Statistics', {
            'fields': ('total_repositories_processed', 'total_conversions', 'storage_used_mb'),
        }),
    )
    
    readonly_fields = ('total_repositories_processed', 'total_conversions', 'storage_used_mb')
