"""
URL Configuration for Quiz App
"""
from django.urls import path
from . import views

urlpatterns = [
    # Authentication
    path('', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Document Management
    path('upload/', views.upload_document_view, name='upload_document'),
    path('questions/<int:document_id>/', views.view_questions_view, name='view_questions'),
    
    # Quiz Management
    path('quiz/create/', views.create_quiz_view, name='create_quiz'),
    path('quiz/list/', views.quiz_list_view, name='quiz_list'),
    path('quiz/<int:quiz_id>/', views.quiz_detail_view, name='quiz_detail'),
    
    # Quiz Taking
    path('quiz/<int:quiz_id>/take/', views.take_quiz_view, name='take_quiz'),
    path('quiz/complete/<int:attempt_id>/', views.complete_quiz_view, name='complete_quiz'),
    path('quiz/result/<int:attempt_id>/', views.quiz_result_view, name='quiz_result'),
    
    # Analytics
    path("analytics/", views.analytics_view, name="analytics"),
]