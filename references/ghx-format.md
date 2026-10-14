# .ghx 序列化格式参考 (已实战验证)

> 本文件是排障时查阅的完整规格。正常情况下只需用 `scripts/ghx_gen.py`，不必手写 XML。
> 所有结论均在 Rhino 7 / Grasshopper 1.0.7 上实测（用户亲测打开成功）。

## 1. 为什么手写 .ghx 容易炸

Grasshopper 用 GH_IO 库反序列化。字段缺失/类型错误时它抛**无上下文的
NullReferenceException**（"未将对象引用设置到对象的实例"），不告诉你哪个字段。
所以要么严格对齐原生格式，要么用生成器。

## 2. C# ScriptSource 铁律（最重要）

1. **ScriptSource 只存 RunScript 方法体**。GH 加载时自动生成 using 区 +
   `public class Script_Instance : GH_ScriptInstance` + 工具成员区 + RunScript 签名，
   把存档文本塞进方法体。若存档含完整类 → 类套类 →
   `CS0542: "Script_Instance": 成员名称不能与封闭类型相同` + 一串 CS1518/CS1022。
2. **输入参数带 double 类型提示**（TypeHintID=`19ff81a2-...`）→ GH 自动生成
   `RunScript(double xxx, ..., ref object Yyy, ...)`，方法体内直接当 double 用。
3. **方法体内不能声明函数**（无本地函数，C#5）。辅助逻辑（如环形构件、盒体创建）
   必须全部内联——写 Python 生成器展开，不要手写展开（易错）。
4. **C# 5 语法**：禁 `$""`、表达式体成员、`out var`、模式匹配。
5. **方法体开头必须先做输入合法性处理**：滑块 min/max 只约束单参数，用户拖动后
   参数**组合**可能产生非法状态（除零、负尺寸、B<A、间距>净空导致零支承等）。
   对每个 double 输入用 `Math.Min/Math.Max` 钳制（范围与 spec.json 滑块 min/max
   一致），对派生量做除零/负值保护（如 `n = Math.Max(1, (int)(w / s))`），参数间
   约束在脚本内强制修正，不要假设用户不拖过头。

6. **输入参数的 NickName 必须是英文 var 名**（2026-10 栏杆项目实录）：GH 生成
   RunScript 签名用的是输入参数的 **NickName 而非 Name**。NickName 是中文 → 签名
   参数名变中文 → 方法体里的英文引用全部 CS0103"当前上下文中不存在名称"，并连带
   一串 CS0121 歧义误报。ghx_gen.py 已固定 NickName=var、中文显示名写入
   Description；手写 XML 必须遵守同一规则。
7. **命名远离 C# 关键字，注释只写 ASCII+中文**：输入 var / 输出名不得与 C# 关键字
   仅大小写不同（Base≈base 会让 GH 隐藏调用点生成非法代码，报 CS1002/CS1026/
   CS1525 且行号超出可见源码）；注释/字符串里的特殊符号（→ ± Φ 等）在中文
   Windows 的 GBK 环境往返中可能破坏语法，一律改 ASCII 写法（→ 写成 -）。
   ghx_gen.py 生成时强制检查，违反即拒生成。

验证法：`scripts/compile_check/wrap_build.py spec.json`（dotnet + 桩，LangVersion=5）。

## 3. 组件 GUID 表（勿改）

| 组件/类型 | GUID |
|---|---|
| Number Slider | `57da07bd-ecab-415d-9d86-af36d7073abc` |
| C# Script | `a9a8ebd2-fff5-4c44-a8f5-739736d129ba` |
| VB Script | `079bd9bd-54a0-41d4-98af-db999015f63d` |
| Param_ScriptVariable（**仅输入**参数类型） | `84fa917c-1ed8-4db3-8be1-7bdc4a6495a2` |
| double 类型提示 | `19ff81a2-dc4f-4035-8de9-26224c561321` |
| Param_String（out 口 / 文本输出） | `3ede854e-c753-40eb-84cb-b48008f14fd4` |
| Param_Geometry（几何输出） | `ac2bc2cb-70fb-4dd5-9c78-7e1ea97fe278` |

