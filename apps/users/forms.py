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
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        empty_label="Select your Branch",
        required=True,
        widget=forms.Select(attrs={'data-premium-select': 'true'})
    )
    semester = forms.ModelChoiceField(
        queryset=Semester.objects.all(),
        empty_label="Select your Semester",
        required=True,
        widget=forms.Select(attrs={'data-premium-select': 'true'})
    )

    class Meta:
        model = User
        fields = [] # We handle these manually in the view for precise assignment
