from django.urls import path
from . import views

urlpatterns = [
    path('board/<int:project_id>/', views.kanban_board, name='kanban_board'),
    path('task/<int:task_id>/', views.task_detail, name='task_detail'),
    path('project/<int:project_id>/task/create/', views.task_create, name='task_create'),
    path('task/<int:task_id>/edit/', views.task_edit, name='task_edit'),
    path('task/<int:task_id>/delete/', views.task_delete, name='task_delete'),
    path('task/<int:task_id>/update-status/', views.update_task_status, name='update_task_status'),
    path('task/<int:task_id>/dependency/add/', views.add_dependency, name='add_dependency'),
    path('dependency/remove/<int:dependency_id>/', views.remove_dependency, name='remove_dependency'),
    path('project/<int:project_id>/sprint/create/', views.sprint_create, name='sprint_create'),
    path('sprint/<int:sprint_id>/toggle/', views.toggle_sprint_status, name='toggle_sprint_status'),
    path('project/<int:project_id>/reports/', views.reports, name='reports'),
    
    # Global Reports and PDF Exports
    path('reports/', views.global_reports, name='global_reports'),
    path('reports/download/', views.download_report_pdf, name='download_report_pdf'),
    
    # Task Calendar
    path('calendar/', views.calendar_view, name='calendar'),
]
