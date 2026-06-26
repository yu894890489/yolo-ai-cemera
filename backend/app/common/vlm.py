from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Any

logger = logging.getLogger(__name__)


class VLMRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class VLMEndpoint:
    provider: str
    url: str
    enabled: bool = True
    priority: int = 100
    timeout_s: float = 10.0
    max_tokens: int = 512


@dataclass
class VLMRuntimeState:
    enabled: bool = True
    active_provider: str | None = None
    last_error: str | None = None
    last_failure_reason: str | None = None
    degraded_mode: str | None = None


Transport = Callable[[VLMEndpoint, dict[str, Any], float], dict[str, Any]]


def _default_transport(endpoint: VLMEndpoint, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:  # noqa: ARG001
    raise VLMRequestError("transport_not_configured")


class VLMClient:
    def __init__(
        self,
        *,
        endpoints: list[VLMEndpoint],
        transport: Transport | None = None,
        state: VLMRuntimeState | None = None,
        max_retries: int = 1,
        backoff_base_s: float = 0.2,
        disable_thinking: bool = True,
    ) -> None:
        self.endpoints = sorted((ep for ep in endpoints if ep.enabled), key=lambda ep: ep.priority)
        self.transport = transport or _default_transport
        self.state = state or VLMRuntimeState()
        self.max_retries = max(0, max_retries)
        self.backoff_base_s = max(0.0, backoff_base_s)
        self.disable_thinking = disable_thinking

    def analyze(self, frame_b64: str, *, prompt: str, crop: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.endpoints:
            self.state.last_error = "no_enabled_vlm_endpoint"
            self.state.last_failure_reason = "no_enabled_vlm_endpoint"
            self.state.degraded_mode = "small_only"
            raise VLMRequestError("no_enabled_vlm_endpoint")

        last_error: str | None = None
        for endpoint in self.endpoints:
            payload = {
                "image": frame_b64,
                "prompt": prompt,
                "crop": crop or {},
                "max_tokens": endpoint.max_tokens,
                "thinking": not self.disable_thinking,
            }
            for attempt in range(self.max_retries + 1):
                try:
                    result = self.transport(endpoint, payload, endpoint.timeout_s)
                    self.state.active_provider = endpoint.provider
                    self.state.last_failure_reason = None
                    self.state.degraded_mode = None
                    return result
                except Exception as exc:
                    last_error = f"{endpoint.provider}: {exc}"
                    self.state.last_error = last_error
                    logger.warning("vlm provider failed provider=%s attempt=%d error=%s", endpoint.provider, attempt + 1, exc)
                    if attempt < self.max_retries and self.backoff_base_s:
                        time.sleep(self.backoff_base_s * (2**attempt))
        self.state.last_failure_reason = last_error
        self.state.degraded_mode = "small_only"
        raise VLMRequestError(last_error or "vlm_failed")
