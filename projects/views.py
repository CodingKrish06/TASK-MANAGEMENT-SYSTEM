from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Q

from .models import Project, ProjectMember
from .forms import ProjectForm, ProjectMemberForm
from accounts.models import UserProfile


def get_user_project_role(user, project):
    """Helper to retrieve a user's role within a project, respecting superuser/global admin roles"""
    if user.is_superuser:
        return 'Administrator'

    # Check global UserProfile role first
    try:
        if user.profile.is_administrator():
            return 'Administrator'
    except AttributeError:
        pass

    # Check project-specific role
    try:
        member = project.memberships.get(user=user)
        return member.role
    except ProjectMember.DoesNotExist:
        return None


@login_required(login_url='login')
def project_list(request):
    projects = Project.objects.all()

    return render(request, 'projects/project_list.html', {
        'projects': projects
    })


@login_required(login_url='login')
def project_setup(request):
    """After login: show step to create project first, then add team members."""
    projects = Project.objects.all().order_by('-created_at')
    needs_project = not projects.exists()

    return render(request, 'projects/setup.html', {
        'needs_project': needs_project,
        'projects': projects,
    })


@login_required(login_url='login')
def project_setup_members(request):
    """Choose a project and redirect to its Add Team Members page."""
    project_id = request.GET.get('project')
    if not project_id:
        return redirect('project_setup')

    return redirect('project_members', project_id=project_id)


@login_required(login_url='login')
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.created_by = request.user
            project.save()

            ProjectMember.objects.create(
                project=project,
                user=request.user,
                role="Administrator"
            )

            messages.success(request, "Project Created Successfully")
            return redirect("project_list")
    else:
        form = ProjectForm()

    return render(request, "projects/project_form.html", {
        "form": form
    })


