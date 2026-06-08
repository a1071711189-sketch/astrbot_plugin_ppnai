"""画师预设模块 — 会话级画师风格切换与注入。"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ArtistPreset:
    """单个画师预设"""
    name: str
    prompt: str
    negative_prompt: str = ""
    description: str = ""


@dataclass(slots=True)
class SessionContext:
    """会话标识"""
    session_key: str
    user_id: str

    @classmethod
    def from_event(cls, event: Any) -> SessionContext:
        return cls(
            session_key=str(getattr(event, "unified_msg_origin", "")),
            user_id=str(event.get_sender_id()),
        )


@dataclass
class RecentImageRecord:
    message_id: str = ""
    prompt: str = ""


@dataclass(slots=True)
class SessionRuntimeState:
    """会话级别的运行时状态"""
    selected_artist_index: int | None = None
    recent_images: deque[RecentImageRecord] = field(
        default_factory=lambda: deque(maxlen=20),
    )


class SessionStateStore:
    """内存中的会话状态存储"""

    def __init__(self) -> None:
        self._states: dict[str, SessionRuntimeState] = {}

    def get(self, session: SessionContext) -> SessionRuntimeState:
        return self._states.setdefault(session.session_key, SessionRuntimeState())


def parse_artist_presets(raw_value: Any) -> list[ArtistPreset]:
    """解析画师预设列表，兼容 list[str]、list[dict] 和 Pydantic model 格式。"""
    if not isinstance(raw_value, list):
        return []

    presets: list[ArtistPreset] = []
    for index, item in enumerate(raw_value, start=1):
        if isinstance(item, ArtistPreset):
            presets.append(item)
            continue
        if isinstance(item, dict):
            name = str(item.get("name") or f"画师串 {index}").strip()
            prompt = str(item.get("prompt") or "").strip()
            negative_prompt = str(item.get("negative_prompt") or "").strip()
            description = str(item.get("description") or "").strip()
        elif hasattr(item, "name") and hasattr(item, "prompt"):
            name = str(getattr(item, "name", None) or f"画师串 {index}").strip()
            prompt = str(getattr(item, "prompt", None) or "").strip()
            negative_prompt = str(getattr(item, "negative_prompt", None) or "").strip()
            description = str(getattr(item, "description", None) or "").strip()
        elif isinstance(item, str):
            name = f"画师串 {index}"
            prompt = item.strip()
            negative_prompt = ""
            description = ""
        else:
            continue

        if prompt:
            presets.append(ArtistPreset(
                name=name,
                prompt=prompt,
                negative_prompt=negative_prompt,
                description=description,
            ))
    return presets


def resolve_artist_preset(
    presets: list[ArtistPreset],
    state: SessionRuntimeState,
) -> ArtistPreset | None:
    """取出当前选中的画师预设，未设置时默认取第一条。"""
    if not presets:
        return None
    index = state.selected_artist_index or 1
    if 1 <= index <= len(presets):
        return presets[index - 1]
    return presets[0]


def inject_artist_prompt(base_prompt: str, artist_prompt: str) -> str:
    """将画师串前置到 prompt 最前面。"""
    artist = artist_prompt.strip()
    if not artist:
        return base_prompt
    base = base_prompt.strip()
    return f"{artist}, {base}" if base else artist


def inject_artist_negative(existing_negative: str, artist_negative: str) -> str:
    """将画师预设的负面提示词追加到已有负面词后面。"""
    extra = artist_negative.strip()
    if not extra:
        return existing_negative
    existing = existing_negative.strip()
    return f"{existing}, {extra}" if existing else extra
