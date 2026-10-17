# @AI-ANCHOR: [HISTORY-MANAGER-CORE] 历史办件 JSON 持久化归档、去重更新与单条/全量清理
"""history_manager.py - 办件快照历史档案管理器（支持搜索过滤、单条删除与一键清空）。"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import ApplicantState

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_HISTORY_FILE = _CONFIG_DIR / "history_snapshots.json"
MAX_HISTORY = 50


class HistoryManager:
    """办件历史快照管理器。"""

    @staticmethod
    def load_history() -> list[dict[str, Any]]:
        if not _HISTORY_FILE.exists():
            return []
        try:
            data = json.loads(_HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    @staticmethod
    def save_snapshot(state: ApplicantState, extra_info: dict[str, Any] | None = None) -> None:
        history = HistoryManager.load_history()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "id": f"{state.owner_id or state.owner_name}_{int(datetime.now().timestamp() * 1000)}",
            "timestamp": now_str,
            "owner_name": state.owner_name,
            "owner_id": state.owner_id,
            "phone": state.phone,
            "shop_name": state.shop_name,
            "shop_address": state.shop_address,
            "town": state.town,
            "supervisor": state.supervisor,
            "state_dict": state.to_dict(),
            "extra": extra_info or {},
        }
        # 同人同店去重置顶
        history = [
            h for h in history
            if not (h.get("owner_id") == state.owner_id and h.get("shop_name") == state.shop_name and state.owner_id)
        ]
        history.insert(0, entry)
        history = history[:MAX_HISTORY]
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def delete_snapshot(index: int = -1, record_id: str = "") -> list[dict[str, Any]]:
        """按索引或唯一 ID 删除单条历史记录并返回最新列表。"""
        history = HistoryManager.load_history()
        if record_id:
            history = [h for h in history if h.get("id") != record_id]
        elif 0 <= index < len(history):
            history.pop(index)
        _HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        return history

    @staticmethod
    def clear_history() -> list[dict[str, Any]]:
        """清空全部历史记录。"""
        _HISTORY_FILE.write_text("[]", encoding="utf-8")
        return []

    @staticmethod
    def restore_state(snapshot_dict: dict[str, Any]) -> ApplicantState:
        s_data = snapshot_dict.get("state_dict", snapshot_dict)
        return ApplicantState.from_dict(s_data)
