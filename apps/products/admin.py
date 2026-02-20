from django.contrib import admin
from .models import ProductCategory, Product, SubscriptionPlan, Purchase, UnlockedContent

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'category', 'base_price', 'discounted_price', 'is_active')
    list_filter = ('category', 'subject__branch', 'is_active')
    search_fields = ('name', 'subject__code')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'is_active')
    list_filter = ('plan_type', 'is_active')

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount_paid', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'razorpay_order_id', 'razorpay_payment_id')

@admin.register(UnlockedContent)
class UnlockedContentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'valid_until')
    search_fields = ('user__username', 'product__name')
