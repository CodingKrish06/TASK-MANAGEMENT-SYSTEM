from django.contrib.auth.models import User

def sidebar_context(request):
    """Context processor to provide sidebar data globally to all templates"""
    if request.user.is_authenticated:
        from accounts.models import UserProfile
        from notifications.models import Notification
        from projects.models import Project
        
        try:
            user_profile = request.user.profile
        except (AttributeError, UserProfile.DoesNotExist):
            user_profile, _ = UserProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'full_name': request.user.first_name or request.user.username,
                    'role': 'Team Member'
                }
            )
            
        unread_notifications_count = request.user.notifications.filter(is_read=False).count()
        
        is_admin = user_profile.role == 'Administrator' or request.user.is_superuser
        is_pm = user_profile.role == 'Project Manager'
        is_tm = user_profile.role == 'Team Member'
        
        if is_admin:
            sidebar_projects = Project.objects.all()
        else:
            sidebar_projects = Project.objects.filter(memberships__user=request.user).distinct()
            
        return {
            'user_profile': user_profile,
            'unread_notifications_count': unread_notifications_count,
            'sidebar_projects': sidebar_projects,
            'is_admin': is_admin,
            'is_pm': is_pm,
            'is_tm': is_tm,
        }
    return {}
