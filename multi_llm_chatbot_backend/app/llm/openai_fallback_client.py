"""OpenAI GPT fallback client with configurable reasoning effort."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from app.llm.llm_client import LLMClient, ToolCallInfo, ToolCallResult
from app.core.context_manager import get_context_manager

logger = logging.getLogger(__name__)

_VLLM_ERROR_MARKERS = (
    "unable to connect",
    "encountered an error",
    "unexpected error",
)


class OpenAIFallbackClient(LLMClient):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.4",
        reasoning_effort: Optional[str] = None,
    ):
        if not api_key:
            raise ValueError("OpenAI API key not set. Provide OPENAI_API_KEY or llm.openai.api_key.")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.client = AsyncOpenAI(api_key=api_key, timeout=120.0)
        self.context_manager = get_context_manager()

    _ALLOWED_ROLES = {"system", "assistant", "user", "function", "tool", "developer"}

    def _reasoning_kwargs(self) -> Dict[str, Any]:
        if not self.reasoning_effort or self.reasoning_effort == "none":
            return {}
        return {"reasoning_effort": self.reasoning_effort}

    def _uses_completion_tokens_param(self) -> bool:
        """gpt-5+ requires `max_completion_tokens`; older models use `max_tokens`."""
        m = (self.model or "").lower()
        return m.startswith("gpt-5") or m.startswith("o1") or m.startswith("o3")

    def _normalize_messages(self, messages: List[dict]) -> List[dict]:
        """Map persona-id roles (e.g. 'jerry_huaute') to 'assistant' so OpenAI
        accepts them. Preserve the persona name via the optional 'name' field
        when possible.
        """
        out: List[dict] = []
        for msg in messages:
            role = msg.get("role", "user")
            if role in self._ALLOWED_ROLES:
                out.append(msg)
                continue
            new_msg = dict(msg)
            new_msg["role"] = "assistant"
            if "name" not in new_msg and isinstance(role, str):
                new_msg["name"] = role[:64]
            out.append(new_msg)
        return out

    async def generate(
        self,
        system_prompt: str,
        context: List[dict],
        temperature: float,
        max_tokens: int,
        response_mime_type: str = None,
    ) -> str:
        context_window = self.context_manager.prepare_context_for_llm(
            messages=context,
            system_prompt=system_prompt,
            llm_provider="openai",
        )
        normalized_messages = self._normalize_messages(context_window.messages)
        token_kwarg = "max_completion_tokens" if self._uses_completion_tokens_param() else "max_tokens"
        create_kwargs: Dict[str, Any] = dict(
            model=self.model,
            messages=normalized_messages,
            **{token_kwarg: max_tokens},
            **self._reasoning_kwargs(),
        )
        if not self._uses_completion_tokens_param():
            create_kwargs["temperature"] = temperature
        if response_mime_type == "application/json":
            create_kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.chat.completions.create(**create_kwargs)
            text = (response.choices[0].message.content or "").strip()
            if not text:
                raise ValueError("OpenAI returned empty content")
            return self._clean_response(text)
        except (APIConnectionError, APIStatusError) as exc:
            logger.error("OpenAI API error: %s", exc)
            raise
        except Exception as exc:
            logger.error("OpenAI generate failed: %s", exc)
            raise

    _MAX_TOOL_ROUNDS = 5

    async def generate_with_tools(
        self,
        system_prompt: str,
        user_message: str,
        tool_definitions: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Callable] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ToolCallResult:
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        openai_tools = tool_definitions or []
        all_tool_calls: List[ToolCallInfo] = []

        try:
            for _round in range(self._MAX_TOOL_ROUNDS):
                token_kwarg = "max_completion_tokens" if self._uses_completion_tokens_param() else "max_tokens"
                tool_kwargs: Dict[str, Any] = dict(
                    model=self.model,
                    messages=self._normalize_messages(messages),
                    tools=openai_tools or None,
                    **{token_kwarg: max_tokens},
                    **self._reasoning_kwargs(),
                )
                if not self._uses_completion_tokens_param():
                    tool_kwargs["temperature"] = temperature
                response = await self.client.chat.completions.create(**tool_kwargs)
                choice = response.choices[0].message
                if not choice.tool_calls:
                    text = choice.content or ""
                    if not text.strip():
                        raise ValueError("OpenAI tool loop returned empty content")
                    return ToolCallResult(
                        text=text,
                        used_tool=bool(all_tool_calls),
                        tool_name=all_tool_calls[0].name if all_tool_calls else None,
                        tool_args=all_tool_calls[0].args if all_tool_calls else {},
                        tool_calls_made=all_tool_calls,
                    )

                messages.append(choice.model_dump())
                for tc in choice.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    all_tool_calls.append(ToolCallInfo(name=fn_name, args=fn_args))
                    try:
                        tool_result = await tool_executor(name=fn_name, **fn_args)
                    except Exception as exc:
                        tool_result = {"error": str(exc)}
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result),
                    })

            raise ValueError("OpenAI tool-calling loop exhausted max rounds")
        except (APIConnectionError, APIStatusError) as exc:
            logger.error("OpenAI tool API error: %s", exc)
            raise
        except Exception as exc:
            logger.error("OpenAI generate_with_tools failed: %s", exc)
            raise
