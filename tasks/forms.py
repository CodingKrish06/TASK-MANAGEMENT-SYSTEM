from django import forms
from django.contrib.auth.models import User
from .models import Sprint, Task, Comment, Attachment, TaskDependency
from projects.models import Project

class SprintForm(forms.ModelForm):
    """Form to create or edit a Sprint"""
    class Meta:
        model = Sprint
        fields = ['name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sprint name, e.g. Sprint 1'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TaskForm(forms.ModelForm):
    """Form to create or edit a Task"""
    class Meta:
        model = Task
        fields = ['sprint', 'title', 'description', 'task_type', 'status', 'priority', 'assignee', 'start_date', 'due_date', 'estimated_hours', 'logged_hours']
        widgets = {
            'sprint': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter task title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter detailed description'}),
            'task_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'assignee': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Estimated hours'}),
            'logged_hours': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Logged hours'}),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        super(TaskForm, self).__init__(*args, **kwargs)
        if project:
            # Restrict sprint choices to the current project's sprints
            self.fields['sprint'].queryset = Sprint.objects.filter(project=project)
            # Restrict assignee choices to users who are members of the current project
            member_ids = project.memberships.values_list('user_id', flat=True)
            self.fields['assignee'].queryset = User.objects.filter(id__in=member_ids)


class CommentForm(forms.ModelForm):
    """Form to add a comment to a task"""
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Add a comment...'}),
        }


class AttachmentForm(forms.ModelForm):
    """Form to upload a file attachment to a task"""
    class Meta:
        model = Attachment
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class TaskDependencyForm(forms.ModelForm):
    """Form to specify dependencies between tasks"""
    depends_on = forms.ModelChoiceField(
        queryset=Task.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select a task"
    )

    class Meta:
        model = TaskDependency
        fields = ['depends_on', 'dependency_type']
        widgets = {
            'dependency_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        task = kwargs.pop('task', None)
        super(TaskDependencyForm, self).__init__(*args, **kwargs)
        if task:
            # Exclude current task and tasks already in dependency relationship to prevent cycles/duplicates
            existing_dep_ids = task.dependencies.values_list('depends_on_id', flat=True)
            self.fields['depends_on'].queryset = Task.objects.filter(project=task.project).exclude(id=task.id).exclude(id__in=existing_dep_ids)
