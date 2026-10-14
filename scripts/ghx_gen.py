#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ghx_gen.py — 通用 Grasshopper .ghx 生成器

从 JSON 规格生成合法的 .ghx 文件 (N 个数字滑块 + 1 个 C# 脚本组件, 滑块按序接到脚本输入)。
已内置 GH 1.0.7 (Rhino 7) 原生文档壳与全部序列化铁律, 生成物可直接在 Grasshopper 打开。

用法:
    python3 ghx_gen.py spec.json -o 输出.ghx

spec.json 结构:
{
  "doc_name": "我的参数化.ghx",          # 文档名 (可选)
  "description": "文档描述",            # 可选
  "script_nickname": "组件昵称",        # 可选, 默认 "参数化生成器"
  "sliders": [                          # 至少 1 个; var 是 C# 输入参数名(英文), nick 是滑块显示名(可中文)
    {"var": "opening", "nick": "井口净空", "min": 400, "max": 1200, "value": 600, "digits": 0}
  ],
  "outputs": [                          # 至少 1 个; "out" 口会自动添加在最前, 不要自己写
    {"name": "Frame", "desc": "不锈钢外框", "type": "geometry"},   # type: geometry|string
    {"name": "Count", "desc": "数量", "type": "string"}
  ],
  "script_body_file": "body.cs"         # C# RunScript 纯方法体文件 (铁律: 不含 using/class/方法声明!)
}

铁律 (违反即报错, 详见 references/ghx-format.md):
  1. script_body 只含 RunScript 方法体 — 禁止 using / class Script_Instance / 辅助方法声明
  2. 输入参数名 = sliders[].var, 带 double 类型提示, 方法体内直接当 double 用
  3. 输出参数在方法体内赋值: geometry 类型赋 List<Brep>, string 类型赋字符串
  4. C# 语法按 C# 5 写 (禁 $"" 插值、表达式体成员、out var 等)
  5. sliders[].var 与 outputs[].name 必须是纯英文标识符, 且不得与 C# 关键字仅大小写
     不同 (如 Base≈base) — GH 用输入参数的 NickName 生成 RunScript 签名, 本生成器已
     固定 NickName=var, 滑块/输入的中文显示名走 Description
  6. script_body 注释/字符串只允许 ASCII + 中文汉字/中文标点 — 禁 → ± Φ 等特殊符号
     (2026-10 栏杆项目实录: 特殊符号经中文 Windows GBK 环境往返可能破坏语法)
"""
import argparse
import json
import re
import sys
import uuid
from xml.sax.saxutils import escape

# ---- 组件 GUID (均已从真实 GH 存档验证, 勿改) ----
CSHARP_GUID = "a9a8ebd2-fff5-4c44-a8f5-739736d129ba"
SLIDER_GUID = "57da07bd-ecab-415d-9d86-af36d7073abc"
SCRIPTVAR_GUID = "84fa917c-1ed8-4db3-8be1-7bdc4a6495a2"   # 仅用于输入参数类型
DOUBLE_HINT_GUID = "19ff81a2-dc4f-4035-8de9-26224c561321"
PARAM_STRING_GUID = "3ede854e-c753-40eb-84cb-b48008f14fd4"
PARAM_GEOMETRY_GUID = "ac2bc2cb-70fb-4dd5-9c78-7e1ea97fe278"
OUTPUT_TYPE_GUID = {"geometry": PARAM_GEOMETRY_GUID, "string": PARAM_STRING_GUID}


def gid():
    return str(uuid.uuid4())


def rect(x, y, w, h):
    return ('<item name="Bounds" type_name="gh_drawing_rectanglef" type_code="35">'
            f'<X>{x}</X><Y>{y}</Y><W>{w}</W><H>{h}</H></item>')


def pivot(x, y):
    return ('<item name="Pivot" type_name="gh_drawing_pointf" type_code="31">'
            f'<X>{x}</X><Y>{y}</Y></item>')


def slider_xml(s, y):
    """数字滑块对象 chunk"""
    ig = gid()
    x = 40
    xml = f'''<chunk name="Object" index="{{IDX}}">
              <items count="2">
                <item name="GUID" type_name="gh_guid" type_code="9">{SLIDER_GUID}</item>
                <item name="Name" type_name="gh_string" type_code="10">Number Slider</item>
              </items>
              <chunks count="1">
                <chunk name="Container">
                  <items count="6">
                    <item name="Description" type_name="gh_string" type_code="10">Numeric slider for single values</item>
                    <item name="InstanceGuid" type_name="gh_guid" type_code="9">{ig}</item>
                    <item name="Name" type_name="gh_string" type_code="10">Number Slider</item>
                    <item name="NickName" type_name="gh_string" type_code="10">{escape(s["nick"])}</item>
                    <item name="Optional" type_name="gh_bool" type_code="1">false</item>
                    <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>
                  </items>
                  <chunks count="2">
                    <chunk name="Attributes">
                      <items count="2">{rect(x, y, 240, 20)}{pivot(x, y + 10)}</items>
                    </chunk>
                    <chunk name="Slider">
                      <items count="7">
                        <item name="Digits" type_name="gh_int32" type_code="3">{s.get("digits", 0)}</item>
                        <item name="GripDisplay" type_name="gh_int32" type_code="3">1</item>
                        <item name="Interval" type_name="gh_int32" type_code="3">1</item>
                        <item name="Max" type_name="gh_double" type_code="6">{s["max"]}</item>
                        <item name="Min" type_name="gh_double" type_code="6">{s["min"]}</item>
                        <item name="SnapCount" type_name="gh_int32" type_code="3">0</item>
                        <item name="Value" type_name="gh_double" type_code="6">{s["value"]}</item>
                      </items>
                    </chunk>
                  </chunks>
                </chunk>
              </chunks>
            </chunk>'''
    return xml, ig


def script_xml(spec, slider_igs, body):
    """C# 脚本组件对象 chunk — 结构为 GH 1.0.7 原生序列化"""
    sliders = spec["sliders"]
    sy, sx = 40, 400
    n_in = len(sliders)
    # "out" 口固定在最前 (对应 Container 的 OutParameter=true)
    all_outputs = [("out", "Print, Reflect and Error streams", PARAM_STRING_GUID)] + [
        (o["name"], o.get("desc", o["name"]), OUTPUT_TYPE_GUID[o.get("type", "geometry")])
        for o in spec["outputs"]
    ]
    n_out = len(all_outputs)

    in_chunks = []
    for i, s in enumerate(sliders):
        py = sy + 10 + i * 28
        in_chunks.append(f'''<chunk name="InputParam" index="{i}">
                          <items count="11">
                            <item name="AllowTreeAccess" type_name="gh_bool" type_code="1">true</item>
                            <item name="Description" type_name="gh_string" type_code="10">{escape(s["nick"])} (Script Variable {s["var"]})</item>
                            <item name="InstanceGuid" type_name="gh_guid" type_code="9">{gid()}</item>
                            <item name="Name" type_name="gh_string" type_code="10">{s["var"]}</item>
                            <item name="NickName" type_name="gh_string" type_code="10">{s["var"]}</item>
                            <item name="Optional" type_name="gh_bool" type_code="1">true</item>
                            <item name="ScriptParamAccess" type_name="gh_int32" type_code="3">0</item>
                            <item name="ShowTypeHints" type_name="gh_bool" type_code="1">true</item>
                            <item name="Source" index="0" type_name="gh_guid" type_code="9">{slider_igs[i]}</item>
                            <item name="SourceCount" type_name="gh_int32" type_code="3">1</item>
                            <item name="TypeHintID" type_name="gh_guid" type_code="9">{DOUBLE_HINT_GUID}</item>
                          </items>
                          <chunks count="1">
                            <chunk name="Attributes">
                              <items count="2">{rect(sx + 2, py, 60, 26)}{pivot(sx + 8, py + 13)}</items>
                            </chunk>
                          </chunks>
                        </chunk>''')

    out_chunks, out_id_items = [], []
    for i, (name, desc, pguid) in enumerate(all_outputs):
        py = sy + 10 + i * 36
        out_id_items.append(f'<item name="OutputId" index="{i}" type_name="gh_guid" type_code="9">{pguid}</item>')
        out_chunks.append(f'''<chunk name="OutputParam" index="{i}">
                          <items count="7">
                            <item name="Access" type_name="gh_int32" type_code="3">1</item>
                            <item name="Description" type_name="gh_string" type_code="10">{escape(desc)}</item>
                            <item name="InstanceGuid" type_name="gh_guid" type_code="9">{gid()}</item>
                            <item name="Name" type_name="gh_string" type_code="10">{name}</item>
                            <item name="NickName" type_name="gh_string" type_code="10">{name}</item>
                            <item name="Optional" type_name="gh_bool" type_code="1">false</item>
                            <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>
                          </items>
                          <chunks count="1">
                            <chunk name="Attributes">
                              <items count="2">{rect(sx + 230, py, 60, 32)}{pivot(sx + 284, py + 16)}</items>
                            </chunk>
                          </chunks>
                        </chunk>''')

    in_id_items = [f'<item name="InputId" index="{i}" type_name="gh_guid" type_code="9">{SCRIPTVAR_GUID}</item>'
                   for i in range(n_in)]
    h = max(n_in * 28, n_out * 36) + 60
    return f'''<chunk name="Object" index="{{IDX}}">
              <items count="2">
                <item name="GUID" type_name="gh_guid" type_code="9">{CSHARP_GUID}</item>
                <item name="Name" type_name="gh_string" type_code="10">C# Script</item>
              </items>
              <chunks count="1">
                <chunk name="Container">
                  <items count="11">
                    <item name="CustomUsing" type_name="gh_bool" type_code="1">false</item>
                    <item name="Description" type_name="gh_string" type_code="10">A C#.NET scriptable component</item>
                    <item name="EditorPosition" type_name="gh_drawing_point" type_code="30">
                      <X>18</X>
                      <Y>58</Y>
                    </item>
                    <item name="Hidden" type_name="gh_bool" type_code="1">false</item>
                    <item name="IconDisplay" type_name="gh_int32" type_code="3">1</item>
                    <item name="InstanceGuid" type_name="gh_guid" type_code="9">{gid()}</item>
                    <item name="Name" type_name="gh_string" type_code="10">C# Script</item>
                    <item name="NickName" type_name="gh_string" type_code="10">{escape(spec.get("script_nickname", "参数化生成器"))}</item>
                    <item name="OutParameter" type_name="gh_bool" type_code="1">true</item>
                    <item name="ReferenceCount" type_name="gh_int32" type_code="3">0</item>
                    <item name="ScriptSource" type_name="gh_string" type_code="10">{escape(body)}
          </item>
                  </items>
                  <chunks count="2">
                    <chunk name="Attributes">
                      <items count="2">{rect(sx, sy, 300, h)}{pivot(sx + 150, sy + h / 2)}</items>
                    </chunk>
                    <chunk name="ParameterData">
                      <items count="{2 + n_in + n_out}">
                        <item name="InputCount" type_name="gh_int32" type_code="3">{n_in}</item>
                        {chr(10).join(in_id_items)}
                        <item name="OutputCount" type_name="gh_int32" type_code="3">{n_out}</item>
                        {chr(10).join(out_id_items)}
                      </items>
                      <chunks count="{n_in + n_out}">
                        {chr(10).join(in_chunks)}
                        {chr(10).join(out_chunks)}
                      </chunks>
                    </chunk>
                  </chunks>
                </chunk>
              </chunks>
            </chunk>'''


def build(spec, body, path, include_script=True):
    """生成 .ghx 文件。include_script=False 可生成仅滑块的二分排障测试文件。"""
    objects, igs = [], []
    for i, s in enumerate(spec["sliders"]):
        xml, ig = slider_xml(s, 40 + i * 30)
        objects.append(xml)
        igs.append(ig)
    if include_script:
        objects.append(script_xml(spec, igs, body))
    objects = [o.replace("{IDX}", str(i)) for i, o in enumerate(objects)]
    n = len(objects)
    doc = f'''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Archive name="Root">
  <!--Grasshopper archive-->
  <!--Grasshopper and GH_IO.dll are copyrighted by Robert McNeel & Associates-->
  <items count="1">
    <item name="ArchiveVersion" type_name="gh_version" type_code="80">
      <Major>0</Major>
      <Minor>2</Minor>
      <Revision>2</Revision>
    </item>
  </items>
  <chunks count="1">
    <chunk name="Definition">
      <items count="1">
        <item name="plugin_version" type_name="gh_version" type_code="80">
          <Major>1</Major>
          <Minor>0</Minor>
          <Revision>7</Revision>
        </item>
      </items>
      <chunks count="5">
        <chunk name="DocumentHeader">
          <items count="5">
            <item name="DocumentID" type_name="gh_guid" type_code="9">{gid()}</item>
            <item name="Preview" type_name="gh_string" type_code="10">Shaded</item>
            <item name="PreviewMeshType" type_name="gh_int32" type_code="3">1</item>
            <item name="PreviewNormal" type_name="gh_drawing_color" type_code="36">
              <ARGB>100;150;0;0</ARGB>
            </item>
            <item name="PreviewSelected" type_name="gh_drawing_color" type_code="36">
              <ARGB>100;0;150;0</ARGB>
            </item>
          </items>
        </chunk>
        <chunk name="DefinitionProperties">
          <items count="3">
            <item name="Date" type_name="gh_date" type_code="8">638600000000000000</item>
            <item name="Description" type_name="gh_string" type_code="10">{escape(spec.get("description", ""))}</item>
            <item name="Name" type_name="gh_string" type_code="10">{escape(spec.get("doc_name", "parametric.ghx"))}</item>
          </items>
          <chunks count="3">
            <chunk name="Revisions">
              <items count="1">
                <item name="RevisionCount" type_name="gh_int32" type_code="3">0</item>
              </items>
            </chunk>
            <chunk name="Projection">
              <items count="2">
                <item name="Target" type_name="gh_drawing_point" type_code="30">
                  <X>-16</X>
                  <Y>-11</Y>
                </item>
                <item name="Zoom" type_name="gh_single" type_code="5">1.0</item>
              </items>
            </chunk>
            <chunk name="Views">
              <items count="1">
                <item name="ViewCount" type_name="gh_int32" type_code="3">0</item>
              </items>
            </chunk>
          </chunks>
        </chunk>
        <chunk name="RcpLayout">
          <items count="1">
            <item name="GroupCount" type_name="gh_int32" type_code="3">0</item>
          </items>
        </chunk>
        <chunk name="GHALibraries">
          <items count="1">
            <item name="Count" type_name="gh_int32" type_code="3">0</item>
          </items>
          <chunks count="0" />
        </chunk>
        <chunk name="DefinitionObjects">
          <items count="1">
            <item name="ObjectCount" type_name="gh_int32" type_code="3">{n}</item>
          </items>
          <chunks count="{n}">
            {chr(10).join(objects)}
          </chunks>
        </chunk>
      </chunks>
    </chunk>
  </chunks>
</Archive>'''
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return n


# C# 关键字表 (命名冲突检查用; 忽略大小写比较, Base 与 base 同样危险)
CS_KEYWORDS = set("""
abstract as base bool break byte case catch char checked class const continue decimal
default delegate do double else enum event explicit extern false finally fixed float for
foreach goto if implicit in int interface internal is lock long namespace new null object
operator out override params private protected public readonly ref return sbyte sealed
short sizeof stackalloc static string struct switch this throw true try typeof uint ulong
unchecked unsafe ushort using virtual void volatile while
""".split())

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def check_spec(spec):
    """命名检查 (铁律 5) — GH 用这些名字生成 C# 签名与隐藏调用点, 非法命名=用户侧编译错误"""
    problems = []
    seen = set()
    for s in spec["sliders"]:
        v = s["var"]
        if not IDENT_RE.match(v):
            problems.append(f"滑块 var {v!r} 不是合法 C# 标识符 (须纯英文, 字母/下划线开头)")
        elif v.lower() in CS_KEYWORDS:
            problems.append(f"滑块 var {v!r} 与 C# 关键字冲突 (大小写不同也不行)")
        if v.lower() in seen:
            problems.append(f"滑块 var {v!r} 与前面的命名重复 (忽略大小写)")
        seen.add(v.lower())
    for o in spec["outputs"]:
        n = o["name"]
        if not IDENT_RE.match(n):
            problems.append(f"输出名 {n!r} 不是合法 C# 标识符 (须纯英文)")
        elif n.lower() in CS_KEYWORDS:
            problems.append(f"输出名 {n!r} 与 C# 关键字 {n.lower()!r} 仅大小写之差, 必须改名 (如 Base→BaseBoard)")
        if n.lower() in seen:
            problems.append(f"输出名 {n!r} 与前面的命名重复 (忽略大小写)")
        seen.add(n.lower())
    return problems


def check_body(body):
    """ScriptSource 纯度检查 (铁律 1/6)"""
    problems = []
    for pat in ["using System", "using Rhino", "class Script_Instance", "GH_ScriptInstance",
                "private void RunScript", "void RunScript"]:
        if pat in body:
            problems.append(f"脚本体含违禁内容: {pat!r} (应为纯方法体)")
    # 铁律 6: 只允许 ASCII + 中文汉字/中文标点; 特殊符号 (→ ± Φ 等) 一律拒绝
    bad = {}
    for i, line in enumerate(body.split("\n"), 1):
        for ch in line:
            o = ord(ch)
            if o > 127 and not (0x4E00 <= o <= 0x9FFF or 0x3000 <= o <= 0x303F
                                or 0xFF00 <= o <= 0xFFEF):
                bad.setdefault(ch, []).append(i)
    for ch, lines in sorted(bad.items()):
        problems.append(f"脚本体含特殊符号 {ch!r} (U+{ord(ch):04X}, 行 {lines[:5]}) "
                        f"— 注释/字符串只许 ASCII+中文, 请改 ASCII (如 → 写成 -)")
    return problems


def main():
    ap = argparse.ArgumentParser(description="生成 Grasshopper .ghx 参数化文件")
    ap.add_argument("spec", help="spec.json 路径")
    ap.add_argument("-o", "--out", required=True, help="输出 .ghx 路径")
    ap.add_argument("--sliders-only", help="同时输出仅滑块的二分排障测试文件到该路径")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    assert spec.get("sliders"), "spec 至少需要 1 个滑块"
    assert spec.get("outputs"), "spec 至少需要 1 个输出"
    import os as _os
    _bf = spec["script_body_file"]
    if not _os.path.isabs(_bf):
        _bf = _os.path.join(_os.path.dirname(_os.path.abspath(args.spec)), _bf)
    body = open(_bf, encoding="utf-8").read()

    problems = check_spec(spec) + check_body(body)
    if problems:
        for p in problems:
            print("❌ " + p, file=sys.stderr)
        sys.exit(2)

    n = build(spec, body, args.out, include_script=True)
    print(f"✅ 完整版: {args.out} ({n} 对象: {len(spec['sliders'])} 滑块 + 1 脚本)")
    if args.sliders_only:
        n2 = build(spec, body, args.sliders_only, include_script=False)
        print(f"✅ 排障版(仅滑块): {args.sliders_only} ({n2} 对象)")


if __name__ == "__main__":
    main()
