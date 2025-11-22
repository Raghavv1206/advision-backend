# backend/core/utils/timezone_utils.py - NEW FILE

from django.utils import timezone
from datetime import datetime

def make_aware(dt):
    """
    Make a datetime timezone-aware if it isn't already.
    Used when loading data from SQLite that had naive datetimes.
    """
    if dt is None:
        return None
    
    if isinstance(dt, datetime):
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
    
    return dt