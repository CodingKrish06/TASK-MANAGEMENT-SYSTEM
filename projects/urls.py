from django.urls import path
from . import views

urlpatterns = [
    path('', views.project_list, name='project_list'),
    path('create/', views.project_create, name='project_create'),
    path('setup/', views.project_setup, name='project_setup'),
    path('setup/members/', views.project_setup_members, name='project_setup_members'),
    path('<int:project_id>/', views.project_detail, name='project_detail'),
    path('<int:project_id>/edit/', views.project_edit, name='project_edit'),
    path('<int:project_id>/delete/', views.project_delete, name='project_delete'),
    path('<int:project_id>/members/', views.project_members, name='project_members'),
    path('<int:project_id>/members/add/', views.add_project_member, name='add_project_member'),
    path('members/remove/<int:member_id>/', views.remove_project_member, name='remove_project_member'),
    
    # Global Team Members Management
    path('team-members/', views.global_team_members, name='global_team_members'),
    path('team-members/add/', views.global_team_member_add, name='global_team_member_add'),
    path('team-members/<int:user_id>/edit/', views.global_team_member_edit, name='global_team_member_edit'),
    path('team-members/<int:user_id>/delete/', views.global_team_member_delete, name='global_team_member_delete'),
]
