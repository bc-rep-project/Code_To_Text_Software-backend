from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('google-oauth/', views.google_oauth, name='google_oauth'),
    
    # Profile endpoints
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('user/', views.user_details, name='user_details'),  # GET for user details
    
    # Password management
    path('password/change/', views.change_password, name='change_password'),
    path('password/reset/', views.request_password_reset, name='request_password_reset'),
    path('password/reset/confirm/', views.confirm_password_reset, name='confirm_password_reset'),
    
    # Subscription endpoints
    path('subscription/status/', views.subscription_status, name='subscription_status'),
    path('subscription/trial/', views.start_trial, name='start_trial'),
    path('subscription/', views.manage_subscription, name='manage_subscription'),  # POST for subscribe, DELETE for cancel
] 