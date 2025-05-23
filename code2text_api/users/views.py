"""
API views for user management and authentication.
"""

import logging
import paypalrestsdk
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from rest_framework import viewsets, status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.decorators import action
from rest_framework.authtoken.models import Token
from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    GoogleAuthSerializer
)
from .utils import (
    get_google_token,
    get_google_user_info,
    create_or_update_user_from_google
)

logger = logging.getLogger(__name__)

# Configure PayPal
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,  # sandbox or live
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})

class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        """Register a new user."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create token for the user
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """
    API endpoint for user login.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Log in a user."""
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        
        user = authenticate(username=username, password=password)
        
        if user:
            login(request, user)
            token, _ = Token.objects.get_or_create(user=user)
            
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key
            })
        else:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """
    API endpoint for user logout.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Log out a user."""
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserDetailView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for user details and profile updates.
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        """Get the current user."""
        return self.request.user


class GoogleAuthView(APIView):
    """
    API endpoint for Google OAuth authentication.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Process Google authentication."""
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        auth_code = serializer.validated_data['auth_code']
        
        try:
            # Exchange auth code for token
            token_info = get_google_token(auth_code)
            
            # Get user info with token
            user_info = get_google_user_info(token_info['access_token'])
            
            # Create or update user
            user, created = create_or_update_user_from_google(
                user_info,
                token_info['access_token'],
                token_info.get('refresh_token'),
                token_info.get('expires_at')
            )
            
            # Create token for the user
            token, _ = Token.objects.get_or_create(user=user)
            
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key,
                'is_new_user': created
            })
        
        except Exception as e:
            logger.error(f"Google auth error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TrialView(APIView):
    """
    API endpoint for starting a free trial.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Start a free trial for the user."""
        user = request.user
        
        if user.trial_start_date:
            return Response(
                {'error': 'User already has an active or expired trial'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.start_trial()
        
        return Response(UserSerializer(user).data)


class SubscriptionView(APIView):
    """
    API endpoint for managing subscriptions.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Process a subscription payment."""
        if not settings.PAYPAL_MODE or not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_CLIENT_SECRET:
            return Response(
                {'error': 'PayPal is not configured'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        
        try:
            # Get payment token from request
            payment_token = request.data.get('payment_token')
            if not payment_token:
                return Response(
                    {'error': 'Payment token is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create or get customer
            if request.user.paypal_customer_id:
                customer = paypalrestsdk.Customer.find(request.user.paypal_customer_id)
            else:
                customer = paypalrestsdk.Customer.create({
                    "email": request.user.email,
                    "first_name": request.user.first_name,
                    "last_name": request.user.last_name,
                    "payer_id": payment_token
                })
                # Save customer ID to user
                request.user.paypal_customer_id = customer.id
                request.user.save()
            
            # Create subscription
            subscription = paypalrestsdk.Subscription.create({
                "plan_id": settings.SUBSCRIPTION_PLAN_ID,
                "customer_id": customer.id
            })
            
            # Update user subscription status
            request.user.subscription_status = 'subscribed'
            request.user.subscription_end_date = timezone.now() + timezone.timedelta(days=30)
            request.user.save()
            
            return Response(UserSerializer(request.user).data)
        
        except Exception as e:
            logger.error(f"Subscription error: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) 