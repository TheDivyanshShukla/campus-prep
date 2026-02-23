from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.utils import timezone
import json
from apps.academics.models import Subject
from .forms import CustomUserCreationForm, UserOnboardingForm, ChangeProgramForm
from .services import ClerkService
from apps.content.data_services import ContentDataService

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'users/signup.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
        
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
        
    return render(request, 'users/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@csrf_exempt
def clerk_sync_view(request):
    """
    Endpoint for Clerk to sync session with Django.
    Expects a JSON payload with 'token' (JWT from Clerk).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        token = data.get('token')
        
        if not token:
            return JsonResponse({'error': 'Token missing'}, status=400)
            
        clerk_user_data = ClerkService.verify_token(token)
        if not clerk_user_data:
            return JsonResponse({'error': 'Invalid token'}, status=401)
            
        user = ClerkService.sync_user(clerk_user_data)
        
        # Only log in if not already authenticated as this user
        # This prevents session rotation which would invalidate CSRF tokens on the current page
        if not request.user.is_authenticated or request.user.clerk_id != user.clerk_id:
            login(request, user)
        
        # Check if onboarding is needed
        needs_onboarding = not (user.first_name and user.last_name and user.phone_number and user.preferred_branch and user.preferred_semester)
        
        return JsonResponse({
            'success': True,
            'redirect_url': '/onboarding/' if needs_onboarding else '/dashboard/'
        })
        
    except Exception as e:
        print(f"Error in clerk_sync_view: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@ensure_csrf_cookie
def onboarding_view(request):
    """
    Allows the user to select or change their preferred Branch and Semester.
    Now also mandates first_name, last_name, and phone_number.
    """
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
    """
    The personalized student dashboard showing subjects for their selected branch and semester.
    """
    user = request.user
    
    if not (user.first_name and user.last_name and user.phone_number and user.preferred_branch and user.preferred_semester):
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
    """
    Displays the user's unlocked premium content and purchase history.
    """
    all_unlocks = request.user.unlocked_contents.select_related('parsed_document').prefetch_related('parsed_document__subjects').all().order_by('-id')
    
    active_unlocks = []
    expired_unlocks = []
    
    today = timezone.now().date()
    
    for unlock in all_unlocks:
        if unlock.parsed_document: # Only show document unlocks for now
            if unlock.valid_until is None or unlock.valid_until >= today:
                active_unlocks.append(unlock)
            else:
                expired_unlocks.append(unlock)
                
    return render(request, 'users/purchases.html', {
        'active_unlocks': active_unlocks,
        'expired_unlocks': expired_unlocks
    })
