"""
API 调用模块 - 使用 config.py 中的 MODEL_REGISTRY 进行模型调用
"""

import os
import base64
from openai import OpenAI
from config import MODEL_REGISTRY


def encode_file_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_user_content(prompt, video_path=None, image_path=None):
    user_messages = [{"type": "text", "text": prompt}]

    if video_path:
        b64_vid = encode_file_base64(video_path)
        user_messages.append(
            {"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64_vid}"}}
        )

    if image_path:
        paths = image_path if isinstance(image_path, (list, tuple)) else [image_path]
        for p in paths:
            b64_img = encode_file_base64(p)
            user_messages.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_img}"}}
            )

    return user_messages


def create_client(model):
    if model not in MODEL_REGISTRY:
        raise ValueError(f"Model '{model}' not found in MODEL_REGISTRY")
    entry = MODEL_REGISTRY[model]
    client = OpenAI(
        base_url=entry["base_url"],
        api_key=entry["api_key"],
    )
    return client, entry["model_id"]


def _get_extra_kwargs(model):
    entry = MODEL_REGISTRY.get(model, {})
    if entry.get("thinking"):
        return {"extra_body": {"enable_thinking": True}}
    return {}


def call_api_stream(prompt, model="Claude-4-Sonnet", video_path=None, image_path=None):
    client, model_id = create_client(model)
    user_messages = _build_user_content(prompt, video_path=video_path, image_path=image_path)

    extra = _get_extra_kwargs(model)
    extra.setdefault("extra_body", {})
    extra["extra_body"]["stream_options"] = {"include_usage": True}

    stream = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": user_messages}],
        stream=True,
        **extra,
    )

    for event in stream:
        if hasattr(event, "usage") and event.usage:
            yield {
                "prompt_tokens": getattr(event.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(event.usage, "completion_tokens", 0),
                "total_tokens": getattr(event.usage, "total_tokens", 0),
            }

        try:
            choice0 = event.choices[0]
        except Exception:
            continue

        delta = getattr(choice0, "delta", None)
        if delta is not None:
            chunk = getattr(delta, "content", None)
            if chunk:
                yield chunk
                continue

        msg = getattr(choice0, "message", None)
        if msg is not None:
            chunk = getattr(msg, "content", None)
            if chunk:
                yield chunk


def call_api(
    prompt,
    model="Claude-4-Sonnet",
    video_path=None,
    image_path=None,
    *,
    on_chunk=None,
    stream_print: bool = False,
    print_fn=None,
    return_thinking: bool = False,
    return_usage: bool = False,
):
    if on_chunk is None and stream_print:
        if print_fn is None:
            def print_fn(t: str):
                print(t, end="", flush=True)
        on_chunk = print_fn

    entry = MODEL_REGISTRY.get(model, {})
    is_thinking = entry.get("thinking", False)

    if not is_thinking or not return_thinking:
        pieces = []
        usage = None
        for chunk in call_api_stream(prompt, model=model, video_path=video_path, image_path=image_path):
            if isinstance(chunk, dict):
                usage = chunk
                continue
            pieces.append(chunk)
            if on_chunk is not None:
                on_chunk(chunk)
        result = "".join(pieces)
        if return_thinking and return_usage:
            return result, "", usage
        if return_thinking:
            return result, ""
        if return_usage:
            return result, usage
        return result

    client, model_id = create_client(model)
    user_messages = _build_user_content(prompt, video_path=video_path, image_path=image_path)

    extra = _get_extra_kwargs(model)
    extra.setdefault("extra_body", {})
    extra["extra_body"]["stream_options"] = {"include_usage": True}

    stream = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "user", "content": user_messages}],
        stream=True,
        **extra,
    )

    pieces = []
    thinking_pieces = []
    usage = None

    for event in stream:
        if hasattr(event, "usage") and event.usage:
            usage = {
                "prompt_tokens": getattr(event.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(event.usage, "completion_tokens", 0),
                "total_tokens": getattr(event.usage, "total_tokens", 0),
            }

        try:
            choice0 = event.choices[0]
        except Exception:
            continue

        delta = getattr(choice0, "delta", None)
        if delta is not None:
            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                thinking_pieces.append(reasoning)
                continue
            chunk = getattr(delta, "content", None)
            if chunk:
                pieces.append(chunk)
                if on_chunk is not None:
                    on_chunk(chunk)
                continue

        msg = getattr(choice0, "message", None)
        if msg is not None:
            chunk = getattr(msg, "content", None)
            if chunk:
                pieces.append(chunk)
                if on_chunk is not None:
                    on_chunk(chunk)

    content = "".join(pieces)
    thinking = "".join(thinking_pieces)
    if return_usage:
        return content, thinking, usage
    return content, thinking


if __name__ == '__main__':
    full = call_api("你是什么模型？", "Gemini-3-Pro")
    print("\n\n[full]", full)
