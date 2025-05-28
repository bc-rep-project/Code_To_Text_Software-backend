from django.contrib import admin
from django.utils.html import format_html
from .models import (
    PayPalSubscription, PayPalPayment, PayPalWebhookEvent, 
    PayPalPlan, PaymentIntent
)

@admin.register(PayPalSubscription)
class PayPalSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'paypal_subscription_id', 'status', 'amount_display', 'created_at')
    list_filter = ('status', 'currency', 'created_at')
    search_fields = ('user__username', 'user__email', 'paypal_subscription_id', 'paypal_plan_id')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user',),
        }),
        ('PayPal Details', {
            'fields': ('paypal_subscription_id', 'paypal_plan_id'),
        }),
        ('Status', {
            'fields': ('status',),
        }),
        ('Billing', {
            'fields': ('amount', 'currency', 'start_time', 'next_billing_time'),
        }),
        ('URLs', {
            'fields': ('approval_url',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'

@admin.register(PayPalPayment)
class PayPalPaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'paypal_payment_id', 'status', 'amount_display', 'payment_type', 'created_at')
    list_filter = ('status', 'payment_type', 'currency', 'created_at')
    search_fields = ('user__username', 'user__email', 'paypal_payment_id', 'paypal_order_id')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user', 'subscription'),
        }),
        ('PayPal Details', {
            'fields': ('paypal_payment_id', 'paypal_order_id', 'payment_type'),
        }),
        ('Amount', {
            'fields': ('amount', 'currency'),
        }),
        ('Status', {
            'fields': ('status', 'payment_date'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'

@admin.register(PayPalWebhookEvent)
class PayPalWebhookEventAdmin(admin.ModelAdmin):
    list_display = ('paypal_event_id', 'event_type', 'status', 'processing_attempts', 'received_at')
    list_filter = ('event_type', 'status', 'received_at')
    search_fields = ('paypal_event_id', 'event_type')
    ordering = ('-received_at',)
    
    fieldsets = (
        ('Event Info', {
            'fields': ('paypal_event_id', 'event_type'),
        }),
        ('Processing', {
            'fields': ('status', 'processing_attempts', 'processing_error'),
        }),
        ('Related Objects', {
            'fields': ('related_user', 'related_subscription', 'related_payment'),
        }),
        ('Data', {
            'fields': ('event_data',),
        }),
        ('Timestamps', {
            'fields': ('received_at', 'processed_at'),
        }),
    )
    
    readonly_fields = ('received_at', 'processed_at')

@admin.register(PayPalPlan)
class PayPalPlanAdmin(admin.ModelAdmin):
    list_display = ('paypal_plan_id', 'name', 'status', 'price_display', 'billing_cycle', 'active_subscriptions')
    list_filter = ('status', 'currency', 'interval_unit')
    search_fields = ('paypal_plan_id', 'name', 'description')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Plan Info', {
            'fields': ('paypal_plan_id', 'name', 'description'),
        }),
        ('Status', {
            'fields': ('status',),
        }),
        ('Pricing', {
            'fields': ('amount', 'currency'),
        }),
        ('Billing Cycle', {
            'fields': ('interval_unit', 'interval_count'),
        }),
        ('Usage', {
            'fields': ('total_subscriptions', 'active_subscriptions'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('total_subscriptions', 'active_subscriptions', 'created_at', 'updated_at')
    
    def price_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    price_display.short_description = 'Price'
    
    def billing_cycle(self, obj):
        return f"Every {obj.interval_count} {obj.interval_unit}"
    billing_cycle.short_description = 'Billing Cycle'

@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ('user', 'intent_id', 'status', 'amount_display', 'purpose', 'created_at')
    list_filter = ('status', 'purpose', 'currency', 'created_at')
    search_fields = ('user__username', 'user__email', 'intent_id')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('User Info', {
            'fields': ('user',),
        }),
        ('Intent Details', {
            'fields': ('intent_id', 'status', 'purpose'),
        }),
        ('Amount', {
            'fields': ('amount', 'currency'),
        }),
        ('Metadata', {
            'fields': ('metadata',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def amount_display(self, obj):
        return f"{obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
