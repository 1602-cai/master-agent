"""Agent backend adapters. OpenAI Agents SDK is the first adapter."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

from agents import Agent, Runner
from agents.stream_events import RawResponsesStreamEvent

log = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry

# Minimum interval (seconds) between streaming callbacks to avoid flooding WS
_STREAM_THROTTLE = 0.35


class OpenAIAgentAdapter:
    """Thin wrapper around OpenAI Agents SDK Runner.

    The adapter does NOT manage job state, confirmations or artifacts.
    It only executes an agent and returns the result.
    """

    async def run_agent(
        self,
        agent: Agent,
        input_text: str,
        max_turns: int = 30,
    ) -> str:
        """Run an agent and return its final output text."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                result = await Runner.run(agent, input=input_text, max_turns=max_turns)
                return result.final_output or ""
            except Exception as e:
                log.warning("Agent error (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                if attempt == MAX_RETRIES:
                    raise
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.info("Retrying in %.1fs...", delay)
                await asyncio.sleep(delay)
        return ""

    async def run_agent_streamed(
        self,
        agent: Agent,
        input_text: str,
        max_turns: int = 30,
        on_tool_args_delta: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> str:
        """Run agent with streaming, calling *on_tool_args_delta(func_name, accumulated_args)*
        each time a function-call argument chunk arrives from the LLM.

        Falls back to non-streaming ``run_agent`` on error.
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                streamed = Runner.run_streamed(agent, input=input_text, max_turns=max_turns)

                # item_id → (function_name, accumulated_args)
                _buffers: dict[str, tuple[str, str]] = {}
                _last_cb: dict[str, float] = {}  # item_id → last callback timestamp

                async for event in streamed.stream_events():
                    if not isinstance(event, RawResponsesStreamEvent):
                        continue
                    ev = event.data
                    ev_type = getattr(ev, "type", "")

                    # ── function call added ──
                    if ev_type == "response.output_item.added":
                        item = getattr(ev, "item", None)
                        if item and getattr(item, "type", "") == "function_call":
                            item_id = getattr(item, "id", "") or getattr(item, "call_id", "")
                            _buffers[item_id] = (getattr(item, "name", ""), "")

                    # ── function call argument delta ──
                    elif ev_type == "response.function_call_arguments.delta":
                        item_id = getattr(ev, "item_id", "")
                        delta = getattr(ev, "delta", "")
                        if item_id in _buffers and delta:
                            name, prev = _buffers[item_id]
                            accumulated = prev + delta
                            _buffers[item_id] = (name, accumulated)
                            if on_tool_args_delta:
                                now = time.monotonic()
                                if now - _last_cb.get(item_id, 0) >= _STREAM_THROTTLE:
                                    _last_cb[item_id] = now
                                    try:
                                        await on_tool_args_delta(name, accumulated)
                                    except Exception:
                                        pass  # never fail the run for a callback error

                # One final flush for each buffer (un-throttled)
                if on_tool_args_delta:
                    for item_id, (name, accumulated) in _buffers.items():
                        if accumulated:
                            try:
                                await on_tool_args_delta(name, accumulated)
                            except Exception:
                                pass

                return streamed.final_output or ""
            except Exception as e:
                log.warning("Agent streamed error (attempt %d/%d): %s", attempt, MAX_RETRIES, e)
                if attempt == MAX_RETRIES:
                    # Last resort: try non-streaming
                    log.info("Falling back to non-streaming run_agent")
                    try:
                        return await self.run_agent(agent, input_text, max_turns)
                    except Exception:
                        raise e
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
        return ""
