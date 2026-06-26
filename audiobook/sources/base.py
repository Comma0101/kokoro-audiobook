from typing import Protocol
from ..models import Chapter

class Source(Protocol):
    def load(self, input_str: str) -> list[Chapter]:
        ...
