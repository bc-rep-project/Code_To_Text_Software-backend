from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    # Webhook list endpoint
    path('', views.webhook_list, name='webhook_list'),  # GET: list available webhooks
    
    # External webhook endpoints (called by third-party services)
    path('github/', views.github_webhook, name='github_webhook'),  # POST: GitHub webhook
    path('paypal/', views.paypal_webhook, name='paypal_webhook'),  # POST: PayPal webhook
] 