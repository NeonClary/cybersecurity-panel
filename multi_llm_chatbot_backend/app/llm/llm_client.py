from abc import ABC, abstractmethod
from typing import List

class LLMClient(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, context: List[dict]) -> str:
        pass
