# 可复用设备样机

资源目录为 `assets/device-mockups/`。先读 `manifest.json`，不凭目测猜屏幕位置。

| 模板 ID | 用途 | 默认表现 |
|---|---|---|
| iphone-14-pro-silver | 竖屏截图或视频 | 银色金属边、侧键、天线、灵动岛；周围沿用页面底色 |
| macbook-pro-screen | 横屏软件截图 | 薄边屏幕和刘海，省去键盘与底座 |

来源为 [picturepan2/devices.css](https://github.com/picturepan2/devices.css)，锁定版本见 manifest；MIT 许可原文保存在同目录 `LICENSE-Devices.css.txt`。保留 CSS 原文件、版权、源版本与衍生说明；不能把“网上免费下载”视为可再分发。当前模板为基于开源 CSS 渲染的矢量风外框，不是实拍设备，也不是 Apple 官方认证素材。模板可用性不代表用户已接受其视觉风格。

## 套入真实截图

先盘点所有截图与案例画面，并决定展示目的。桌面软件/网页界面、作为屏幕作品展示的完整横屏画面默认用 `macbook-pro-screen`；手机界面默认用 iPhone。横屏视频抽帧可以装入 Mac 屏幕作为作品展示，不声称它原本就在 Mac 上运行。尺寸只是线索：竖幅摄影或游戏画面不自动等于手机截图，方形 UI 局部也不硬塞进电脑。局部放大、逐状态裁图、已经拼好的前后对照、已有设备框或无设备语义的照片可保留原样，保留原图时简记展示原因；用户明确要求加框/不加框优先。

常规制作沿用项目素材记录，明确每张截图的用途、裁切和加框选择即可。需要脚本审计时，再把全部证据图片整理为每页 evidence_images 数组，无则空数组；逐项写 id、source（原始文件）、media_kind、purpose、treatment（device / plain / already-framed）、protected_content（必须保留的内容）。plain / already-framed 写 reason；device 写 template、mode（layered / composite）、files 和 object_ids。横屏完整作品与局部裁图在规划阶段就分开，不能排版完成后才想起样机。

优先直接用已经渲染好的透明外框和遮罩；普通执行不需要浏览器或重新下载。每个模板的 frame 是有透明屏幕孔的 PNG，screen_mask 是白色 alpha 遮罩，已经排除刘海/灵动岛。两者共享像素尺寸，保留三倍分辨率。模板透明边距属于资源，不是设备轮廓。

```bash
node <本Skill>/scripts/compose_device_mockup.mjs --device macbook-pro-screen --input screenshot.png --output preview.png --layers-dir device-layers
```

依赖为 Node.js 与 `@napi-rs/canvas`；从项目或 Skill 附近的 node_modules 解析，`RUNTIME_NODE_MODULES` 只作可选的已有依赖路径，详见工具适配。

脚本默认 `cover`，按比例铺满屏幕并裁掉多余区域，不留比例不匹配造成的黑边/空带，不拉伸界面。先确认必须保留的标题、按钮、数值或结论；居中裁切不合适时，用 `--source-crop x,y,w,h` 选取原截图像素中的窗口，再执行 cover。例如960×540截图装入16:10屏幕，可选 `--source-crop 24,0,864,540`，但位置须由本次证据决定，不能固定照抄。无法同时保住证据和填满时改布局、选合适容器或拆细节，不能默默切掉关键信息。`--fit contain` 仅为明确要求完整截图且接受空带的例外，不作为默认降级。

`--source-crop` 裁截图内容；`--crop x,y,w,h` 裁合成后的设备两层，用于画布出血，二者坐标不同。脚本拒绝输出覆盖输入截图。保持原截图和两种裁切参数。

`device-layers/screen.png` 和 `frame.png` 是独立图层，以同一个显示框、同一缩放倍率放入 PPT；屏幕在下，外框在上。文字、数字、胶囊与箭头仍用 PPT 原生对象。保留原截图及 placement.json，换截图时重新生成屏幕层，不能把带截图的预览覆盖回通用模板。外框可移动/缩放/替换，但不是逐个侧键可编辑的原生形状。

默认使用独立两层。工具只能插入合成图时，允许插入脚本输出的完整 preview.png，记录 composite 模式并保留两层源文件；截图与框在该图片内不能单独编辑。不能把 screen.png 单独插入后称已加框，也不能只上传外框却没把它加入页面。工具/依赖失败时尝试现有等效合成能力，仍不可用就报告具体缺口，不能无说明交付裸截图。外框应保留可辨边缘，出血裁切不把整个框都裁没。

placement.json 记录 `source_crop`、`visible_source_rect` 及 `source_to_layer`；可见源区域计算同时考虑设备出血裁切，整块屏幕裁出时为 null（制作时应避免）。原截图中的点经 `layer_x=source_x*scale_x+offset_x`、`layer_y=source_y*scale_y+offset_y` 映射到输出层，再按该层在PPT中的缩放和平移映射到页面。换图、裁切或缩放后同步更新圈框、箭头端点和局部标注；不能只换屏幕图而沿用旧坐标。刘海/圆角遮罩覆盖区也不能放关键证据。

## 按需脚本审计

日常仍检查实际页面里的外框、裁切和证据可读性。需要批量审计或排障时才整理下列数据；不以“文件存在”代替页面使用。可用当前工具等效检查，或运行：

```bash
python3 <本Skill>/scripts/audit_assets.py slide_plan.json --stage plan
python3 <本Skill>/scripts/audit_assets.py slide_plan.json --stage delivery --objects readback-objects.json
```

plan 阶段检查已提供的 palette_contract 与证据清单；未提供的项目标为未检查。delivery 阶段还检查本地文件、placement来源/模板、实际插入对象及屏幕/框层几何和前后顺序。输入素材路径相对计划中的 asset_base（建议执行项目绝对路径；不写入通用 Skill），未指定时相对计划文件。readback-objects.json 是从最终稿回读并用上传映射还原的 `{ "slides": [{ "slide_no": 1, "native_colors": ["#FFFFFF", "#1246F2"], "objects": [{ "id": "实际对象ID", "type": "image", "file": "本地源文件", "bbox": [0,0,100,100], "layer_index": 0, "kind": "evidence" }] }] }`；不能拿提交前的拟用对象冒充回读。非证据对象可省略 kind。两层模式的 object_ids 按 screen、frame 顺序填写，files 使用 screen、frame、placement；合成模式用一个ID，files 使用 composite、placement。原图/已有框模式用 source 和实际 object_ids。

若来源清单中有证据图片而 evidence_images 为空，先补盘点；检查器只能识别被正确登记的素材，无法从图片像素自动判断截图。规则/文件检查不证明最终框可见或裁切合理，还要查看目标端截图。

新增或修改模板时，用真实竖屏、横屏各试一次，检查外框中心透明、屏幕遮罩中心可见、灵动岛/刘海不透图，外框与屏幕定位一致；检查默认 cover 铺满屏幕、源裁切窗口正确且未丢关键内容；外框保留正常设备边缘不等于屏幕内部留空。普通制作只验证本次实际使用的模板和截图，不额外测试未用模板。修改裁切后更新项目里的可见区域和标注映射，目标端截图复核出血、间距及文字可读性；需要几何诊断时才填写 bleed_objects。不能因使用模板就省略目标端验证。
