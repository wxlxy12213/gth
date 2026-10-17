# GTH — 个体工商户政务登记与一键开办工作台
> **Individual Business Gov RPA Workbench** · 面向山东省市场主体全程电子化登记系统的全流程自动化、智能办件与文书生成桌面平台。

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%20Edge%20WebView2-blue?style=flat-square)](https://developer.microsoft.com/microsoft-edge/webview2/)
[![Python](https://img.shields.io/badge/Python-3.11%2B%20%2F%203.15-yellow?style=flat-square)](https://www.python.org/)
[![UI Style](https://img.shields.io/badge/Design-Neo--Brutalist%20Experimental-ff007d?style=flat-square)](https://www.stylekit.top/zh/templates/anx-blog)
[![RPA Engine](https://img.shields.io/badge/RPA-KeySprite%202014%20.Q%20%2B%20Action%20IR-green?style=flat-square)](https://github.com/wxlxy12213/gth)

---

## 1. 软件概述 (Overview)

**GTH** 是一套专为工商代办、政务中介及行政审批服务场景量身打造的桌面级自动化办件工作台。

系统直面山东省政务服务网（“企业开办一窗通” / 全程电子化登记平台）的申报链路，针对个体工商户设立过程中**信息繁杂、核名繁琐、经营范围查询录入慢、表单重复填写、以及线下窗口法定文书手工排版易错**等痛点，提供端到端的自动化解决方案：

1. **非结构化进料粘贴即解析**：支持微信聊天记录、证件文字、图片识别结果等自然语言的一键粘贴（粘贴即自动触发脱水识别），自动完成经营者、联系方式、经营场所、房东权属及行政区划的结构化消元与 GB 11643 国标模 11 校验。
2. **经营范围 2,064 底库毫秒检索与代数差集**：内置官方全量条目底库与高频免审批黄金套餐，在「01 填报总控」即可一键速切套餐并预览已选范围；在「02 经营范围沙盒」支持首字母拼音毫秒检索与政务网原生范围的集合差集计算。
3. **Action IR 驱动的 RPA 脚本双轨直发与零损逆向还原**：基于结构化动作中间表示（`ActionNode` IR）实时生成适配按键精灵 2014 的 `.Q` 自动化脚本，支持 01~05 积木步骤自由启停与单步断点重编；脚本内嵌 `@GTH-STATE-IR` 状态快照，支持随时从任意 `.Q` 脚本 O(1) 零损还原全部办件表单。
4. **单源法定文书矩阵出件与智能洗牌互通**：统一收敛《房屋租赁合同》、《住改商登记利害关系业主同意证明》（含前两页免签章高清 PNG 直传图与四邻/业主签字表）、《经营场所使用证明》与《餐饮服务承诺书》至单源 OpenXML 渲染内核；「01 填报总控」与「03 文书工坊」支持客户要素一键双向互通。

---

## 2. 视觉与美术设计系统 (Visual & Aesthetic Design System)

本工作台在界面交互与视觉表达上，摒弃了传统企业管理软件单调、灰暗的表格模板，贯彻了独特的个人审美与实验性设计语言，全面对齐**人类使用哲学**与 **1080P 全屏免滚工程学**：

### 2.1 美术溯源与设计基因
- **核心溯源**：本系统界面设计参考并借鉴了开源工程 [实验风博客示例 (Anx Blog)](https://www.stylekit.top/zh/templates/anx-blog)（基于 StyleKit Templates 的实验性设计体系）。
- **设计哲学**：新野兽派（Neo-Brutalism）与先锋工装控制台（Cyber-Industrial Console）的深度融合。

### 2.2 强化审美特征与人类工程学
- **字体风格大胆（Loud & Bold Typography）**：大面积采用超粗字重无衬线体（Impact / Arial Black / PingFang SC Heavy）与等宽工程字体（Cascadia Code / Consolas），标题与核心状态信息极具辨识度。
- **边框粗犷高反差 & 实体硬落焦投影**：全界面采用纯黑实体线描边与硬落焦阴影（无高斯模糊扩散），赋予界面如工业物理按键般的扎实按压反馈。
- **方格工程画布与 CMYK 电光强调色**：以 44px 浅灰参考网格为画布基底，点缀高饱和度的电光粉（`#ff007d`）、电光绿（`#ccff00`）、青蓝（`#00d9ff`）与日光黄（`#ffd400`）。
- **符合人类直觉的导航动线与温和三态校验**：
  - 顶部导航按使用频次与作业顺序划分为**主作业流（`01 填报总控` ➔ `02 经营范围沙盒` ➔ `03 文书工坊`）**与**辅助及归档区（`04 坐标与延时` ➔ `05 历史档案`）**，历史档案归置最末位。
  - 摒弃未填先报错的刺眼红牌，采用**温和三态校验芯片**（未填显示中性灰 `待填` / `免字号`，填错格式或身份证校验位错误才亮红提醒，核验通过亮绿 `✓ 就绪`）。
  - 针对 **1080P (`1920×1080`)** 屏幕精调纵向空间，在「01 填报总控」一屏三栏内完整囊括智能进料、独立文书快出、核心要素、黄金套餐速切、已选范围预览、01~05 积木矩阵与产物交付柜。

---

## 3. 核心业务领域模型与专属设计机理 (Domain-Specific Design Rationale)

### 3.1 市级系统代码（371300）与县域属地业务的架构收敛
* **背景机制**：山东省市场主体登记系统实行市级集中部署，`371300` 为临沂市市级统筹行政区划编码，统一规范了申报网关入口与 2,064 条经营范围基础底库。
* **属地特化**：在线下实际办件中，业务深度扎根于临沂市下辖的**郯城县（371322）**。系统通过 `config/ocr_rules.json` 动态维护郯城县 14 个乡镇街道（马头镇、郯城街道、李庄镇等）与其属地市场监督管理所（马头所、城区所、李庄所等）的法定映射关系，前后端共享同一真源。

### 3.2 官方 2,064 条经营范围底库与黄金套餐体系
* **官方底库保真**：`scope_library_371300.json` 严格收录官方政务系统标准的 2,064 条规范经营范围表述。
* **拼音首字母加速引擎**：底层构建汉字首字母倒排索引，无需全拼即可实现 `< 0.05ms` 即时检索。
* **代数差集点选（Algebraic Diffing）**：通过集合运算计算出目标套餐与政务网原生范围的差集（$A \setminus B$），自动将已有项灰化划线剔除，防止按键精灵重复点击取消勾选。

### 3.3 智能多主体 OCR 消元与权属推导
* **双证自动对齐**：当进料包含两组身份信息时，系统自动推导首位为主体经营者、次位为出租方（房东），并联动将经营场所权属切换为租赁模式（`usage=lease`）。
* **前后端同源国标强校验**：前后端均内置 GB 11643 ISO 7064:1983.MOD 11-2 算法，对输入的 18 位身份证执行离散加权模算核验，实时拦截伪号并提示正确校验位。

### 3.4 桌面主体目录与按键精灵固定槽位（Action IR & Manifest-Driven）
* **桌面主体出件守卫**：全链路产物默认落盘至用户桌面主体名称同名文件夹（如 `桌面/郯城县某某店/`），自动复用既有主体目录或规范新建。
* **固定槽位秒级挂机**：编译生成的 `.Q` 脚本同步写入主体目录与按键精灵本机的 `QMScript` 运行目录（`【当前待跑】个体户自动填报.Q`），按下 `F10` 即可启动最新任务。
* **确定性 `@GTH-STATE-IR` 逆向反解**：系统内置 `.Q` 解析引擎（`q_parser.py`），优先读取 `.Q` 脚本内嵌的 `@GTH-STATE-IR` JSON 快照实现 O(1) 零损还原（即使单步 `.Q` 脚本也能完整恢复全部客户字段与经营范围），同时向下兼容历史 `.Q` 脚本的正则提取。

---

## 4. 架构全景与工程目录清单 (Architecture & Repository Structure)

```text
GTH/
├── config/                        # 权威离散配置与官方底库（唯一业务真源）
│   ├── golden_packages.json       # 行业免审批“黄金套餐”配置
│   ├── history_snapshots.json     # 办件快照历史数据（空数组占位防隐私上云）
│   ├── ocr_rules.json             # 智能提取正则与乡镇-监管所映射字典
│   ├── portal_profile_371300.json # 临沂政务系统坐标、延迟与表单默认值配置
│   ├── q_steps_dsl.json           # 自动化步骤前后置 DSL 钩子定义
│   └── scope_library_371300.json  # 官方 2064 条经营范围标准底库
├── engine/                        # 核心业务逻辑与确定性计算引擎（微切片架构）
│   ├── addr_parser.py             # 地址消元、分段缝合与属地识别
│   ├── doc_wash_engine.py         # 业务员文书智能洗牌与桌面直通出件（复用 docx_engine）
│   ├── docx_engine.py             # 单源法定文书并发渲染内核（场地/租赁/住改商/餐饮）
│   ├── history_manager.py         # 办件快照历史归档与复原管理器
│   ├── id_validator.py            # GB 11643 身份证国标模 11 校验
│   ├── models.py                  # 强类型数据状态模型 (ApplicantState)
│   ├── ocr_cleaner.py             # 进料文本提取、双证配对与清洗流水线
│   ├── ocr_rules_loader.py        # 规则动态加载与热更新守卫
│   ├── q_compiler.py              # 按键精灵 01~05 积木式 Action IR 与 .Q 编译器
│   ├── q_parser.py                # 按键精灵 .Q 脚本 @GTH-STATE-IR 零损逆向还原器
│   ├── scope_search.py            # 经营范围首字母索引与差集运算引擎
│   ├── subject_dir.py             # 桌面主体同名文件夹单源解析与防冲突自愈器
│   ├── win_os_service.py          # Windows 原生系统服务封装（剪贴板/坐标/Explorer/HUD）
│   └── zhugai_img_exporter.py     # 《住改商证明》前两页免签章高清 PNG 导出模块
├── ui/                            # 桌面端控制台前端界面（1080P 全屏免滚设计）
│   ├── css/
│   │   ├── base.css               # 全局变量、工业按钮与分区顶部导航样式
│   │   ├── brutalist.css          # 新野兽派样式表总索引入口 (@import)
│   │   ├── panels.css             # 经营范围、文书洗牌、坐标方块、历史与弹窗样式
│   │   └── workbench.css          # 场景 01 填报总控三栏全闭环网格与三态芯片样式
│   ├── js/
│   │   ├── app.js                 # 前端启动总控、乡镇动态挂载、Tab路由、HUD与CMD+K
│   │   ├── config_meta.js         # 步骤坐标与延时中文元数据字典
│   │   ├── state.js               # Proxy 微响应式状态树、GB11643 校验与三态评估
│   │   ├── tab_workbench.js       # 场景 01：填报总控、自动识萃、全套/独立出件
│   │   ├── tab_scope.js           # 场景 02：经营范围黄金套餐速切、检索与代数差集
│   │   ├── tab_docs.js            # 场景 03：文书智能洗牌、与总控双向互通、桌面直出
│   │   ├── tab_config.js          # 场景 04：01~05 积木步骤与坐标/延时可视化工作台
│   │   └── tab_history.js         # 场景 05：历史办件档案检索、调入与清理（置末位）
│   ├── api_bridge.py              # 轻量 IPC 路由桥接层（已与 Win32 OS 调用解耦）
│   └── workbench.html             # 桌面工作台主页面（5 大场景符合人类直觉排布）
├── tests/                         # 自动化验证与毫秒级靶向快检
│   ├── fast_check.py              # 核心功能与前端 DOM ID 契约毫秒级快检 (ocr/q/scope/docx/ui/all)
│   └── test_edge_cases.py         # 边界情况全量用例深度测试
├── .aiignore / .cursorignore / .geminiignore / .gitignore / .rgignore
├── .cursorrules                   # 本地 AI 极速维护铁律与六大架构红线
├── LICENSE                        # 开源许可证 (MIT License)
├── requirements.txt               # 运行环境与依赖清单
├── ai_locate.py                   # 0.01 秒实时行号与 @AI-ANCHOR 代码切片定位雷达
├── app_main.py                    # 桌面端主程序入口 (PyWebView 窗口宿主)
├── build_exe.py / launcher.cs     # 原生 C# 极速无控制台启动外壳源码与编译脚本
├── integrate_external.py          # 外部文书技能脚本与模板一键收拢工具
├── 修改前请看我.md                # 架构规范、极速维护与 @AI-ANCHOR 锚点手册 (Demo)
└── README.md                      # 软件总览与设计架构说明
```

---

## 5. 快速启动、快捷键与自检指令 (Quick Start & Verification)

### 5.1 启动方式
* **日常使用**：双击根目录下的 **`个体户填报.exe`**，秒级拉起独立工作台窗口。
* **开发者源码启动**：
  ```powershell
  # 1. 安装核心依赖（推荐国内清华镜像源）
  pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

  # 2. 启动桌面端界面
  python app_main.py
  ```

### 5.2 快捷交互与快捷键
* <kbd>Alt</kbd> + <kbd>1</kbd> ~ <kbd>5</kbd>：一键切换顶部 `01 填报总控` ~ `05 历史档案` 五大场景。
* <kbd>F5</kbd> / <kbd>Ctrl</kbd>+<kbd>R</kbd>：热重载全部 JSON 配置与前端界面（无需重启程序）。
* <kbd>Ctrl</kbd> + <kbd>K</kbd>：呼出全局指令控制台（快速检索经营范围、执行出件、清空新办件）。
* <kbd>Ctrl</kbd> + <kbd>M</kbd>：切换 `380×140` 悬浮 Mini-HUD 盯盘伴随窗。
* <kbd>F10</kbd> / <kbd>F12</kbd>：按键精灵默认启动键 / 紧急中止键。

### 5.3 毫秒级靶向自检
```powershell
python tests/fast_check.py all     # 全量核心模块冒烟自检 (< 600ms)
python tests/fast_check.py ocr     # 单独验证 OCR 与地址切分
python tests/fast_check.py q       # 单独验证 .Q 编译与 Action IR 还原
python tests/fast_check.py ui      # 单独验证前端 DOM ID 契约
```
