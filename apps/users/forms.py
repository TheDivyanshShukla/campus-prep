from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.conf import settings
from apps.academics.models import Branch, Semester
from apps.common.turnstile import turnstile_service
from .models import User


class TurnstileField(forms.CharField):
    """Custom form field for Turnstile verification."""
    
    def __init__(self, *args, **kwargs):
        kwargs['widget'] = forms.HiddenInput()
        kwargs['required'] = settings.TURNSTILE_ENABLED
        super().__init__(*args, **kwargs)
    
    def clean(self, value):
        """Verify Turnstile token."""
        if not settings.TURNSTILE_ENABLED:
            return value
        
        if not value:
            raise forms.ValidationError("Please complete the Turnstile verification.")
        
        # Verify the token with Turnstile service
        is_valid, message = turnstile_service.verify_token(value)
        if not is_valid:
            raise forms.ValidationError(f"Turnstile verification failed: {message}")
        
        return value


class CustomUserCreationForm(UserCreationForm):
    turnstile_token = TurnstileField(required=settings.TURNSTILE_ENABLED)
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.TURNSTILE_ENABLED:
            # Remove Turnstile field if not enabled
            self.fields.pop('turnstile_token', None)


class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'phone_number', 'preferred_branch', 'preferred_semester')


class UserOnboardingForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label="First Name")
    last_name = forms.CharField(max_length=150, required=True, label="Last Name")
    phone_number = forms.CharField(max_length=15, required=True, label="Phone Number")
    
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label="Select your Branch",
        required=True
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        empty_label="Select your Semester",
        required=True
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']


class ChangeProgramForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label="Select your Branch",
        required=True
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        empty_label="Select your Semester",
        required=True
    )

    class Meta:
        model = User
        fields = [] # We handle branch/semester manually to sync with preferred_branch/preferred_semester