@login_required(login_url='login')
def project_detail(request, project_id):
    """Detailed dashboard of a project, showing roadmap, stats, and sprints"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "You do not have access to this project.")
        return redirect('project_list')

    active_sprints = project.sprints.filter(is_active=True)
    backlog_tasks = project.tasks.filter(sprint__isnull=True)

    # Calculate stats
    total_tasks = project.tasks.count()
    done_tasks = project.tasks.filter(status='Done').count()
    in_progress_tasks = project.tasks.filter(status='In Progress').count()
    todo_tasks = project.tasks.filter(status='To Do').count()
    in_review_tasks = project.tasks.filter(status='In Review').count()

    progress = 0
    if total_tasks > 0:
        progress = int((done_tasks / total_tasks) * 100)

    context = {
        'project': project,
        'user_role': role,
        'active_sprints': active_sprints,
        'backlog_tasks': backlog_tasks,
        'total_tasks': total_tasks,
        'done_tasks': done_tasks,
        'in_progress_tasks': in_progress_tasks,
        'todo_tasks': todo_tasks,
        'in_review_tasks': in_review_tasks,
        'progress': progress,
        'is_manager': role in ['Administrator', 'Project Manager']
    }
    return render(request, 'projects/project_detail.html', context)


@login_required(login_url='login')
def project_edit(request, project_id):
    """Edit project configuration (Managers/Admins only)"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to edit this project.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project details updated.")
            return redirect('project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {'form': form, 'title': 'Edit Project', 'project': project})


@login_required(login_url='login')
def project_delete(request, project_id):
    """Delete project (Admins only)"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if role != 'Administrator':
        messages.error(request, "Only Administrators can delete projects.")
        return redirect('project_detail', project_id=project.id)

    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f"Project '{name}' has been deleted.")
        return redirect('project_list')

    return render(request, 'projects/project_delete_confirm.html', {'project': project})


@login_required(login_url='login')
def project_members(request, project_id):
    """View and manage project memberships"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if not role:
        messages.error(request, "You do not have access to this project's members.")
        return redirect('project_list')

    memberships = project.memberships.all()

    # Filter users who are not already project members for the add dropdown
    current_member_ids = memberships.values_list('user_id', flat=True)
    available_users = User.objects.exclude(id__in=current_member_ids)

    form = ProjectMemberForm()

    context = {
        'project': project,
        'memberships': memberships,
        'available_users': available_users,
        'form': form,
        'user_role': role,
        'is_manager': role in ['Administrator', 'Project Manager']
    }
    return render(request, 'projects/project_members.html', context)


@login_required(login_url='login')
def add_project_member(request, project_id):
    """Add a member to the project team"""
    project = get_object_or_404(Project, id=project_id)
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to manage members.")
        return redirect('project_members', project_id=project.id)

    if request.method == 'POST':
        form = ProjectMemberForm(request.POST)
        if form.is_valid():
            membership = form.save(commit=False)
            membership.project = project
            membership.save()

            # Send notification
            from notifications.helper import send_notification
            send_notification(
                recipient=membership.user,
                message=f"You have been added to the project '{project.name}' as '{membership.role}'.",
                sender=request.user,
                url=f"/projects/{project.id}/"
            )

            messages.success(request, f"Added {membership.user.username} to project.")
        else:
            messages.error(request, "Failed to add member. Make sure fields are valid.")

    return redirect('project_members', project_id=project.id)


@login_required(login_url='login')
def remove_project_member(request, member_id):
    """Remove a member from the project team"""
    membership = get_object_or_404(ProjectMember, id=member_id)
    project = membership.project
    role = get_user_project_role(request.user, project)

    if role not in ['Administrator', 'Project Manager']:
        messages.error(request, "You do not have permission to remove members.")
        return redirect('project_members', project_id=project.id)

    # Don't allow removing the last Administrator/Manager of the project
    if membership.role in ['Administrator', 'Project Manager'] and project.memberships.filter(role=membership.role).count() <= 1:
        messages.error(request, "Cannot remove the only remaining Manager/Administrator of this project.")
    else:
        username = membership.user.username
        membership.delete()
        messages.success(request, f"Removed {username} from the project.")

    return redirect('project_members', project_id=project.id)


@login_required(login_url='login')
def global_team_members(request):
    """View to list all team members in the system and their assigned projects"""
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile.objects.create(
            user=request.user,
            full_name=request.user.username,
            role='Team Member'
        )
        
    users = User.objects.all().select_related('profile')
    for u in users:
        u.projects_list = ProjectMember.objects.filter(user=u).select_related('project')
        try:
            u.phone_number = u.profile.phone_number
            u.role = u.profile.role
            u.full_name = u.profile.full_name
        except (AttributeError, UserProfile.DoesNotExist):
            u.phone_number = ""
            u.role = "Team Member"
            u.full_name = u.username
            
    is_manager = user_profile.role in ['Administrator', 'Project Manager'] or request.user.is_superuser
    return render(request, 'projects/team_members.html', {
        'users': users,
        'is_manager': is_manager
    })


@login_required(login_url='login')
def global_team_member_add(request):
    """View to add a new team member user, set their role, and assign to a project"""
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if user_profile.role not in ['Administrator', 'Project Manager'] and not request.user.is_superuser:
        messages.error(request, "You do not have permission to manage members.")
        return redirect('global_team_members')
        
    from .forms import TeamMemberAddForm
    if request.method == 'POST':
        form = TeamMemberAddForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            full_name = form.cleaned_data['full_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            role = form.cleaned_data['role']
            project = form.cleaned_data['project']
            
            # Create user with a standard temporary password
            user = User.objects.create_user(
                username=username,
                email=email,
                password='TempPassword123!',
                first_name=full_name.split()[0] if len(full_name.split()) > 0 else full_name
            )
            
            # Create profile
            UserProfile.objects.create(
                user=user,
                full_name=full_name,
                role=role,
                phone_number=phone_number
            )
            
            # If project assigned, create membership and send notification
            if project:
                ProjectMember.objects.create(
                    project=project,
                    user=user,
                    role=role
                )
                
                from notifications.helper import send_notification
                send_notification(
                    recipient=user,
                    message=f"You have been added to the project '{project.name}' as '{role}'.",
                    sender=request.user,
                    url=f"/projects/{project.id}/"
                )
                
            messages.success(request, f"Team member {full_name} has been added successfully. Temporary password: TempPassword123!")
            return redirect('global_team_members')
    else:
        form = TeamMemberAddForm()
        
    return render(request, 'projects/team_member_form.html', {
        'form': form,
        'title': 'Add Team Member'
    })


@login_required(login_url='login')
def global_team_member_edit(request, user_id):
    """View to edit an existing user profile and change project assignments"""
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if user_profile.role not in ['Administrator', 'Project Manager'] and not request.user.is_superuser:
        messages.error(request, "You do not have permission to manage members.")
        return redirect('global_team_members')
        
    edit_user = get_object_or_404(User, id=user_id)
    try:
        edit_profile = edit_user.profile
    except UserProfile.DoesNotExist:
        edit_profile = UserProfile.objects.create(user=edit_user, full_name=edit_user.username, role='Team Member')
        
    from .forms import TeamMemberEditForm
    current_membership = ProjectMember.objects.filter(user=edit_user).first()
    current_project = current_membership.project if current_membership else None
    
    if request.method == 'POST':
        form = TeamMemberEditForm(request.POST, user_instance=edit_user)
        if form.is_valid():
            full_name = form.cleaned_data['full_name']
            email = form.cleaned_data['email']
            phone_number = form.cleaned_data['phone_number']
            role = form.cleaned_data['role']
            project = form.cleaned_data['project']
            
            # Update user details
            edit_user.email = email
            edit_user.first_name = full_name.split()[0] if len(full_name.split()) > 0 else full_name
            edit_user.save()
            
            # Update profile
            edit_profile.full_name = full_name
            edit_profile.phone_number = phone_number
            edit_profile.role = role
            edit_profile.save()
            
            # Update Project Membership
            if project:
                if current_membership:
                    current_membership.project = project
                    current_membership.role = role
                    current_membership.save()
                else:
                    ProjectMember.objects.create(
                        project=project,
                        user=edit_user,
                        role=role
                    )
                    
                    from notifications.helper import send_notification
                    send_notification(
                        recipient=edit_user,
                        message=f"You have been added to the project '{project.name}' as '{role}'.",
                        sender=request.user,
                        url=f"/projects/{project.id}/"
                    )
            else:
                # Remove from project memberships if project is set to None/Empty
                ProjectMember.objects.filter(user=edit_user).delete()
                
            messages.success(request, f"Team member {full_name} details updated.")
            return redirect('global_team_members')
    else:
        initial_data = {
            'full_name': edit_profile.full_name,
            'email': edit_user.email,
            'phone_number': edit_profile.phone_number,
            'role': edit_profile.role,
            'project': current_project.id if current_project else None
        }
        form = TeamMemberEditForm(initial=initial_data, user_instance=edit_user)
        
    return render(request, 'projects/team_member_form.html', {
        'form': form,
        'title': f'Edit Team Member: {edit_user.username}',
        'edit_user': edit_user
    })


@login_required(login_url='login')
def global_team_member_delete(request, user_id):
    """View to delete a user profile from the database entirely"""
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        return redirect('login')
        
    if user_profile.role != 'Administrator' and not request.user.is_superuser:
        messages.error(request, "Only Administrators can delete members from the system.")
        return redirect('global_team_members')
        
    delete_user = get_object_or_404(User, id=user_id)
    if delete_user == request.user:
        messages.error(request, "You cannot delete yourself.")
    else:
        username = delete_user.username
        delete_user.delete()
        messages.success(request, f"User '{username}' was deleted successfully.")
        
    return redirect('global_team_members')


