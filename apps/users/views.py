from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from apps.content.data_services import ContentDataService
from apps.products.data_services import ProductDataService
from apps.common.turnstile import turnstile_service


@login_required
@ensure_csrf_cookie
def onboarding_view(request):
    """
    Lets the user fill in their profile details and choose Branch / Semester.
    """
    from .forms import UserOnboardingForm
    user = request.user

    if request.method == 'POST':
        form = UserOnboardingForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save(commit=False)
            user.preferred_branch = form.cleaned_data['branch']
            user.preferred_semester = form.cleaned_data['semester']
            user.save()
            return redirect('dashboard')
    else:
        initial_data = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
        }
        if user.preferred_branch:
            initial_data['branch'] = user.preferred_branch
        if user.preferred_semester:
            initial_data['semester'] = user.preferred_semester
        form = UserOnboardingForm(initial=initial_data, instance=user)

    return render(request, 'users/onboarding.html', {'form': form})


@login_required
def change_program_view(request):
    from .forms import ChangeProgramForm
    user = request.user

    if request.method == 'POST':
        form = ChangeProgramForm(request.POST, instance=user)
        if form.is_valid():
            user.preferred_branch = form.cleaned_data['branch']
            user.preferred_semester = form.cleaned_data['semester']
            user.save()
            return redirect('dashboard')
    else:
        initial_data = {}
        if user.preferred_branch:
            initial_data['branch'] = user.preferred_branch
        if user.preferred_semester:
            initial_data['semester'] = user.preferred_semester
        form = ChangeProgramForm(initial=initial_data, instance=user)

    return render(request, 'users/change_program.html', {'form': form})


@login_required
def user_dashboard(request):
    """Personalized dashboard: redirects to onboarding if profile is incomplete."""
    user = request.user

    if not (user.first_name and user.last_name and user.phone_number
            and user.preferred_branch and user.preferred_semester):
        return redirect('onboarding')

    subjects = ContentDataService.get_subjects_by_branch_and_semester(
        user.preferred_branch,
        user.preferred_semester
    )

    return render(request, 'users/dashboard.html', {
        'subjects': subjects,
        'user_branch': user.preferred_branch,
        'user_sem': user.preferred_semester
    })


@login_required
def user_purchases(request):
    """Displays the user’s unlocked premium content and purchase history."""
    active_unlocks, expired_unlocks = ProductDataService.get_all_unlocks(request.user)

    return render(request, 'users/purchases.html', {
        'active_unlocks': active_unlocks,
        'expired_unlocks': expired_unlocks,
    })


@csrf_exempt
@require_http_methods(["POST"])
def verify_turnstile_api(request):
    """
    API endpoint to verify Turnstile tokens.
    
    Expected POST data: { "token": "..." }
    Returns: { "success": bool, "message": str }
    """
    import json
    
    try:
        data = json.loads(request.body)
        token = data.get('token', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({
            'success': False,
            'message': 'Invalid request body'
        }, status=400)
    
    # Get client IP for Turnstile verification
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR')
    
    is_valid, message = turnstile_service.verify_token(token, client_ip)
    
    return JsonResponse({
        'success': is_valid,
        'message': message
    })


