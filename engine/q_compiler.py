"""
@AI-ANCHOR: [Q-COMPILER-CORE] 声明式按键精灵 .Q 脚本编译器与 Action IR 中间表示引擎
q_compiler.py - 声明式 Action IR + .Q 脚本编译器 (Action IR 架构版)。

核心升级：
1. 引入结构化动作中间表示 `ActionNode` (Action IR)，解耦「业务动作编排」与「按键精灵底层语法渲染」。
2. 在生成的 `.Q` 脚本头部写入单行确定性状态元数据注释 `// @GTH-STATE-IR: {...}`，使 `q_parser.py` 具备 O(1) 零损逆向还原能力（彻底解决修改注释文案或单步编译导致逆向解析失灵的问题）。
3. 收敛原本硬编码在代码中的表单默认值（面积 60、从业人数 1、出资额 1、邮箱后缀 @tel.com）至 `profile["form_defaults"]`。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ApplicantState
from .ocr_rules_loader import SUPERVISOR_MAP

try:
    from .q_parser import parse_q_script
except ModuleNotFoundError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location("engine.q_parser", Path(__file__).resolve().parent / "q_parser.py")
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    parse_q_script = _mod.parse_q_script

_DSL_PATH = Path(__file__).resolve().parent.parent / "config" / "q_steps_dsl.json"
_CACHED_DSL_STEPS: dict[str, Any] | None = None

HEADER_TEMPLATE = """[General]
Description={title}
BeginHotkey={begin_hotkey}
BeginHotkeyMod=0
PauseHotkey={pause_hotkey}
PauseHotkeyMod=0
StopHotkey={stop_hotkey}
StopHotkeyMod=0
RunOnce=1
EnableWindow=
Enable=1
[Repeat]
Type=0
Number=1
[CallBack]
OnSetup=
[Comment]
Content=F10启动 F2暂停 F7中止 由 个体户政务填报工作台 生成 | Shop={shop_name} | Steps={steps_tag}
[Script]
// @GTH-STATE-IR: {state_ir_json}
SetSimMode 2
Delay {start_delay}
"""


@dataclass
class ActionNode:
    """动作中间表示 (Action IR Node)，解耦高级业务意图与按键精灵文本指令。"""
    step_stage: int
    step_no: int
    op: str  # "click" | "typetext" | "wheel" | "delay" | "keypress" | "marker"
    desc: str = ""
    target_key: str = ""
    coord: tuple[int, int] | None = None
    text: str = ""
    delay_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_stage": self.step_stage,
            "step_no": self.step_no,
            "op": self.op,
            "desc": self.desc,
            "target_key": self.target_key,
            "coord": list(self.coord) if self.coord else None,
            "text": self.text,
            "delay_ms": self.delay_ms,
            "extra": self.extra,
        }


def _sanitize_say(text: str) -> str:
    """清理 SayString 文本（严禁双引号与换行，防语法破坏）。"""
    return (text or "").replace('"', " ").replace("\r", " ").replace("\n", " ").strip()


def _build_compact_state_ir(state: ApplicantState, active_steps: list[int]) -> str:
    """生成单行确定性状态快照 JSON，嵌入 .Q 脚本注释头部供逆向解析器 O(1) 无损读取。"""
    ir_payload = {
        "v": 3,
        "owner_name": state.owner_name,
        "owner_id": state.owner_id,
        "phone": state.phone,
        "email": state.email,
        "id_addr": state.id_addr,
        "shop_name": state.shop_name,
        "shop_address": state.shop_address,
        "town": state.town,
        "street_rest": state.street_rest,
        "usage": state.usage,
        "landlord_name": state.landlord_name,
        "landlord_id": state.landlord_id,
        "supervisor": state.supervisor,
        "capital": state.capital,
        "active_package": state.active_package,
        "enabled_steps": active_steps,
        "scopes": [
            {
                "code": s.code,
                "name": s.name,
                "is_primary": s.is_primary,
                "is_permit": s.is_permit,
                "excluded": s.excluded,
            }
            for s in state.scopes
        ],
    }
    return json.dumps(ir_payload, ensure_ascii=False, separators=(",", ":"))


def _load_steps_dsl(force_reload: bool = False) -> dict[str, Any]:
    """加载并缓存外置声明式步骤钩子配置 config/q_steps_dsl.json。"""
    global _CACHED_DSL_STEPS
    if _CACHED_DSL_STEPS is not None and not force_reload:
        return _CACHED_DSL_STEPS
    if _DSL_PATH.exists():
        try:
            _CACHED_DSL_STEPS = json.loads(_DSL_PATH.read_text(encoding="utf-8")).get("steps", {})
            return _CACHED_DSL_STEPS
        except Exception:
            pass
    _CACHED_DSL_STEPS = {}
    return _CACHED_DSL_STEPS


_load_steps_dsl()


# @AI-ANCHOR: [Q-BUILDER-BASE] 按键精灵原子指令与 Action IR 双轨构建器
class QBuilder:
    """按键精灵 2014 脚本指令构建器（同步产出结构化 ActionNode IR 与可读脚本行）。"""

    def __init__(self, profile: dict[str, Any]) -> None:
        self.p = profile
        self.coords = profile.get("coordinates", {})
        self.delays = profile.get("delays", {})
        self.defaults = profile.get("form_defaults", {})
        self.mult = float(profile.get("global_delay_multiplier", 1.0))
        self.step1_cfg = profile.get("step1_name_check", {})
        self.lines: list[str] = []
        self.ir_nodes: list[ActionNode] = []
        self.step_no = 0
        self.current_stage = 0
        self._last_desc = ""

    def d(self, key_or_ms: str | int, default_ms: int = 0) -> int:
        """从 profile 计算延迟毫秒，应用全局倍率。"""
        if isinstance(key_or_ms, str):
            fallback = default_ms if default_ms > 0 else self.delays.get("default_ms", 350)
            ms = self.delays.get(key_or_ms, fallback)
        else:
            ms = key_or_ms
        min_d = self.delays.get("min_delay_ms", 50)
        return max(min_d, int(ms * self.mult))

    def step_marker(self, step_idx: int, desc: str) -> None:
        self.current_stage = step_idx
        self.lines.append(f"\r\n// ===== 第 {step_idx} 阶段：{desc} =====")
        self.ir_nodes.append(ActionNode(step_stage=step_idx, step_no=self.step_no, op="marker", desc=desc))

    def step(self, desc: str) -> None:
        """输出带全局序号的高可读性中文步骤注释。"""
        self.step_no += 1
        self._last_desc = desc
        self.lines.append(f"// 第 {self.step_no} 步：{desc}")

    def click(self, key_or_xy: str | tuple[int, int], delay_key: str = "click_ms") -> None:
        if isinstance(key_or_xy, str):
            xy = self.coords.get(key_or_xy, (0, 0))
            x, y = int(xy[0]), int(xy[1])
            target_key = key_or_xy
        else:
            x, y = int(key_or_xy[0]), int(key_or_xy[1])
            target_key = f"({x},{y})"
        wait_ms = self.d(delay_key)
        self.lines.extend([f"MoveTo {x}, {y}", "LeftClick 1", f"Delay {wait_ms}"])
        self.ir_nodes.append(
            ActionNode(
                step_stage=self.current_stage,
                step_no=self.step_no,
                op="click",
                desc=self._last_desc,
                target_key=target_key,
                coord=(x, y),
                delay_ms=wait_ms,
            )
        )

    def typetext(self, text: str, clear: bool = True, delay_key: str = "type_ms") -> None:
        clean = _sanitize_say(text)
        wait_ms = self.d(delay_key, 400)
        if clear:
            self.lines.extend([
                'KeyDown "Ctrl", 1',
                'KeyPress "A", 1',
                'KeyUp "Ctrl", 1',
                f"Delay {self.d('start_delay_ms', 100)}",
            ])
        self.lines.extend([f'SayString "{clean}"', f"Delay {wait_ms}"])
        self.ir_nodes.append(
            ActionNode(
                step_stage=self.current_stage,
                step_no=self.step_no,
                op="typetext",
                desc=self._last_desc,
                text=clean,
                delay_ms=wait_ms,
                extra={"clear": clear},
            )
        )

    def wheel(self, delta: int, delay_key: str = "wheel_wait_ms") -> None:
        wait_ms = self.d(delay_key, 200)
        self.lines.extend([f"MouseWheel {delta}", f"Delay {wait_ms}"])
        self.ir_nodes.append(
            ActionNode(
                step_stage=self.current_stage,
                step_no=self.step_no,
                op="wheel",
                desc=self._last_desc,
                delay_ms=wait_ms,
                extra={"delta": delta},
            )
        )

    def run_dsl_actions(self, actions: list[dict[str, Any]], state: ApplicantState) -> None:
        """执行 config/q_steps_dsl.json 中声明的前置/后置自定义指令。"""
        for act in actions:
            op = act.get("op", "")
            delay_key = act.get("delay", "click_ms")
            if op == "click":
                target = act.get("target")
                if isinstance(target, list) and len(target) == 2:
                    self.click((int(target[0]), int(target[1])), delay_key)
                elif isinstance(target, str) and target in self.coords:
                    self.click(target, delay_key)
            elif op == "delay":
                ms_key = act.get("ms", "step_wait_ms")
                wait_ms = self.d(ms_key)
                self.lines.append(f"Delay {wait_ms}")
                self.ir_nodes.append(ActionNode(step_stage=self.current_stage, step_no=self.step_no, op="delay", delay_ms=wait_ms))
            elif op == "keypress":
                key_name = act.get("key", "Enter")
                cnt = int(act.get("count", 1))
                wait_ms = self.d(delay_key)
                self.lines.extend([f'KeyPress "{key_name}", {cnt}', f"Delay {wait_ms}"])
                self.ir_nodes.append(ActionNode(step_stage=self.current_stage, step_no=self.step_no, op="keypress", text=key_name, delay_ms=wait_ms))
            elif op == "say":
                raw_txt = str(act.get("text", ""))
                if raw_txt.startswith("$"):
                    raw_txt = str(getattr(state, raw_txt[1:], ""))
                self.typetext(raw_txt, clear=bool(act.get("clear", True)), delay_key=delay_key)

    # @AI-ANCHOR: [Q-STEP1-HEMING] 第 1 阶段：名称自主申报与承诺书 (核名)
    def build_step1_heming(self, s: ApplicantState, has_follow_up: bool = True) -> None:
        self.step_marker(1, "名称自主申报与告知书打印")
        capital_str = s.capital or str(self.defaults.get("default_capital", "1"))
        default_area = str(self.defaults.get("default_area", "60"))
        default_emp = str(self.defaults.get("default_employees", "1"))
        email_domain = str(self.defaults.get("default_email_domain", "tel.com"))

        self.step(f"出资额：点击输入框并输入「{capital_str}」（单位万元，缺省 1）")
        self.click("核名_出资额", "input_ms")
        self.typetext(capital_str)

        self.step("点「下一步」进入经营者页（跨页等待）")
        self.click("核名_下一步", "step_wait_ms")

        self.step(f"名称（姓名）：点击输入框并输入「{s.owner_name}」")
        self.click("核名_经营者姓名", "input_ms")
        self.typetext(s.owner_name)

        self.step("证件类型：点开下拉")
        self.click("核名_证件类型下拉", "dropdown_open_ms")

        self.step("下拉选项：点「中华人民共和国居民身份证」")
        self.click("核名_居民身份证", "option_pick_ms")

        self.step(f"证件号码：点击输入框并输入「{s.owner_id}」（国标校验位已核）")
        self.click("核名_证件号码", "input_ms")
        self.typetext(s.owner_id)

        save_wait = self.d("person_save_ms")
        self.step(f"点「保存」，经营者落入下方列表（延时 {save_wait} 毫秒）")
        self.click("核名_经营者保存", "person_save_ms")

        self.step("点「完成」，弹出承诺书（列表插入姓名行后的按钮下移位）")
        self.click("核名_经营者完成", "done_ms")

        countdown_ms = self.d("countdown_ms")
        self.step(f"承诺书弹窗强制倒计时至少 12 秒，等待 {countdown_ms // 1000} 秒后操作")
        self.lines.append(f"Delay {countdown_ms}")

        self.step("勾选「我已仔细阅读并同意和履行《企业名称自主申报承诺书》中的内容」")
        self.click("核名_承诺书勾选", "agree_ms")

        self.step("点「我已阅读并同意和履行」")
        self.click("核名_承诺书同意", "agree_ms")

        self.step("系统确认弹窗点「确认」（申报成功后将无法修改）")
        self.click("核名_确认弹窗确定", "confirm_ms")

        self.step("等待跳转申报成功页（弹窗停留后页面余量）")
        self.lines.append(f"Delay {self.d('jump_settle_ms')}")

        wrap_threshold = self.step1_cfg.get("wrap_char_threshold", 18)
        single_y = self.step1_cfg.get("single_line_confirm_y", 850)
        wrapped_y = self.step1_cfg.get("wrapped_line_confirm_y", 887)
        is_wrapped = bool(wrap_threshold is not None and len(s.shop_name) >= wrap_threshold)
        row = wrapped_y if is_wrapped else single_y

        print_x = self.step1_cfg.get("print_notice_x", 953)
        launch_x = self.step1_cfg.get("launch_setup_x", 685)

        self.step(f"点「打印告知书和承诺书」（坐标 X:{print_x}, Y:{row}）")
        self.click((print_x, row), "launch_jump_ms")

        self.step("回车确认打开/下载告知书 PDF")
        self.lines.extend(['KeyPress "Enter", 1', f"Delay {self.d('submit_settle_ms')}"])

        self.step(f"点「发起设立」进入设立登记（坐标 X:{launch_x}, Y:{row}）")
        self.click((launch_x, row), "launch_jump_ms")

        if has_follow_up:
            cross_ms = self.d("cross_system_wait_ms")
            self.step(f"跨系统实例加载：缓冲 {cross_ms // 1000} 秒等待一窗通完成设立实例创建并渲染大表单")
            self.lines.append(f"Delay {cross_ms}")

            self.step("设立登记·温馨提示：点击弹窗「确定」关闭代理人备案提示")
            self.click("设立登记_温馨提示确定", "step_wait_ms")

            self.step(f"联系电话：点击并输入客户电话「{s.phone}」")
            self.click("联系电话", "input_ms")
            self.typetext(s.phone)

            self.step("滚动条下翻 1 屏")
            self.click("滚动条_下翻", "add_ms")

            self.step(f"经营场所面积：点击并填 {default_area}")
            self.click("面积", "input_ms")
            self.typetext(default_area)

            self.step(f"法律文书送达联系电话：点击并输入「{s.phone}」")
            self.click("送达电话", "input_ms")
            self.typetext(s.phone)

            email_val = s.email or f"{s.phone}@{email_domain}"
            self.step(f"法律文书送达邮箱：点击并输入「{email_val}」")
            self.click("送达邮箱", "input_ms")
            self.typetext(email_val)

            self.step("组成形式：单击选「个人经营」")
            self.click("组成形式_个人经营", "dropdown_open_ms")

            self.step(f"从业人数：点击并填 {default_emp}")
            self.click("从业人数", "input_ms")
            self.typetext(default_emp)

            self.step(f"资金数额：点击并填 {capital_str}")
            self.click("资金数额", "input_ms")
            self.typetext(capital_str)

    # @AI-ANCHOR: [Q-STEP2-SCOPE] 第 2 阶段：经营范围装配与许可确认
    def build_step2_scope(self, s: ApplicantState) -> None:
        self.step_marker(2, "经营范围装配与许可确认")
        self.step("经营范围开启：点击打开经营范围装配弹窗")
        self.click("经营范围开启", "scope_open_ms")

        self.step("经营范围·关闭提示：点击「知道了」关闭地区限制提示")
        self.click("范围_不符合提示知道了", "confirm_ms")

        codes = s.effective_codes
        if not codes:
            self.step("经营范围：目标为系统默认项，直接保存退出")
        else:
            total_codes = len(codes)
            for idx, code in enumerate(codes, 1):
                item = next((it for it in s.scopes if it.code == code), None)
                item_name = f"【{item.name}】" if item else ""
                self.step(f"经营范围条目 {idx}/{total_codes}：搜索输入代码「{code}」{item_name}")
                self.click("范围搜索框", "search_ms")
                self.typetext(code)

                self.step(f"经营范围条目 {idx}/{total_codes}：点「搜索」并勾选添加")
                self.click("范围搜索按钮", "add_ms")
                self.click("范围添加", "add_ms")

        self.step("经营范围弹窗「完成并保存」：提交条目并返回主表单")
        self.click("范围_完成并保存", "save_ms")

        if any(sc.is_permit for sc in s.scopes if not sc.excluded):
            self.step("许可项目确认：点击「我已阅读并知晓」")
            self.click("许可_我已阅读并知晓", "add_ms")
            self.step("许可项目确认：点击「确定」")
            self.click("许可_确定", "confirm_ms")

    # @AI-ANCHOR: [Q-STEP3-PERSON] 第 3 阶段：经营者、联络员与经办人填报
    def build_step3_person(self, s: ApplicantState) -> None:
        self.step_marker(3, "经营者与联络员信息录入")
        email_domain = str(self.defaults.get("default_email_domain", "tel.com"))

        self.step("滚动条下翻 1 屏进入经营者信息区")
        self.click("滚动条_下翻", "add_ms")

        self.step("是否申领印章：单击选「否」（个体户默认否，双点抗抖动）")
        self.click("印章_否", "dropdown_open_ms")
        self.click("印章_否", "dropdown_open_ms")

        self.step(f"经营者姓名：点击并输入「{s.owner_name}」")
        self.click("经营者姓名", "input_ms")
        self.typetext(s.owner_name)

        self.step(f"经营者联系电话：点击并输入「{s.phone}」")
        self.click("经营者电话", "input_ms")
        self.typetext(s.phone)

        self.step(f"住所（身份证地址）：点击并输入「{s.id_addr}」")
        self.click("住所", "input_ms")
        self.typetext(s.id_addr)

        self.step(f"移动电话：点击并输入「{s.phone}」")
        self.click("移动电话", "input_ms")
        self.typetext(s.phone)

        email_val = s.email or f"{s.phone}@{email_domain}"
        self.step(f"电子邮箱：点击并输入「{email_val}」")
        self.click("邮箱", "input_ms")
        self.typetext(email_val)

        self.step("经营者类别：打开下拉选「中国大陆」")
        self.click("经营者类别", "dropdown_open_ms")
        self.click("类别_中国大陆", "option_pick_ms")

        self.step("身份证件：打开下拉选「居民身份证」")
        self.click("身份证件", "dropdown_open_ms")
        self.click("证件_居民身份证", "option_pick_ms")

        self.step(f"身份证号码：点击并输入「{s.owner_id}」（国标校验位已核）")
        self.click("身份证号码", "input_ms")
        self.typetext(s.owner_id)

        self.step("滚动条下翻 1 屏进入联络员信息区")
        self.click("滚动条_下翻", "add_ms")

        self.step("联络员信息：点击「增加」按钮")
        self.click("联络员_增加", "dropdown_open_ms")

        self.step("联络员弹窗：是否公示系统登录联络员选「是」")
        self.click("联络员_公示是", "add_ms")

        self.step("联络员弹窗：点姓名搜索框（自动关联经营者信息）")
        self.click("联络员_姓名搜索", "launch_jump_ms")

        self.step(f"联络员弹窗：点候选「{s.owner_name}」自动带出除住所外全部内容")
        self.click("联络员_候选项", "dropdown_open_ms")

        self.step(f"联络员弹窗：点「住所」并输入身份证地址「{s.id_addr}」")
        self.click("联络员_住所", "input_ms")
        self.typetext(s.id_addr)

        self.step("联络员弹窗：点击「保存」按钮关闭弹窗")
        self.click("联络员_保存", "agree_ms")

        agent_addr = s.agent_addr or s.id_addr
        self.step(f"经办人现居住地址：点击并输入「{agent_addr}」")
        self.click("经办人现居住地址", "input_ms")
        self.typetext(agent_addr)

        self.step("滚动条下翻进入银行开户区")
        self.click("滚动条_下翻", "add_ms")

        self.step("是否预约银行开户：单击选「否」")
        self.click("银行开户_否", "dropdown_open_ms")

    # @AI-ANCHOR: [Q-STEP4-ADDR] 第 4 阶段：经营场所、乡镇街道与房屋权属填报
    def build_step4_addr(self, s: ApplicantState) -> None:
        self.step_marker(4, "经营场所填报与地图定位")

        self.step("滚动条上翻 4 次回到页面顶部经营场所区")
        for _ in range(4):
            self.click("滚动条_上翻", "wheel_wait_ms")

        self.step("点「经营场所·填报」打开选择地址弹窗")
        self.click("经营场所_填报", "step_wait_ms")

        tip_read_ms = self.d("tip_read_ms")
        self.step(f"温馨提示强制阅读缓冲 {tip_read_ms // 1000} 秒后点「我已阅读」")
        self.lines.append(f"Delay {tip_read_ms}")
        self.click("温馨提示_我已阅读", "step_wait_ms")

        self.step("房屋用途下拉：选「住宅」")
        self.click("房屋用途下拉", "dropdown_open_ms")
        self.click("房屋用途_住宅", "option_pick_ms")

        self.step("住宅提示弹窗：点击「确定」")
        self.click("住宅提示_确定", "confirm_ms")

        self.step("县区下拉：选「郯城县」")
        self.click("县区下拉", "dropdown_open_ms")
        self.click("县区_郯城县", "option_pick_ms")

        town_top = self.p.get("town_top", {})
        town_bot = self.p.get("town_bottom", {})
        town_x = self.p.get("town_dropdown_x", 1222)
        wheel_delta = self.p.get("town_wheel_delta", -1)
        wheel_count = self.p.get("town_wheel_count", 3)

        if s.town in town_top:
            self.step(f"乡镇下拉：选择「{s.town}」")
            self.click("乡镇下拉", "dropdown_open_ms")
            self.click((town_x, town_top[s.town]), "dropdown_open_ms")
        elif s.town in town_bot:
            self.step(f"乡镇下拉：滚轮下翻并选择底页「{s.town}」")
            self.click("乡镇下拉", "dropdown_open_ms")
            hx, hy = self.p.get("town_wheel_hover", (1222, 860))
            self.lines.extend([f"MoveTo {hx}, {hy}", f"Delay {self.d('wheel_wait_ms', 200)}"])
            for _ in range(wheel_count):
                self.wheel(wheel_delta)
            self.click((town_x, town_bot[s.town]), "dropdown_open_ms")

        street_val = s.street_rest or s.shop_address
        self.step(f"街路门牌输入框：输入详细地址「{street_val}」")
        self.click("街路输入", "input_ms")
        self.typetext(street_val)

        self.step("滚动条下翻一屏，进入房屋权属区")
        self.click("滚动条_下翻", "add_ms")

        owner = s.landlord_name if s.usage == "lease" else s.owner_name
        owner_id = s.landlord_id if s.usage == "lease" else s.owner_id
        self.step(f"所有权人姓名：点击并输入「{owner}」")
        self.click("所有权人姓名", "input_ms")
        self.typetext(owner)

        cert_name = s.cert_name or "房屋使用证明"
        self.step(f"产权证名称：点击并输入「{cert_name}」")
        self.click("产权证名称", "input_ms")
        self.typetext(cert_name)

        self.step("房屋性质下拉：选「市场化商品房」")
        self.click("房屋性质下拉", "dropdown_open_ms")
        self.click("房屋性质_市场化商品房", "option_pick_ms")

        self.step(f"产权人联系方式：点击并输入「{s.phone}」")
        self.click("产权人联系方式", "input_ms")
        self.typetext(s.phone)

        self.step(f"产权人证件号码：点击并输入「{owner_id}」")
        self.click("产权人证件号码", "input_ms")
        self.typetext(owner_id)

        usage_map = {
            "lease": ("使用方式_租赁", "租赁"),
            "free": ("使用方式_无偿使用", "无偿使用"),
            "own": ("使用方式_自有", "自有"),
        }
        u_key, u_label = usage_map.get(s.usage, ("使用方式_自有", "自有"))
        self.step(f"使用方式：点击单选「{u_label}」")
        self.click(u_key, "dropdown_open_ms")

        self.step("使用方式提示弹窗：点击「确定」")
        self.click("使用方式提示_确定", "confirm_ms")

        self.step("点「位置标记」打开地图选址")
        self.click("位置标记", "done_ms")

        map_kw = s.shop_address
        self.step(f"地图搜索框：输入地址关键词「{map_kw}」")
        self.click("地图搜索框", "input_ms")
        self.typetext(map_kw)

        self.step("点击「搜索」按钮并在地图居中定位")
        self.click("地图搜索按钮", "map_search_ms")

        self.step("点击地图中央坐标点选定地址位置")
        self.click("地图中央坐标点", "map_click_ms")

        self.step("地图弹窗：点击「确定」完成坐标标记")
        self.click("地图_确定", "done_ms")

        self.step("选择地址弹窗：点击「确定」保存经营场所")
        self.click("选择地址_确定", "step_wait_ms")

        self.step("提交确认提示弹窗：点击「确定」")
        self.click("提交确认_确定", "step_wait_ms")

    # @AI-ANCHOR: [Q-STEP5-SUPERVISOR] 第 5 阶段：属地市场监管所选择与暂存
    def build_step5_supervisor(self, s: ApplicantState) -> None:
        self.step_marker(5, "暂存业务与属地监管所匹配")
        self.step("点击右侧「暂存业务」按钮保存当前草稿")
        self.click("暂存业务", "step_wait_ms")

        self.step("暂存确认弹窗：点击「确定」")
        self.click("暂存确认_确定", "step_wait_ms")

        target = (
            s.supervisor
            or self.p.get("supervisor_by_town", {}).get(s.town, "")
            or SUPERVISOR_MAP.get(s.town, "")
        )
        opts = self.p.get("supervisor_options", {})
        if target in opts:
            scrolls, y = opts[target]
            sx = self.p.get("supervisor_x", 734)
            s_open_y = self.p.get("supervisor_dropdown_y", 227)
            s_wheel_y = self.p.get("supervisor_wheel_y", 390)
            s_wheel_delta = self.p.get("supervisor_wheel_delta", -1)

            self.step(f"属地监管所：点击展开监管所下拉选择框（匹配目标：{target}）")
            self.click((sx, s_open_y), "dropdown_open_ms")
            if scrolls:
                self.step(f"属地监管所列表：鼠标移至列表区滚轮向下滚动 {scrolls} 次到底")
                self.lines.extend([f"MoveTo {sx}, {s_wheel_y}", f"Delay {self.d('wheel_wait_ms', 200)}"])
                for _ in range(scrolls):
                    self.wheel(s_wheel_delta)
            self.step(f"属地监管所：点击选择「{target}」（坐标 Y:{y}）")
            self.click((sx, y), "dropdown_open_ms")


# @AI-ANCHOR: [Q-COMPILE-ENTRY] 按所选步骤积木数组编译并输出 GBK/CRLF .Q 脚本
def build_action_ir(state: ApplicantState, profile: dict[str, Any]) -> tuple[QBuilder, list[int]]:
    """构建结构化 Action IR 与脚本构建器实例（可供预览、审计与直接编译）。"""
    builder = QBuilder(profile)
    dsl_steps = _load_steps_dsl()
    active_steps = state.get_active_steps()
    has_follow_up_after_1 = any(idx > 1 for idx in active_steps)

    step_builders = {
        1: lambda st: builder.build_step1_heming(st, has_follow_up=has_follow_up_after_1),
        2: builder.build_step2_scope,
        3: builder.build_step3_person,
        4: builder.build_step4_addr,
        5: builder.build_step5_supervisor,
    }

    for idx in active_steps:
        step_cfg = dsl_steps.get(str(idx), {})
        if not step_cfg.get("enabled", True):
            continue
        pre_acts = step_cfg.get("pre_actions", [])
        post_acts = step_cfg.get("post_actions", [])
        if pre_acts:
            builder.run_dsl_actions(pre_acts, state)
        if idx in step_builders:
            step_builders[idx](state)
        if post_acts:
            builder.run_dsl_actions(post_acts, state)

    return builder, active_steps


def compile_q_script(state: ApplicantState, profile: dict[str, Any], output_path: str | Path) -> str:
    """编译声明式 .Q 脚本并执行 GBK/CRLF 单次极速落盘（支持任意积木式步骤组合与嵌入式 Action IR 元数据）。"""
    builder, active_steps = build_action_ir(state, profile)

    start = active_steps[0] if active_steps else state.step_start
    end = active_steps[-1] if active_steps else state.step_end
    steps_tag = ",".join(str(x) for x in active_steps)
    display_owner = state.owner_name or state.shop_name or "当前办件"
    builder.lines.append(f'\r\nMessageBox "【{display_owner}】第 {start} 至 {end} 步自动化执行完毕！"')
    builder.lines.append("EndScript\r\n")

    hotkeys = profile.get("hotkeys", {})
    delays = profile.get("delays", {})
    title = f"个体户填报_{display_owner}_{start}至{end}步"
    state_ir_json = _build_compact_state_ir(state, active_steps)

    full_content = HEADER_TEMPLATE.format(
        title=title,
        begin_hotkey=hotkeys.get("begin", 121),
        pause_hotkey=hotkeys.get("pause", 113),
        stop_hotkey=hotkeys.get("stop", 118),
        start_delay=delays.get("start_delay_ms", 100),
        shop_name=_sanitize_say(state.shop_name),
        steps_tag=steps_tag,
        state_ir_json=state_ir_json,
    ) + "\r\n".join(builder.lines)
    full_crlf = full_content.replace("\r\n", "\n").replace("\n", "\r\n")

    p = Path(output_path)
    p.write_bytes(full_crlf.encode("gbk", errors="replace"))
    return str(p)
