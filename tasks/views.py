import os
from io import BytesIO
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.db import models
from django.utils import timezone
from django.http import FileResponse

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from projects.models import Project
from projects.views import get_user_project_role
from .models import Sprint, Task, TaskDependency, Comment, Attachment
from .forms import SprintForm, TaskForm, CommentForm, AttachmentForm, TaskDependencyForm
from notifications.helper import send_notification


@login_required(login_url='login')
def kanban_board(request, project_id):
    """View to display the interactive Kanban Board for a project"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)
    
    if not role:
        messages.error(request, "You do not have access to this project.")
        return redirect('project_list')

    # Optional filter by active sprint, or display all tasks
    active_sprint_id = request.GET.get('sprint_id')
    sprints = project.sprints.all()
    
    if active_sprint_id:
        tasks = project.tasks.filter(sprint_id=active_sprint_id)
        selected_sprint = get_object_or_404(Sprint, id=active_sprint_id)
    else:
        # Default to active sprint if available, else all tasks
        active_sprint = project.sprints.filter(is_active=True).first()
        if active_sprint:
            tasks = project.tasks.filter(sprint=active_sprint)
            selected_sprint = active_sprint
        else:
            tasks = project.tasks.all()
            selected_sprint = None

    todo_tasks = tasks.filter(status='To Do')
    in_progress_tasks = tasks.filter(status='In Progress')
    review_tasks = tasks.filter(status='Review')
    blocked_tasks = tasks.filter(status='Blocked')
    done_tasks = tasks.filter(status='Done')

    context = {
        'project': project,
        'sprints': sprints,
        'selected_sprint': selected_sprint,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'review_tasks': review_tasks,
        'blocked_tasks': blocked_tasks,
        'done_tasks': done_tasks,
        'user_role': role,
        'is_manager': role in ['Administrator', 'Project Manager']
    }
    return render(request, 'tasks/kanban_board.html', context)


@login_required(login_url='login')
def task_detail(request, task_id):
    """Detailed workspace for a specific task (comments, attachments, dependencies, hours)"""
    task = get_object_or_404(Task, id=task_id)
    project = task.project
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "You do not have access to this task.")
        return redirect('project_list')

    comments = task.comments.all()
    attachments = task.attachments.all()
    dependencies = task.dependencies.all()

    # Forms
    comment_form = CommentForm()
    attachment_form = AttachmentForm()
    dependency_form = TaskDependencyForm(task=task)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Add Comment
        if action == 'add_comment':
            comment_form = CommentForm(request.POST)
            if comment_form.is_valid():
                comment = comment_form.save(commit=False)
                comment.task = task
                comment.author = request.user
                comment.save()
                
                # Notify assignee if it's someone else
                if task.assignee and task.assignee != request.user:
                    send_notification(
                        recipient=task.assignee,
                        message=f"{request.user.username} commented on task '{task.title}'",
                        sender=request.user,
                        url=f"/tasks/task/{task.id}/"
                    )
                messages.success(request, "Comment added.")
                return redirect('task_detail', task_id=task.id)

        # Upload Attachment
        elif action == 'upload_attachment':
            attachment_form = AttachmentForm(request.POST, request.FILES)
            if attachment_form.is_valid():
                attachment = attachment_form.save(commit=False)
                attachment.task = task
                attachment.uploaded_by = request.user
                attachment.filename = request.FILES['file'].name
                attachment.save()
                messages.success(request, "File attached successfully.")
                return redirect('task_detail', task_id=task.id)

    context = {
        'task': task,
        'project': project,
        'comments': comments,
        'attachments': attachments,
        'dependencies': dependencies,
        'comment_form': comment_form,
        'attachment_form': attachment_form,
        'dependency_form': dependency_form,
        'user_role': role,
        'is_manager': role in ['Administrator', 'Project Manager']
    }
    return render(request, 'tasks/task_detail.html', context)


@login_required(login_url='login')
def task_create(request, project_id):
    """Create a new task in the project (Managers/Admins only)"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to create tasks.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        form = TaskForm(request.POST, project=project)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.reporter = request.user
            task.save()

            # Log Activity
            from .models import ActivityLog
            ActivityLog.objects.create(
                project=project,
                task=task,
                user=request.user,
                action=f"Created task '{task.title}'"
            )
            if task.assignee:
                ActivityLog.objects.create(
                    project=project,
                    task=task,
                    user=request.user,
                    action=f"Assigned task '{task.title}' to {task.assignee.username}"
                )

            # Notify assignee
            if task.assignee and task.assignee != request.user:
                send_notification(
                    recipient=task.assignee,
                    message=f"You have been assigned to task '{task.title}' in project '{project.name}'.",
                    sender=request.user,
                    url=f"/tasks/task/{task.id}/"
                )

            messages.success(request, f"Task '{task.title}' created.")
            return redirect('kanban_board', project_id=project.id)
    else:
        # Pre-select sprint if passed in query string
        sprint_id = request.GET.get('sprint_id')
        initial_data = {}
        if sprint_id:
            initial_data['sprint'] = sprint_id
        form = TaskForm(project=project, initial=initial_data)

    return render(request, 'tasks/task_form.html', {'form': form, 'project': project, 'title': 'Create Task'})


