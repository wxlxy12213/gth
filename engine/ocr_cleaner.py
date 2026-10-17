# @AI-ANCHOR: [OCR-CLEANER-CORE] 微信/OCR 乱序文本脱水清洗、双身份证分流与字号提取引擎
"""ocr_cleaner.py - 办件文本要素识别与规范化清洗流水线编排器 (GTH V2 模块化版)。

架构说明：
- 字典与关键词配置已解耦至 `config/ocr_rules.json` 与 `engine/ocr_rules_loader.py`
- 身份证校验已解耦至 `engine/id_validator.py`
- 地址清洗与倒置拼接已解耦至 `engine/addr_parser.py`
- 本文件仅负责四阶消元流水线编排，并 100% 保持原版 API 导出兼容。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .addr_parser import (
    clean_address_text,
    extract_town_and_rest,
    stitch_address_pieces,
)
from .id_validator import validate_id_card_details, verify_id_card
from .models import ApplicantState, ConfidenceLevel
from .ocr_rules_loader import (
    LANDLORD_KEYWORDS,
    OWNER_KEYWORDS,
    SELF_REFERENTIAL_WORDS,
    SHOP_SUFFIXES,
    SUPERVISOR_MAP,
    TOWN_ALIASES,
    TOWNS_LIST,
)

__all__ = [
    "TOWNS_LIST",
    "TOWN_ALIASES",
    "SUPERVISOR_MAP",
    "OWNER_KEYWORDS",
    "LANDLORD_KEYWORDS",
    "SELF_REFERENTIAL_WORDS",
    "verify_id_card",
    "validate_id_card_details",
    "clean_address_text",
    "extract_town_and_rest",
    "clean_raw_ocr",
]


def _extract_bounded_tag_value(
    text: str,
    prefix_patterns: tuple[str, ...],
    stop_patterns: tuple[str, ...],
    max_len: int = 40,
) -> tuple[str, str, int, int] | None:
    """带显式边界截断的标签提取器，防止贪婪越界吞噬后序要素。"""
    for pfx in prefix_patterns:
        m = re.search(pfx, text)
        if not m:
            continue
        start_pos = m.end()
        remaining = text[start_pos : start_pos + max_len]
        stop_indices: list[int] = []
        nl_match = re.search(r"[\r\n,，；;。]", remaining)
        if nl_match:
            stop_indices.append(nl_match.start())
        for sp in stop_patterns:
            sm = re.search(sp, remaining)
            if sm:
                stop_indices.append(sm.start())
        cut_len = min(stop_indices) if stop_indices else len(remaining)
        val = remaining[:cut_len].strip()
        val = re.sub(r"^[\"\'“‘\s]+|[\"\'”’\s]+$", "", val)
        if val:
            return val, m.group(0), m.start(), start_pos + cut_len
    return None


def _extract_and_pair_ids(raw: str, warnings: list[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, bool, bool, list[dict[str, Any]]]:
    """提取所有 18 位身份证号，并通过最近角色标签距离算法绑定经营者与房东。"""
    id_records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # 优先匹配严格由 18 位数字/X 组成、中间允许空格/Tab 间隙的候选（避免贪婪跨越到相邻手机号）
    for m in re.finditer(r"(?<![0-9])((?:[0-9Xx][ \t]*){17}[0-9Xx])(?![0-9])", raw):
        cand_raw = m.group(1)
        toks = cand_raw.split()
        if len(toks) > 1 and re.fullmatch(r"1[3-9]\d{9}", toks[0]):
            continue
        clean_cand = re.sub(r"\s+", "", cand_raw).upper()
        if len(clean_cand) == 18 and re.match(r"^[0-9]{17}[0-9X]$", clean_cand):
            if clean_cand in seen_ids:
                continue
            seen_ids.add(clean_cand)
            is_val, val_msg = validate_id_card_details(clean_cand)
            id_records.append({
                "id": clean_cand,
                "raw_snippet": cand_raw,
                "valid": is_val,
                "val_msg": val_msg,
                "pos": m.start(1),
            })

    if not id_records:
        for m in re.finditer(r"(?<![0-9])([0-9]{17}[0-9Xx])(?![0-9])", raw):
            cand = m.group(1).upper()
            if cand in seen_ids:
                continue
            seen_ids.add(cand)
            is_val, val_msg = validate_id_card_details(cand)
            id_records.append({
                "id": cand,
                "raw_snippet": m.group(1),
                "valid": is_val,
                "val_msg": val_msg,
                "pos": m.start(),
            })

    for r in id_records:
        pos = r["pos"]
        prefix_text = raw[:pos]
        best_owner_dist = min(
            (pos - (prefix_text.rfind(kw) + len(kw)) for kw in OWNER_KEYWORDS if prefix_text.rfind(kw) != -1 and pos >= prefix_text.rfind(kw) + len(kw)),
            default=999999,
        )
        best_ll_dist = min(
            (pos - (prefix_text.rfind(kw) + len(kw)) for kw in LANDLORD_KEYWORDS if prefix_text.rfind(kw) != -1 and pos >= prefix_text.rfind(kw) + len(kw)),
            default=999999,
        )
        r["is_owner"] = (best_owner_dist < 80 or best_ll_dist < 80) and (best_owner_dist < best_ll_dist)
        r["is_landlord"] = (best_owner_dist < 80 or best_ll_dist < 80) and (best_ll_dist < best_owner_dist)

    owner_rec = None
    landlord_rec = None
    explicit_owner_tag = False
    explicit_ll_tag = False

    for r in id_records:
        if r["is_owner"] and owner_rec is None:
            owner_rec, explicit_owner_tag = r, True
        elif r["is_landlord"] and landlord_rec is None:
            landlord_rec, explicit_ll_tag = r, True

    remaining = [r for r in id_records if r is not owner_rec and r is not landlord_rec]
    if owner_rec and not landlord_rec and remaining:
        landlord_rec = remaining[0]
    elif landlord_rec and not owner_rec and remaining:
        owner_rec = remaining[0]

    if not owner_rec and not landlord_rec:
        if len(id_records) >= 2:
            owner_rec, landlord_rec = id_records[0], id_records[1]
        elif len(id_records) == 1:
            owner_rec = id_records[0]

    if len(id_records) > 2:
        warnings.append(f"检测到输入中包含 {len(id_records)} 个身份证号码，已忽略其余 {len(id_records) - 2} 个多余号码")

    return owner_rec, landlord_rec, explicit_owner_tag, explicit_ll_tag, id_records


def _split_conjoined_id_and_phone(text: str) -> str:
    """自动拆解无任何空格、紧挨在一起的 29 位连体输入（18位身份证 + 11位手机号 或 11位手机号 + 18位身份证）。"""
    def _repl_id_phone(m: re.Match) -> str:
        cand_id = m.group(1).upper()
        phone = m.group(2)
        is_val, _ = validate_id_card_details(cand_id)
        if is_val:
            return f"{m.group(1)} {phone}"
        birth = cand_id[6:14]
        if re.match(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$", birth):
            return f"{m.group(1)} {phone}"
        return m.group(0)

    text = re.sub(r"(?<![0-9])([1-9]\d{16}[0-9Xx])(1[3-9]\d{9})(?![0-9])", _repl_id_phone, text)

    def _repl_phone_id(m: re.Match) -> str:
        phone = m.group(1)
        cand_id = m.group(2).upper()
        is_val, _ = validate_id_card_details(cand_id)
        if is_val:
            return f"{phone} {m.group(2)}"
        birth = cand_id[6:14]
        if re.match(r"^(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])$", birth):
            return f"{phone} {m.group(2)}"
        return m.group(0)

    text = re.sub(r"(?<![0-9])(1[3-9]\d{9})([1-9]\d{16}[0-9Xx])(?![0-9])", _repl_phone_id, text)
    return text


# @AI-ANCHOR: [OCR-MAIN-PIPELINE] OCR 文本全流程清洗与经营者/房东角色配对主入口
def clean_raw_ocr(text: str) -> ApplicantState:
    """执行办件文本结构化清洗与要素提取全流程。"""
    state = ApplicantState()
    if not text:
        return state

    raw = unicodedata.normalize("NFKC", text.strip())[:20000]
    raw = re.sub(r"[ \t\u3000\xa0]+", " ", raw)
    raw = _split_conjoined_id_and_phone(raw)

    confidence: dict[str, str] = {}
    warnings: list[str] = []

    # ---------------- 阶 1: 强特征锚点提取与角色配对 ----------------
    ll_stop = (r"身份证", r"证件", r"电话", r"手机", r"住址", r"地址", r"经营者", r"申请人", r"乙方", r"承租", r"[0-9]")
    ll_res = _extract_bounded_tag_value(
        raw,
        prefix_patterns=(r"(?:房东|出租人|出租方|出租者|产权人|甲方|业主)(?:姓名)?[ \t:：]*",),
        stop_patterns=ll_stop,
        max_len=15,
    )
    landlord_extracted = ll_res[0] if (ll_res and ll_res[0] not in SELF_REFERENTIAL_WORDS) else ""

    owner_rec, landlord_rec, explicit_owner_tag, explicit_ll_tag, id_records = _extract_and_pair_ids(raw, warnings)

    if owner_rec:
        state.owner_id = owner_rec["id"]
        if owner_rec["valid"]:
            confidence["owner_id"] = ConfidenceLevel.GREEN.value if (explicit_owner_tag or len(id_records) == 1) else ConfidenceLevel.AMBER.value
        else:
            confidence["owner_id"] = ConfidenceLevel.RED.value
            warnings.append(f"经营者身份证号不合规: {owner_rec['val_msg']}")
    else:
        confidence["owner_id"] = ConfidenceLevel.RED.value

    if landlord_rec:
        state.landlord_id = landlord_rec["id"]
        state.usage = "lease"
        if landlord_rec["valid"]:
            confidence["landlord_id"] = ConfidenceLevel.GREEN.value if explicit_ll_tag else ConfidenceLevel.AMBER.value
        else:
            confidence["landlord_id"] = ConfidenceLevel.RED.value
            warnings.append(f"房东身份证号不合规: {landlord_rec['val_msg']}")

    if landlord_extracted and landlord_extracted != state.owner_name:
        state.landlord_name = landlord_extracted
        state.usage = "lease"
        confidence["landlord_name"] = ConfidenceLevel.GREEN.value

    # 消元身份证与手机邮箱（精确匹配18位身份证及前缀标签，避免贪婪吃掉相邻手机号前缀）
    erased_text = re.sub(
        r"(?:公民身份号码|居民身份证(?:号码|号)?|身份证(?:号码|号)?|证件(?:号码|号)?|证号)[ \t:：]*(?:[0-9Xx][ \t]*){17}[0-9Xx](?![0-9])",
        " ",
        raw,
    )
    for r in id_records:
        erased_text = erased_text.replace(r["raw_snippet"], " ").replace(r["id"], " ")

    phone_pattern = r"(?<!\d)(1[3-9]\d{9})(?!\d)"
    phone_matches = list(re.finditer(phone_pattern, erased_text))
    if phone_matches:
        owner_phone = phone_matches[0].group(1)
        if len(phone_matches) >= 2 and landlord_rec:
            for pm in phone_matches:
                pre = erased_text[max(0, pm.start() - 30) : pm.start()]
                if not any(kw in pre for kw in LANDLORD_KEYWORDS) and any(kw in pre for kw in OWNER_KEYWORDS):
                    owner_phone = pm.group(1)
        state.phone = owner_phone
        confidence["phone"] = ConfidenceLevel.GREEN.value
    else:
        confidence["phone"] = ConfidenceLevel.RED.value

    m_email = re.search(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", erased_text)
    if m_email:
        state.email = m_email.group(1).strip()
        confidence["email"] = ConfidenceLevel.GREEN.value
        erased_text = erased_text.replace(m_email.group(0), " ")
    elif state.phone:
        state.email = f"{state.phone}@tel.com"
        confidence["email"] = ConfidenceLevel.AMBER.value

    erased_text = re.sub(r"(?:联系电话|移动电话|手机(?:号码|号)?|电话(?:号码|号)?|联系方式)[ \t:：]*" + phone_pattern, " ", erased_text)
    erased_text = re.sub(phone_pattern, " ", erased_text)

    # ---------------- 阶 2: 固定噪声词条剥离与姓名锁定 ----------------
    erased_text = re.sub(r"(?:19|20)\d{2}[年\.\-]\s*\d{1,2}\s*[月\.\-]?\s*\d{1,2}\s*日?", " ", erased_text)
    erased_text = re.sub(r"民族[ \t:：]*(?:汉|回|满|蒙古|朝鲜|壮|苗|维吾尔|彝|藏|布依|侗|瑶|白|土家|哈尼|哈萨克|傣|黎|傈僳|佤|畲|高山|拉祜|水|东乡|纳西|景颇|柯尔克孜|土|达斡尔|仫佬|羌|布朗|撒拉|毛南|仡佬|锡伯|阿昌|普米|塔吉克|怒|乌孜别克|俄罗斯|鄂温克|德昂|保安|裕固|京|塔塔尔|独龙|鄂伦春|赫哲|门巴|珞巴|基诺)?族?", " ", erased_text)
    erased_text = re.sub(r"性别[ \t:：]*[男女]?", " ", erased_text)
    erased_text = re.sub(r"(?:公民身份号码|居民身份证|签发机关[ \t:：]*[^\s\r\n]{2,20}|有效期限[ \t:：]*[\d\.\-至永久]{4,25}|有效日期[ \t:：]*[\d\.\-至永久]{4,25}|出生[ \t:：]?)", " ", erased_text)

    name_stop_pat = r"(?:身份证|证件|电话|手机|住址|地址|场所|房屋|坐落|门牌|现住|户籍|村委会|居委会|街道办|\d)"
    owner_name = ""

    m_owner = re.search(
        r"(?:经营者(?:姓名)?|申请人(?:姓名)?|负责人(?:姓名)?|本人(?:姓名)?|乙方(?:姓名)?)[ \t:：]*([\u4e00-\u9fa5]{2,15}(?:[·•・\.\u00b7\u2022\u30fb][\u4e00-\u9fa5]{1,15})*)",
        erased_text,
    )
    if m_owner:
        cand = re.sub(r"[•・\.\u2022\u30fb]", "·", re.split(name_stop_pat, m_owner.group(1).strip())[0].strip())
        if len(cand) >= 2 and cand != state.landlord_name:
            owner_name = cand

    if not owner_name:
        for m_n in re.finditer(
            r"(?<!出租人)(?<!房东)(?<!产权人)(?<!甲方)(?<!业主)(?:姓名)[ \t:：]*([\u4e00-\u9fa5]{2,15}(?:[·•・\.\u00b7\u2022\u30fb][\u4e00-\u9fa5]{1,15})*)",
            erased_text,
        ):
            cand = re.sub(r"[•・\.\u2022\u30fb]", "·", re.split(name_stop_pat, m_n.group(1).strip())[0].strip())
            if len(cand) >= 2 and cand != state.landlord_name:
                owner_name = cand
                break

    if not owner_name:
        m_pre = re.search(r"([\u4e00-\u9fa5]{2,6})[ \t:：]*姓名", erased_text)
        if m_pre:
            cand = re.sub(r"[•・\.\u2022\u30fb]", "·", m_pre.group(1).strip())
            if len(cand) >= 2 and cand != state.landlord_name:
                owner_name = cand

    if owner_name:
        state.owner_name = owner_name
        confidence["owner_name"] = ConfidenceLevel.GREEN.value
        erased_text = re.sub(r"(?:姓名|经营者(?:姓名)?|申请人(?:姓名)?|负责人(?:姓名)?|本人(?:姓名)?)[ \t:：]*" + re.escape(owner_name), " ", erased_text)
        erased_text = re.sub(re.escape(owner_name) + r"[ \t:：]*姓名", " ", erased_text)

    if state.landlord_name:
        erased_text = re.sub(r"(?:房东|出租人|出租方|出租者|产权人|甲方|业主)(?:姓名)?[ \t:：]*" + re.escape(state.landlord_name), " ", erased_text)
    erased_text = re.sub(r"(?:姓名|经营者|申请人|负责人|本人|房东|出租人|出租方|产权人|甲方|乙方|业主)[ \t:：]*", " ", erased_text)

    # ---------------- 阶 3: 提取店铺字号、显式经营场所与经营范围 ----------------
    shop_res = _extract_bounded_tag_value(
        erased_text,
        prefix_patterns=(r"(?:字号叫|店名叫|字号|店名|商号|名称|招牌)[ \t:：]*",),
        stop_patterns=(r"姓名", r"经营者", r"申请人", r"身份证", r"电话", r"手机", r"住址", r"地址", r"场所", r"房屋", r"[0-9]{6,}"),
        max_len=35,
    )
    if shop_res:
        state.shop_name = shop_res[0].strip()
        confidence["shop_name"] = ConfidenceLevel.GREEN.value
        erased_text = erased_text[: shop_res[2]] + " " + erased_text[shop_res[3] :]
    else:
        suffix_pat = "|".join(re.escape(sfx) for sfx in SHOP_SUFFIXES)
        m_shop = re.search(rf"((?:郯城县)?[\u4e00-\u9fa50-9a-zA-Z（）\(\)]{{2,25}}(?:{suffix_pat}))", erased_text)
        if m_shop:
            cand_shop = m_shop.group(1).strip()
            if cand_shop not in (state.owner_name, state.landlord_name) and not any(cand_shop.endswith(d) for d in ("东", "西", "南", "北", "旁", "对", "前", "后")):
                state.shop_name = cand_shop
                confidence["shop_name"] = ConfidenceLevel.AMBER.value
                erased_text = erased_text.replace(cand_shop, " ")

    explicit_shop_addr = ""
    shop_addr_res = _extract_bounded_tag_value(
        erased_text,
        prefix_patterns=(r"(?:经营场所|门店地址|门面地址|店址)[ \t:：]*",),
        stop_patterns=(r"字号", r"店名", r"姓名", r"经营者", r"房东", r"出租", r"电话"),
        max_len=60,
    )
    if shop_addr_res:
        explicit_shop_addr = clean_address_text(shop_addr_res[0])
        erased_text = erased_text[: shop_addr_res[2]] + " " + erased_text[shop_addr_res[3] :]

    m_scope = re.search(r"(?:经营范围|业务范围|主营项目|主营业务|许可项目|一般项目)[ \t:：]*([\s\S]+)", erased_text)
    if m_scope:
        cand_scope = m_scope.group(1)
        m_stop = re.search(r"(?:\r?\n|\s+)(?:经营者|姓名|申请人|负责人|身份证|电话|手机|字号|店名|商号|住址|地址|经营场所|详细地址|房屋|房东|出租)[ \t:：]", cand_scope)
        if m_stop:
            cand_scope = cand_scope[: m_stop.start()]
        state.raw_scope_text = cand_scope.strip()
        full_seg = m_scope.group(0)[: len(m_scope.group(0)) - len(m_scope.group(1))] + cand_scope
        erased_text = erased_text.replace(full_seg, " ")
    else:
        segs = re.findall(r"[\u4e00-\u9fa5（）\(\)]{2,20}(?:销售|批发|零售|服务|制造|加工|维修|咨询)", erased_text)
        if len(segs) >= 2:
            state.raw_scope_text = "；".join(segs)
            for seg in segs:
                erased_text = erased_text.replace(seg, " ")

    # ---------------- 阶 4: 地址提取与行政层级规范化拼接 ----------------
    addr_split_tag = "@@@ADDR_SPLIT@@@"
    addr_erased = re.sub(r"(?:住址|地址|经营场所|详细地址|户籍地址|门牌|坐落于?)[ \t:：]*", addr_split_tag, erased_text)
    raw_pieces = [p.strip() for p in re.split(r"[\r\n；;。]+|[，,]{2,}|" + addr_split_tag, addr_erased) if p.strip()]

    if not state.owner_name:
        for p in raw_pieces:
            if p in (state.landlord_name, state.shop_name):
                continue
            norm_p = re.sub(r"[•・\.\u2022\u30fb]", "·", p)
            if re.fullmatch(r"[\u4e00-\u9fa5]{2,15}(?:·[\u4e00-\u9fa5]{1,15})*", norm_p):
                if not any(k in norm_p for k in ("省", "市", "县", "区", "镇", "乡", "街道", "村", "号", "路", "街", "室", "铺", "档", "店", "部", "所", "超市")):
                    state.owner_name = norm_p
                    confidence["owner_name"] = ConfidenceLevel.AMBER.value
                    break
        if not state.owner_name:
            confidence["owner_name"] = ConfidenceLevel.RED.value

    addr_pieces = [p for p in raw_pieces if p not in (state.owner_name, state.landlord_name, state.shop_name)]
    stitched_address, is_stitched, tail_only = stitch_address_pieces(addr_pieces, warnings)

    if stitched_address:
        state.id_addr = stitched_address
        town, rest = extract_town_and_rest(stitched_address)
        state.town = town
        state.street_rest = rest

        if town and town in SUPERVISOR_MAP:
            state.supervisor = SUPERVISOR_MAP[town]
            confidence["supervisor"] = ConfidenceLevel.GREEN.value
            confidence["town"] = ConfidenceLevel.GREEN.value
            confidence["id_addr"] = ConfidenceLevel.AMBER.value if (is_stitched or tail_only) else ConfidenceLevel.GREEN.value
        elif town:
            confidence["town"] = ConfidenceLevel.GREEN.value
            confidence["supervisor"] = ConfidenceLevel.AMBER.value
            confidence["id_addr"] = ConfidenceLevel.AMBER.value
        else:
            confidence["town"] = ConfidenceLevel.RED.value
            confidence["id_addr"] = ConfidenceLevel.AMBER.value
    else:
        confidence["id_addr"] = ConfidenceLevel.RED.value

    if explicit_shop_addr:
        state.shop_address = explicit_shop_addr
        confidence["shop_address"] = ConfidenceLevel.GREEN.value
    else:
        state.shop_address = state.id_addr
        confidence["shop_address"] = confidence.get("id_addr", ConfidenceLevel.AMBER.value)

    state.agent_addr = state.id_addr
    state.confidence = confidence
    state.warnings = warnings
    return state
