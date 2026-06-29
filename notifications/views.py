from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Notification

@login_required(login_url='login')
def notification_list(request):
    """View to list all notifications of the logged-in user"""
    user_notifications = request.user.notifications.all()
    return render(request, 'notifications/list.html', {'notifications': user_notifications})

@login_required(login_url='login')
def mark_as_read(request, notification_id):
    """Mark a notification as read and redirect to its destination URL"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    
    if notification.url:
        return redirect(notification.url)
    return redirect('notification_list')

@login_required(login_url='login')
def mark_all_read(request):
    """Mark all notifications of the logged-in user as read"""
    request.user.notifications.filter(is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect('notification_list')
