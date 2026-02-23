from apps.common.services import BaseService
from apps.products.models import Purchase, UnlockedContent
from django.db.models import Q
from django.utils import timezone

class ProductDataService(BaseService):
    """
    Service for handling purchases and content unlocks.
    """
    
    @classmethod
    def user_has_unlocked_document(cls, user, document):
        if not user.is_authenticated:
            return False
        return cls.get_or_set_cache(
            f'user_{user.id}_has_unlocked_doc_{document.id}',
            lambda: UnlockedContent.objects.filter(
                user=user, 
                parsed_document=document
            ).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date())
            ).exists(),
            timeout=1800
        )

    @classmethod
    def get_active_unlocks(cls, user):
        if not user.is_authenticated:
            return []
        
        today = timezone.now().date()
        return cls.get_or_set_cache(
            f'user_active_unlocks_{user.id}',
            lambda: list(UnlockedContent.objects.filter(user=user).filter(
                Q(valid_until__isnull=True) | Q(valid_until__gte=today)
            ).select_related('parsed_document').prefetch_related('parsed_document__subjects').order_by('-id')),
            timeout=1800
        )
