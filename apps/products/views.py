from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from apps.content.models import ParsedDocument
from .data_services import ProductDataService
from apps.academics.data_services import AcademicsDataService
from apps.content.data_services import ContentDataService
import razorpay

# Initialize Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

@login_required
def checkout_document(request, document_id):
    document = ContentDataService.get_document_by_id(document_id)
    if not document:
        return redirect('home')
    
    # Block totally free documents
    if not document.is_premium or not document.price:
        return redirect('subject_dashboard', subject_id=document.subjects.first().id)

    # Has the user already bought it?
    if ProductDataService.user_has_unlocked_document(request.user, document):
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
    ProductDataService.create_purchase(
        request.user,
        document=document,
        amount=document.price,
        razorpay_order_id=razorpay_order['id'],
        status='PENDING',
    )

    context = {
        'document': document,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': razorpay_order['id'],
        'amount': amount_in_paise,
    }
    return render(request, 'products/checkout.html', context)


@login_required
def checkout_gold_pass(request):
    from apps.products.models import SubscriptionPlan

    branch_id = request.GET.get('branch')
    semester_id = request.GET.get('semester')

    if not branch_id or not semester_id:
        return redirect('home')

    branch = AcademicsDataService.get_branch_by_id(branch_id)
    semester = AcademicsDataService.get_semester_by_id(semester_id)

    if not branch or not semester:
        return redirect('home')

    # Check if a SEMESTER plan exists
    plan = ProductDataService.get_active_semester_plan()
    if not plan:
        return render(request, 'products/payment_error.html', {'error': 'Gold Pass is not currently available.'})
        
    # Check if user already has an active Gold Pass for this exact branch/sem
    if request.user.has_gold_pass() and request.user.gold_pass_branch == branch and request.user.gold_pass_semester == semester:
        return redirect('dashboard')
        
    amount_in_paise = int(plan.price * 100)
    data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "receipt": f"receipt_gold_{plan.id}_{request.user.id}",
        "payment_capture": "1"
    }

    try:
        razorpay_order = client.order.create(data=data)
    except Exception as e:
        return render(request, 'products/payment_error.html', {'error': str(e)})

    # Create a pending Purchase record
    ProductDataService.create_purchase(
        request.user,
        subscription=plan,
        amount=plan.price,
        razorpay_order_id=razorpay_order['id'],
        status='PENDING',
    )
    
    # Store branch/sem in session for post-payment verification
    request.session['pending_gold_pass_branch'] = branch.id
    request.session['pending_gold_pass_semester'] = semester.id

    context = {
        'plan': plan,
        'branch': branch,
        'semester': semester,
        'razorpay_key_id': settings.RAZORPAY_KEY_ID,
        'order_id': razorpay_order['id'],
        'amount': amount_in_paise,
    }
    return render(request, 'products/checkout_gold_pass.html', context)


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
        purchase = ProductDataService.get_purchase_by_order_id(razorpay_order_id)
        if not purchase:
            return render(request, 'products/payment_error.html', {'error': 'Order not found.'})

        try:
            # Verify the payment signature through razorpay SDK
            client.utility.verify_payment_signature(params_dict)
            
            # If successful, mark as SUCCESS
            purchase.status = 'SUCCESS'
            purchase.razorpay_payment_id = payment_id
            purchase.save()

            # Calculate the validity based on the Exam Date for this branch + semester
            if purchase.parsed_document:
                subject = purchase.parsed_document.subjects.first()
                valid_until_date = None
                if subject:
                    exam = AcademicsDataService.get_exam_date(subject.branch, subject.semester)
                    if exam:
                        valid_until_date = exam.date
                
                if not valid_until_date:
                    # If no ExamDate configured, default to 6 months from purchase
                    valid_until_date = timezone.now().date() + timedelta(days=180)

                # Unlock the content for the user until the exam date
                ProductDataService.unlock_document_for_user(
                    purchase.user, purchase.parsed_document, valid_until_date
                )

                # Route them right into the document reader they just bought
                return redirect('read_document', document_id=purchase.parsed_document.id)
                
            elif purchase.subscription:
                # Gold Pass purchase
                branch_id = request.session.get('pending_gold_pass_branch')
                semester_id = request.session.get('pending_gold_pass_semester')
                
                if branch_id and semester_id:
                    branch = AcademicsDataService.get_branch_by_id(branch_id)
                    semester = AcademicsDataService.get_semester_by_id(semester_id)
                    
                    purchase.user.gold_pass_branch = branch
                    purchase.user.gold_pass_semester = semester
                    purchase.user.active_subscription_plan = purchase.subscription
                    
                    valid_until_date = None
                    exam = AcademicsDataService.get_exam_date(branch, semester)
                    if exam:
                        valid_until_date = exam.date
                    
                    if not valid_until_date:
                        valid_until_date = timezone.now().date() + timedelta(days=180)
                        
                    purchase.user.active_subscription_valid_until = valid_until_date
                    purchase.user.save()
                    
                    # Clean up session
                    del request.session['pending_gold_pass_branch']
                    del request.session['pending_gold_pass_semester']
                
                return redirect('dashboard')
            
        except razorpay.errors.SignatureVerificationError:
            purchase.status = 'FAILED'
            purchase.save()
            return render(request, 'products/payment_error.html', {'error': 'Payment Verification Failed'})

    return redirect('home')

