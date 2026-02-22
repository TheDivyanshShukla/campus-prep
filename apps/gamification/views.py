import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from .models import StudySession, GamerProfile
from apps.content.models import ParsedDocument
from apps.academics.models import Subject

@csrf_exempt
@login_required
def study_heartbeat(request):
    """
    Called every 60 seconds by the frontend while a user is actively reading a document.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            document_id = data.get('document_id')
            subject_id = data.get('subject_id')
            active_seconds = int(data.get('active_seconds', 60))
            
            # Ensure GamerProfile exists
            profile, _ = GamerProfile.objects.get_or_create(user=request.user)
            
            # Find the active session for today for this specific document
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            document = None
            if document_id:
                try:
                    document = ParsedDocument.objects.get(id=document_id)
                except ParsedDocument.DoesNotExist:
                    pass
            
            subject = None
            if subject_id:
                try:
                    subject = Subject.objects.get(id=subject_id)
                except Subject.DoesNotExist:
                    pass
            
            session, created = StudySession.objects.get_or_create(
                user=request.user,
                parsed_document=document,
                subject=subject,
                start_time__gte=today_start,
                defaults={'start_time': now, 'last_ping_time': now}
            )
            
            # Prevent abuse (if ping is wildly out of sync, cap to 120s max increment)
            time_since_last_ping = (now - session.last_ping_time).total_seconds()
            increment = min(active_seconds, 120) 
            
            session.duration_seconds += increment
            session.last_ping_time = now
            session.save()
            
            # Award 1 XP per minute studied
            if session.duration_seconds % 60 == 0 or increment >= 60:
                profile.add_xp(1)
                
            return JsonResponse({
                "success": True, 
                "total_session_seconds": session.duration_seconds,
                "total_xp": profile.total_xp
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
            
    return JsonResponse({"success": False, "error": "Invalid method"})
