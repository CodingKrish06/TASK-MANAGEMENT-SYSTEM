from django.db import models
from django.contrib.auth.models import User
from projects.models import Project

class Sprint(models.Model):
    """Sprint entity grouping tasks into distinct intervals of work"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='sprints')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    class Meta:
        ordering = ['-start_date']


class Task(models.Model):
    """Task entity representing a block of work, issue, or feature request"""
    STATUS_CHOICES = (
        ('To Do', 'To Do'),
        ('In Progress', 'In Progress'),
        ('Review', 'Review'),
        ('Blocked', 'Blocked'),
        ('Done', 'Done'),
    )

    PRIORITY_CHOICES = (
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    )

    TYPE_CHOICES = (
        ('User Story', 'User Story'),
        ('Task', 'Task'),
        ('Bug', 'Bug'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks')
    sprint = models.ForeignKey(Sprint, on_delete=models.SET_NULL, null=True, blank=True, related_name='tasks')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='To Do')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium')
    task_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Task')
    assignee = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reported_tasks')
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    logged_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"#{self.id}: {self.title}"

    class Meta:
        ordering = ['-priority', 'due_date']


class TaskDependency(models.Model):
    """Specifies dependencies between tasks, e.g. blocking or blocked by"""
    DEPENDENCY_CHOICES = (
        ('blocked_by', 'Blocked By'),
        ('blocks', 'Blocks'),
    )

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependencies')
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='dependent_on_me')
    dependency_type = models.CharField(max_length=30, choices=DEPENDENCY_CHOICES, default='blocked_by')

    def __str__(self):
        return f"{self.task.title} {self.dependency_type} {self.depends_on.title}"

    class Meta:
        unique_together = ('task', 'depends_on')


class Comment(models.Model):
    """Discussion comments on a specific task"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on #{self.task.id}"

    class Meta:
        ordering = ['created_at']


class Attachment(models.Model):
    """File attachments uploaded for a specific task"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_attachments')
    file = models.FileField(upload_to='task_attachments/')
    filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filename} for task #{self.task.id}"

    class Meta:
        ordering = ['-uploaded_at']


class ActivityLog(models.Model):
    """Activity Log entity to track major updates in the task management pipeline"""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activities')
    action = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at.strftime('%Y-%m-%d %H:%M')}] {self.user.username if self.user else 'System'}: {self.action}"

    class Meta:
        ordering = ['-created_at']
