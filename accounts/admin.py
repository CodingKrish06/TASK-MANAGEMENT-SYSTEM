from django.contrib import admin
from django.contrib.auth.models import User
from .models import UserProfile, OTP


class UserProfileAdmin(admin.ModelAdmin):
    """Admin configuration for UserProfile"""
    list_display = ('full_name', 'user', 'role', 'email_verified', 'is_active', 'created_at')
    list_filter = ('role', 'email_verified', 'is_active', 'created_at')
    search_fields = ('full_name', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'full_name', 'role')
        }),
        ('Contact Information', {
            'fields': ('phone_number',)
        }),
        ('Additional Information', {
            'fields': ('bio', 'profile_picture', 'is_active', 'email_verified')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class OTPAdmin(admin.ModelAdmin):
    """Admin configuration for OTP"""
    list_display = ('email', 'otp_code', 'is_verified', 'created_at', 'expires_at', 'attempt_count')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('email', 'otp_code')
    readonly_fields = ('otp_code', 'created_at', 'expires_at')
    fieldsets = (
        ('OTP Details', {
            'fields': ('email', 'otp_code')
        }),
        ('Timing', {
            'fields': ('created_at', 'expires_at')
        }),
        ('Verification', {
            'fields': ('attempt_count', 'is_verified')
        }),
    )


admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(OTP, OTPAdmin)
