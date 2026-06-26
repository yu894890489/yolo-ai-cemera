from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Any

logger = logging.getLogger(__name__)

_POSITIVE_HINTS = ("告警", "报警", "异常", "入侵", "翻越", "闯入", "yes", "alarm")
_NEGATIVE_HINTS = ("无异常", "未发现", "没有", "正常", "no alarm", "normal")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


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


def _extract_text(raw: dict[str, Any]) -> str:
    """Pull the model's text answer out of common response shapes."""
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    for key in ("content", "summary", "output", "text"):
        val = raw.get(key)
        if isinstance(val, str):
            return val
    return ""


def _coerce_confidence(value: Any, default: float = 0.0) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, conf))


def interpret_judgment(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalise a raw VLM response into a structured alarm judgment.

    Returns ``{is_alarm, reason, confidence, summary}``. Tries, in order:
    an already-structured dict, a JSON object embedded in the text, then a
    keyword heuristic. Unknown input degrades to ``is_alarm=False`` so a
    confused model never raises a false alarm.
    """
    if isinstance(raw, dict) and isinstance(raw.get("is_alarm"), bool):
        return {
            "is_alarm": raw["is_alarm"],
            "reason": str(raw.get("reason", "")),
            "confidence": _coerce_confidence(raw.get("confidence")),
            "summary": str(raw.get("reason", "") or raw.get("summary", "")),
        }

    text = _extract_text(raw)
    match = _JSON_OBJECT_RE.search(text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict) and "is_alarm" in parsed:
                return {
                    "is_alarm": bool(parsed.get("is_alarm")),
                    "reason": str(parsed.get("reason", "")),
                    "confidence": _coerce_confidence(parsed.get("confidence")),
                    "summary": str(parsed.get("reason", "")) or text[:200],
                }
        except json.JSONDecodeError:
            pass

    lowered = text.lower()
    is_alarm = False
    if any(hint in text or hint in lowered for hint in _POSITIVE_HINTS):
        is_alarm = True
    if any(hint in text or hint in lowered for hint in _NEGATIVE_HINTS):
        is_alarm = False
    return {
        "is_alarm": is_alarm,
        "reason": text[:200],
        "confidence": 0.5 if is_alarm else 0.0,
        "summary": text[:200],
    }


def build_openai_vision_body(endpoint: VLMEndpoint, payload: dict[str, Any]) -> dict[str, Any]:
    """Translate the generic VLM payload into an OpenAI-compatible vision body.

    Qwen-VL and GLM-4V both speak the OpenAI chat-completions schema. The system
    prompt asks for a strict JSON judgment so :func:`interpret_judgment` has a
    clean object to parse.
    """
    image_b64 = payload.get("image", "")
    user_prompt = payload.get("prompt", "")
    system_prompt = (
        "你是安防视频分析助手。判断图像是否构成告警。"
        '只输出 JSON：{"is_alarm": true/false, "reason": "中文简述", "confidence": 0~1}'
    )
    return {
        "model": endpoint.provider,
        "max_tokens": payload.get("max_tokens", endpoint.max_tokens),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            },
        ],
    }


def http_transport(endpoint: VLMEndpoint, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    """POST an OpenAI-compatible vision request and return the parsed JSON.

    Auth is taken from the ``VLM_API_KEY`` env var when present (BE-M1-C owns
    per-provider key management; v1 uses one shared key). Network and decode
    errors surface as :class:`VLMRequestError` so the client's failover kicks in.
    """
    import os

    body = build_openai_vision_body(endpoint, payload)
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("VLM_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(endpoint.url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 - configured endpoint
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise VLMRequestError(str(exc)) from exc


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
