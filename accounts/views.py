import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.conf import settings
from projects.models import Project
from tasks.models import Task
from django.db.models import Sum

import uuid

from .models import UserProfile
from .forms import (
    RegisterForm, LoginForm, PasswordChangeCustomForm,
    PasswordResetForm, PasswordResetConfirmForm, UserProfileUpdateForm,
    OTPVerificationForm
)


from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth.models import User

def user_login(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request.POST)

        if form.is_valid():

            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            remember_me = form.cleaned_data["remember_me"]

            user = authenticate(request, username=username, password=password)

            if user is None:
                try:
                    user_obj = User.objects.get(email=username)
                    user = authenticate(
                        request,
                        username=user_obj.username,
                        password=password
                    )
                except User.DoesNotExist:
                    user = None

            if user is not None and user.is_active:

                login(request, user)

                if remember_me:
                    request.session.set_expiry(30 * 24 * 60 * 60)
                else:
                    request.session.set_expiry(0)

                messages.success(request, f"Welcome back, {user.username}!")

                return redirect("dashboard")

            elif user is not None and not user.is_active:

                messages.error(request, "Your account has been disabled.")

            else:

                messages.error(request, "Invalid username/email or password.")

    else:

        form = LoginForm()

    return render(request, "login.html", {"form": form})

def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():

            otp = random.randint(100000, 999999)

            request.session['otp'] = str(otp)

            request.session['full_name'] = form.cleaned_data['full_name']
            request.session['email'] = form.cleaned_data['email']
            request.session['username'] = form.cleaned_data['username']
            request.session['password'] = form.cleaned_data['password']
            request.session['role'] = form.cleaned_data['role']

            send_mail(
                subject="Task Management System OTP",
                message=f"Your OTP is: {otp}",
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[form.cleaned_data['email']],
                fail_silently=False,
            )

            messages.success(request, "OTP sent to your email.")

            return redirect("verify_otp")

    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})

def verify_otp(request):
    email = request.session.get("email")
    if not email:
        messages.error(request, "Session expired. Please register again.")
        return redirect("register")

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data.get("otp_code")
            session_otp = request.session.get("otp")

            if entered_otp == session_otp:
                # Create user
                user = User.objects.create_user(
                    username=request.session.get("username"),
                    email=request.session.get("email"),
                    password=request.session.get("password"),
                    first_name=request.session.get("full_name"),
                )
                
                # Create user profile
                UserProfile.objects.create(
                    user=user,
                    full_name=request.session.get("full_name"),
                    role=request.session.get("role", "Team Member"),
                )

                messages.success(request, "Registration Successful. Please log in.")
                request.session.flush()
                return redirect("login")
            else:
                messages.error(request, "Invalid OTP")
    else:
        form = OTPVerificationForm()

    return render(request, "verify_otp.html", {"form": form, "email": email, "dev_otp": request.session.get("otp")})


def resend_otp(request):
    email = request.session.get("email")
    if not email:
        messages.error(request, "Session expired. Please register again.")
        return redirect("register")

    otp = random.randint(100000, 999999)
    request.session["otp"] = str(otp)

    send_mail(
        subject="Task Management System OTP",
        message=f"Your OTP is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, "OTP sent again.")
    return redirect("verify_otp")

@login_required(login_url='login')
def dashboard(request):

    user_profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "full_name": request.user.username,
            "role": "Team Member",
        }
    )

    is_admin = (
        user_profile.is_administrator()
        or request.user.is_superuser
    )

    # All Projects
    projects = Project.objects.all()

    # User Assigned Tasks
    assigned_tasks = Task.objects.filter(
        assignee=request.user
    )

    # Notifications
    unread_notifications = request.user.notifications.filter(
        is_read=False
    )

    # Dashboard Counts
    total_assigned_count = assigned_tasks.count()

    completed_assigned_count = assigned_tasks.filter(
        status="Done"
    ).count()

    total_est_hours = assigned_tasks.aggregate(
        total=Sum("estimated_hours")
    )["total"] or 0

    total_users = User.objects.count()
    total_projects = Project.objects.count()
    total_tasks = Task.objects.count()
    completed_tasks_count = Task.objects.filter(status="Done").count()
    pending_tasks_count = Task.objects.exclude(status="Done").count()

    # Recent Activity Logs
    from tasks.models import ActivityLog
    if is_admin or user_profile.role == 'Project Manager':
        activities = ActivityLog.objects.all()[:10]
    else:
        activities = ActivityLog.objects.filter(project__memberships__user=request.user).distinct()[:10]

    context = {
        "user_profile": user_profile,
        "is_admin": is_admin,
        "is_pm": user_profile.is_project_manager(),
        "is_tm": user_profile.is_team_member(),

        "projects": projects,
        "assigned_tasks": assigned_tasks,
        "unread_notifications": unread_notifications,

        "total_assigned_count": total_assigned_count,
        "completed_assigned_count": completed_assigned_count,
        "total_est_hours": total_est_hours,

        "total_users": total_users,
        "total_projects": total_projects,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks_count,
        "pending_tasks": pending_tasks_count,
        "activities": activities,
    }

    # Redirect checks removed so users always land directly on the dashboard
    return render(request, "dashboard.html", context)



