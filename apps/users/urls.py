from django.urls import path
from django.views.generic.base import RedirectView
from . import views

urlpatterns = [
    # Auth redirects — keep URL names so every {% url 'login' %} still works
    path('login/', RedirectView.as_view(url='/accounts/login/', permanent=False), name='login'),
    path('signup/', RedirectView.as_view(url='/accounts/signup/', permanent=False), name='signup'),
    path('logout/', RedirectView.as_view(url='/accounts/logout/', permanent=False), name='logout'),

    # App views
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('change-program/', views.change_program_view, name='change_program'),
    path('dashboard/', views.user_dashboard, name='dashboard'),
    path('purchases/', views.user_purchases, name='user_purchases'),
]
