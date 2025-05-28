from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User, UserProfile


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user = User.objects.create_user(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login
    """
    username_or_email = serializers.CharField()
    password = serializers.CharField(write_only=True)


class GoogleOAuthSerializer(serializers.Serializer):
    """
    Serializer for Google OAuth authentication
    """
    access_token = serializers.CharField()
    refresh_token = serializers.CharField(required=False)


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for user profile
    """
    class Meta:
        model = UserProfile
        fields = (
            'avatar_url', 'timezone', 'language',
            'email_notifications', 'github_monitoring_notifications',
            'conversion_completion_notifications', 'total_repositories_processed',
            'total_conversions', 'storage_used_mb'
        )
        read_only_fields = ('total_repositories_processed', 'total_conversions', 'storage_used_mb')


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user information
    """
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = (
            'id', 'username', 'email', 'first_name', 'last_name',
            'subscription_status', 'trial_ends_at', 'created_at', 'profile'
        )
        read_only_fields = ('id', 'subscription_status', 'trial_ends_at', 'created_at') 