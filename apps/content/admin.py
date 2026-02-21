from django.contrib import admin
from django import forms
from .models import ParsedDocument, DocumentImage
from apps.academics.models import Subject, Branch

from django.http import HttpResponseRedirect
from django.contrib import messages
from .services.ai_parser import DocumentParserService
from .tasks import process_document_ai

class DocumentImageInline(admin.TabularInline):
    model = DocumentImage
    extra = 1

class ParsedDocumentAdminForm(forms.ModelForm):
    subject_code = forms.ChoiceField(
        choices=[], 
        required=True, 
        help_text="Step 1: Select the base subject (e.g. BT-201 - Engineering Physics)"
    )
    apply_to_all_branches = forms.BooleanField(
        required=False, 
        initial=True, 
        help_text="Step 2: If checked, this document will be natively available to ALL branches that share this subject."
    )
    specific_branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="If NOT applying to all branches, select the specific ones here."
    )

    class Meta:
        model = ParsedDocument
        fields = '__all__'
        exclude = ('subjects',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unique_subjects = Subject.objects.values_list('code', 'name').distinct()
        choices = [(f"{code}::{name}", f"{code} - {name}") for code, name in unique_subjects]
        self.fields['subject_code'].choices = [('', '---------')] + sorted(choices, key=lambda x: x[1])

        if self.instance and self.instance.pk:
            subjects = self.instance.subjects.all()
            if subjects.exists():
                first_sub = subjects.first()
                self.initial['subject_code'] = f"{first_sub.code}::{first_sub.name}"
                
                subject_branches = set(s.branch_id for s in subjects)
                all_possible_branches = set(Subject.objects.filter(code=first_sub.code).values_list('branch_id', flat=True))
                
                if subject_branches == all_possible_branches:
                    self.initial['apply_to_all_branches'] = True
                else:
                    self.initial['apply_to_all_branches'] = False
                    self.initial['specific_branches'] = Branch.objects.filter(id__in=subject_branches)

    def clean(self):
        cleaned_data = super().clean()
        subject_code_val = cleaned_data.get('subject_code')
        apply_to_all = cleaned_data.get('apply_to_all_branches')
        specific_branches = cleaned_data.get('specific_branches')

        if subject_code_val:
            code, name = subject_code_val.split('::', 1)
            matching_subjects = Subject.objects.filter(code=code)
            
            if not apply_to_all:
                if not specific_branches:
                    raise forms.ValidationError("You must select 'Apply to all branches' or pick specific branches.")
                matching_subjects = matching_subjects.filter(branch__in=specific_branches)
                
            if not matching_subjects.exists():
                raise forms.ValidationError("No subjects found for the selected code and branch combination in the database.")
            
            cleaned_data['matching_subjects'] = matching_subjects
        
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        matching_subjects = self.cleaned_data.get('matching_subjects', [])
        
        if commit:
            instance.save()
            instance.subjects.set(matching_subjects)
            self.save_m2m()
        else:
            old_save_m2m = self.save_m2m
            def save_m2m():
                old_save_m2m()
                instance.subjects.set(matching_subjects)
            self.save_m2m = save_m2m
            
        return instance

@admin.register(ParsedDocument)
class ParsedDocumentAdmin(admin.ModelAdmin):
    form = ParsedDocumentAdminForm
    change_form_template = 'admin/parseddocument_change_form.html'
    inlines = [DocumentImageInline]
    list_display = ('title', 'display_subjects', 'document_type', 'parsing_status', 'is_premium', 'is_published', 'updated_at')
    list_filter = ('parsing_status', 'is_published', 'is_premium', 'document_type', 'subjects__branch')
    search_fields = ('title', 'subjects__code')
    readonly_fields = ('parsing_status',)
    
    fieldsets = (
        ('Target Subject & Branches', {
            'fields': ('subject_code', 'apply_to_all_branches', 'specific_branches'),
            'description': 'Select which subject and branches this Document applies to.'
        }),
        ('Basic Information', {
            'fields': ('document_type', 'title', 'year', 'is_published')
        }),
        ('Pricing & Access', {
            'fields': ('is_premium', 'price'),
            'description': 'Configure if this document is free, requires a subscription, or has a specific unlock price.'
        }),
        ('AI Data Sources (Fill at least one)', {
            'fields': ('source_file', 'source_text'),
            'description': 'Upload a massive PDF OR paste raw text. You can also upload screenshots in the Images section below.'
        }),
        ('AI Configuration', {
            'fields': ('system_prompt',),
            'classes': ('collapse',)
        }),
        ('Generated Struct Data (Editable Preview)', {
            'fields': ('structured_data',),
        }),
    )

    class Media:
        js = ('js/admin_parsed_document.js',)
    
    def display_subjects(self, obj):
        return ", ".join([s.code for s in obj.subjects.all()])
    display_subjects.short_description = 'Subjects'

    def response_change(self, request, obj):
        if "_parse_ai" in request.POST:
            if obj.parsing_status == 'PROCESSING':
                self.message_user(request, "This document is already being parsed. Please wait for it to complete.", messages.WARNING)
                return HttpResponseRedirect(".")

            # Set status to PENDING before starting the task
            obj.parsing_status = 'PENDING'
            obj.save(update_fields=['parsing_status'])
            
            # Start the background task
            process_document_ai.delay(obj.id)
            
            self.message_user(request, "AI Parsing started in the background. Please refresh in a few minutes to see results.")
            return HttpResponseRedirect(".")
        return super().response_change(request, obj)
