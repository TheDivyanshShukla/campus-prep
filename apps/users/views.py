from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.academics.models import Subject
from .forms import CustomUserCreationForm, UserOnboardingForm

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

@login_required
def onboarding_view(request):
    """
    Allows the user to select or change their preferred Branch and Semester.
    """
    user = request.user
        
    if request.method == 'POST':
        form = UserOnboardingForm(request.POST)
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
            
        form = UserOnboardingForm(initial=initial_data)
        
    return render(request, 'users/onboarding.html', {'form': form})

@login_required
def user_dashboard(request):
    """
    The personalized student dashboard showing subjects for their selected branch and semester.
    """
    user = request.user
    
    if not user.preferred_branch or not user.preferred_semester:
        return redirect('onboarding')
        
    subjects = Subject.objects.filter(
        branch=user.preferred_branch,
        semester=user.preferred_semester
    ).order_by('code')
    
    
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
