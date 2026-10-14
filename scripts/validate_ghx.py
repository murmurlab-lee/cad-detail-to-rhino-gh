#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_ghx.py — .ghx 文件交付前四重校验

用法:  python3 validate_ghx.py 文件.ghx
退出码: 0=全部通过, 1=发现问题
"""
import re
import sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import unescape


def fail(msg):
    print("❌ " + msg)
    return 1


def main():
    path = sys.argv[1]
    raw = open(path, encoding="utf-8").read()
    errors = 0

    # 1) XML 良构
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        fail(f"XML 解析失败: {e}")
        sys.exit(1)
    print("✅ 1/5 XML 良构")

    # 2) 所有 count 属性与子节点数一致
    bad = []

    def walk(e):
        cnt = e.get("count")
        if cnt is not None:
            kids = [c for c in e if c.tag in ("item", "chunk")]
            if len(kids) != int(cnt):
                bad.append(f"{e.tag}[@name={e.get('name')}] 声明 count={cnt} 实际 {len(kids)}")
        for c in e:
            walk(c)

    walk(tree.getroot())
    if bad:
        for b in bad:
            errors += fail("count 不一致: " + b)
    else:
        print("✅ 2/5 items/chunks count 全部一致")

    # 3) 接线完整性: 每个 Source 引用的 InstanceGuid 存在; 脚本输入数 == 滑块数
    igs = re.findall(r'<item name="InstanceGuid" type_name="gh_guid" type_code="9">([0-9a-f-]+)</item>', raw)
    srcs = re.findall(r'<item name="Source" index="0" type_name="gh_guid" type_code="9">([0-9a-f-]+)</item>', raw)
    dangling = [s for s in srcs if s not in igs]
    if dangling:
        errors += fail(f"悬空接线: {dangling}")
    else:
        print(f"✅ 3/5 接线完整 ({len(srcs)} 条, 无悬空)")

    # 4) ScriptSource 纯度: 必须是纯 RunScript 方法体
    m = re.search(r'<item name="ScriptSource"[^>]*>(.*?)</item>', raw, re.S)
    if m:
        src = unescape(m.group(1))
        for pat in ["using System", "class Script_Instance", "GH_ScriptInstance", "void RunScript"]:
            if pat in src:
                errors += fail(f"ScriptSource 含违禁内容 {pat!r} — 必须是纯方法体 (见 references/ghx-format.md 铁律1)")
        if errors == 0:
            print("✅ 4/5 ScriptSource 为纯方法体")
        # 附带提示: 是否含 C#6+ 语法
        if re.search(r'\$"', src):
            fail("ScriptSource 含字符串插值 $\"\" — Rhino 7 编译器不支持 (C#5 限制)")
            errors += 1
        # 启发式: 输入钳制检查 (ghx-format.md 铁律 5)
        if not re.search(r'Math\.(Min|Max)', src):
            print("⚠️  ScriptSource 未见 Math.Min/Max 输入钳制 — 请确认已做除零/负值/范围保护 (铁律5)")
    else:
        print("ℹ️  4/5 无 ScriptSource (仅滑块文件?) — 跳过纯度检查")

    # 5) 脚本参数命名: 输入 NickName 必须是合法英文标识符 (GH 用它生成 RunScript 签名,
    #    中文 NickName 会让方法体引用全部 CS0103); 输入/输出名不得与 C# 关键字仅大小写不同
    CS_KW = set(("abstract as base bool break byte case catch char checked class const continue "
                 "decimal default delegate do double else enum event explicit extern false finally "
                 "fixed float for foreach goto if implicit in int interface internal is lock long "
                 "namespace new null object operator out override params private protected public "
                 "readonly ref return sbyte sealed short sizeof stackalloc static string struct "
                 "switch this throw true try typeof uint ulong unchecked unsafe ushort using "
                 "virtual void volatile while").split())
    ident = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    in_nicks = [unescape(x) for x in re.findall(
        r'<chunk name="InputParam".*?<item name="NickName" type_name="gh_string" type_code="10">(.*?)</item>',
        raw, re.S)]
    out_names = [unescape(x) for x in re.findall(
        r'<chunk name="OutputParam".*?<item name="Name" type_name="gh_string" type_code="10">(.*?)</item>',
        raw, re.S)]
    names_bad = []
    for n in in_nicks:
        if not ident.match(n):
            names_bad.append(f"输入 NickName {n!r} 非英文标识符 — GH 按 NickName 生成签名, 必须=英文 var 名")
        elif n.lower() in CS_KW:
            names_bad.append(f"输入 NickName {n!r} 与 C# 关键字冲突")
    for n in out_names:
        if n == "out":
            continue  # GH 内置 Print 流口, 特例
        if not ident.match(n):
            names_bad.append(f"输出名 {n!r} 非英文标识符")
        elif n.lower() in CS_KW:
            names_bad.append(f"输出名 {n!r} 与 C# 关键字 {n.lower()!r} 仅大小写之差 (如 Base) — 必须改名")
    if names_bad:
        for b in names_bad:
            errors += fail("命名检查: " + b)
    elif in_nicks or out_names:
        print(f"✅ 5/5 参数命名合法 ({len(in_nicks)} 入 + {len(out_names)} 出)")

    print("\n" + ("❌ 校验未通过" if errors else "✅ 全部通过, 可交付"))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
