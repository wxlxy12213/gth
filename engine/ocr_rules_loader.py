"""ocr_rules_loader.py - 办件 OCR 规则与行政区划字典配置加载器（支持外置 JSON 原地热更新与内置兜底）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_RULES_PATH = _CONFIG_DIR / "ocr_rules.json"

_DEFAULT_RULES: dict[str, Any] = {
    "city_county_prefixes": [
        "山东省临沂市郯城县", "临沂市郯城县", "山东省郯城县", "郯城县"
    ],
    "towns_list": [
        "郯城经济开发区", "高峰头镇", "胜利镇", "泉源镇", "花园镇", "归昌乡",
        "郯城街道", "马头镇", "李庄镇", "重坊镇", "杨集镇", "庙山镇", "港上镇", "红花镇"
    ],
    "town_aliases": {
        "郯城镇": "郯城街道",
        "郯城开发区": "郯城经济开发区",
        "经济开发区": "郯城经济开发区",
        "开发区": "郯城经济开发区",
        "花园乡": "花园镇",
        "马头": "马头镇",
        "李庄": "李庄镇",
        "杨集": "杨集镇",
        "泉源": "泉源镇",
        "港上": "港上镇",
        "庙山": "庙山镇",
        "胜利": "胜利镇",
        "红花": "红花镇",
        "归昌": "归昌乡",
        "高峰头": "高峰头镇",
        "重坊": "重坊镇",
        "花园": "花园镇",
    },
    "supervisor_map": {
        "马头镇": "马头所", "李庄镇": "李庄所", "杨集镇": "杨集所", "泉源镇": "泉源所",
        "港上镇": "港上所", "庙山镇": "庙山所", "胜利镇": "胜利所", "红花镇": "红花所",
        "归昌乡": "归昌所", "郯城经济开发区": "经济开发区所", "高峰头镇": "高峰头所",
        "重坊镇": "重坊所", "花园镇": "花园所", "郯城街道": "城区所"
    },
    "owner_keywords": [
        "经营者", "申请人", "负责人", "法定代表人", "本人", "乙方", "承租人", "承租方"
    ],
    "landlord_keywords": [
        "房东", "出租人", "出租方", "出租者", "产权人", "甲方", "业主"
    ],
    "self_referential_words": [
        "本人", "自己", "申请人", "同上", "无", "自有", "自营"
    ],
    "shop_suffixes": [
        "百货店", "便利店", "超市", "食品经营部", "商行", "门市部", "经营部", "工作室", "饭店", "馆", "店"
    ],
    "address_tail_keywords": [
        "村", "庄", "社区", "居委会", "路", "街", "巷", "弄", "组", "栋", "单元"
    ],
    "terminal_markers": [
        "号", "室", "铺", "档", "院", "层", "店", "部", "栋", "单元"
    ],
}

_cached_mtime: float = -1.0
_cached_rules: dict[str, Any] = dict(_DEFAULT_RULES)

# 导出可变容器引用，确保 F5 热重载时已导入模块的引用同步原地刷新
TOWNS_LIST: list[str] = []
TOWN_ALIASES: dict[str, str] = {}
SUPERVISOR_MAP: dict[str, str] = {}
OWNER_KEYWORDS: list[str] = []
LANDLORD_KEYWORDS: list[str] = []
SELF_REFERENTIAL_WORDS: set[str] = set()
CITY_COUNTY_PREFIXES: list[str] = []
SHOP_SUFFIXES: list[str] = []
ADDRESS_TAIL_KEYWORDS: list[str] = []
TERMINAL_MARKERS: list[str] = []


def _sync_exported_containers(rules: dict[str, Any]) -> None:
    """原地更新所有导出容器，确保跨模块引用在 F5 热重载后立即生效。"""
    TOWNS_LIST[:] = sorted(rules.get("towns_list", []), key=len, reverse=True)
    TOWN_ALIASES.clear()
    TOWN_ALIASES.update(rules.get("town_aliases", {}))
    SUPERVISOR_MAP.clear()
    SUPERVISOR_MAP.update(rules.get("supervisor_map", {}))
    OWNER_KEYWORDS[:] = list(rules.get("owner_keywords", []))
    LANDLORD_KEYWORDS[:] = list(rules.get("landlord_keywords", []))
    SELF_REFERENTIAL_WORDS.clear()
    SELF_REFERENTIAL_WORDS.update(rules.get("self_referential_words", []))
    CITY_COUNTY_PREFIXES[:] = list(rules.get("city_county_prefixes", []))
    SHOP_SUFFIXES[:] = sorted(rules.get("shop_suffixes", []), key=len, reverse=True)
    ADDRESS_TAIL_KEYWORDS[:] = list(rules.get("address_tail_keywords", []))
    TERMINAL_MARKERS[:] = list(rules.get("terminal_markers", []))


def load_ocr_rules(force_reload: bool = False) -> dict[str, Any]:
    """加载外置 config/ocr_rules.json，若文件修改则自动原地热更新所有字典容器。"""
    global _cached_mtime, _cached_rules
    try:
        if _RULES_PATH.exists():
            mtime = _RULES_PATH.stat().st_mtime
            if force_reload or mtime != _cached_mtime:
                raw = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
                merged = dict(_DEFAULT_RULES)
                merged.update(raw)
                _cached_rules = merged
                _cached_mtime = mtime
                _sync_exported_containers(_cached_rules)
        elif not TOWNS_LIST:
            _sync_exported_containers(_cached_rules)
    except Exception:
        if not TOWNS_LIST:
            _sync_exported_containers(_cached_rules)
    return _cached_rules


# 启动时初始化
load_ocr_rules(force_reload=True)
