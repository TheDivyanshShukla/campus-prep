from django.core.cache import cache
from django.db import models
from typing import TypeVar, Type, List, Optional, Any, Callable
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=models.Model)

class BaseService:
    """
    Base service class providing common utilities for data retrieval and caching.
    """
    
    @staticmethod
    def get_or_set_cache(key: str, callback: Callable, timeout: int = 3600) -> Any:
        """
        Generic helper to get data from cache or set it using the callback.
        """
        data = cache.get(key)
        if data is None:
            logger.debug(f"Cache miss for key: {key}")
            data = callback()
            cache.set(key, data, timeout)
        else:
            logger.debug(f"Cache hit for key: {key}")
        return data

    @staticmethod
    def clear_cache(key: str):
        """
        Clears a specific cache key.
        """
        cache.delete(key)
        logger.debug(f"Cleared cache for key: {key}")

    @classmethod
    def get_all_cached(cls, model: Type[T], cache_key: str, timeout: int = 3600) -> List[T]:
        """
        Retrieves all instances of a model, with caching.
        Note: Use carefully for large tables.
        """
        return cls.get_or_set_cache(
            cache_key,
            lambda: list(model.objects.all()),
            timeout
        )
