from django.contrib import admin
from .models import Branch, Semester, Subject, Unit, ExamDate

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'is_active')
    search_fields = ('code', 'name')

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('number', 'is_active')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'branch', 'semester', 'is_active')
    list_filter = ('branch', 'semester', 'is_active')
    search_fields = ('code', 'name')

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('subject', 'number', 'name')
    list_filter = ('subject',)

@admin.register(ExamDate)
class ExamDateAdmin(admin.ModelAdmin):
    list_display = ('branch', 'semester', 'date')
    list_filter = ('branch', 'semester')
