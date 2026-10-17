# @AI-ANCHOR: [MODELS-STATE-SCHEMA] 核心业务数据契约 ScopeItem 与 ApplicantState
"""models.py - 办件状态核心数据模型与三色置信度契约（支持积木式自由步骤组合）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ConfidenceLevel(str, Enum):
    """三色核验置信度评级。"""
    GREEN = "green"   # 强特征校验完全通过 (如 18 位模算、11位有效手机)
    AMBER = "amber"   # 经启发式规则重组提取，建议人工复核
    RED = "red"       # 核心要素缺失或强校验未通过，必须干预


class UsageType(str, Enum):
    """经营场所使用权属类型。"""
    OWN = "own"       # 自有产权
    LEASE = "lease"   # 租赁门面
    FREE = "free"     # 无偿使用


class RunMode(str, Enum):
    """申报填报执行模式。"""
    TO_END = "to_end"             # 连续或按积木勾选步骤执行
    SINGLE_STEP = "single_step"   # 仅执行当前指定单步
    CUSTOM_BLOCKS = "custom"      # 自由积木组合执行


@dataclass
class FieldStatus:
    """带置信度评级的字段包装。"""
    value: str = ""
    level: ConfidenceLevel = ConfidenceLevel.RED
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "level": self.level.value if isinstance(self.level, ConfidenceLevel) else str(self.level),
            "message": self.message,
        }


@dataclass
class ScopeItem:
    """经营范围规范条目。"""
    code: str
    name: str
    is_primary: bool = False
    is_permit: bool = False
    excluded: bool = False  # 反向做减法：True 表示已剔除/灰化划线
    is_native_existing: bool = False  # True 表示为原生已有项（已在套餐中剔除，不重复在网站点选）

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "is_primary": self.is_primary,
            "is_permit": self.is_permit,
            "excluded": self.excluded,
            "is_native_existing": self.is_native_existing,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScopeItem:
        return cls(
            code=data.get("code", ""),
            name=data.get("name", ""),
            is_primary=bool(data.get("is_primary", False)),
            is_permit=bool(data.get("is_permit", False)),
            excluded=bool(data.get("excluded", False)),
            is_native_existing=bool(data.get("is_native_existing", False)),
        )


@dataclass
# @AI-ANCHOR: [MODELS-APPLICANT-STATE] 办件全要素状态类、积木步骤过滤与 Stage 自动推导
class ApplicantState:
    """个体户申报全景办件状态树 (State Tree)。"""
    schema_version: int = 2

    # 经营者基础要素
    owner_name: str = ""
    owner_id: str = ""
    phone: str = ""
    email: str = ""
    id_addr: str = ""

    # 经营场所要素
    shop_name: str = ""
    shop_address: str = ""
    town: str = ""
    street_rest: str = ""
    house_use: str = "住宅"
    usage: str = "own"  # own, lease, free
    landlord_name: str = ""
    landlord_id: str = ""
    cert_name: str = "房屋使用证明"
    supervisor: str = ""
    agent_addr: str = ""
    capital: str = "1"

    # 经营范围要素
    active_package: str = "百货店"
    raw_scope_text: str = ""  # 原生经营范围原始文本
    scopes: list[ScopeItem] = field(default_factory=list)

    # 步骤切片与积木式自由发射控制
    step_start: int = 1      # 1~5
    step_end: int = 5        # 1~5
    run_mode: str = "to_end" # 'to_end', 'single_step', 'custom'
    enabled_steps: list[int] = field(default_factory=list)  # 非空时按所选积木步骤集合执行 (如 [1, 2, 4, 5])

    # 三色核验状态索引
    confidence: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """步骤与枚举合法性归一化守卫。"""
        if not (1 <= self.step_start <= 5):
            self.step_start = max(1, min(5, self.step_start))
        if not (1 <= self.step_end <= 5):
            self.step_end = max(1, min(5, self.step_end))
        if self.step_start > self.step_end:
            self.step_end = self.step_start

        if self.enabled_steps:
            clean_steps = sorted({int(x) for x in self.enabled_steps if 1 <= int(x) <= 5})
            self.enabled_steps = clean_steps
            if clean_steps:
                self.step_start = clean_steps[0]
                self.step_end = clean_steps[-1]

        if isinstance(self.usage, UsageType):
            self.usage = self.usage.value
        elif self.usage not in ("own", "lease", "free"):
            self.usage = "own"

        if isinstance(self.run_mode, RunMode):
            self.run_mode = self.run_mode.value
        elif self.run_mode not in ("to_end", "single_step", "custom"):
            self.run_mode = "to_end"

    def get_active_steps(self) -> list[int]:
        """计算当前实际应执行的步骤编号有序列表 (1~5)。"""
        if self.run_mode == "single_step":
            return [max(1, min(5, int(self.step_start)))]
        if self.enabled_steps:
            valid = sorted({int(x) for x in self.enabled_steps if 1 <= int(x) <= 5})
            if valid:
                return valid
        start = max(1, min(5, int(self.step_start)))
        end = max(start, min(5, int(self.step_end)))
        return list(range(start, end + 1))

    @property
    def stage(self) -> int:
        """三阶材料智能分流：
        1: 仅身份证住址且自有（前期勘验/免字号场地证明）
        2: 有经营场所 + 自有产权（正式申报 + 住改商证明 + 可选场地证明）
        3: 租赁门面（正式申报 + 租赁合同 + 住改商证明 + 可选租赁场地证明）无论有无字号
        """
        if self.usage == "lease" or bool(self.landlord_name.strip()) or bool(self.landlord_id.strip()):
            return 3

        has_shop = bool(self.shop_address.strip() and self.shop_address != self.id_addr)
        if not has_shop and not self.shop_name.strip():
            return 1
        return 2

    @property
    def effective_codes(self) -> list[str]:
        """获取当前未被剔除的生效经营范围代码列表（主营置顶在前，且严格去重）。"""
        active = [s for s in self.scopes if not s.excluded]
        active.sort(key=lambda x: not x.is_primary)
        return list(dict.fromkeys(s.code for s in active))

    @property
    def scope_summary(self) -> str:
        """未被剔除的生效经营范围条目名称拼接。"""
        names = [s.name for s in self.scopes if not s.excluded]
        return "，".join(names) if names else "日用百货销售"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "owner_name": self.owner_name,
            "owner_id": self.owner_id,
            "phone": self.phone,
            "email": self.email,
            "id_addr": self.id_addr,
            "shop_name": self.shop_name,
            "shop_address": self.shop_address,
            "town": self.town,
            "street_rest": self.street_rest,
            "house_use": self.house_use,
            "usage": self.usage,
            "landlord_name": self.landlord_name,
            "landlord_id": self.landlord_id,
            "cert_name": self.cert_name,
            "supervisor": self.supervisor,
            "agent_addr": self.agent_addr,
            "capital": self.capital,
            "active_package": self.active_package,
            "raw_scope_text": self.raw_scope_text,
            "scopes": [s.to_dict() for s in self.scopes],
            "step_start": self.step_start,
            "step_end": self.step_end,
            "run_mode": self.run_mode,
            "enabled_steps": list(self.enabled_steps),
            "stage": self.stage,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplicantState:
        """从字典安全反序列化恢复状态。"""
        scopes_data = data.get("scopes", [])
        scopes = [
            ScopeItem.from_dict(s) if isinstance(s, dict) else s
            for s in scopes_data
        ]
        raw_enabled = data.get("enabled_steps") or []
        return cls(
            schema_version=data.get("schema_version", 2),
            owner_name=data.get("owner_name", ""),
            owner_id=data.get("owner_id", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            id_addr=data.get("id_addr", ""),
            shop_name=data.get("shop_name", ""),
            shop_address=data.get("shop_address", ""),
            town=data.get("town", ""),
            street_rest=data.get("street_rest", ""),
            house_use=data.get("house_use", "住宅"),
            usage=data.get("usage", "own"),
            landlord_name=data.get("landlord_name", ""),
            landlord_id=data.get("landlord_id", ""),
            cert_name=data.get("cert_name", "房屋使用证明"),
            supervisor=data.get("supervisor", ""),
            agent_addr=data.get("agent_addr", ""),
            capital=data.get("capital", "1"),
            active_package=data.get("active_package", "百货店"),
            raw_scope_text=data.get("raw_scope_text", ""),
            scopes=scopes,
            step_start=data.get("step_start", 1),
            step_end=data.get("step_end", 5),
            run_mode=data.get("run_mode", "to_end"),
            enabled_steps=[int(x) for x in raw_enabled if str(x).isdigit()],
            confidence=data.get("confidence", {}),
            warnings=data.get("warnings", []),
        )
