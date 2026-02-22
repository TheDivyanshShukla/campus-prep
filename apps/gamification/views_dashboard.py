from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from .models import GamerProfile, StudySession

@login_required
def analytics_dashboard(request):
    """
    Renders the Gamification Dashboard with XP, Streaks, and Time Tracking charts.
    """
    profile, _ = GamerProfile.objects.get_or_create(user=request.user)
    
    # Calculate Total Study Time (Lifetime)
    total_seconds = StudySession.objects.filter(user=request.user).aggregate(
        total=Sum('duration_seconds')
    )['total'] or 0
    
    total_hours = round(total_seconds / 3600, 1)
    
    # Chart Data: Last 7 Days
    labels = []
    data_points = []
    
    today = timezone.now().date()
    for i in range(6, -1, -1):
        target_date = today - timedelta(days=i)
        
        # Aggregate seconds for that specific day
        daily_seconds = StudySession.objects.filter(
            user=request.user,
            start_time__date=target_date
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        
        daily_minutes = round(daily_seconds / 60)
        
        labels.append(target_date.strftime('%a')) # e.g. "Mon"
        data_points.append(daily_minutes)

    context = {
        'profile': profile,
        'total_hours': total_hours,
        'chart_labels': labels,
        'chart_data': data_points,
        # Determine Progress to Daily Bar (assume 50 min goal = 50 XP)
        'daily_progress': min(100, int((data_points[-1] / max(1, profile.daily_xp_goal)) * 100))
    }
    
    return render(request, 'gamification/user_analytics.html', context)