@login_required(login_url='login')
def task_edit(request, task_id):
    """Edit task details"""
    task = get_object_or_404(Task, id=task_id)
    project = task.project
    role = get_user_project_role(request.user, project)

    # Team members can edit task assignments/status, but we restrict full edit if necessary
    # For a simple system, we allow editing if they are member of the project
    if not role:
        messages.error(request, "You do not have access to this task.")
        return redirect('project_list')

    # Store old properties to check if changed
    old_assignee = task.assignee
    old_status = task.status
    old_due_date = task.due_date

    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, project=project)
        if form.is_valid():
            updated_task = form.save()

            from .models import ActivityLog
            # Log Activity based on what changed
            if updated_task.assignee != old_assignee:
                ActivityLog.objects.create(
                    project=project,
                    task=updated_task,
                    user=request.user,
                    action=f"Reassigned task '{updated_task.title}' to {updated_task.assignee.username if updated_task.assignee else 'Unassigned'}"
                )
            if updated_task.status != old_status:
                ActivityLog.objects.create(
                    project=project,
                    task=updated_task,
                    user=request.user,
                    action=f"Changed status of task '{updated_task.title}' to '{updated_task.status}'"
                )
            if updated_task.due_date != old_due_date:
                ActivityLog.objects.create(
                    project=project,
                    task=updated_task,
                    user=request.user,
                    action=f"Changed deadline of task '{updated_task.title}' to {updated_task.due_date.strftime('%Y-%m-%d') if updated_task.due_date else 'None'}"
                )
            
            # Generic detail log if nothing specific registered
            if updated_task.assignee == old_assignee and updated_task.status == old_status and updated_task.due_date == old_due_date:
                ActivityLog.objects.create(
                    project=project,
                    task=updated_task,
                    user=request.user,
                    action=f"Updated details for task '{updated_task.title}'"
                )

            # Notify new assignee if changed
            if updated_task.assignee and updated_task.assignee != old_assignee and updated_task.assignee != request.user:
                send_notification(
                    recipient=updated_task.assignee,
                    message=f"You have been assigned to task '{updated_task.title}'.",
                    sender=request.user,
                    url=f"/tasks/task/{updated_task.id}/"
                )

            messages.success(request, "Task details updated.")
            return redirect('task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task, project=project)

    return render(request, 'tasks/task_form.html', {'form': form, 'project': project, 'task': task, 'title': 'Edit Task'})


@login_required(login_url='login')
def task_delete(request, task_id):
    """Delete a task (Managers/Admins only)"""
    task = get_object_or_404(Task, id=task_id)
    project = task.project
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to delete tasks.")
        return redirect('task_detail', task_id=task.id)

    if request.method == 'POST':
        title = task.title
        task.delete()
        messages.success(request, f"Task '{title}' deleted.")
        return redirect('kanban_board', project_id=project.id)

    return render(request, 'tasks/task_delete_confirm.html', {'task': task})


@login_required(login_url='login')
def update_task_status(request, task_id):
    """Endpoint to trigger quick status updates from Kanban board or detail pane"""
    task = get_object_or_404(Task, id=task_id)
    project = task.project
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "Unauthorized access.")
        return redirect('project_list')

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Task.STATUS_CHOICES):
            task.status = new_status
            task.save()
            
            # Log Activity
            from .models import ActivityLog
            ActivityLog.objects.create(
                project=project,
                task=task,
                user=request.user,
                action=f"Changed status of task '{task.title}' to '{new_status}'"
            )
            
            # Notify reporter if status changed by assignee
            if task.reporter and task.reporter != request.user:
                send_notification(
                    recipient=task.reporter,
                    message=f"Task '{task.title}' status was updated to '{new_status}' by {request.user.username}.",
                    sender=request.user,
                    url=f"/tasks/task/{task.id}/"
                )
            
            # Send Task Completed notifications
            if new_status == 'Done':
                if task.reporter and task.reporter != request.user:
                    send_notification(
                        recipient=task.reporter,
                        message=f"Task '{task.title}' has been completed (marked Done) by {request.user.username}.",
                        sender=request.user,
                        url=f"/tasks/task/{task.id}/"
                    )
                if project.created_by and project.created_by != request.user and project.created_by != task.reporter:
                    send_notification(
                        recipient=project.created_by,
                        message=f"Task '{task.title}' has been completed in your project '{project.name}'.",
                        sender=request.user,
                        url=f"/tasks/task/{task.id}/"
                    )
            
            messages.success(request, f"Task status updated to '{new_status}'.")
    
    return redirect(request.META.get('HTTP_REFERER', f"/tasks/board/{project.id}/"))


