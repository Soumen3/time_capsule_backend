from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email, name, dob=None, password=None, password2=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(
            email=self.normalize_email(email), 
            name=name, 
            dob=dob,
            **extra_fields
            )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        # Pass a default name for superuser
        user = self.create_user(email, name=extra_fields.get('name', ''), password=password, **extra_fields)
        user.save(using=self._db)
        return user

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(
        unique=True,
        verbose_name='email address',
        error_messages={
            'unique': "A user with that email already exists.",
            'blank': "This field cannot be blank.",
            'invalid': "Enter a valid email address."
        },
        max_length=255
        )
    name = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True) 
    dob= models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False) # Changed default to False
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Fields for OTP based password reset
    otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    # REQUIRED_FIELDS = ['name'] 

    objects = UserManager()

    def __str__(self):
        return self.email
    
    def has_perm(self, perm, obj=None):
        # "Does the user have a specific permission?"
        # Simplest possible answer: Yes, if the user is active and is_staff.
        # For more granular permissions, Django's permission framework (via PermissionsMixin)
        # will handle checks if this returns False or if superuser.
        return self.is_active and self.is_staff

    def has_module_perms(self, app_label):
        # "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, if the user is active and is_staff.
        return self.is_active and self.is_staff




