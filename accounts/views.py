from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import( 
    UserSerializer, 
    UserLoginSerializer, 
    UserRegistrationSerializer, 
    UserProfileSerializer, 
    ChangePasswordSerializer,
    PasswordResetRequestSerializer, 
    OTPVerifySerializer,            
    PasswordResetSetNewSerializer,
    VerifyAccountSerializer   # Added
                         )
from .models import User
from .renderer import UserRenderer # Assuming you have this custom renderer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
import logging
from django.conf import settings # Import settings
from google.oauth2 import id_token as google_id_token # For Google ID token verification
from google.auth.transport import requests as google_requests # For Google ID token verification
import requests # General requests, if needed for other things

logger = logging.getLogger(__name__)


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)

    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }



# Create your views here.
class UserLoginView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, email=email, password=password) # authenticate checks is_active by default
        if user:
            if not user.is_active: # Explicit check, though authenticate should handle it
                return Response({'error': 'Account not verified. Please check your email for OTP.'}, status=status.HTTP_403_FORBIDDEN)
            token, _ = Token.objects.get_or_create(user=user)
            tokens = get_tokens_for_user(user)
            return Response({
                'token': token.key,
                'tokens': tokens,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            # Check if user exists but is inactive
            try:
                user_exists = User.objects.get(email=email)
                if not user_exists.is_active:
                    return Response({'error': 'Account not verified. Please check your email for OTP.', 'email': email, 'needsVerification': True}, status=status.HTTP_403_FORBIDDEN)
            except User.DoesNotExist:
                pass # Fall through to invalid credentials
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [UserRenderer]

    def post(self, request):
        """
        Logs out the authenticated user by deleting their auth token.
        """
        # If you see "no such table: authtoken_token", you need to run migrations for rest_framework.authtoken.
        # Run: python manage.py migrate authtoken
        try:
            token = Token.objects.get(user=request.user)
            token.delete()
            return Response({'message': 'Successfully logged out.', 'status':200}, status=status.HTTP_200_OK)
        except Token.DoesNotExist:
            return Response({'error': 'No active session found for this user.'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserRegistrationView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save() # User is created inactive, OTP is sent
        logger.info(f"User {user.email} registered. OTP sent for verification.")
        return Response({
            'message': 'Registration successful. Please check your email for an OTP to verify your account.',
            'email': user.email, # Send email back to frontend for OTP page
            # 'user': UserSerializer(user).data, # Don't send full user data or tokens yet
        }, status=status.HTTP_201_CREATED)

class VerifyAccountView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request, *args, **kwargs):
        serializer = VerifyAccountSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save() # Activates the user
            logger.info(f"Account verified successfully for user {user.email}.")
            # Optionally, log the user in and return tokens, or just confirm verification
            # For now, just confirm. User can login separately.
            return Response({"detail": "Account verified successfully. You can now log in."}, status=status.HTTP_200_OK)
        logger.warning(f"Account verification failed. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = [UserRenderer]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get(self, request):
        user = request.user
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        # Pass partial=True to allow partial updates (e.g., only updating 'bio')
        serializer = UserProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            # Update the session auth hash to prevent the user from being logged out
            update_session_auth_hash(request, user)
            logger.info(f"User {request.user.email} successfully changed their password.")
            return Response({"detail": "Password changed successfully."}, status=status.HTTP_200_OK)
        logger.warning(f"User {request.user.email} failed to change password. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]


    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.save() 
            logger.info(f"Password reset OTP sent to {data.get('email')}.")
            return Response(
                {"detail": "An OTP has been sent to your email address.", "email": data.get('email')},
                status=status.HTTP_200_OK
            )
        logger.warning(f"Password reset request failed for {request.data.get('email')}. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request, *args, **kwargs):
        serializer = OTPVerifySerializer(data=request.data)
        if serializer.is_valid():
            logger.info(f"OTP verified successfully for email: {request.data.get('email')}")
            return Response({"detail": "OTP verified successfully. You can now set a new password.", "email": request.data.get('email')}, status=status.HTTP_200_OK)
        logger.warning(f"OTP verification failed for email: {request.data.get('email')}. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetSetNewView(APIView):
    permission_classes = [AllowAny] 
    renderer_classes = [UserRenderer]

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetSetNewSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Password successfully reset for email: {request.data.get('email')}")
            return Response({"detail": "Password has been reset successfully. You can now log in."}, status=status.HTTP_200_OK)
        logger.warning(f"Setting new password failed for email: {request.data.get('email')}. Errors: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    renderer_classes = [UserRenderer]

    def post(self, request, *args, **kwargs):
        id_token = request.data.get('id_token')
        if not id_token:
            return Response({'error': 'ID token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the ID token
            # The audience should be your Google Client ID
            # You might need to store this client ID in Django settings or an environment variable accessible by the backend.
            # For now, we'll assume it's passed or known.
            # It's crucial that this GOOGLE_CLIENT_ID is the same one used by your frontend.
            # You can get it from settings:
            # google_client_id_backend = settings.GOOGLE_CLIENT_ID 
            # For this example, let's assume it's hardcoded or you'll add it to settings
            # A common practice is to have this in an env var and load via settings.
            
            # IMPORTANT: You MUST configure settings.GOOGLE_CLIENT_ID
            # For example, in your settings.py:
            # GOOGLE_CLIENT_ID = os.environ.get('VITE_GOOGLE_CLIENT_ID') # If backend can access frontend env vars
            # Or better, define a separate backend env var for it.
            
            # For now, let's try to get it from settings, expecting it to be set up.
            # If not set in settings, this will raise an AttributeError.
            # You should ensure settings.GOOGLE_CLIENT_ID is configured.
            # A placeholder for demonstration:
            # google_client_id_from_settings = getattr(settings, 'GOOGLE_CLIENT_ID', None)
            # if not google_client_id_from_settings:
            #     logger.error("GOOGLE_CLIENT_ID not configured in Django settings.")
            #     return Response({'error': 'Server configuration error for Google Sign-In.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Using a requests.Request() object for the transport
            google_request = google_requests.Request()
            id_info = google_id_token.verify_oauth2_token(
                id_token, google_request #, audience=google_client_id_from_settings # Uncomment and use your client ID
            )
            
            # The 'aud' claim in id_info should match one of your client IDs.
            # It's good practice to explicitly check this if verify_oauth2_token doesn't do it strictly enough for your needs,
            # or if you have multiple client IDs.
            # For example:
            # if id_info['aud'] not in [settings.GOOGLE_CLIENT_ID_WEB, settings.GOOGLE_CLIENT_ID_ANDROID]:
            #     raise ValueError('Invalid audience.')


            userid = id_info['sub'] # Google's unique ID for the user
            email = id_info.get('email')
            name = id_info.get('name', '')
            # picture = id_info.get('picture') # You can store this if you want

            if not email:
                return Response({'error': 'Email not provided by Google.'}, status=status.HTTP_400_BAD_REQUEST)

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'name': name, 'is_active': True} # New users via SSO are active
            )

            if created:
                user.set_unusable_password() # SSO users don't need a local password
                # You might want to set a flag like user.sso_provider = 'google'
                user.save()
                logger.info(f"New user created via Google SSO: {email}")
            else:
                # If user exists, ensure they are active (e.g., if they registered but didn't verify, then used SSO)
                if not user.is_active:
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                logger.info(f"User logged in via Google SSO: {email}")

            # Generate DRF token (or JWT)
            drf_token, _ = Token.objects.get_or_create(user=user)
            jwt_tokens = get_tokens_for_user(user) # Assuming you have this function for JWTs

            return Response({
                'token': drf_token.key,
                'tokens': jwt_tokens,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            # Invalid token
            logger.error(f"Google ID token verification failed: {e}")
            return Response({'error': f'Invalid Google token: {e}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"An unexpected error occurred during Google login: {e}", exc_info=True)
            return Response({'error': 'An unexpected error occurred.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)