import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

from .data_services import GamificationDataService
from apps.content.data_services import ContentDataService
from apps.academics.data_services import AcademicsDataService
from apps.notifications.data_services import NotificationDataService


@csrf_exempt
@login_required
def study_heartbeat(request):
    """
    Called every 60 seconds by the frontend while a user is actively reading a document.
    Streak rule: user must spend at least 5 minutes (300 s) on the platform in a day.
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"})

    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        subject_id = data.get('subject_id')
        active_seconds = int(data.get('active_seconds', 60))

        # ── Resolve entities via cached data-service layer ────────────────
        profile = GamificationDataService.get_user_profile(request.user)

        document = ContentDataService.get_document_by_id(document_id) if document_id else None
        subject = AcademicsDataService.get_subject_by_id(subject_id) if subject_id else None

        # ── Session bookkeeping ───────────────────────────────────────────
        session, _ = GamificationDataService.get_or_create_today_session(
            request.user, document, subject,
        )
        increment = GamificationDataService.record_heartbeat(session, active_seconds)

        # Award 1 XP per minute studied
        if session.duration_seconds % 60 == 0 or increment >= 60:
            profile.add_xp(1)

        # ── Streak evaluation ─────────────────────────────────────────────
        streak_updated = GamificationDataService.evaluate_streak(profile)
        if streak_updated:
            # Reload profile to reflect updated streak values
            GamificationDataService.invalidate_profile_cache(request.user)
            profile = GamificationDataService.get_user_profile(request.user)

            from apps.notifications.services import NotificationService
            NotificationService.notify(
                user=request.user,
                level='success',
                title="Streak Active! 🔥",
                message=f"You're on a {profile.current_streak} day streak! Keep it up.",
                link='/dashboard/',
            )

        unread_notifications = NotificationDataService.get_unread_count(request.user)

        return JsonResponse({
            "success": True,
            "total_session_seconds": session.duration_seconds,
            "total_xp": profile.total_xp,
            "current_streak": profile.current_streak,
            "unread_notifications": unread_notifications,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