@login_required(login_url='login')
def add_dependency(request, task_id):
    """Add a block dependency between two tasks"""
    task = get_object_or_404(Task, id=task_id)
    project = task.project
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "Unauthorized access.")
        return redirect('project_list')

    if request.method == 'POST':
        form = TaskDependencyForm(request.POST, task=task)
        if form.is_valid():
            dep = form.save(commit=False)
            dep.task = task
            dep.save()
            messages.success(request, "Dependency relationship added.")
        else:
            messages.error(request, "Failed to add dependency.")
            
    return redirect('task_detail', task_id=task.id)


@login_required(login_url='login')
def remove_dependency(request, dependency_id):
    """Remove a dependency relationship"""
    dep = get_object_or_404(TaskDependency, id=dependency_id)
    task = dep.task
    project = task.project
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "Unauthorized access.")
        return redirect('project_list')

    dep.delete()
    messages.success(request, "Dependency relationship removed.")
    return redirect('task_detail', task_id=task.id)


@login_required(login_url='login')
def sprint_create(request, project_id):
    """Create a new sprint interval (Managers/Admins only)"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to create Sprints.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        form = SprintForm(request.POST)
        if form.is_valid():
            sprint = form.save(commit=False)
            sprint.project = project
            
            # If marked active, deactivate other sprints first
            if sprint.is_active:
                project.sprints.filter(is_active=True).update(is_active=False)
                
            sprint.save()
            messages.success(request, f"Sprint '{sprint.name}' created successfully.")
            return redirect('project_detail', project_id=project.id)
    else:
        form = SprintForm()

    return render(request, 'tasks/sprint_form.html', {'form': form, 'project': project})


@login_required(login_url='login')
def toggle_sprint_status(request, sprint_id):
    """Toggle a sprint's active state"""
    sprint = get_object_or_404(Sprint, id=sprint_id)
    project = sprint.project
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to manage Sprints.")
        return redirect('project_detail', project_id=project.id)

    if sprint.is_active:
        sprint.is_active = False
        sprint.save()
        messages.success(request, f"Sprint '{sprint.name}' deactivated.")
    else:
        # Deactivate all other sprints in project
        project.sprints.filter(is_active=True).update(is_active=False)
        sprint.is_active = True
        sprint.save()
        messages.success(request, f"Sprint '{sprint.name}' is now active.")

    return redirect('project_detail', project_id=project.id)


