from django.urls import path
from . import views
urlpatterns = [
    path('checkout/document/<int:document_id>/', views.checkout_document, name='checkout_document'),
    path('checkout/gold-pass/', views.checkout_gold_pass, name='checkout_gold_pass'),
    path('checkout/validate-coupon/', views.validate_coupon, name='validate_coupon'),
    path('checkout/apply-free/', views.process_free_checkout, name='process_free_checkout'),
    path('checkout/verify/', views.payment_verify, name='payment_verify'),
]
