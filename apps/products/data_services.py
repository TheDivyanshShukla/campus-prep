from apps.common.services import BaseService
from apps.products.models import Purchase, UnlockedContent, SubscriptionPlan, Coupon
from django.db.models import Q
from django.utils import timezone


class ProductDataService(BaseService):
    """
    Service for handling purchases and content unlocks.
    """

    # ── Unlock queries ────────────────────────────────────────────────────────

    @classmethod
    def user_has_unlocked_document(cls, user, document):
        if not user.is_authenticated:
            return False
        return cls.get_or_set_cache(
            f'user_{user.id}_has_unlocked_doc_{document.id}',
            lambda: UnlockedContent.objects.filter(
                user=user, parsed_document=document
            )
            .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date()))
            .exists(),
            timeout=1800,
        )

    @classmethod
    def get_active_unlocks(cls, user):
        if not user.is_authenticated:
            return []
        today = timezone.now().date()
        return cls.get_or_set_cache(
            f'user_active_unlocks_{user.id}',
            lambda: list(
                UnlockedContent.objects.filter(user=user)
                .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today))
                .select_related('parsed_document')
                .prefetch_related('parsed_document__subjects')
                .order_by('-id')
            ),
            timeout=1800,
        )

    @classmethod
    def get_all_unlocks(cls, user):
        """All unlocks split into active/expired lists."""
        if not user.is_authenticated:
            return [], []
        all_unlocks = list(
            UnlockedContent.objects.filter(user=user, parsed_document__isnull=False)
            .select_related('parsed_document')
            .prefetch_related('parsed_document__subjects')
            .order_by('-id')
        )
        today = timezone.now().date()
        active = [u for u in all_unlocks if u.valid_until is None or u.valid_until >= today]
        expired = [u for u in all_unlocks if u.valid_until is not None and u.valid_until < today]
        return active, expired

    @classmethod
    def unlock_document_for_user(cls, user, document, valid_until):
        """Get-or-create an unlock; renew validity if already exists."""
        unlocked, created = UnlockedContent.objects.get_or_create(
            user=user,
            parsed_document=document,
            defaults={'valid_until': valid_until},
        )
        if not created:
            unlocked.valid_until = valid_until
            unlocked.save(update_fields=['valid_until'])
        # Bust per-document and per-user caches
        cls.clear_cache(f'user_{user.id}_has_unlocked_doc_{document.id}')
        cls.clear_cache(f'user_active_unlocks_{user.id}')
        return unlocked, created

    # ── Purchase helpers ──────────────────────────────────────────────────────

    @classmethod
    def create_purchase(cls, user, *, document=None, subscription=None, amount=0,
                        razorpay_order_id=None, status='PENDING'):
        return Purchase.objects.create(
            user=user,
            parsed_document=document,
            subscription=subscription,
            amount_paid=amount,
            razorpay_order_id=razorpay_order_id or '',
            status=status,
        )

    @classmethod
    def get_purchase_by_order_id(cls, order_id):
        return Purchase.objects.filter(razorpay_order_id=order_id).first()

    # ── Plan / Coupon lookups ─────────────────────────────────────────────────

    @classmethod
    def get_active_semester_plan(cls):
        return cls.get_or_set_cache(
            'active_semester_plan',
            lambda: SubscriptionPlan.objects.filter(plan_type='SEMESTER', is_active=True).first(),
            timeout=3600,
        )

    @classmethod
    def get_coupon_by_code(cls, code):
        """Uncached — coupons are mutable (current_uses changes)."""
        try:
            return Coupon.objects.get(code=code)
        except Coupon.DoesNotExist:
            return None
