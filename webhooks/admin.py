from django.contrib import admin
from django.utils.html import format_html
from .models import (
    GitHubWebhookEvent, WebhookDeliveryLog, WebhookSubscription
)

@admin.register(GitHubWebhookEvent)
class GitHubWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('repository_full_name', 'event_type', 'status', 'processing_attempts', 'received_at')
    list_filter = ('event_type', 'status', 'received_at')
    search_fields = ('repository_full_name', 'github_delivery_id', 'project_id_affected')
    ordering = ('-received_at',)
    
    fieldsets = (
        ('Event Info', {
            'fields': ('github_delivery_id', 'event_type'),
        }),
        ('Repository', {
            'fields': ('repository_full_name', 'repository_url'),
        }),
        ('Processing', {
            'fields': ('status', 'processing_attempts', 'processing_error'),
        }),
        ('Project', {
            'fields': ('project_id_affected',),
        }),
        ('Actions', {
            'fields': ('actions_taken',),
        }),
        ('Payload', {
            'fields': ('payload',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('received_at', 'processed_at', 'last_processing_attempt'),
        }),
    )
    
    readonly_fields = ('received_at', 'processed_at', 'last_processing_attempt')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    list_display = ('source', 'webhook_id', 'delivery_status', 'response_status_code', 'retry_count', 'created_at')
    list_filter = ('source', 'delivery_status', 'created_at')
    search_fields = ('webhook_id', 'endpoint_url')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Webhook Info', {
            'fields': ('source', 'webhook_id', 'endpoint_url', 'http_method'),
        }),
        ('Request', {
            'fields': ('headers', 'payload'),
            'classes': ('collapse',),
        }),
        ('Response', {
            'fields': ('response_status_code', 'response_headers', 'response_body'),
        }),
        ('Status', {
            'fields': ('delivery_status', 'error_message'),
        }),
        ('Retry Info', {
            'fields': ('retry_count', 'max_retries', 'next_retry_at'),
        }),
        ('Timing', {
            'fields': ('request_timestamp', 'response_timestamp', 'processing_duration_ms'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at', 'processing_duration_ms')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related()

@admin.register(WebhookSubscription)
class WebhookSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('service_name', 'webhook_url', 'status', 'is_enabled', 'total_events_received', 'last_event_received_at')
    list_filter = ('service_name', 'status', 'is_enabled', 'created_at')
    search_fields = ('service_name', 'webhook_url', 'external_webhook_id')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Subscription Info', {
            'fields': ('service_name', 'webhook_url', 'secret_token'),
        }),
        ('Configuration', {
            'fields': ('event_types', 'status', 'is_enabled'),
        }),
        ('External Service', {
            'fields': ('external_webhook_id', 'external_subscription_data'),
            'classes': ('collapse',),
        }),
        ('Statistics', {
            'fields': ('total_events_received', 'last_event_received_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('total_events_received', 'last_event_received_at', 'created_at', 'updated_at')
    
    actions = ['activate_subscriptions', 'deactivate_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        updated = queryset.update(status='active', is_enabled=True)
        self.message_user(request, f'{updated} subscriptions were successfully activated.')
    activate_subscriptions.short_description = "Activate selected subscriptions"
    
    def deactivate_subscriptions(self, request, queryset):
        updated = queryset.update(status='inactive', is_enabled=False)
        self.message_user(request, f'{updated} subscriptions were successfully deactivated.')
    deactivate_subscriptions.short_description = "Deactivate selected subscriptions"