@login_required(login_url='login')
def reports(request, project_id):
    """Dashboard showing task velocity, members workload and a visual Gantt timeline"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "You do not have access to this project's reports.")
        return redirect('project_list')

    # Calculations for stats
    todo_count = project.tasks.filter(status='To Do').count()
    progress_count = project.tasks.filter(status='In Progress').count()
    review_count = project.tasks.filter(status='In Review').count()
    done_count = project.tasks.filter(status='Done').count()

    # Workload statistics (Tasks assigned per user)
    workload = User.objects.filter(project_memberships__project=project).annotate(
        task_count=Count('assigned_tasks', filter=models.Q(assigned_tasks__project=project)),
        total_est=Sum('assigned_tasks__estimated_hours', filter=models.Q(assigned_tasks__project=project))
    )

    # Gantt Chart Schedule Data (Tasks with start/end dates)
    scheduled_tasks = project.tasks.filter(start_date__isnull=False, due_date__isnull=False)
    
    project_duration = (project.end_date - project.start_date).days or 1
    gantt_tasks = []
    for task in scheduled_tasks:
        start_offset = (task.start_date - project.start_date).days
        task_duration = (task.due_date - task.start_date).days or 1
        left_pct = max(0, min(100, int((start_offset / project_duration) * 100)))
        width_pct = max(1, min(100 - left_pct, int((task_duration / project_duration) * 100)))
        gantt_tasks.append({
            'task': task,
            'left': left_pct,
            'width': width_pct,
        })

    context = {
        'project': project,
        'todo_count': todo_count,
        'progress_count': progress_count,
        'review_count': review_count,
        'done_count': done_count,
        'workload': workload,
        'gantt_tasks': gantt_tasks,
        'user_role': role,
        'is_manager': role in ['Administrator', 'Project Manager']
    }
    return render(request, 'projects/reports.html', context)


@login_required(login_url='login')
def global_reports(request):
    """View to display global statistics and reports across all projects"""
    try:
        user_profile = request.user.profile
    except (AttributeError, UserProfile.DoesNotExist):
        from accounts.models import UserProfile
        user_profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.username, 'role': 'Team Member'}
        )
        
    total_users = User.objects.count()
    total_projects = Project.objects.count()
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='Done').count()
    pending_tasks = Task.objects.exclude(status='Done').count()
    
    # Projects summary data
    projects = Project.objects.all().annotate(
        task_count=Count('tasks'),
        done_count=Count('tasks', filter=Q(tasks__status='Done')),
    )
    
    # Task reports (by priority and status)
    tasks_by_priority = Task.objects.values('priority').annotate(count=Count('id'))
    tasks_by_status = Task.objects.values('status').annotate(count=Count('id'))
    
    context = {
        'total_users': total_users,
        'total_projects': total_projects,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'pending_tasks': pending_tasks,
        'projects': projects,
        'tasks_by_priority': tasks_by_priority,
        'tasks_by_status': tasks_by_status,
        'is_manager': user_profile.role in ['Administrator', 'Project Manager'] or request.user.is_superuser
    }
    return render(request, 'projects/global_reports.html', context)


@login_required(login_url='login')
def download_report_pdf(request):
    """View to generate a system-wide reports PDF using reportlab"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    # Create custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#6366f1'),
        spaceAfter=20
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#94a3b8'),
        spaceAfter=20
    )
    heading_style = ParagraphStyle(
        'DocHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=15,
        spaceAfter=10
    )
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        spaceAfter=12
    )

    elements = []
    
    # Title & Metadata
    elements.append(Paragraph("Task Management System - Global Report", title_style))
    elements.append(Paragraph(f"Generated on: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')} UTC | Generated by: {request.user.username}", subtitle_style))
    elements.append(Spacer(1, 10))
    
    # Section 1: Summary Statistics
    elements.append(Paragraph("System Summary Statistics", heading_style))
    
    total_users = User.objects.count()
    total_projects = Project.objects.count()
    total_tasks = Task.objects.count()
    completed_tasks = Task.objects.filter(status='Done').count()
    pending_tasks = Task.objects.exclude(status='Done').count()
    
    summary_data = [
        ["Metric", "Count"],
        ["Total Users", str(total_users)],
        ["Total Projects", str(total_projects)],
        ["Total Tasks", str(total_tasks)],
        ["Completed Tasks (Done)", str(completed_tasks)],
        ["Pending Tasks", str(pending_tasks)]
    ]
    
    summary_table = Table(summary_data, colWidths=[300, 100])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#6366f1')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Section 2: Projects Overview
    elements.append(Paragraph("Projects Performance Overview", heading_style))
    
    project_headers = ["Project Name", "Start Date", "End Date", "Total Tasks", "Completed", "Completion %"]
    project_data = [project_headers]
    
    for p in Project.objects.all():
        p_tasks = p.tasks.count()
        p_done = p.tasks.filter(status='Done').count()
        p_perc = f"{int((p_done/p_tasks)*100)}%" if p_tasks > 0 else "0%"
        project_data.append([
            p.name,
            p.start_date.strftime('%Y-%m-%d'),
            p.end_date.strftime('%Y-%m-%d'),
            str(p_tasks),
            str(p_done),
            p_perc
        ])
        
    project_table = Table(project_data, colWidths=[150, 80, 80, 80, 80, 80])
    project_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    elements.append(project_table)
    elements.append(Spacer(1, 20))
    
    # Section 3: Tasks Breakdown
    elements.append(Paragraph("Tasks Priority Breakdown", heading_style))
    
    priority_data = [["Priority", "Tasks Count"]]
    for priority_choice in ['Low', 'Medium', 'High', 'Critical']:
        cnt = Task.objects.filter(priority=priority_choice).count()
        priority_data.append([priority_choice, str(cnt)])
        
    priority_table = Table(priority_data, colWidths=[200, 100])
    priority_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#475569')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#e2e8f0')),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
    ]))
    elements.append(priority_table)
    
    # Build Document
    doc.build(elements)
    buffer.seek(0)
    
    return FileResponse(buffer, as_attachment=True, filename="global_report.pdf")


