---
name: cad-detail-to-rhino-gh
description: >
  把建筑节点详图/大样图（PDF/DWG 导出）+ 现场参考照片转化为 Rhino 3D 模型（.3dm，
  Rhino 7/8 双版本）和 Grasshopper 参数化文件（.ghx，滑块驱动 C# 脚本生成几何）。
  适用场景：用户上传构造详图、节点图、大样图（如井盖、排水沟、幕墙节点、五金预制件）
  并要求"建 rhino 模型"、"生成 3dm"、"做成 Grasshopper 参数化"、"ghx/gh 文件"、
  "滑块可以调参数"。构件级精度（主要构件尺寸准确，用于方案表达），非加工级。
  完成的节点自动入库到 Detail Atlas 构造库（阿里云 OSS 托管 + 本地单文件入口网页，
  首次使用本 skill 时引导建库）。
  Do NOT use for: 自由曲面/异形造型建模（本 skill 以盒体组合的构件级建模为主）、
  纯渲染图需求、无需参数化的单次建模。
---

# 节点详图 → Rhino 模型 + Grasshopper 参数化

## 核心流程（8 阶段）

完整细节见 `references/workflow.md`，执行时严格按阶段推进：

1. **读图解析**：`python3 scripts/pdf_to_png.py 图纸.pdf -o work/` 栅格化+增强后视觉读图
   （矢量 CAD PDF 直接读文本是空的）。抄录尺寸标注+**构造注记（逐条编号，不许漏）**+标高，
   记录标注矛盾。**数值一律以图纸为准，照片不用于定数。**
2. **疑问清单（强制确认门）**：把关键尺寸缺失/矛盾/建模范围列成清单，用 ask_user
   一次问完。**用户回答前不建模**（除非用户明确要求全自动）。细节不问，合理假设。
3. **参数体系设计**：选 8-15 个用户最可能调的尺寸做滑块；先写 Python 坐标推导并跑通，
   再翻译成 C#。Python 与 C# 的推导公式必须一致。
4. **Python 建模**：用 `scripts/rhino3dm_helpers.py`（box/ring/图层/dual 双版本写出）。
   z=0 取完成面，向下为负；构件级用盒体组合，环形拆 4 块。
5. **校验+预览**：`scripts/check_intersections.py`（先列有意相交白名单，其余清零）；
   matplotlib Poly3DCollection 渲预览图确认几何（内部自查可多渲几张，**交付只给一张
   轴测图** `xxx_轴测.png`）。
6. **生成 .ghx**：写纯方法体 `body.cs` + `spec.json`，然后
   `python3 scripts/ghx_gen.py spec.json -o 输出.ghx --sliders-only 排障版.ghx`。
   **假设清单与图面注记对照表写进 spec.json 的 `description` 字段**（随 .ghx 走，
   不再单独交付说明文件）。排障版/完整源码.cs 是内部文件，仅排障时按需给用户。
7. **验证（交付前必做）**：`python3 scripts/validate_ghx.py 输出.ghx` 全绿 +
   `python3 scripts/compile_check/wrap_build.py spec.json` 编译通过 +
   `--emit` 生成手动粘贴退路 .cs。
8. **交付（恰好三件，不多不少）**：`xxx_Rhino7.3dm` + `xxx_参数化.ghx` +
   `xxx_轴测.png`。**只输出这三个文件**（REF 标签也只挂这三个）；其余中间产物
   （R8 版 .3dm、排障版 ghx、完整源码.cs、其他角度预览图）留在工作目录，不交付。
   告知用户 .ghx 在 GH 直接打开、另存即转 .gh。
9. **入库（自动，无需用户操作）**：`python3 scripts/library_add.py --add ...`
   上传节点文件到 OSS 并重建索引，用户刷新入口网页即见。**首次使用本 skill 必须先
   建库**（见下节）。用户明确说"不入库"则跳过。

## 构造库 (Detail Atlas)：建库与自动入库

架构（2026-10 实测定论）：**阿里云 OSS 默认域名强制所有文件 Content-Disposition:
attachment，无法直接托管 HTML 页面**。因此页面 = 用户本地的单文件入口 html，
数据（library.js + nodes/）全部在 OSS 桶，index.html 以绝对 URL 引用。

