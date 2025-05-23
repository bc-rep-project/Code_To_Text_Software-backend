"""
URL configuration for users app.
"""

from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    UserDetailView,
    GoogleAuthView,
    TrialView,
    SubscriptionView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('user/', UserDetailView.as_view(), name='user-detail'),
    path('google/', GoogleAuthView.as_view(), name='google-auth'),
    path('trial/', TrialView.as_view(), name='trial'),
    path('subscribe/', SubscriptionView.as_view(), name='subscribe'),
]