// @AI-ANCHOR: [JS-CONFIG-META] 01~05 步骤专属延时键名与坐标中文元数据大字典 (已被 .rgignore 屏蔽)
/**
 * app.js - 前端交互逻辑、积木式步骤编排、坐标延时直调与文书矩阵中心 (GTH V2.5)
 * 核心升级：
 * 1. 01~05 积木式步骤卡片：单击自由加入/剔除步骤，双击直接弹出该步骤专属「坐标方块 + 时间方块」快调面板。
 * 2. 单步重编与全套出件实时刷新交付柜与状态反馈，彻底告别黑盒。
 * 3. 场地证明独立一键出件、住改商自动导出前两页 PNG 图片、直接解析 .Q 脚本还原表单。
 * 4. 历史办件档案支持实时搜索过滤、单条删除与一键清空。
 */

const STEP_DELAY_MAP = {
  step1: ["countdown_ms", "person_save_ms", "jump_settle_ms", "launch_jump_ms", "cross_system_wait_ms", "agree_ms", "done_ms", "confirm_ms", "input_ms", "step_wait_ms", "save_ms"],
  step2: ["scope_open_ms", "search_ms", "add_ms", "save_ms", "confirm_ms"],
  step3: ["input_ms", "type_ms", "dropdown_open_ms", "option_pick_ms", "agree_ms", "add_ms", "launch_jump_ms"],
  step4: ["tip_read_ms", "map_search_ms", "map_click_ms", "wheel_wait_ms", "dropdown_open_ms", "option_pick_ms", "confirm_ms", "step_wait_ms", "input_ms", "done_ms", "add_ms"],
  step5: ["step_wait_ms", "dropdown_open_ms", "wheel_wait_ms", "confirm_ms"],
};

