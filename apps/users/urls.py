from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('change-program/', views.change_program_view, name='change_program'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('purchases/', views.user_purchases, name='user_purchases'),
    path('clerk-sync/', views.clerk_sync_view, name='clerk_sync'),
]
