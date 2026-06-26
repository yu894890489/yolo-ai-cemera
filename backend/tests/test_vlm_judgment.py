"""Tests for VLM judgment interpretation and request body building (BE-M1-B)."""

from __future__ import annotations

from app.common.vlm import VLMEndpoint, build_openai_vision_body, interpret_judgment


def test_interpret_judgment_parses_embedded_json():
    raw = {
        "choices": [
            {
                "message": {
                    "content": 'Sure. {"is_alarm": true, "reason": "person climbing fence", "confidence": 0.91}'
                }
            }
        ]
    }
    j = interpret_judgment(raw)
    assert j["is_alarm"] is True
    assert j["reason"] == "person climbing fence"
    assert abs(j["confidence"] - 0.91) < 1e-6


def test_interpret_judgment_accepts_already_structured_dict():
    raw = {"is_alarm": False, "reason": "nothing happening", "confidence": 0.2}
    j = interpret_judgment(raw)
    assert j["is_alarm"] is False
    assert j["reason"] == "nothing happening"
    assert abs(j["confidence"] - 0.2) < 1e-6


def test_interpret_judgment_heuristic_positive_chinese_text():
    raw = {"choices": [{"message": {"content": "是的，有人翻越围墙，存在入侵告警。"}}]}
    j = interpret_judgment(raw)
    assert j["is_alarm"] is True
    assert j["summary"]


def test_interpret_judgment_heuristic_negative_text():
    raw = {"choices": [{"message": {"content": "正常，无异常情况。"}}]}
    j = interpret_judgment(raw)
    assert j["is_alarm"] is False


def test_interpret_judgment_defaults_to_no_alarm_on_garbage():
    j = interpret_judgment({"unexpected": "shape"})
    assert j["is_alarm"] is False
    assert "confidence" in j


def test_build_openai_vision_body_embeds_image_and_prompt_and_disables_thinking():
    ep = VLMEndpoint("qwen-vl-max", "https://x/v1/chat/completions", True, 10, 5.0, 256)
    payload = {
        "image": "BASE64DATA",
        "prompt": "Is there an intruder?",
        "crop": {"bbox": [1, 2, 3, 4]},
        "max_tokens": 256,
        "thinking": False,
    }
    body = build_openai_vision_body(ep, payload)
    assert body["max_tokens"] == 256
    text = str(body["messages"])
    assert "Is there an intruder?" in text
    assert "data:image/jpeg;base64,BASE64DATA" in text
