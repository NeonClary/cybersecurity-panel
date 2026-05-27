import base64
import json
import logging
from typing import Any, Callable, Dict, List, Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError

from app.llm.llm_client import LLMClient, ToolCallInfo, ToolCallResult
from app.llm.neon_pile import get_pile_system_prompt
from app.core.context_manager import get_context_manager

logger = logging.getLogger(__name__)


class ImprovedVllmClient(LLMClient):
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model_name: str = None,
        neon_persona: str | None = None,
        model_revision: str | None = None,
        api_username: str | None = None,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.api_username = api_username or None
        self.model_name = model_name
        self.neon_persona = neon_persona
        self.model_revision = model_revision

        client_kwargs: dict = {
            "base_url": f"{api_url}/v1",
            "api_key": api_key or "not-needed",
            "timeout": 90.0,
        }

        if self.api_username:
            # Some Neon endpoints (e.g. BrainForge/Security at 4090-x1-3)
            # require HTTP Basic auth using HANA-style credentials rather
            # than the regular Bearer token. The OpenAI SDK injects its own
            # Authorization: Bearer <api_key> header on every request, so we
            # override it via default_headers to ensure Basic auth wins.
            basic = base64.b64encode(
                f"{self.api_username}:{api_key or ''}".encode("utf-8")
            ).decode("ascii")
            client_kwargs["default_headers"] = {"Authorization": f"Basic {basic}"}

        self.client = AsyncOpenAI(**client_kwargs)
        self.context_manager = get_context_manager()

    def _resolve_model_revision(self) -> str | None:
        if not self.model_name or "@" not in self.model_name:
            return self.model_revision
        _, _, suffix = self.model_name.partition("@")
        return suffix or self.model_revision

    def _resolve_base_model_name(self) -> str:
        if not self.model_name:
            return ""
        return self.model_name.split("@", 1)[0]

    def _build_messages(self, system_prompt: str, context_messages: List[dict]) -> List[dict]:
        """Prepend Neon pile persona system prompt when configured."""
        messages: List[dict] = []
        base_model = self._resolve_base_model_name()
        if base_model and self.neon_persona:
            pile_prompt = get_pile_system_prompt(
                base_model,
                self.neon_persona,
                revision=self._resolve_model_revision(),
            )
            if pile_prompt:
                messages.append({"role": "system", "content": pile_prompt})
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(context_messages)
        return messages

    async def refresh_model(self):
        """Query the vLLM endpoint to discover the currently loaded model."""
        models = await self.client.models.list()
        if not models.data:
            raise ValueError("No models available at the vLLM endpoint")
        self.model_name = models.data[0].id

    async def generate(self, system_prompt: str, context: List[dict],
                       temperature: float, max_tokens: int,
                       response_mime_type: str = None) -> str:
        try:
            context_window = self.context_manager.prepare_context_for_llm(
                messages=context,
                system_prompt="",
                llm_provider="vllm",
            )

            logger.debug(f"Context prepared: {len(context_window.messages)} messages, "
                        f"~{context_window.total_tokens} tokens, truncated={context_window.truncated}")

            if not self.model_name:
                await self.refresh_model()

            api_messages = self._build_messages(system_prompt, context_window.messages)

            create_kwargs = dict(
                model=self.model_name,
                messages=api_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            if response_mime_type == "application/json":
                create_kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**create_kwargs)

            text = response.choices[0].message.content.strip()
            return self._clean_response(text)

        except APIConnectionError as e:
            logger.error(f"Unable to connect to vLLM at {self.api_url}")
            return "I'm unable to connect to the AI service. Please ensure the vLLM endpoint is available."
        except APIStatusError as e:
            logger.error(f"vLLM API error: {e.status_code} - {e.message}")
            if e.status_code == 404:
                logger.info("Model not found, will re-discover on next request")
                self.model_name = None
            return "The AI service encountered an error. Please try again."
        except Exception as e:
            logger.error(f"Unexpected error in vLLM client: {str(e)}")
            return "I encountered an unexpected error. Please try again."

    # ------------------------------------------------------------------
    # Tool-calling support (OpenAI-compatible format)
    # ------------------------------------------------------------------

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
        """OpenAI-compatible tool-calling loop for vLLM.

        Tool definitions are expected in OpenAI format (as returned by the
        tool registry).  Loops through the standard tool-call protocol
        until the model produces a plain text response:

            request → detect tool_calls → execute all → feed results
            back → repeat (up to ``_MAX_TOOL_ROUNDS`` rounds).

        All tool calls in a single response are executed before the next
        round, so multi-tool queries (e.g. "compare professor A vs B")
        work correctly.
        """
        if not self.model_name:
            await self.refresh_model()

        messages: List[Dict[str, Any]] = self._build_messages(
            system_prompt,
            [{"role": "user", "content": user_message}],
        )

        openai_tools = tool_definitions or []

        all_tool_calls: List[ToolCallInfo] = []

        try:
            for _round in range(self._MAX_TOOL_ROUNDS):
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    tools=openai_tools or None,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                choice = response.choices[0].message

                if not choice.tool_calls:
                    return ToolCallResult(
                        text=choice.content or "",
                        used_tool=bool(all_tool_calls),
                        tool_name=all_tool_calls[0].name if all_tool_calls else None,
                        tool_args=all_tool_calls[0].args if all_tool_calls else {},
                        tool_calls_made=all_tool_calls,
                    )

                messages.append(choice.model_dump())

                for tc in choice.tool_calls:
                    fn_name = tc.function.name
                    fn_args = json.loads(tc.function.arguments)
                    logger.info("vLLM requested tool call: %s(%s)", fn_name, fn_args)
                    all_tool_calls.append(ToolCallInfo(name=fn_name, args=fn_args))

                    try:
                        tool_result = await tool_executor(name=fn_name, **fn_args)
                    except Exception as exc:
                        logger.error("Tool %s failed: %s", fn_name, exc)
                        tool_result = {"error": str(exc)}

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result),
                    })

            logger.warning(
                "Tool-calling loop exhausted after %d rounds", self._MAX_TOOL_ROUNDS,
            )
            last_content = response.choices[0].message.content or ""
            return ToolCallResult(
                text=last_content or "I was unable to finish looking that up. Please try again.",
                used_tool=bool(all_tool_calls),
                tool_name=all_tool_calls[0].name if all_tool_calls else None,
                tool_args=all_tool_calls[0].args if all_tool_calls else {},
                tool_calls_made=all_tool_calls,
            )

        except APIConnectionError:
            logger.error("Unable to connect to vLLM at %s", self.api_url)
            return ToolCallResult(
                text="I'm unable to connect to the AI service. Please ensure the vLLM endpoint is available.",
                used_tool=False,
            )
        except APIStatusError as e:
            logger.error("vLLM tool-call API error: %s - %s", e.status_code, e.message)
            if e.status_code == 404:
                self.model_name = None
            return ToolCallResult(
                text="The AI service encountered an error. Please try again.",
                used_tool=False,
            )
        except Exception as e:
            logger.error("Unexpected error in vLLM tool-calling: %s", e)
            return ToolCallResult(
                text="I encountered an unexpected error. Please try again.",
                used_tool=False,
            )