@login_required(login_url='login')
def user_logout(request):
    """Handle user logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required(login_url='login')
def change_password(request):
    """Handle password change"""
    if request.method == 'POST':
        form = PasswordChangeCustomForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session to prevent logout
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            
            # Send Notification
            from notifications.helper import send_notification
            send_notification(
                recipient=request.user,
                message="Your account password was successfully changed.",
                sender=request.user,
                url="/profile/"
            )
            
            messages.success(request, 'Your password has been changed successfully.')
            return redirect('dashboard')
    else:
        form = PasswordChangeCustomForm(request.user)
    
    return render(request, 'change_password.html', {'form': form})


def forgot_password(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("email")
            
            # Generate a 6-digit OTP
            otp = random.randint(100000, 999999)
            request.session["reset_email"] = email
            request.session["reset_otp"] = str(otp)

            # Send email
            subject = "Password Reset OTP - Task Management System"
            message = f"Hello,\n\nYour OTP code to reset your password is: {otp}\n\nThis OTP will expire shortly. If you did not request this reset, please ignore this email."

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(request, "OTP has been sent to your email.")
            return redirect("verify_reset_otp")
    else:
        form = PasswordResetForm()

    return render(request, "forgot_password.html", {"form": form})


def verify_reset_otp(request):
    email = request.session.get("reset_email")
    if not email:
        messages.error(request, "Session expired. Please try resetting again.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data.get("otp_code")
            session_otp = request.session.get("reset_otp")

            if entered_otp == session_otp:
                request.session["reset_otp_verified"] = True
                return redirect("reset_password")
            else:
                messages.error(request, "Invalid OTP")
    else:
        form = OTPVerificationForm()

    return render(request, "verify_reset_otp.html", {"form": form, "email": email})


def resend_reset_otp(request):
    email = request.session.get("reset_email")
    if not email:
        messages.error(request, "Session expired. Please try resetting again.")
        return redirect("forgot_password")

    otp = random.randint(100000, 999999)
    request.session["reset_otp"] = str(otp)

    send_mail(
        subject="Password Reset OTP - Task Management System",
        message=f"Your new OTP is: {otp}",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        fail_silently=False,
    )

    messages.success(request, "OTP sent again.")
    return redirect("verify_reset_otp")


def reset_password(request):
    if not request.session.get("reset_otp_verified") or not request.session.get("reset_email"):
        messages.error(request, "Unauthorized access. Please verify your OTP first.")
        return redirect("forgot_password")

    email = request.session.get("reset_email")
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            
            # Send Notification
            from notifications.helper import send_notification
            send_notification(
                recipient=user,
                message="Your account password was successfully reset.",
                sender=user,
                url="/profile/"
            )
            
            # Clear reset session data
            request.session.flush()
            
            messages.success(request, "Your password has been reset successfully. Please log in.")
            return redirect("login")
    else:
        form = PasswordResetConfirmForm()

    return render(request, "reset_password.html", {"form": form})


def reset_password_confirm(request, uidb64, token):
    """Handle password reset confirmation"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        messages.error(request, 'Invalid reset link.')
        return redirect('login')
    
    # Verify token
    token_generator = PasswordResetTokenGenerator()
    if not token_generator.check_token(user, token):
        messages.error(request, 'Reset link has expired.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password1'])
            user.save()
            messages.success(request, 'Your password has been reset successfully. Please log in.')
            return redirect('login')
    else:
        form = PasswordResetConfirmForm()
    
    return render(request, 'reset_password_confirm.html', {'form': form, 'uid': uidb64, 'token': token})


@login_required(login_url='login')
def profile_view(request):
    """Display user profile"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    context = {
        'user_profile': user_profile,
    }
    return render(request, 'profile.html', context)


@login_required(login_url='login')
def profile_edit(request):
    """Edit user profile"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('profile')
    else:
        form = UserProfileUpdateForm(instance=user_profile)
    
    return render(request, 'profile_edit.html', {'form': form})


# Role-based decorators for access control

def role_required(role):
    """Decorator to check if user has required role"""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                if user_profile.role == role:
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, f'You do not have permission to access this page.')
                    return redirect('dashboard')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found.')
                return redirect('login')
        
        return wrapper
    return decorator


def admin_required(view_func):
    """Decorator to require administrator role"""
    return role_required('Administrator')(view_func)


def project_manager_required(view_func):
    """Decorator to require project manager role"""
    return role_required('Project Manager')(view_func)


def team_member_required(view_func):
    """Decorator to require team member role"""
    return role_required('Team Member')(view_func)


@login_required(login_url='login')
def module_flow(request):
    return render(request, "module_flow.html")


@login_required(login_url='login')
@admin_required
def admin_panel(request):
    """Admin panel - manage users, projects, and system settings"""
    all_users = User.objects.all().count()
    active_users = User.objects.filter(is_active=True).count()
    staff_users = User.objects.filter(is_staff=True).count()
    
    context = {
        'all_users': all_users,
        'active_users': active_users,
        'staff_users': staff_users,
    }
    return render(request, 'admin_panel.html', context)


@login_required(login_url='login')
def settings_view(request):
    """Unified Settings panel displaying profile details edit and password change options"""
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    profile_form = UserProfileUpdateForm(instance=user_profile)
    password_form = PasswordChangeCustomForm(request.user)
    
    active_tab = 'profile'
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_profile':
            profile_form = UserProfileUpdateForm(request.POST, request.FILES, instance=user_profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Your profile has been updated successfully.')
                return redirect('settings')
            active_tab = 'profile'
            
        elif action == 'change_password':
            password_form = PasswordChangeCustomForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, user)
                
                # Send Notification
                from notifications.helper import send_notification
                send_notification(
                    recipient=request.user,
                    message="Your account password was successfully changed.",
                    sender=request.user,
                    url="/profile/"
                )
                
                messages.success(request, 'Your password has been changed successfully.')
                return redirect('settings')
            active_tab = 'password'
            
    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'active_tab': active_tab,
        'user_profile': user_profile
    }
    return render(request, 'settings.html', context)


