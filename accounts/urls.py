from django.urls import path
from .views import (
    UserLoginView, 
    UserLogoutView, 
    UserRegistrationView, 
    CurrentUserView, 
    UserProfileView,
    ChangePasswordView,
    PasswordResetRequestView,    
    OTPVerifyView,                 
    PasswordResetSetNewView,
    VerifyAccountView,
    GoogleLoginView        
)

app_name = 'accounts'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='user_login'),
    path('logout/', UserLogoutView.as_view(), name='user_logout'),
    path('register/', UserRegistrationView.as_view(), name='user_register'),
    path('verify-account/', VerifyAccountView.as_view(), name='verify_account'),
    path('google-login/', GoogleLoginView.as_view(), name='google_login'),
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('profile/', UserProfileView.as_view(), name='user-profile'), 
    path('profile/change-password/', ChangePasswordView.as_view(), name='account_change_password'),
    
    # OTP Based Password Reset URLs
    path('password-reset/request-otp/', PasswordResetRequestView.as_view(), name='password_reset_request_otp'),
    path('password-reset/verify-otp/', OTPVerifyView.as_view(), name='password_reset_verify_otp'),
    path('password-reset/set-new-password/', PasswordResetSetNewView.as_view(), name='password_reset_set_new'),
]