const CONFIG_METADATA = [
  {
    groupId: "step1",
    title: "步骤 01 · 名称自主申报与承诺书 (核名)",
    badge: "HEMING_STEP1",
    items: [
      { key: "核名_出资额", label: "出资额输入框", desc: "步骤1：拟设企业首屏，出资额输入框", type: "coord", delayKey: "input_ms" },
      { key: "核名_下一步", label: "下一步按钮", desc: "步骤1：出资额录入后点击「下一步」进入经营者页", type: "coord", delayKey: "step_wait_ms" },
      { key: "核名_经营者姓名", label: "经营者姓名输入框", desc: "步骤1：经营者页，经营者姓名输入框", type: "coord", delayKey: "input_ms" },
      { key: "核名_证件类型下拉", label: "证件类型下拉框", desc: "步骤1：经营者页，证件类型下拉选择框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "核名_居民身份证", label: "下拉项：居民身份证", desc: "步骤1：证件类型展开后的「居民身份证」选项", type: "coord", delayKey: "option_pick_ms" },
      { key: "核名_证件号码", label: "身份证号码输入框", desc: "步骤1：经营者页，证件号码输入框", type: "coord", delayKey: "input_ms" },
      { key: "核名_经营者保存", label: "经营者保存按钮", desc: "步骤1：点击「保存」，经营者落入下方列表", type: "coord", delayKey: "person_save_ms" },
      { key: "核名_经营者完成", label: "经营者完成按钮", desc: "步骤1：列表插入姓名行后，下移位的「完成」按钮（弹出承诺书）", type: "coord", delayKey: "done_ms" },
      { key: "核名_承诺书勾选", label: "承诺书同意勾选框", desc: "步骤1：承诺书弹窗强制倒计时结束后勾选「我已仔细阅读并同意...」", type: "coord", delayKey: "agree_ms" },
      { key: "核名_承诺书同意", label: "我已阅读并同意按钮", desc: "步骤1：承诺书弹窗底部「我已阅读并同意和履行」确定按钮", type: "coord", delayKey: "agree_ms" },
      { key: "核名_确认弹窗确定", label: "申报确认弹窗确定", desc: "步骤1：系统确认弹窗点「确认」（申报成功后将无法修改）", type: "coord", delayKey: "confirm_ms" },
      { key: "核名_打印告知书", label: "打印告知书和承诺书", desc: "步骤1：申报成功页，点击新标签打开告知书 PDF", type: "coord", delayKey: "launch_jump_ms" },
      { key: "核名_另存为地址栏", label: "另存为窗口地址栏", desc: "步骤1：另存为对话框上方地址栏（用于键入归档文件夹路径）", type: "coord", delayKey: "input_ms" },
      { key: "核名_另存为保存", label: "另存为保存按钮", desc: "步骤1：另存为对话框右下角保存按钮", type: "coord", delayKey: "save_ms" },
      { key: "核名_发起设立", label: "发起设立按钮", desc: "步骤1：申报成功页，「发起设立」按钮进入开办大表单", type: "coord", delayKey: "launch_jump_ms" },
      { key: "设立登记_温馨提示确定", label: "设立登记温馨提示确定", desc: "开办首屏：跨系统加载后，关闭代理人备案提示弹窗", type: "coord", delayKey: "step_wait_ms" },
    ]
  },
  {
    groupId: "step2",
    title: "步骤 02 · 经营范围装配与许可确认",
    badge: "SCOPE_STEP2",
    items: [
      { key: "经营范围开启", label: "经营范围开启按钮", desc: "步骤2：大表单右侧点击打开经营范围装配弹窗", type: "coord", delayKey: "scope_open_ms" },
      { key: "范围_不符合提示知道了", label: "地区提示「知道了」", desc: "步骤2：经营范围弹窗开启后，点击关闭地区限制提示", type: "coord", delayKey: "confirm_ms" },
      { key: "范围搜索框", label: "经营范围代码搜索框", desc: "步骤2：弹窗内输入经营范围条目代码的搜索框", type: "coord", delayKey: "search_ms" },
      { key: "范围搜索按钮", label: "经营范围搜索按钮", desc: "步骤2：弹窗搜索框右侧「搜索」按钮", type: "coord", delayKey: "add_ms" },
      { key: "范围添加", label: "结果条目点选/添加", desc: "步骤2：搜索结果首行条目的勾选/添加按钮", type: "coord", delayKey: "add_ms" },
      { key: "许可_我已阅读并知晓", label: "许可提示「知晓」", desc: "步骤2：含许可项目时弹出的审批提示「我已阅读并知晓」", type: "coord", delayKey: "confirm_ms" },
      { key: "许可_确定", label: "许可提示「确定」", desc: "步骤2：许可提示弹窗确认按钮", type: "coord", delayKey: "confirm_ms" },
      { key: "范围_完成并保存", label: "经营范围「完成并保存」", desc: "步骤2：经营范围弹窗右下角「完成并保存」关闭按钮", type: "coord", delayKey: "save_ms" },
    ]
  },
  {
    groupId: "step3",
    title: "步骤 03 · 经营者、联络员与经办人",
    badge: "PERSON_STEP3",
    items: [
      { key: "印章_否", label: "是否申领公章：选「否」", desc: "步骤3：开办大表单顶部，是否申领公章选「否」（双点抗抖）", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "联系电话", label: "开办联系电话输入框", desc: "步骤3：开办大表单顶部联系电话输入框", type: "coord", delayKey: "input_ms" },
      { key: "经营者姓名", label: "开办经营者姓名", desc: "步骤3：大表单经营者信息段，姓名输入框", type: "coord", delayKey: "input_ms" },
      { key: "经营者电话", label: "经营者联系电话", desc: "步骤3：大表单经营者信息段，联系电话输入框", type: "coord", delayKey: "input_ms" },
      { key: "住所", label: "经营者住所输入框", desc: "步骤3：大表单经营者信息段，身份证地址输入框", type: "coord", delayKey: "input_ms" },
      { key: "移动电话", label: "经营者移动电话", desc: "步骤3：大表单经营者移动电话输入框", type: "coord", delayKey: "input_ms" },
      { key: "邮箱", label: "经营者电子邮箱", desc: "步骤3：大表单经营者电子邮箱输入框", type: "coord", delayKey: "input_ms" },
      { key: "经营者类别", label: "经营者类别下拉框", desc: "步骤3：经营者类别下拉选择框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "类别_中国大陆", label: "下拉项：中国大陆", desc: "步骤3：经营者类别展开后的「中国大陆」项", type: "coord", delayKey: "option_pick_ms" },
      { key: "身份证件", label: "身份证件类型下拉", desc: "步骤3：身份证件类型下拉框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "证件_居民身份证", label: "下拉项：居民身份证", desc: "步骤3：证件类型展开后的「中华人民共和国居民身份证」", type: "coord", delayKey: "option_pick_ms" },
      { key: "身份证号码", label: "身份证号码输入框", desc: "步骤3：大表单经营者身份证号码输入框", type: "coord", delayKey: "input_ms" },
      { key: "联络员_增加", label: "联络员「增加」按钮", desc: "步骤3：联络员表格右侧「增加」按钮", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "联络员_公示是", label: "公示联络员：选「是」", desc: "步骤3：联络员弹窗内「是否公示系统登录联络员」选「是」", type: "coord", delayKey: "add_ms" },
      { key: "联络员_姓名搜索", label: "联络员姓名搜索框", desc: "步骤3：联络员弹窗姓名搜索框（点击关联经营者）", type: "coord", delayKey: "launch_jump_ms" },
      { key: "联络员_候选项", label: "联络员候选人项", desc: "步骤3：联络员搜索弹出的同名候选人项（自动带出数据）", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "联络员_住所", label: "联络员住所输入框", desc: "步骤3：联络员弹窗住所输入框", type: "coord", delayKey: "input_ms" },
      { key: "联络员_保存", label: "联络员弹窗「保存」", desc: "步骤3：联络员弹窗右下角「保存」关闭按钮", type: "coord", delayKey: "agree_ms" },
      { key: "经办人现居住地址", label: "经办人现居住地址", desc: "步骤3：大表单经办人现居住地址输入框", type: "coord", delayKey: "input_ms" },
      { key: "银行开户_否", label: "是否预约银行开户：选「否」", desc: "步骤3：大表单底部是否预约银行开户单选「否」", type: "coord", delayKey: "dropdown_open_ms" },
    ]
  },
  {
    groupId: "step4",
    title: "步骤 04 · 经营场所选址与地图定位",
    badge: "SITE_STEP4",
    items: [
      { key: "经营场所_填报", label: "经营场所「填报」按钮", desc: "步骤4：大表单经营场所栏右侧「填报」按钮", type: "coord", delayKey: "step_wait_ms" },
      { key: "温馨提示_我已阅读", label: "场所温馨提示「我已阅读」", desc: "步骤4：选择地址弹窗强制倒计时结束后「我已阅读」按钮", type: "coord", delayKey: "tip_read_ms" },
      { key: "房屋用途下拉", label: "房屋用途下拉框", desc: "步骤4：选择地址弹窗，规划用途下拉框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "房屋用途_住宅", label: "下拉项：住宅", desc: "步骤4：用途下拉展开后的「住宅」项", type: "coord", delayKey: "option_pick_ms" },
      { key: "住宅提示_确定", label: "住宅提示弹窗「确定」", desc: "步骤4：选住宅后弹出的住改商提示弹窗「确定」", type: "coord", delayKey: "confirm_ms" },
      { key: "县区下拉", label: "行政区划县区下拉框", desc: "步骤4：县区下拉选择框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "县区_郯城县", label: "下拉项：郯城县", desc: "步骤4：县区下拉展开后的「郯城县」项", type: "coord", delayKey: "option_pick_ms" },
      { key: "乡镇下拉", label: "乡镇街道下拉框", desc: "步骤4：乡镇街道下拉选择框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "街路输入", label: "街路门牌输入框", desc: "步骤4：详细街路门牌号输入框", type: "coord", delayKey: "input_ms" },
      { key: "房屋性质下拉", label: "房屋性质下拉框", desc: "步骤4：房屋性质下拉选择框", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "房屋性质_市场化商品房", label: "下拉项：市场化商品房", desc: "步骤4：性质下拉展开后的「市场化商品房」项", type: "coord", delayKey: "option_pick_ms" },
      { key: "所有权人姓名", label: "房屋产权人姓名输入框", desc: "步骤4：房屋所有权人姓名", type: "coord", delayKey: "input_ms" },
      { key: "产权证名称", label: "产权证名称输入框", desc: "步骤4：产权证明材料名称", type: "coord", delayKey: "input_ms" },
      { key: "产权人联系方式", label: "产权人联系电话输入框", desc: "步骤4：产权人联系电话", type: "coord", delayKey: "input_ms" },
      { key: "产权人证件号码", label: "产权人身份证号输入框", desc: "步骤4：产权人身份证件号码", type: "coord", delayKey: "input_ms" },
      { key: "使用方式_自有", label: "使用方式：自有", desc: "步骤4：房屋使用方式单选「自有」", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "使用方式_租赁", label: "使用方式：租赁", desc: "步骤4：房屋使用方式单选「租赁」", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "使用方式_无偿使用", label: "使用方式：无偿使用", desc: "步骤4：房屋使用方式单选「无偿使用」", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "使用方式提示_确定", label: "使用方式提示「确定」", desc: "步骤4：选使用方式后弹窗确认按钮", type: "coord", delayKey: "confirm_ms" },
      { key: "位置标记", label: "地图选址「位置标记」按钮", desc: "步骤4：地址弹窗右上角「位置标记」按钮", type: "coord", delayKey: "done_ms" },
      { key: "地图搜索框", label: "地图选址搜索输入框", desc: "步骤4：高德地图定位弹窗地址搜索框", type: "coord", delayKey: "input_ms" },
      { key: "地图搜索按钮", label: "地图搜索按钮", desc: "步骤4：地图搜索框右侧「搜索」按钮", type: "coord", delayKey: "map_search_ms" },
      { key: "地图中央坐标点", label: "地图中心落点定位", desc: "步骤4：搜索结果地图正中央图钉点", type: "coord", delayKey: "map_click_ms" },
      { key: "地图_确定", label: "地图弹窗「确定」按钮", desc: "步骤4：地图弹窗右下角「确定」回填坐标", type: "coord", delayKey: "done_ms" },
      { key: "选择地址_确定", label: "选择地址弹窗「确定」", desc: "步骤4：选择地址弹窗底部「确定」按钮", type: "coord", delayKey: "step_wait_ms" },
      { key: "提交确认_确定", label: "场所提交确认「确定」", desc: "步骤4：场所提交后系统确认弹窗「确定」", type: "coord", delayKey: "confirm_ms" },
      { key: "面积", label: "经营场所面积输入框", desc: "开办表单：经营场所面积（默认 60 平方米）", type: "coord", delayKey: "input_ms" },
      { key: "送达电话", label: "法律文书送达电话输入框", desc: "开办表单：文书送达电话", type: "coord", delayKey: "input_ms" },
      { key: "送达邮箱", label: "法律文书送达邮箱输入框", desc: "开办表单：文书送达邮箱", type: "coord", delayKey: "input_ms" },
      { key: "组成形式_个人经营", label: "组成形式：个人经营", desc: "开办表单：组成形式单选「个人经营」", type: "coord", delayKey: "dropdown_open_ms" },
      { key: "从业人数", label: "从业人数输入框", desc: "开办表单：从业人数输入框（默认 1）", type: "coord", delayKey: "input_ms" },
      { key: "资金数额", label: "资金数额输入框", desc: "开办表单：资金数额输入框（单位万元）", type: "coord", delayKey: "input_ms" },
      { key: "滚动条_上翻", label: "滚动条上翻按钮", desc: "页面滚动条上方箭头", type: "coord", delayKey: "wheel_wait_ms" },
      { key: "滚动条_下翻", label: "滚动条下翻按钮", desc: "页面滚动条下方箭头", type: "coord", delayKey: "add_ms" },
    ]
  },
  {
    groupId: "step5",
    title: "步骤 05 · 暂存业务与属地监管所",
    badge: "SUPERVISOR_STEP5",
    items: [
      { key: "暂存业务", label: "页面右侧「暂存业务」按钮", desc: "步骤5：右侧浮动工具栏「暂存业务」按钮", type: "coord", delayKey: "step_wait_ms" },
      { key: "暂存确认_确定", label: "暂存确认弹窗「确定」", desc: "步骤5：点击暂存后弹出的确认弹窗「确定」", type: "coord", delayKey: "confirm_ms" },
    ]
  },
  {
    groupId: "delays",
    title: "⏱️ 流程延时与时间积木配置",
    badge: "DELAYS_TIMING",
    items: [
      { key: "countdown_ms", label: "承诺书强制倒计时延时", desc: "步骤1：自主申报承诺书弹窗官方强制倒计时（硬性规定 12~15s，建议 16000ms）", type: "delay" },
      { key: "jump_settle_ms", label: "页面跳转缓冲延时", desc: "步骤1：确认弹窗确定后跳转申报成功页的等待余量（建议 1500ms）", type: "delay" },
      { key: "person_save_ms", label: "经营者保存等待延时", desc: "步骤1：核名经营者保存后落入列表的等待时间（建议 4000ms）", type: "delay" },
      { key: "cross_system_wait_ms", label: "跨系统实例加载延时", desc: "从核名成功页发起设立到开办大表单渲染完成的缓冲时间（建议 8000ms）", type: "delay" },
      { key: "tip_read_ms", label: "场所温馨提示阅读延时", desc: "步骤4：经营场所选择地址弹窗温馨提示强制阅读时间（建议 5000ms）", type: "delay" },
      { key: "scope_open_ms", label: "经营范围弹窗开启延时", desc: "步骤2：点击经营范围开启后等待大弹窗加载的缓冲时间（建议 4000ms）", type: "delay" },
      { key: "launch_jump_ms", label: "发起设立跨页跳转延时", desc: "点击发起设立或打印告知书后的跳转缓冲（建议 2000ms）", type: "delay" },
      { key: "save_ms", label: "数据保存等待延时", desc: "经营范围或大表单保存通用延时（建议 1500ms）", type: "delay" },
      { key: "done_ms", label: "完成按钮点击延时", desc: "经营者完成或弹窗完成按钮延时（建议 1000ms）", type: "delay" },
      { key: "agree_ms", label: "承诺/协议同意延时", desc: "承诺书勾选后及联络员保存等待延时（建议 1200ms）", type: "delay" },
      { key: "confirm_ms", label: "提示弹窗确认延时", desc: "各类确认提示弹窗关闭等待延时（建议 1500ms）", type: "delay" },
      { key: "step_wait_ms", label: "常规单步跨步等待延时", desc: "通用单步操作后的缓冲等待时间（建议 800ms）", type: "delay" },
      { key: "map_search_ms", label: "地图搜索定位等待延时", desc: "高德地图搜索地址后的渲染等待时间（建议 1500ms）", type: "delay" },
      { key: "map_click_ms", label: "地图标点落位等待延时", desc: "点击地图中央点后的坐标捕捉时间（建议 800ms）", type: "delay" },
      { key: "wheel_wait_ms", label: "滚轮滚动步进间隔延时", desc: "下拉列表滚轮滚动的单次间隔时间（建议 200ms）", type: "delay" },
      { key: "dropdown_open_ms", label: "下拉菜单展开延时", desc: "点击下拉框后等待下拉列表弹出的时间（建议 400ms）", type: "delay" },
      { key: "option_pick_ms", label: "下拉选项选定延时", desc: "点击下拉选项后的回填时间（建议 350ms）", type: "delay" },
      { key: "click_ms", label: "通用鼠标单次点击延时", desc: "全局通用单次鼠标左键点击后的缓冲时间（建议 350ms）", type: "delay" },
      { key: "input_ms", label: "输入框聚焦等待延时", desc: "点击输入框后等待光标就绪的时间（建议 300ms）", type: "delay" },
      { key: "type_ms", label: "文本键入后延时", desc: "SayString 键入文本后的缓冲时间（建议 400ms）", type: "delay" },
      { key: "start_delay_ms", label: "脚本启动前缓冲延时", desc: "脚本启动后执行第一条命令前的启动缓冲（建议 100ms）", type: "delay" },
      { key: "search_ms", label: "范围搜索框点击延时", desc: "步骤2：点击范围搜索框后的聚焦等待（建议 200ms）", type: "delay" },
      { key: "add_ms", label: "范围条目勾选延时", desc: "步骤2：点击搜索及勾选添加后的等待（建议 500ms）", type: "delay" },
    ]
  }
];
