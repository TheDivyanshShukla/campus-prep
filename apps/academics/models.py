from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Computer Science & Engineering")
    code = models.CharField(max_length=20, unique=True, help_text="e.g., CSE")
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Branches"

    def __str__(self):
        return f"{self.name} ({self.code})"

class Semester(models.Model):
    number = models.PositiveSmallIntegerField(unique=True, help_text="1 to 8")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Semester {self.number}"

class Subject(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='subjects')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='subjects')
    code = models.CharField(max_length=20, help_text="e.g., CS-402")
    name = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'semester', 'code')

    def __str__(self):
        return f"[{self.branch.code} Sem {self.semester.number}] {self.code} - {self.name}"

class Unit(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='units')
    number = models.PositiveSmallIntegerField(help_text="Unit number (usually 1-5)")
    name = models.CharField(max_length=1000)
    description = models.TextField(blank=True)
    topics = models.JSONField(default=list, blank=True, help_text="List of topics for this unit, synced from syllabus.")

    class Meta:
        unique_together = ('subject', 'number')
        ordering = ['number']

    def __str__(self):
        return f"Unit {self.number}: {self.name}"

class ExamDate(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    date = models.DateField(help_text="Date when this semester's exams finish. Triggers auto-expiry.")

    class Meta:
        unique_together = ('branch', 'semester')

    def __str__(self):
        return f"{self.branch.code} Sem {self.semester.number} - {self.date} "

class SubjectAnalytics(models.Model):
    subject = models.OneToOneField(Subject, on_delete=models.CASCADE, related_name='analytics')
    
    # Updated every time a new PYQ is added and parsed, or via command
    last_computed_at = models.DateTimeField(auto_now=True)
    
    # High-level scores (Fast querying)
    predictability_score = models.FloatField(default=0.0, help_text="0.0 to 100.0, e.g., 78.5%")
    total_papers_analyzed = models.PositiveIntegerField(default=0, help_text="How many PYQs were used to generate this data.")
    
    # Pre-computed JSON for immediate Frontend Visualization (Zero processing on GET)
    unit_roi_data = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Format: { '1': {'avg_marks': 14, 'efficiency': 'High', 'name': '...'} }"
    )
    
    syllabus_heatmap = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Format: { 'Topic Name': {'frequency': 4, 'years': [2019, 2021, 2022, 2023], 'unit': 1} }"
    )
    
    complexity_breakdown = models.JSONField(
        default=dict, 
        blank=True,
        help_text="Format: { 'Theory': 45, 'Numerical': 30, 'Derivation': 25 }"
    )
    
    # List of top repeating questions mapped to topics
    top_repeated_questions = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of objects: [{'text': '...', 'occurrences': 5, 'years': [2021, 2023]}]"
    )

    class Meta:
        verbose_name_plural = "Subject Analytics"

    def __str__(self):
        return f"Analytics Snapshot for {self.subject.code}"