## 4. C# 脚本组件序列化要点

- Container 固定 **11 items**：CustomUsing=false, Description, EditorPosition
  (gh_drawing_point), Hidden=false, IconDisplay=1, InstanceGuid, Name="C# Script",
  NickName, **OutParameter=true**, ReferenceCount=0, ScriptSource。
- ParameterData：InputCount + InputId（**SCRIPTVAR_GUID**）；OutputCount + OutputId
  （**必须是具体类型** Param_Geometry/Param_String，用 SCRIPTVAR_GUID 会在打开时 NRE）。
- **第一个输出固定为 "out"**（Param_String），之后才是自定义输出。
- 输入 11 items：Optional=true, ScriptParamAccess=0, ShowTypeHints=true, TypeHintID,
  Source（接线目标 InstanceGuid）+SourceCount=1。**NickName=英文 var 名**（铁律 6），
  中文显示名放 Description。
- 输出 7 items：**Access=1**（列表访问，配合脚本赋 `List<Brep>`）, Optional=false。

## 5. 文档壳（GH 1.0.7）

Archive(items: ArchiveVersion 0.2.2) → Definition(items: plugin_version 1.0.7) → 5 chunks：
DocumentHeader(5 items, 含 PreviewNormal=`100;150;0;0` / PreviewSelected=`100;0;150;0`)、
DefinitionProperties(Date/Description/Name + Revisions/Projection/Views 三子块)、
RcpLayout(GroupCount=0)、GHALibraries(Count=0 + `<chunks count="0" />`)、DefinitionObjects。
**缺块会导致打开时 NRE**——直接复用 `ghx_gen.py` 里的壳，勿裁剪。

## 6. 滑块序列化要点

Container 6 items + Attributes(Bounds/Pivot) + Slider chunk 7 items
(Digits/GripDisplay=1/Interval=1/Max/Min/SnapCount=0/Value)。NickName 支持中文。

## 7. 报错对照表（实录）

| 现象 | 根因 | 解法 |
|---|---|---|
| "IO generated 1 messages" | 通用提示 | 让用户发 Event Log 具体内容再诊断 |
| 打开时 NullReferenceException | 输出用了 SCRIPTVAR 占位类型 / 文档壳缺块 | OutputId 改具体类型；补全文档壳 |
| 电池红 + CS0542/CS1518/CS1022 | ScriptSource 含类包装被二次包装 | 改纯方法体（铁律 1） |
| 电池红 + 语法错误 | C# 6+ 语法 | 降 C# 5（铁律 4），wrap_build.py 验证 |
| 电池红 + CS0103"不存在名称"（全部输入名）+ CS0121 连锁 | 输入 NickName 是中文，GH 按 NickName 生成签名（铁律 6） | 用本版 ghx_gen.py 重新生成 |
| 电池红 + CS1002/CS1026/CS1525 成对、行号超出可见源码 | 输出名与 C# 关键字仅大小写之差（如 Base）或注释含 → 等特殊符号（铁律 7） | 输出改名（如 BaseBoard）、符号改 ASCII 后重新生成；仍不行则用完整源码手动粘贴兜底 |

## 8. 二分排障法

用户打不开时，用 `ghx_gen.py --sliders-only 排障版.ghx` 同时交付两个文件：
仅滑块版能开 ⇒ 壳/滑块没问题，问题在脚本组件；仅滑块版也报错 ⇒ 问题在文档壳。

## 9. 关于 .gh 二进制

离线只能生成 .ghx。Grasshopper 打开 .ghx 后另存即自动转 .gh。对用户说明这一点即可，
不要尝试手写二进制 .gh。
