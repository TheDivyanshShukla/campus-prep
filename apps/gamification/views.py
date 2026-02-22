import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from .models import StudySession, GamerProfile
from apps.content.models import ParsedDocument
from apps.academics.models import Subject

STREAK_THRESHOLD_SECONDS = 300  # 5 minutes

@csrf_exempt
@login_required
def study_heartbeat(request):
    """
    Called every 60 seconds by the frontend while a user is actively reading a document.
    Streak rule: user must spend at least 5 minutes (300s) on the platform in a day.
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
            today = now.date()
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

            # Prevent abuse: cap increment to 120s max
            increment = min(active_seconds, 120)

            session.duration_seconds += increment
            session.last_ping_time = now
            session.save()

            # Award 1 XP per minute studied
            if session.duration_seconds % 60 == 0 or increment >= 60:
                profile.add_xp(1)

            # ── Streak logic ───────────────────────────────────────────────
            # Only evaluate streak if today's total crosses the 5-min threshold
            # and we haven't already counted today.
            if profile.last_active_date != today:
                # Calculate total study seconds for today across ALL sessions
                today_total_seconds = StudySession.objects.filter(
                    user=request.user,
                    start_time__date=today,
                ).aggregate(total=Sum('duration_seconds'))['total'] or 0

                if today_total_seconds >= STREAK_THRESHOLD_SECONDS:
                    yesterday = today - timedelta(days=1)

                    if profile.last_active_date == yesterday:
                        # Consecutive day — extend streak
                        profile.current_streak += 1
                    else:
                        # Streak broken (gap > 1 day) or very first session
                        profile.current_streak = 1

                    # Update best streak
                    if profile.current_streak > profile.longest_streak:
                        profile.longest_streak = profile.current_streak

                    profile.last_active_date = today
                    profile.save(update_fields=['current_streak', 'longest_streak', 'last_active_date'])

                    # Notify user about streak
                    from apps.notifications.services import NotificationService
                    NotificationService.notify(
                        user=request.user,
                        level='success',
                        title="Streak Active! 🔥",
                        message=f"You're on a {profile.current_streak} day streak! Keep it up.",
                        link='/dashboard/'
                    )

            from apps.notifications.services import NotificationService
            unread_notifications = NotificationService.get_unread_count(request.user)

            return JsonResponse({
                "success": True,
                "total_session_seconds": session.duration_seconds,
                "total_xp": profile.total_xp,
                "current_streak": profile.current_streak,
                "unread_notifications": unread_notifications,
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid method"})

