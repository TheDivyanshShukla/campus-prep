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


@login_required
def checkout_gold_pass(request):
    from apps.academics.models import Branch, Semester
    from apps.products.models import SubscriptionPlan
    
    branch_id = request.GET.get('branch')
    semester_id = request.GET.get('semester')
    
    if not branch_id or not semester_id:
        return redirect('home')
        
    branch = get_object_or_404(Branch, id=branch_id)
    semester = get_object_or_404(Semester, id=semester_id)
    
    # Check if a SEMESTER plan exists
    try:
        plan = SubscriptionPlan.objects.get(plan_type='SEMESTER', is_active=True)
    except SubscriptionPlan.DoesNotExist:
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
    Purchase.objects.create(
        user=request.user,
        subscription=plan,
        amount_paid=plan.price,
        razorpay_order_id=razorpay_order['id'],
        status='PENDING'
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
            if purchase.parsed_document:
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
                
            elif purchase.subscription:
                # Gold Pass purchase
                from apps.academics.models import Branch, Semester
                branch_id = request.session.get('pending_gold_pass_branch')
                semester_id = request.session.get('pending_gold_pass_semester')
                
                if branch_id and semester_id:
                    branch = Branch.objects.get(id=branch_id)
                    semester = Semester.objects.get(id=semester_id)
                    
                    purchase.user.gold_pass_branch = branch
                    purchase.user.gold_pass_semester = semester
                    purchase.user.active_subscription_plan = purchase.subscription
                    
                    valid_until_date = None
                    try:
                        exam = ExamDate.objects.get(branch=branch, semester=semester)
                        valid_until_date = exam.date
                    except ExamDate.DoesNotExist:
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
    from .models import Coupon
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '').upper().strip()
            original_price = float(data.get('price', 0))
            
            try:
                coupon = Coupon.objects.get(code=code)
            except Coupon.DoesNotExist:
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
    from .models import Coupon, SubscriptionPlan, Purchase, UnlockedContent
    from apps.academics.models import Branch, Semester, ExamDate
    from apps.content.models import ParsedDocument
    
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            code = data.get('code', '').upper().strip()
            item_type = data.get('item_type') # 'document' or 'gold_pass'
            item_id = data.get('item_id')
            
            # Verify Coupon is valid and actually 100% off
            try:
                coupon = Coupon.objects.get(code=code)
                if not coupon.is_valid() or coupon.discount_percentage != 100:
                    return JsonResponse({"success": False, "message": "Coupon invalid or not 100% free."})
            except Coupon.DoesNotExist:
                return JsonResponse({"success": False, "message": "Invalid coupon code."})
                
            if item_type == 'document':
                document = get_object_or_404(ParsedDocument, id=item_id)
                purchase = Purchase.objects.create(
                    user=request.user,
                    parsed_document=document,
                    amount_paid=0.00,
                    status='SUCCESS'
                )
                
                # Check for document.subjects.first() instead of document.subject
                subject = document.subjects.first()
                valid_until_date = None
                if subject:
                    try:
                        exam = ExamDate.objects.get(branch=subject.branch, semester=subject.semester)
                        valid_until_date = exam.date
                    except ExamDate.DoesNotExist:
                        valid_until_date = timezone.now().date() + timedelta(days=180)
                else:
                    valid_until_date = timezone.now().date() + timedelta(days=180)

                UnlockedContent.objects.get_or_create(
                    user=request.user,
                    parsed_document=document,
                    defaults={'valid_until': valid_until_date}
                )
                coupon.current_uses += 1
                coupon.save()
                return JsonResponse({"success": True, "redirect_url": reverse('read_document', args=[document.id])})
                
            elif item_type == 'gold_pass':
                branch_id = data.get('branch_id')
                semester_id = data.get('semester_id')
                plan = get_object_or_404(SubscriptionPlan, id=item_id)
                branch = get_object_or_404(Branch, id=branch_id)
                semester = get_object_or_404(Semester, id=semester_id)
                
                purchase = Purchase.objects.create(
                    user=request.user,
                    subscription=plan,
                    amount_paid=0.00,
                    status='SUCCESS'
                )
                
                request.user.gold_pass_branch = branch
                request.user.gold_pass_semester = semester
                request.user.active_subscription_plan = plan
                
                valid_until_date = None
                try:
                    exam = ExamDate.objects.get(branch=branch, semester=semester)
                    valid_until_date = exam.date
                except ExamDate.DoesNotExist:
                    valid_until_date = timezone.now().date() + timedelta(days=180)
                    
                request.user.active_subscription_valid_until = valid_until_date
                request.user.save()
                coupon.current_uses += 1
                coupon.save()
                return JsonResponse({"success": True, "redirect_url": "/"}) # Dashboard isn't strictly defined, fallback to root
                
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
            
    return JsonResponse({"success": False, "message": "Invalid request."})
