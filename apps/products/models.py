from django.db import models
from django.conf import settings
from apps.academics.models import Subject

class ProductCategory(models.Model):
    name = models.CharField(max_length=100, help_text="e.g., PYQ Solutions, Chapter Notes")
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name_plural = "Product Categories"

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=200, help_text="e.g., Physics Complete PYQ Solutions")
    base_price = models.DecimalField(max_digits=8, decimal_places=2)
    discounted_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.subject.code}"

class SubscriptionPlan(models.Model):
    PLAN_TYPES = (
        ('SEMESTER', 'Semester Pass'),
        ('MONTHLY', 'Monthly Pass'),
        ('YEARLY', 'Year Pass'),
    )
    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"

class Purchase(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    subscription = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2)
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Purchase {self.id} by {self.user.username}"

class UnlockedContent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='unlocked_contents')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    valid_until = models.DateField(null=True, blank=True, help_text="Null means permanent access until RGPV exam.")

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"
