from django.urls import path
from . import views, views_dashboard

urlpatterns = [
    # Telemetry
    path('heartbeat/', views.study_heartbeat, name='study_heartbeat'),
    # Dashboard
    path('dashboard/', views_dashboard.analytics_dashboard, name='gamification_dashboard'),
]
