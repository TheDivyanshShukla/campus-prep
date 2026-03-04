(function () {
    'use strict';

    var dataEl = document.getElementById('checkout-data');
    if (!dataEl) return;
    var config = JSON.parse(dataEl.textContent);

    var options = {
        key: config.razorpayKeyId,
        amount: String(config.amount),
        currency: 'INR',
        name: 'CampusPrep',
        description: config.description,
        image: 'https://avataaars.io/?avatarStyle=Circle&topType=ShortHairShortFlat&accessoriesType=Blank&hairColor=Black&facialHairType=Blank&clotheType=Hoodie&clotheColor=Black&eyeType=Happy&eyebrowType=Default&mouthType=Smile&skinColor=Light',
        order_id: config.orderId,
        handler: function (response) {
            document.getElementById('razorpay_payment_id').value = response.razorpay_payment_id;
            document.getElementById('razorpay_order_id').value = response.razorpay_order_id;
            document.getElementById('razorpay_signature').value = response.razorpay_signature;
            document.getElementById('razorpay-form').submit();
        },
        prefill: {
            name: config.userName,
            email: config.userEmail
        },
        theme: {
            color: '#f59e0b'
        }
    };

    var rzp1 = new Razorpay(options);

    rzp1.on('payment.failed', function (response) {
        alert('Payment Failed: ' + response.error.description);
    });

    document.getElementById('rzp-button1').onclick = function (e) {
        rzp1.open();
        e.preventDefault();
    };

    // --- Coupon Logic ---
    var currentAmountPaise = parseInt(config.amount);
    var basePriceFloat = parseFloat(config.basePrice);
    var activeCoupon = null;

    document.getElementById('apply_coupon_btn').onclick = function () {
        var code = document.getElementById('coupon_input').value.trim();
        var msgEl = document.getElementById('coupon_msg');
        var rzpBtn = document.getElementById('rzp-button1');
        var btn = this;

        if (!code) return;

        btn.innerHTML = '<svg class="animate-spin h-5 w-5 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';

        fetch(config.validateCouponUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, price: basePriceFloat })
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                btn.innerHTML = 'Apply';
                msgEl.classList.remove('hidden');

                if (data.valid) {
                    activeCoupon = code;
                    msgEl.className = 'text-xs mt-2 text-emerald-500 font-medium';
                    msgEl.innerText = '\u2713 Coupon applied! ' + data.discount_percentage + '% off.';

                    document.getElementById('original_price_display').classList.remove('hidden');
                    document.getElementById('final_price_display').innerText = '\u20B9' + data.new_price.toFixed(2);

                    currentAmountPaise = Math.round(data.new_price * 100);
                    options.amount = currentAmountPaise;
                    rzp1 = new Razorpay(options);
                    rzp1.on('payment.failed', function (response) {
                        alert('Payment Failed: ' + response.error.description);
                    });

                    // 100% OFF Bypass
                    if (currentAmountPaise === 0) {
                        rzpBtn.innerHTML = '<div class="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/20 to-transparent group-hover:animate-shine transition-transform"></div><svg class="w-6 h-6 mr-2 text-white shrink-0 relative z-10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg><span class="relative z-10">' + config.freeClaimText + '</span>';
                        rzpBtn.classList.remove('bg-[#00b86b]', 'hover:bg-[#00a35f]', 'shadow-[0_8px_20px_-8px_rgba(0,184,107,0.6)]');
                        rzpBtn.classList.add('bg-indigo-500', 'hover:bg-indigo-600', 'shadow-[0_8px_20px_-8px_rgba(99,102,241,0.6)]');

                        rzpBtn.onclick = function (e) {
                            e.preventDefault();
                            rzpBtn.innerHTML = 'Processing...';

                            var body = {
                                code: activeCoupon,
                                item_type: config.itemType,
                                item_id: config.itemId
                            };

                            // Gold pass needs extra fields
                            if (config.branchId) body.branch_id = config.branchId;
                            if (config.semesterId) body.semester_id = config.semesterId;

                            fetch(config.processFreeCheckoutUrl, {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(body)
                            })
                                .then(function (res) { return res.json(); })
                                .then(function (resp) {
                                    if (resp.success) {
                                        window.location.href = resp.redirect_url;
                                    } else {
                                        alert(resp.message);
                                        rzpBtn.innerHTML = config.freeClaimText;
                                    }
                                });
                        };
                    }
                } else {
                    msgEl.className = 'text-xs mt-2 text-red-500 font-medium';
                    msgEl.innerText = '\u2715 ' + data.message;
                }
            });
    };
})();
