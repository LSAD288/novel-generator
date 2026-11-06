# 自由画布：指定原型接入

用户2026-10-25明确指定完整采用 `http://127.0.0.1:4174/?view=canvas`。来源为 `/Volumes/WorkDisk/Qoder/Qoder的炼笔智作/自由画布原型-20261024/`，非Git仓库；来源版本以控制仓库对应记录中的HTML/JS/CSS SHA-256固定，不根据目录日期推定版本。

本目录保留实际原型的DOM/SVG渲染、卡片样式、顶部工具栏、手势、连线、手绘和详情编辑。产品适配包括：移除独立演示的品牌壳、样例正文和示例卡；增加场景/UI/主题桥接；稳定新对象ID；输入法组合保护；只读失效资料；卡片文字在小尺寸下收缩裁切。演示原型的内存状态接回原有资料JSON与本机可靠保存，不沿用“刷新重置”。

宿主使用受控同源文档载入本目录的固定HTML及外部JS/CSS，保持现有CSP，不开放`frame-ancestors`，不加载CDN，不接收跨域内容。主题接入写作台的`lianbi:theme`和`LianbiAppearance.applyTheme`。原型内部不接触账号凭据或正文编辑器；业务引用、权限、校验、保存、作品切换都在宿主适配层中。

旧的`materials.storyCanvas.version=1`场景仍可读取，不迁移数据库。旧绘制引擎和构建依赖已退场；新卡片仍关联原人物／设定／情节ID，删除画布卡不删除原资料，撤销保留引用，视口与未完成输入按账号及作品留在本机。后续修改原型不会自动更新产品，需按新来源版本再适配与验证。

## 2026-10-26 画布打磨

按用户六张截图收口：去掉宿主重复标题/保存行和外层左右/下方留白，资料入口移至正文/画布标签行；正常保存反馈留在画布底部。卡片工具下拉选择方卡或圆卡，详情可改形态与主题适配预设色/自选色，连线与箭头同步着色。人物与情节的业务引用不因形态改变而转换。

手绘菜单含铅笔、蜡笔、毛笔、粗细、颜色、压感开关与压力强度；笔事件读取PointerEvent.pressure，鼠标固定宽度。笔迹使用本地SVG轮廓，蜡笔有颗粒表现，毛笔收笔。局部/整笔/框选三种橡皮仅操作笔迹，一次手势一次撤销。两指平移缩放会取消尚未完成的单指墨迹，随后仍可继续绘制；实体Pencil结论与模拟输入分开。

缩放控件不进入画布双击建卡逻辑；端口拖动优先于连线模式的点选逻辑。连线工具明确点起点/终点，详情的“从这张卡连线”才预置起点；可连续连线，取消/失焦回收指针捕获。端口和命中区不随缩放变小。

色值、cardShape、写作速查标记/速记、笔类/压力数组均为storyCanvas.version1的可选customData元信息，仍使用rectangle/text/arrow/freedraw四类对象，无数据库迁移。旧DTO缺少样式时保留既有元信息。新宿主给受控文档标记data-host-bridge=2；旧缓存宿主遇到新版工具会显示先保存/刷新的可操作指引，flush原样保留旧数据，避免新控件修改被旧编解码器静默丢失。

写作速查按稳定资料引用去重。用户在卡片详情主动勾选并可填写240字内速记，未填写时只截取内容首段用于展示，不改动全文、不调用模型；全文和全部关联仍可在原资料/画布查看。关系方向及同纲的明确分级继续受原校验约束。场景示例的宽布局由验收时真实拖动完成，不会自动重排用户原画布。

