"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.notifications import views as views_notifications

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.content.urls')),
    path('', include('apps.users.urls')),
    path('payments/', include('apps.products.urls')),
    path('api/gamification/', include('apps.gamification.urls')),
    path('practice/', include('apps.practice.urls')),
    path('notifications/', include('apps.notifications.urls')),
    path('webpush/', include('webpush.urls')),
    path('webpush/vapid/', views_notifications.vapid_config, name='vapid_config'),
    path('sw.js', views_notifications.service_worker, name='service_worker'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
