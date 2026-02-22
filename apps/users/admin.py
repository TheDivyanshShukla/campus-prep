from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('CampusPrep Details', {'fields': ('phone_number', 'preferred_branch', 'preferred_semester', 'active_subscription_valid_until')}),
    )
    list_display = ('username', 'email', 'phone_number', 'preferred_branch', 'preferred_semester', 'is_staff')
    list_filter = UserAdmin.list_filter + ('preferred_branch', 'preferred_semester')