**首次使用（建库，一次性）**：配置 `/mnt/agents/output/构造库/library_oss.json` 不存在
→ 引导用户：① 控制台建 OSS 桶（建议就近地域）；② 建专用 AccessKey（权限仅限此桶）。
只需这两样——公共访问封锁关闭/公共读/静态托管全由脚本 API 完成。然后：
`python3 scripts/library_add.py --init --bucket X --region oss-cn-xxx --ak X --sk X
--password 页面密码`，产出入口 html 交付用户下载。配置同时写入长期记忆。

**日常入库**：交付三件后自动 `--add`（编号 NNN_名称按时间顺序、同名加 _01；分类限
11 部位：基础/结构/屋顶/楼地面/墙面/幕墙/楼梯/景观/照明/机电/室内；参数表从
spec.json 自动抽取）。入库失败不隐瞒：报告用户并可重试。

## ⚠️ 最高风险区：C# 脚本体

写 .ghx 内嵌 C# 前**必读** `references/ghx-format.md` 第 2 节铁律。一句话版：
**ScriptSource 只写 RunScript 方法体**——禁 using/class/辅助方法声明（辅助逻辑用
Python 生成器展开内联）；输入参数名=spec 滑块 var，直接当 double 用；输出赋
List<Brep>；语法按 C# 5；**方法体开头钳制全部输入**（Math.Min/Max + 除零/负值保护）；
**输入 NickName 必须=英文 var**（GH 按 NickName 生成签名，ghx_gen.py 已内置，中文名走
Description）；**输入/输出命名避开 C# 关键字**（仅大小写不同也不行，如 Base→BaseBoard）；
**脚本注释/字符串只写 ASCII+中文**（禁 → ± Φ 等特殊符号）。命名与符号由 ghx_gen.py
生成时强制检查、validate_ghx.py 交付前复查，违反即拒生成。违反任何一条 = 用户那边红色电池。

## 资源速查

| 文件 | 何时用 |
|---|---|
| `references/workflow.md` | 开工先读：阶段细节、疑问清单策略、置信度分级、交付清单 |
| `references/ghx-format.md` | 写/排障 .ghx 时读：序列化规格、GUID 表、报错对照表 |
| `references/case-manhole-cover.md` | 首个任务参考：井盖完整案例（几何推导+参数体系） |
| `assets/ghx_spec_example.json` + `assets/manhole_body.cs` | spec.json 和脚本体的对照样例 |
| `scripts/ghx_gen.py` | 生成 .ghx（含 --sliders-only 排障版） |
| `scripts/validate_ghx.py` | 交付前五重校验（含参数命名检查） |
| `scripts/compile_check/wrap_build.py` | 模拟 GH 环境编译验证（需 dotnet；无则人工复查语法） |
| `scripts/pdf_to_png.py` | PDF 读图预处理 |
| `scripts/rhino3dm_helpers.py` | .3dm 建模辅助 |
| `scripts/check_intersections.py` | 几何相交校验 |
| `scripts/library_add.py` | 构造库建库 (--init) 与节点入库 (--add) |
| `assets/library/index.html` | 构造库页面模板 (__LIB_BASE__ 占位符) |

## 质量门（每关不过不进入下一阶段）

- 疑问清单未经用户确认 → 不建模
- 相交检查有非白名单碰撞 → 不渲染预览
- validate_ghx 或编译验证不通过 → 不交付
- 假设清单/图面注记对照表未写进 .ghx 的 description → 不交付
- 图面构造注记未逐条列入"实现对照表"（实现 / 有意省略+理由）→ 不交付

## 版本记录

- v1.1 (2026-10)：①修复 GH 签名按输入 NickName 生成的问题（NickName 固定=英文 var）；
  新增命名/特殊符号强制检查（ghx_gen 拒生成 + validate_ghx 第五重校验），目标 ghx
  一次成功。②交付物精简为恰好三件：Rhino7 .3dm + .ghx + 轴测 .png；假设清单与注记
  对照表改写入 .ghx description；排障版/完整源码.cs/建模说明.md 转为内部文件。
- v1.2 (2026-10)：新增 Detail Atlas 构造库 —— 首次建库引导 + 每次任务自动入库
  （library_add.py，免依赖 REST 签名上传 OSS + 重建索引）。
- v1.0：初版（井盖案例）。

## 排障

用户反馈报错 → 索取报错原文截图 → 对照 `references/ghx-format.md` 第 7 节报错表 →
用 `--sliders-only` 排障版二分定位。沙箱内无法运行 Rhino，"能否打开"的最终验证
永远在用户侧，排障回路是正常流程而非失败。
