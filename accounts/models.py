from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import random
import string


class UserProfile(models.Model):
    """Extended user profile with role-based access control"""
    
    ROLE_CHOICES = (
        ('Administrator', 'Administrator'),
        ('Project Manager', 'Project Manager'),
        ('Team Member', 'Team Member'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', null=True, blank=True)
    full_name = models.CharField(max_length=100, default='')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='Team Member')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    designation = models.CharField(max_length=100, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} ({self.role})"

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "User Profiles"

    def has_role(self, role):
        """Check if user has specific role"""
        return self.role == role

    def is_administrator(self):
        """Check if user is an administrator"""
        return self.role == 'Administrator'

    def is_project_manager(self):
        """Check if user is a project manager"""
        return self.role == 'Project Manager'

    def is_team_member(self):
        """Check if user is a team member"""
        return self.role == 'Team Member'


class OTP(models.Model):
    """Model to store OTP for email verification"""
    
    email = models.EmailField(unique=False)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)
    attempt_count = models.IntegerField(default=0)
    
    def __str__(self):
        return f"OTP for {self.email} - {self.otp_code}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "OTP"
        verbose_name_plural = "OTPs"
    
    @staticmethod
    def generate_otp():
        """Generate a random 6-digit OTP"""
        return ''.join(random.choices(string.digits, k=6))
    
    def is_expired(self):
        """Check if OTP has expired"""
        return timezone.now() > self.expires_at
    
    def is_valid_attempt(self):
        """Check if OTP still has valid attempts"""
        return self.attempt_count < 5