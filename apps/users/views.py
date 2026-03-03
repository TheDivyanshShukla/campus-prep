from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from apps.content.data_services import ContentDataService


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
    all_unlocks = (
        request.user.unlocked_contents
        .select_related('parsed_document')
        .prefetch_related('parsed_document__subjects')
        .all()
        .order_by('-id')
    )

    active_unlocks = []
    expired_unlocks = []
    today = timezone.now().date()

    for unlock in all_unlocks:
        if unlock.parsed_document:
            if unlock.valid_until is None or unlock.valid_until >= today:
                active_unlocks.append(unlock)
            else:
                expired_unlocks.append(unlock)

    return render(request, 'users/purchases.html', {
        'active_unlocks': active_unlocks,
        'expired_unlocks': expired_unlocks
    })


