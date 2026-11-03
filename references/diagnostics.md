# 按需诊断

仅在布局问题难定位、批量审计或用户要求时读取。普通制作按主流程做回读与页面预览，不以填写 JSON 或运行全部脚本作为前置。

## 简要计划检查

需要机器检查时，将项目已有记录整理成 JSON，slides 为非空数组；每页至少有唯一的正整数 slide_no、非空 key_message 和 composition。标题和插画说明可直接用自然语言写。选样页时保留原页码，不要求连续。

可选 canvas 写 width/height，默认 960×540。需要几何检查时才增加 text_boxes、characters、bleed_objects；文本项用 id/bbox/font_size，角色项用 id/visible_bbox。bbox 为 [x,y,w,h]。有意出血的完整框、画内交集、裁切边、理由及受保护区域写入 bleed_objects；缺少这些数据时不声称出血几何通过。字体可读性最终仍看目标端。

```bash
python3 <skill-root>/scripts/validate_plan.py slide_plan.json
```

## 测量对齐、间距与指定面积

objects.json 包含 asset_base、font_files 和 slides；每页 objects 为 text/image（id、bbox及文字/字体或 file），可用 groups 分组，layout_constraints 列出本次要检查的关系。text 使用实际手动断行，font_size 按画布单位；本地测量不模拟目标端自动换行。图片裁切先落实到实际素材，再测量。

```bash
node <skill-root>/scripts/measure_layout.mjs objects.json measured.json
python3 <skill-root>/scripts/audit_layout.py measured.json
```

align 使用 ids、edge（left/right/top/bottom/center_x/center_y）、tolerance；gap/gutter 使用 a/b 对象ID数组、axis和min/max，或引用 spacing_system 中的 token。basis=layout 测文件框，basis=ink 测字形或图片 alpha 包围框。默认值取自[排版基准](layout-rules.md)，按目标画布比例换算；显式传入 tolerance，不依赖脚本内置回退值。有已确定的构图例外时按例外检查，不因脚本方便而改成另一套设计。

现有 audit_layout.py 检查已声明的对齐、间距和生成图面积，不自动检查安全区、内容块上限、行距或结构空余率。这些通过页面记录和目标端预览核对；需要精确空余率时按排版基准另行测量。generated_visual_coverage 的补数不是留白率：它只包含生成图，不包含文字、图表和截图。未测量不能宣称新增规则数值全部通过。

用户明确指定生成视觉面积时才声明 generated_visual_coverage：ids 列图像对象，basis=ink，并显式给出本次 min_ratio（0到1）。脚本没有统一面积下限。alpha 包围框只度量不透明范围，白底和内部空洞会影响结果，不能据此证明角色体量或构图质量。无声明时不声称检查过视觉面积。

## 截图与配色审计

需要追踪素材或配色时，可用 audit_assets.py 单独审查证据清单和已声明的 palette_contract；两者均为可选数据，未提供的项目显示为未检查，不能称通过。证据字段与调用见[样机协议](device-mockups.md)。

配色审计填写 source_kind、source_refs、rationale、page_strategy；roles 的 primary/background/environment/text/accent 各含 colors/source/usage。secondary_colors 记录有依据的辅色或局部状态色；source_kind 为 explicit/visual-reference/semantic，参考来源以 source_ref 对应 source_refs。交付审计还需回读的实际 native_colors。此分支是来源/对象核查，不证明颜色搭配或主题主次好看。

所有脚本结果只描述实际运行的检查。未测量、未登记或没有目标端预览的项目分别报告，不能用总通过状态代替视觉确认。
