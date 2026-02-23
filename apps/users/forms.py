from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from apps.academics.models import Branch, Semester
from .models import User

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

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