@csrf_exempt
def validate_coupon(request):
    import json
    from django.http import JsonResponse
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '').upper().strip()
            original_price = float(data.get('price', 0))

            coupon = ProductDataService.get_coupon_by_code(code)
            if not coupon:
                return JsonResponse({"valid": False, "message": "Invalid coupon code."})
                
            if not coupon.is_valid():
                return JsonResponse({"valid": False, "message": "Coupon expired or usage limit reached."})
                
            discount_amount = original_price * (coupon.discount_percentage / 100.0)
            new_price = max(0, original_price - discount_amount)
            
            return JsonResponse({
                "valid": True,
                "discount_percentage": coupon.discount_percentage,
                "new_price": round(new_price, 2)
            })
            
        except Exception as e:
            return JsonResponse({"valid": False, "message": str(e)})
            
    return JsonResponse({"valid": False, "message": "Invalid req."})

@login_required
@csrf_exempt
def process_free_checkout(request):
    import json
    from django.http import JsonResponse
    from django.urls import reverse
    from .models import SubscriptionPlan
    from apps.content.models import ParsedDocument

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '').upper().strip()
            item_type = data.get('item_type') # 'document' or 'gold_pass'
            item_id = data.get('item_id')

            # Verify Coupon is valid and actually 100% off
            coupon = ProductDataService.get_coupon_by_code(code)
            if not coupon or not coupon.is_valid() or coupon.discount_percentage != 100:
                return JsonResponse({"success": False, "message": "Coupon invalid or not 100% free."})
                
            if item_type == 'document':
                document = get_object_or_404(ParsedDocument, id=item_id)
                ProductDataService.create_purchase(
                    request.user,
                    document=document,
                    amount=0.00,
                    status='SUCCESS',
                )
                
                # Check for document.subjects.first() instead of document.subject
                subject = document.subjects.first()
                valid_until_date = None
                if subject:
                    exam = AcademicsDataService.get_exam_date(subject.branch, subject.semester)
                    if exam:
                        valid_until_date = exam.date
                    
                    if not valid_until_date:
                        valid_until_date = timezone.now().date() + timedelta(days=180)
                else:
                    valid_until_date = timezone.now().date() + timedelta(days=180)

                ProductDataService.unlock_document_for_user(
                    request.user, document, valid_until_date
                )
                coupon.current_uses += 1
                coupon.save()
                return JsonResponse({"success": True, "redirect_url": reverse('read_document', args=[document.id])})
                
            elif item_type == 'gold_pass':
                branch_id = data.get('branch_id')
                semester_id = data.get('semester_id')
                plan = get_object_or_404(SubscriptionPlan, id=item_id)
                branch = AcademicsDataService.get_branch_by_id(branch_id)
                semester = AcademicsDataService.get_semester_by_id(semester_id)
                if not branch or not semester:
                    return JsonResponse({"success": False, "message": "Invalid branch or semester."})

                ProductDataService.create_purchase(
                    request.user,
                    subscription=plan,
                    amount=0.00,
                    status='SUCCESS',
                )
                
                request.user.gold_pass_branch = branch
                request.user.gold_pass_semester = semester
                request.user.active_subscription_plan = plan
                
                valid_until_date = None
                exam = AcademicsDataService.get_exam_date(branch, semester)
                if exam:
                    valid_until_date = exam.date
                
                if not valid_until_date:
                    valid_until_date = timezone.now().date() + timedelta(days=180)
                    
                request.user.active_subscription_valid_until = valid_until_date
                request.user.save()
                coupon.current_uses += 1
                coupon.save()
                return JsonResponse({"success": True, "redirect_url": "/"}) # Dashboard isn't strictly defined, fallback to root
                
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
            
    return JsonResponse({"success": False, "message": "Invalid request."})
