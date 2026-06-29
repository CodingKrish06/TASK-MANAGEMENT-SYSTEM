from django.db import models
from django.contrib.auth.models import User

class Project(models.Model):
    """Project entity representing a workspace of sprints and tasks"""
    STATUS_CHOICES = (
        ('Planning', 'Planning'),
        ('Active', 'Active'),
        ('On Hold', 'On Hold'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def completed_tasks_count(self):
        return self.tasks.filter(status='Done').count()

    @property
    def total_tasks_count(self):
        return self.tasks.count()

    class Meta:
        ordering = ['-created_at']


class ProjectMember(models.Model):
    """Many-to-many relationship mapping users to projects with custom project roles"""
    ROLE_CHOICES = (
        ('Administrator', 'Administrator'),
        ('Project Manager', 'Project Manager'),
        ('Team Member', 'Team Member'),
    )

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_memberships')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='Team Member')
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.project.name} ({self.role})"

    class Meta:
        unique_together = ('project', 'user')
        ordering = ['joined_at']
