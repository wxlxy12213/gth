"""id_validator.py - 18位公民身份号码 ISO 7064 MOD 11-2 模算与出生日期历法核验模块。"""
from __future__ import annotations

import re
from datetime import datetime

# ISO 7064:1983.MOD 11-2 常量
_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_ID_CHECK_CODES = ("1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2")
_RE_ID18 = re.compile(r"^[0-9]{17}[0-9X]$")


def verify_id_card(id18: str) -> bool:
    """ISO 7064 MOD 11-2 确定性模算核验 + 出生日期真实性双重核验。"""
    valid, _ = validate_id_card_details(id18)
    return valid


def validate_id_card_details(id18: str) -> tuple[bool, str]:
    """详细校验 18 位身份证模算与出生日期合理性。"""
    s = id18.strip().upper()
    if len(s) != 18 or not _RE_ID18.match(s):
        return False, "身份证号长度或格式不符合 18 位规则"

    # 1. 模 11 确定性模算校验
    total = sum(int(s[i]) * _ID_WEIGHTS[i] for i in range(17))
    expected = _ID_CHECK_CODES[total % 11]
    if s[17] != expected:
        return False, f"身份证校验位不符（实测为 {s[17]}，应为 {expected}）"

    # 2. 出生日期历法合法性核验（排查 20030231 等非法日期）
    birth_str = s[6:14]
    try:
        birth_date = datetime.strptime(birth_str, "%Y%m%d")
        now = datetime.now()
        if not (1900 <= birth_date.year <= now.year):
            return False, f"出生年份 {birth_date.year} 超出合理范围"
    except ValueError:
        return False, f"身份证出生日期 {birth_str} 不符合公历日期"

    return True, ""
