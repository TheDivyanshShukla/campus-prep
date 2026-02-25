from django.contrib import admin
from .models import ProductCategory, Product, SubscriptionPlan, Purchase, UnlockedContent, Coupon

@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('name',)}
    list_display = ('name', 'slug')
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject', 'category', 'base_price', 'discounted_price', 'is_active')
    list_filter = ('category', 'subject__branch', 'is_active')
    search_fields = ('name', 'subject__code')
    list_select_related = ('subject', 'category')
    autocomplete_fields = ['subject', 'category']
    list_per_page = 20

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'is_active')
    list_filter = ('plan_type', 'is_active')
    search_fields = ('name',)

@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount_paid', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'razorpay_order_id', 'razorpay_payment_id')
    list_select_related = ('user', 'product', 'parsed_document', 'subscription')
    autocomplete_fields = ['user', 'product', 'parsed_document', 'subscription']
    list_per_page = 20
    show_full_result_count = False

@admin.register(UnlockedContent)
class UnlockedContentAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'valid_until')
    search_fields = ('user__username', 'product__name')
    list_select_related = ('user', 'product', 'parsed_document')
    autocomplete_fields = ['user', 'product', 'parsed_document']
    list_per_page = 20
    show_full_result_count = False
    
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'current_uses', 'max_uses', 'is_active')
    list_filter = ('is_active', 'discount_percentage')
    search_fields = ('code',)
