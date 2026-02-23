from apps.common.services import BaseService
from django.db.models import Q
from django.utils import timezone

class UserDataService(BaseService):
    """
    Service for user-related data retrieval and operations.
    """
    
    @staticmethod
    def get_unlocked_document_ids(user, documents):
        """
        Returns a set of document IDs that the user has unlocked via granular gold pass or one-off purchase.
        """
        if not user.is_authenticated:
            return set()
            
        unlocked_doc_ids = set()
        
        # Check granular Gold Pass unlocks
        for doc in documents:
            if doc.is_premium and any(user.has_gold_pass(s, doc.document_type) for s in doc.subjects.all()):
                unlocked_doc_ids.add(doc.id)
                
        # Get documents unlocked specifically by one-off purchase
        valid_unlocked = user.unlocked_contents.filter(
            parsed_document__isnull=False
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date())
        ).values_list('parsed_document_id', flat=True)
        
        unlocked_doc_ids.update(valid_unlocked)
        return unlocked_doc_ids

    @staticmethod
    def check_premium_access(user, document):
        """
        Comprehensive check if a user can access a specific document.
        """
        if not document.is_premium:
            return True
            
        if user.is_staff:
            return True
            
        if not user.is_authenticated:
            return False
            
        # Global/Plan Check
        has_gold_pass = any(user.has_gold_pass(subj, document.document_type) for subj in document.subjects.all())
        if has_gold_pass:
            return True
            
        # Specific Unlocked Content Check
        has_specific_unlock = user.unlocked_contents.filter(
            Q(product__subject__in=document.subjects.all(), product__category__name__icontains=document.document_type) |
            Q(parsed_document=document)
        ).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=timezone.now().date())
        ).exists()
        
        return has_specific_unlock
