from django.urls import path
from . import views

urlpatterns = [
    path('checkout/document/<int:document_id>/', views.checkout_document, name='checkout_document'),
    path('checkout/verify/', views.payment_verify, name='payment_verify'),
]
