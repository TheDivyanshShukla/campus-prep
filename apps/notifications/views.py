from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, FileResponse
import os
from django.conf import settings
from .models import Notification
from .data_services import NotificationDataService

@login_required
def notification_list(request):
    notifications = NotificationDataService.get_user_notifications(request.user)
    return render(request, 'notifications/list.html', {'notifications': notifications})

@login_required
def mark_as_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.is_read = True
    notification.save()
    NotificationDataService.clear_user_notification_cache(request.user)
    response = HttpResponse("")
    # Signal the navbar to update the unread count badge
    response['HX-Trigger'] = 'notifications-updated'
    return response

@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    NotificationDataService.clear_user_notification_cache(request.user)
    response = HttpResponse("")
    response['HX-Refresh'] = 'true'
    response['HX-Trigger'] = 'notifications-updated'
    return response

@login_required
def unread_count(request):
    count = NotificationDataService.get_unread_count(request.user)
    return render(request, 'notifications/partials/unread_count.html', {'count': count})

@login_required
def vapid_config(request):
    from django.http import JsonResponse
    return JsonResponse({
        'publicKey': settings.WEBPUSH_SETTINGS.get('VAPID_PUBLIC_KEY')
    })

def service_worker(request):
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
    # Use a short cache for the service worker (e.g., 1 hour)
    # Browsers will still check for updates, but this avoids redundant fetches during a session
    response['Cache-Control'] = 'public, max-age=3600'
    return response
