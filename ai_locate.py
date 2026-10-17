#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@AI-ANCHOR: [AI-LOCATE-RADAR] 桌面端 AI 0.01秒 极速行号定位雷达 (GTH V3.0)
用法:
  1. python ai_locate.py                 -> 打印全项目所有 @AI-ANCHOR 锚点的【实时文件路径 + 精确起止行号】
  2. python ai_locate.py <关键词>        -> 按关键词搜索锚点、函数/类名，直接返回精确行号区间
  3. python ai_locate.py <关键词> --show -> 直接在终端打印出对应代码块内容（自带行号），免去再次调用 view_file！
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SCAN_FILES = [
    "app_main.py",
    "engine/models.py",
    "engine/addr_parser.py",
    "engine/id_validator.py",
    "engine/ocr_cleaner.py",
    "engine/ocr_rules_loader.py",
    "engine/scope_search.py",
    "engine/subject_dir.py",
    "engine/history_manager.py",
    "engine/zhugai_img_exporter.py",
    "engine/docx_engine.py",
    "engine/doc_wash_engine.py",
    "engine/q_parser.py",
    "engine/q_compiler.py",
    "engine/win_os_service.py",
    "ui/api_bridge.py",
    "ui/workbench.html",
    "ui/css/brutalist.css",
    "ui/css/base.css",
    "ui/css/workbench.css",
    "ui/css/panels.css",
    "ui/js/state.js",
    "ui/js/config_meta.js",
    "ui/js/tab_workbench.js",
    "ui/js/tab_scope.js",
    "ui/js/tab_docs.js",
    "ui/js/tab_config.js",
    "ui/js/tab_history.js",
    "ui/js/app.js",
    "tests/fast_check.py",
    "config/portal_profile_371300.json",
    "config/ocr_rules.json",
    "config/golden_packages.json",
    "config/q_steps_dsl.json",
]

ANCHOR_RE = re.compile(r"@AI-ANCHOR:\s*\[([^\]]+)\]\s*(.*)")
DEF_RE = re.compile(
    r"^\s*(?:async\s+def|def|class|async\s+function|function)\s+([A-Za-z0-9_\$]+)"
    r"|^\s*(?:window\.[A-Za-z0-9_\$]+\s*=\s*(?:async\s*)?function)"
)


def scan_file(rel_path: str):
    fpath = ROOT / rel_path
    if not fpath.exists():
        return [], []
    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
    total = len(lines)
    anchors = []
    defs = []
    for idx, line in enumerate(lines, start=1):
        m = ANCHOR_RE.search(line)
        if m:
            key = m.group(1).strip()
            desc = m.group(2).strip().rstrip("-->").rstrip("*/").strip()
            anchors.append({"key": key, "desc": desc, "start": idx, "end": total, "file": rel_path})
        dm = DEF_RE.search(line)
        if dm:
            name = dm.group(1) or line.strip().split("=")[0].strip()
            defs.append({"name": name, "line": idx, "file": rel_path, "preview": line.strip()[:80]})
    for i in range(len(anchors) - 1):
        anchors[i]["end"] = anchors[i + 1]["start"] - 1
    return anchors, defs


def print_code_slice(rel_path: str, start: int, end: int):
    fpath = ROOT / rel_path
    lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
    s = max(1, start)
    e = min(len(lines), end)
    print(f"\n==================== {rel_path} (Lines {s}..{e} / Total {len(lines)}) ====================")
    for i in range(s, e + 1):
        print(f"{i:4d} | {lines[i-1]}")
    print("=" * 78)


def main():
    args = [a for a in sys.argv[1:] if a != "--show"]
    show_code = "--show" in sys.argv[1:]
    query = " ".join(args).strip().lower()

    all_anchors = []
    all_defs = []
    for rel in SCAN_FILES:
        a_list, d_list = scan_file(rel)
        all_anchors.extend(a_list)
        all_defs.extend(d_list)

    if not query:
        print("================================================================================")
        print("⚡ GTH V3.0 桌面端 AI 极速定位雷达 (实时行号地图 - 0.01s)")
        print("用法: python ai_locate.py <关键词> [--show]")
        print("================================================================================")
        cur_file = None
        for a in all_anchors:
            if a["file"] != cur_file:
                cur_file = a["file"]
                total_lines = len((ROOT / cur_file).read_text(encoding="utf-8", errors="ignore").splitlines())
                print(f"\n📁 {cur_file} (共 {total_lines} 行)")
            span = f"L{a['start']}..L{a['end']}"
            print(f"   🎯 [{a['key']:<26}] {span:<12} | {a['desc']}")
        print("\n💡 提示: 运行 `python ai_locate.py <锚点名或中文关键词> --show` 可直接打印对应代码块！")
        return

    matched_anchors = [
        a for a in all_anchors
        if query in a["key"].lower() or query in a["desc"].lower() or query in a["file"].lower()
    ]
    matched_defs = [
        d for d in all_defs
        if query in d["name"].lower() or query in d["preview"].lower()
    ]

    print(f"🔍 搜索关键词: '{query}' (匹配到 {len(matched_anchors)} 个锚点区块, {len(matched_defs)} 个函数/类定义)")
    for a in matched_anchors:
        print(f"  🎯 锚点 [{a['key']}] -> {a['file']} : Lines {a['start']}..{a['end']} ({a['end'] - a['start'] + 1} 行) | {a['desc']}")
        if show_code:
            print_code_slice(a["file"], a["start"], min(a["end"], a["start"] + 120))

    for d in matched_defs:
        print(f"  🔧 定义 {d['name']} -> {d['file']} : Line {d['line']} | {d['preview']}")
        if show_code and not matched_anchors:
            print_code_slice(d["file"], max(1, d["line"] - 2), d["line"] + 45)


if __name__ == "__main__":
    main()
