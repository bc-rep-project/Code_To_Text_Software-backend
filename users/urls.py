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
    
    # Subscription endpoints
    path('subscription/status/', views.subscription_status, name='subscription_status'),
    path('subscription/start-trial/', views.start_trial, name='start_trial'),
] 