import calendar
from datetime import date, datetime

@login_required(login_url='login')
def calendar_view(request):
    """Monthly Calendar view of task deadlines and start dates"""
    # Parse year and month or default to current
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    
    # Bound month/year checks
    if month < 1 or month > 12:
        month = today.month
    if year < 2000 or year > 2100:
        year = today.year

    cal = calendar.Calendar(firstweekday=6) # Sunday start
    month_days = cal.monthdatescalendar(year, month)
    
    # Fetch all tasks that fall in the queried month/year for the current user's projects
    try:
        user_profile = request.user.profile
    except (AttributeError, UserProfile.DoesNotExist):
        from accounts.models import UserProfile
        user_profile, _ = UserProfile.objects.get_or_create(
            user=request.user,
            defaults={'full_name': request.user.username, 'role': 'Team Member'}
        )
        
    is_admin = user_profile.role == 'Administrator' or request.user.is_superuser
    
    if is_admin:
        tasks = Task.objects.filter(
            Q(start_date__year=year, start_date__month=month) |
            Q(due_date__year=year, due_date__month=month)
        )
    else:
        tasks = Task.objects.filter(
            project__memberships__user=request.user
        ).filter(
            Q(start_date__year=year, start_date__month=month) |
            Q(due_date__year=year, due_date__month=month)
        ).distinct()

    # Organize tasks by day
    # day_tasks will be a dict: {date_object: [task1, task2]}
    day_tasks = {}
    for task in tasks:
        # Populate for start date
        if task.start_date:
            day_tasks.setdefault(task.start_date, []).append({
                'task': task,
                'type': 'start',
                'label': f"▶ {task.title}"
            })
        # Populate for due date
        if task.due_date:
            day_tasks.setdefault(task.due_date, []).append({
                'task': task,
                'type': 'due',
                'label': f"⌛ {task.title}"
            })

    # Prepare navigation months
    prev_month = month - 1
    prev_year = year
    if prev_month == 0:
        prev_month = 12
        prev_year = year - 1
        
    next_month = month + 1
    next_year = year
    if next_month == 13:
        next_month = 1
        next_year = year + 1

    current_month_name = calendar.month_name[month]

    # Convert days structure to context-friendly dictionary
    # We will build a calendar grid structure: list of weeks, where each week is a list of day dicts.
    calendar_weeks = []
    for week in month_days:
        week_days = []
        for day in week:
            # Check if day belongs to current month
            in_month = (day.month == month and day.year == year)
            day_items = day_tasks.get(day, [])
            week_days.append({
                'date': day,
                'day_num': day.day,
                'in_month': in_month,
                'items': day_items,
                'is_today': (day == today)
            })
        calendar_weeks.append(week_days)

    context = {
        'weeks': calendar_weeks,
        'year': year,
        'month': month,
        'month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today
    }
    return render(request, 'tasks/calendar.html', context)

