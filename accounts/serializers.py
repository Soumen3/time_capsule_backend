from rest_framework import serializers
from .models import User
from django.utils.encoding import smart_str, force_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
# from django.contrib.auth.tokens import PasswordResetTokenGenerator # Not used for OTP
from .utils import Util # Ensure this is correctly imported
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone # Added
import random # Added
import string # Added
from django.conf import settings # Added


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={'input_type': 'password'}, write_only=True)
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'name', 'dob', 'password', 'password2', 'is_active', 'is_staff', 'created_at', 'updated_at')
        extra_kwargs = {
            'password': {'write_only': True},
            'is_active': {'required': False, 'default': True},
            'is_staff': {'required': False, 'default': False}
        }
    
    def validate(self, attrs):
        password = attrs.get('password')
        password2 = attrs.get('password2')
        if password and password2 and password != password2:
            raise serializers.ValidationError("Passwords do not match.")
        if not attrs.get('email'):
            raise serializers.ValidationError("Email is required.")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2', None)
        # User is created as inactive by default due to model change
        return User.objects.create_user(**validated_data)
    


class UserLoginSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(max_length=255, min_length=5)
    password = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ('email', 'password')

class UserLogoutSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=255, min_length=5)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email does not exist.")
        return value
    
class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(style={'input_type': 'password'}, write_only=True, validators=[validate_password])
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)

    class Meta:
        model = User
        fields = ('email', 'name', 'dob', 'password', 'password2')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password2', None)
        # User.is_active is False by default from model definition
        user = User.objects.create_user(**validated_data) 
        
        # Generate OTP
        otp = ''.join(random.choices(string.digits, k=6))
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.save(update_fields=['otp', 'otp_created_at'])

        # Send OTP email
        email_body = f"""
Hi {user.name or user.email},

Thank you for registering with Time Capsule!
Your One-Time Password (OTP) to verify your email address is:

{otp}

This OTP is valid for 10 minutes. Please enter it on the verification page.

If you did not request this, please ignore this email.

Thanks,
The Time Capsule Team
"""
        email_data = {
            'email_subject': 'Verify Your Email - Time Capsule',
            'email_body': email_body,
            'to_email': user.email
        }
        Util.send_email(email_data)
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'bio', 'dob', 'created_at', 'last_login', 'created_at']
        read_only_fields = ['email', 'created_at', 'id', 'last_login', 'created_at']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    new_password2 = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'}, label="Confirm New Password")

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Your old password was entered incorrectly. Please enter it again.")
        return value

    def validate_new_password(self, value):
        # Use Django's built-in password validators
        try:
            validate_password(value, self.context['request'].user)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, data):
        if data['new_password'] != data['new_password2']:
            raise serializers.ValidationError({"new_password2": "The two new password fields didn't match."})
        if data['old_password'] == data['new_password']:
            raise serializers.ValidationError({"new_password": "New password cannot be the same as the old password."})
        return data

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(min_length=2)

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email address does not exist.")
        return value

    def save(self):
        email = self.validated_data['email']
        user = User.objects.get(email=email)
        
        otp = ''.join(random.choices(string.digits, k=6))
        user.otp = otp
        user.otp_created_at = timezone.now()
        user.save(update_fields=['otp', 'otp_created_at'])
        
        email_body = f"""
Hi {user.name or user.email},

Your One-Time Password (OTP) for resetting your Time Capsule account password is:

{otp}

This OTP is valid for 10 minutes.

If you did not request this, please ignore this email.

Thanks,
The Time Capsule Team
"""
        email_data = {
            'email_subject': 'Password Reset OTP - Time Capsule',
            'email_body': email_body,
            'to_email': user.email
        }
        Util.send_email(email_data)
        return {'email': user.email}


class OTPVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        email = attrs.get('email')
        otp_entered = attrs.get('otp')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP.")

        if user.otp != otp_entered:
            raise serializers.ValidationError("Invalid OTP.")
        
        otp_validity_duration = getattr(settings, 'OTP_VALIDITY_DURATION_SECONDS', 600) # Default 10 mins
        if user.otp_created_at and (timezone.now() - user.otp_created_at).total_seconds() > otp_validity_duration:
            user.otp = None
            user.otp_created_at = None
            user.save(update_fields=['otp', 'otp_created_at'])
            raise serializers.ValidationError("OTP has expired. Please request a new one.")
        elif not user.otp_created_at: # Should not happen if OTP was set
             raise serializers.ValidationError("OTP not found or already used. Please request a new one.")

        user.otp = None # Clear OTP after successful verification
        # user.otp_created_at = None # Optionally clear this too, or keep for short-term session validation
        user.save(update_fields=['otp'])
        attrs['user'] = user
        return attrs


class PasswordResetSetNewSerializer(serializers.Serializer):
    email = serializers.EmailField() 
    password = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'}
    )
    password2 = serializers.CharField(
        write_only=True, required=True, style={'input_type': 'password'}, label="Confirm New Password"
    )

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password2": "Passwords do not match."})
        
        try:
            user = User.objects.get(email=attrs['email'])
            # Ideally, ensure this step is only possible shortly after OTP verification.
            # This could be managed by a short-lived token from OTPVerifyView or by checking
            # if user.otp was recently cleared (though that's less robust).
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found.")
        
        try:
            validate_password(attrs['password'], user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})
        
        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['password'])
        user.otp = None # Ensure OTP fields are fully cleared
        user.otp_created_at = None
        user.save()
        return user

class VerifyAccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        email = attrs.get('email')
        otp_entered = attrs.get('otp')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid email or OTP.")

        if user.is_active:
            raise serializers.ValidationError("Account already verified.")

        if user.otp != otp_entered:
            raise serializers.ValidationError("Invalid OTP.")
        
        otp_validity_duration = getattr(settings, 'OTP_VALIDITY_DURATION_SECONDS', 600) # Default 10 mins
        if user.otp_created_at and (timezone.now() - user.otp_created_at).total_seconds() > otp_validity_duration:
            # Optionally, clear the expired OTP from the user model here
            user.otp = None
            user.otp_created_at = None
            user.save(update_fields=['otp', 'otp_created_at'])
            raise serializers.ValidationError("OTP has expired. Please register again to get a new OTP.")
        elif not user.otp_created_at: # Should not happen if OTP was set during registration
             raise serializers.ValidationError("OTP not found. Please register again.")

        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.is_active = True
        user.otp = None # Clear OTP after successful verification
        user.otp_created_at = None # Clear OTP creation time
        user.save(update_fields=['is_active', 'otp', 'otp_created_at'])
        return user