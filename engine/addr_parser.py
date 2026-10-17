# @AI-ANCHOR: [ADDR-PARSER-CORE] 畸变地址消噪、跨行倒置缝合与乡镇-监管所拓扑锁定
"""addr_parser.py - 地址文本清洗、乡镇别名识别与跨行行政拓扑拼接模块。"""
from __future__ import annotations

import re
from .ocr_rules_loader import (
    ADDRESS_TAIL_KEYWORDS,
    CITY_COUNTY_PREFIXES,
    TERMINAL_MARKERS,
    TOWN_ALIASES,
    TOWNS_LIST,
)

# 预编译高频正则，消除重复编译开销
_RE_BRACKETS = re.compile(r"[【】\[\]\(\)（）\"\'`]")
_RE_MULTI_PUNCT = re.compile(r"[，,、；;]{2,}")
_RE_CJK_SPACE = re.compile(r"(?<=[\u4e00-\u9fa5])\s+(?=[\u4e00-\u9fa5\d])")
_RE_DIGIT_SPACE = re.compile(r"(?<=[\d])\s+(?=[\u4e00-\u9fa5])")
_RE_DOOR_NUM = re.compile(r"\s*([号室铺档院层\-#])\s*")
_RE_ANY_PUNCT = re.compile(r"[，,、；;。]+")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_HAS_NUMBER_DOOR = re.compile(r"\d+号?")
_RE_END_DOOR = re.compile(r"\d+号?(-\d+)?$")


def clean_address_text(addr: str) -> str:
    """消除地址文本中的 OCR 噪声字符、畸变标点与冗余空白（抗二次回溯）。"""
    if not addr:
        return ""
    s = addr[:500].strip()
    s = _RE_BRACKETS.sub("", s)
    s = _RE_MULTI_PUNCT.sub("", s)
    s = _RE_CJK_SPACE.sub("", s)
    s = _RE_DIGIT_SPACE.sub("", s)
    s = _RE_DOOR_NUM.sub(r"\1", s)
    s = _RE_ANY_PUNCT.sub("", s)
    s = _RE_WHITESPACE.sub("", s)
    return s.strip("，,。；;：: \t\r\n")


def extract_town_and_rest(address: str) -> tuple[str, str]:
    """从地址中提取乡镇名与后续街路门牌（支持别名展开与最早出现优先）。"""
    cleaned = clean_address_text(address)
    for prefix in CITY_COUNTY_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    candidates: list[tuple[int, str, int]] = []
    for town in TOWNS_LIST:
        idx = cleaned.find(town)
        if idx != -1:
            candidates.append((idx, town, len(town)))

    for alias, standard_town in TOWN_ALIASES.items():
        idx = cleaned.find(alias)
        if idx != -1:
            candidates.append((idx, standard_town, len(alias)))

    if candidates:
        candidates.sort(key=lambda c: (c[0], -c[2]))
        best_idx, best_town, match_len = candidates[0]
        rest = clean_address_text(cleaned[best_idx + match_len:])
        return best_town, rest

    return "", cleaned


def is_administrative_head(text: str) -> bool:
    """判定文本是否包含明确行政区划前缀（排除幸福小区、商贸中心等）。"""
    if any(pfx in text for pfx in ("山东省", "临沂市", "郯城县")):
        return True
    return any(tw in text for tw in TOWNS_LIST) or any(tw in text for tw in TOWN_ALIASES)


def is_address_tail(text: str) -> bool:
    """判定文本是否包含村/庄/路/街/号/室/铺等有效尾部特征。"""
    return bool(
        any(kw in text for kw in ADDRESS_TAIL_KEYWORDS)
        or _RE_HAS_NUMBER_DOOR.search(text)
    )


def stitch_address_pieces(addr_pieces: list[str], warnings: list[str]) -> tuple[str, bool, bool]:
    """将多段乱序/倒置的地址碎片按行政层级规范缝合。
    返回: (stitched_address, is_stitched, tail_only)
    """
    head_pieces: list[str] = []
    tail_pieces: list[str] = []

    for p in addr_pieces:
        cl_p = clean_address_text(p)
        if not cl_p:
            continue
        town_in_p, _ = extract_town_and_rest(cl_p)
        head_match = is_administrative_head(cl_p)
        if (
            head_match
            and not cl_p.startswith(("山东省", "临沂市", "郯城县"))
            and town_in_p
            and not cl_p.startswith(town_in_p)
        ):
            # 同块内部倒置：如“前赵庄村45号 山东省临沂市郯城县马头镇”
            for pfx in CITY_COUNTY_PREFIXES:
                if pfx in cl_p:
                    p_idx = cl_p.find(pfx)
                    head_pieces.append(clean_address_text(cl_p[p_idx:]))
                    tail_pieces.append(clean_address_text(cl_p[:p_idx]))
                    break
            else:
                t_idx = cl_p.find(town_in_p)
                head_pieces.append(clean_address_text(cl_p[t_idx:]))
                tail_pieces.append(clean_address_text(cl_p[:t_idx]))
        elif head_match:
            head_pieces.append(cl_p)
        elif is_address_tail(cl_p):
            tail_pieces.append(cl_p)
        else:
            warnings.append(f"忽略未能识别的地址碎片杂质: '{cl_p}'")

    if head_pieces and tail_pieces:
        head = head_pieces[0]
        tail = tail_pieces[0]
        is_terminal = head.endswith(tuple(TERMINAL_MARKERS)) or bool(_RE_END_DOOR.search(head))
        if not is_terminal and (tail != head and not head.endswith(tail)):
            return clean_address_text(head + tail), True, False
        return clean_address_text(head), False, False
    if head_pieces:
        if len(head_pieces) >= 2:
            return clean_address_text("".join(head_pieces)), True, False
        return clean_address_text(head_pieces[0]), False, False
    if tail_pieces:
        return clean_address_text(tail_pieces[0]), False, True
    return "", False, False
