from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.content.models import ParsedDocument
from apps.products.models import Purchase, UnlockedContent
from apps.academics.models import ExamDate
import razorpay

# Initialize Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def checkout_document(request, document_id):
    document = get_object_or_404(ParsedDocument, id=document_id)
    
    # Block totally free documents
    if not document.is_premium or not document.price:
        return redirect('subject_dashboard', subject_id=document.subject.id)

    # Has the user already bought it?
    if UnlockedContent.objects.filter(user=request.user, parsed_document=document).exists():
        return redirect('read_document', document_id=document.id)

    # Create Razorpay order (amount is in paise)
    amount_in_paise = int(document.price * 100)
    data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"receipt_doc_{document.id}_{request.user.id}",
        "payment_capture": "1"
    }
    
    try:
        razorpay_order = client.order.create(data=data)
    except Exception as e:
        # If API keys are wrong or Razorpay is down
        return render(request, 'products/payment_error.html', {'error': str(e)})

    # Create a pending Purchase record in our database
    Purchase.objects.create(
        user=request.user,
        parsed_document=document,
        amount_paid=document.price,
        razorpay_order_id=razorpay_order['id'],
        status='PENDING'
    )

    context = {
        'document': document,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': razorpay_order['id'],
        'amount': amount_in_paise,
    }
    return render(request, 'products/checkout.html', context)


@csrf_exempt
def payment_verify(request):
    if request.method == "POST":
        payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        signature = request.POST.get('razorpay_signature', '')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }

        # Find the pending purchase
        try:
            purchase = Purchase.objects.get(razorpay_order_id=razorpay_order_id)
        except Purchase.DoesNotExist:
            return render(request, 'products/payment_error.html', {'error': 'Order not found.'})

        try:
            # Verify the payment signature through razorpay SDK
            client.utility.verify_payment_signature(params_dict)
            
            # If successful, mark as SUCCESS
            purchase.status = 'SUCCESS'
            purchase.razorpay_payment_id = payment_id
            purchase.save()

            # Calculate the validity based on the Exam Date for this branch + semester
            subject = purchase.parsed_document.subject
            valid_until_date = None
            try:
                exam = ExamDate.objects.get(branch=subject.branch, semester=subject.semester)
                valid_until_date = exam.date
            except ExamDate.DoesNotExist:
                # If no ExamDate configured, default to 6 months from purchase
                valid_until_date = timezone.now().date() + timedelta(days=180)

            # Unlock the content for the user until the exam date
            unlocked, created = UnlockedContent.objects.get_or_create(
                user=purchase.user,
                parsed_document=purchase.parsed_document,
                defaults={'valid_until': valid_until_date}
            )
            
            # If they already had it (but it was expired), renew the validity
            if not created:
                unlocked.valid_until = valid_until_date
                unlocked.save()

            # Route them right into the document reader they just bought
            return redirect('read_document', document_id=purchase.parsed_document.id)
            
        except razorpay.errors.SignatureVerificationError:
            purchase.status = 'FAILED'
            purchase.save()
            return render(request, 'products/payment_error.html', {'error': 'Payment Verification Failed'})

    return redirect('home')
