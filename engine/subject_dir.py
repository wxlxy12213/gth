# -*- coding: utf-8 -*-
"""subject_dir.py - 桌面主体目录解析器：统一遵循市场主体登记出件单源契约（与 wendang / ahk 规范同源）。

确定性防冲突策略：
1. 精确命中：桌面已存在与主体同名的文件夹 -> 直接复用；
2. 带括号后缀命中：桌面存在「主体名（个体工商户）」文件夹 -> 自动更名规范化并复用；
3. 宽松同名命中：桌面存在仅空格或大小写差异的同名文件夹 -> 宽容复用，避免产生重复重名文件夹；
4. 无候选：以规范主体名新建文件夹；
5. 绝不抛出阻断性冲突异常，保障出件流水线 100% 畅通。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

SUFFIX_GEHU = "（个体工商户）"
SUFFIX_GEHU_EN = "(个体工商户)"


# @AI-ANCHOR: [SUBJECT-DIR-RESOLVER] 桌面客户专属主体目录防冲突解析器
def _default_desktop() -> Path:
    override = os.environ.get("SKILL_DESKTOP_DIR")
    if override:
        return Path(override)
    cand = Path.home() / "Desktop"
    try:
        cand.mkdir(parents=True, exist_ok=True)
        test_probe = cand / ".gth_write_probe"
        test_probe.write_text("ok", encoding="utf-8")
        test_probe.unlink(missing_ok=True)
        return cand
    except Exception:
        fallback = Path(__file__).resolve().parent.parent / ".cache" / "Desktop"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def clean_subject(subject: str) -> str:
    """去除非法文件名字符与括号后缀，提取纯净主体名称。"""
    s = (subject or "").strip()
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    s = re.sub(r"[（(][^（）()]*[)）]", "", s).strip()
    return s


def normalize_for_match(name: str) -> str:
    """归一化用于模糊对比（去空白、去括号、小写）。"""
    s = clean_subject(name)
    s = re.sub(r"\s+", "", s).lower()
    return s


def resolve_subject_dir(subject: str, desktop: Optional[Path] = None) -> Path:
    """定位或新建桌面主体目录，返回物理绝对路径 Path。

    消歧与防冲突保障：
    1. 同名文件夹已存在：100% 直接复用，不重复创建、不报错；
    2. 带「（个体工商户）」历史后缀文件夹存在：自动重命名为纯主体名后复用；
    3. 存在仅有空格微异的文件夹：宽容复用现有目录，避免在桌面散落两个类似文件夹；
    4. 无候选：以纯主体名自动建目录；
    5. 全程异常自愈，绝不抛出 FileExistsError 或冲突中断出件。
    """
    clean_name = clean_subject(subject)
    if not clean_name or clean_name == "未定字号":
        clean_name = "个体户"

    desk = Path(desktop) if desktop else _default_desktop()
    desk.mkdir(parents=True, exist_ok=True)

    plain = desk / clean_name
    if plain.is_dir():
        return plain

    # 检查带后缀的历史文件夹：主体名（个体工商户）
    for suffix in (SUFFIX_GEHU, SUFFIX_GEHU_EN):
        legacy = desk / f"{clean_name}{suffix}"
        if legacy.is_dir():
            if not plain.exists():
                try:
                    legacy.rename(plain)
                    return plain
                except Exception:
                    return legacy
            else:
                return plain if plain.is_dir() else legacy

    # 宽松扫描桌面直接子目录（防止多余空格导致重复建目录）
    norm_target = normalize_for_match(clean_name)
    try:
        for entry in desk.iterdir():
            if entry.is_dir() and not entry.name.startswith((".", "~$", "$")):
                if normalize_for_match(entry.name) == norm_target:
                    return entry
    except Exception:
        pass

    # 无候选时新建，带异常自愈
    try:
        plain.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        plain = desk / f"{clean_name}_主体"
        plain.mkdir(parents=True, exist_ok=True)

    return plain
