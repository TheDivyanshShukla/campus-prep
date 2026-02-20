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
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('branch', 'semester', 'code')

    def __str__(self):
        return f"[{self.branch.code} Sem {self.semester.number}] {self.code} - {self.name}"

class Unit(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='units')
    number = models.PositiveSmallIntegerField(help_text="Unit number (usually 1-5)")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

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
        return f"{self.branch.code} Sem {self.semester.number} - {self.date}"