交互依据：[W3C Pointer Events3](https://www.w3.org/TR/pointerevents3/)。源码仍来自前述已选原型的产品适配，新增几何代码为本项目扩展，未引入通用画布SDK、在线资源或新依赖。完整需求、原始失败用例、小说和回归结果沿控制仓库原发布记录canvasPolish20261026保存。

2026-10-26本地候选：顶部工具栏与原详情区保留；作品画布标签复用现有作品栏。工具状态、选择与视角按作品恢复，撤销历史只在同会话内存保留，不写入稿件。`controls.js`从本项目`market/rank-select.js`适配现有值／change契约，增加画布范围的单一菜单、边缘避让和方圆分段。参考[tldraw UI components](https://tldraw.dev/sdk-features/ui-components)的工具／动作一致性，不引入其SDK、代码或依赖。回归入口：`tests/writer_canvas_state_browser.cjs <隔离runtime目录>`、`tests/writer_canvas_tabs_browser.cjs <隔离runtime目录>`，后者通过`LIANBI_CANVAS_SAMPLE`指定原40卡小说备份；环境沿项目Playwright与隔离服务约定。

同日用户补充：选择支持框选、Shift多选、Ctrl/⌘A、组移动及四角等比缩放（连线随卡片端点）；选择模式空白拖动框选，手形/空格平移。新增T文字为既有原生text场景元素，双击输入、独立移动/缩放/颜色，旧DTO缺少texts字段时保留已有独立文字。自动保存合并到800ms闲时，活动指针及IME组合期延后，1.2秒回执延迟与2.2秒连续笔画回归覆盖。参考[tldraw selection](https://tldraw.dev/sdk-features/selection)的选择ID与联合边界方法，无SDK依赖。

22:32返工：自动保存现为所有画布交互结束3秒后触发，取代800ms策略。`writer:prototype-activity`传递轻量活动通知；自动读取快照只在空闲时进行。画布保存用`commitMaterials(...,{quiet:true})`保留验证和容量保护，跳过常规编辑器重绘与重复自动保存；回执不更新画布数据/选中。`tests/writer_canvas_quiet_save_browser.cjs <独立runtime目录>`验证计时、零标签重绘、延迟回执、手动关闭和失败保护。


## 2026-10-27 手动保存、侧栏与开源笔迹（仅本地候选）

本节替代上文3秒自动保存：操作中不再定时持久化画布；“保存”及⌘／Ctrl S主动收拢最新快照，切换正文／作品、关闭画布标签和退出登录通过原保存钩子收拢。恢复草稿仍使用原按账号／作品隔离的draft字段，普通刷新前同步检查点、重开恢复，成功落盘后清除；不能保证浏览器关闭后的异步请求完成，也未验证强制终止系统。保存失败不关闭画布，输入法组合期等待用户结束组合再保存。新增测试入口`tests/writer_canvas_manual_save_browser.cjs <隔离runtime目录>`；旧quiet_save/autosave命令入口转向同一套当前策略检查，避免运行已被替代的计时断言。

侧栏两区互斥、独立滚动、隐藏滚动条；原生details展开语义保留，显式内容容器适配Chrome的::details-content布局。搜索／展开全文及原来源ID保持不变。

| 候选 | 核验与采用方式 |
| --- | --- |
| [perfect-freehand](https://github.com/steveruizok/perfect-freehand)1.2.3 | MIT，零运行依赖；采用官方npm固定版本的CJS发布代码（约4.6KB），外加浏览器／CommonJS包装，无网络运行依赖。支持实际压力、平滑、端点及收笔，适合本画布的SVG轮廓。保留LICENSE；只替换毛笔渲染，不替换原中心线、存储、选框或橡皮。 |
| [fabric-brush](https://github.com/tennisonchan/fabric-brush/tree/811f13415fdd396aa30ecc75f1b51ba45e1d9e6d) | 源LICENSE为自定义宽松授权（GitHub识别为NOASSERTION），不是标准MIT标识；旧代码依赖Fabric.js的BaseBrush／util API，与本画布不直接匹配。仅参考CrayonBrush颗粒盖印思路，未复制其代码、未引入依赖；适配为本项目SVG确定性颗粒，长笔画粒子数有上限。 |

毛笔的鼠标宽度仍固定，仅保留自然收笔；手写笔使用原采样压力，未制造鼠标压力。新旧笔迹复用原DTO／version1，重新渲染会显示新效果，中心线及业务资料不迁移。单点、重复点、长笔画、压力、擦除、撤销／重做和保存重开均在现有测试中验证；实体Pencil／Safari及原生包未验证。

固定包核验：npm `perfect-freehand@1.2.3` 的SHA-512完整性已与registry元数据比对，SHA-256为`060048047071b6ffb2170c8b867ba995f365ec811dc32435574d3d5f7625981f`。`vendor/perfect-freehand.js`保留未经改写的CJS代码，仅去掉未打包的sourceMappingURL并包入全局导出函数；无需npm安装或框架构建。


2026-10-27 鼠标快速落笔返工（仍仅本地）：原61413的事件观察捕获21次鼠标拖画，11次在pointerup前8–18ms先收到lostpointercapture，旧处理将已有9–26点的笔画回滚。lostpointercapture只表示后续事件恢复正常命中投递，不能据此等同pointercancel；修复保留活动手势，用document级pointermove/up/cancel接住捕获丢失后的投递，系统pointercancel和失焦仅收尾并保留笔迹／位置；用户主动Esc／撤销才回滚，双指平移为明确手势切换。每次抬笔只提交一次，不改手绘工具、保存策略或笔迹结构。参考[W3C Pointer Events3 capture](https://www.w3.org/TR/pointerevents3/#the-lostpointercapture-event)和[Chrome drag guidance](https://github.com/GoogleChrome/modern-web-guidance/blob/main/skills/modern-web-guidance/guides/ui-behaviors/drag.md)。新增回归`tests/writer_canvas_pointer_capture_browser.cjs <源码目录> <证据目录>`重放原顺序；普通连续画笔计数通过不能替代此用例。


同日用户最新明确确认替代上文手动保存限定：恢复最早原型接入提交422ca2c／94f4dd6中的300ms改动后自动保存间隔，同时保留手动保存及离开前收拢。采用现有quiet资料提交，活动手势和IME延后，保存回执不重建场景、输入或标签；不恢复旧的整页重绘调用链。自动失焦／系统取消不会恢复旧快照，只有用户主动Esc、活动手势期间的撤销，或明确切换双指平移才取消当次未完成手势。


## 2026-10-27 搭子确认式联动（本地待试用）

`writer-canvas-proposal.js`是受限的纯数据适配层：`validate`校验8／16节点树与授权引用，`apply`只新增大纲／卡片及明确选择的侧栏状态。`proposalContext()`收拢当前有效输入并提供账号、作品和资料基线，`applyProposal()`核对基线后沿原保存链持久化，`showWritingSidebar()`复用既有侧栏开关。模型没有DOM、文件、SQL或任意动作执行接口。

新增`storyCanvas.companionApplications`是version1的可选JSON元数据，最多保留100份防重复回执；`outlines[].companionOrigin`记录来源请求和提炼／规划类型，不改变数据库结构。既有DTO转换保留元数据，场景与原资料继续分开；单次图形撤销不会删除业务大纲。来源和验证沿控制仓库原记录`unifiedWriter20261027`，发布仍等待用户试用。

结构化回复延续[DeepSeek JSON Output](https://api-docs.deepseek.com/zh-cn/guides/json_mode/)的JSON格式与示例约束，保留空白／非法JSON／截断和保存失败分支，不自动重试供应商调用。服务端只输出已校验草案，模型回复不能作为“已应用”的事实；程序状态与真正保存结果单独显示。
