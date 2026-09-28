from typing import Protocol
from app.models import Alert

class Publisher(Protocol):
    name: str

    async def publish(self, alert: Alert) -> None:
        """Publish alert payload asynchronously."""
        ...
