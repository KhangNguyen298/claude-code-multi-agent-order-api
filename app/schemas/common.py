from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from pydantic import PlainSerializer

# Decimal internally, JSON number on the wire.
MoneyOut = Annotated[Decimal, PlainSerializer(lambda d: float(d), return_type=float, when_used="json")]


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes that are always UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
