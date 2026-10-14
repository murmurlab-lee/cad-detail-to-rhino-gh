#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wrap_build.py — 模拟 GH 编译环境: 把纯脚本体包进 GH 标准模板后用 dotnet 编译

Grasshopper 加载脚本组件时会自动生成类外壳 (using + Script_Instance + 成员区 +
RunScript 签名), 存档里的 ScriptSource 只是方法体。本脚本复现这一过程做编译验证。

用法:
    python3 wrap_build.py spec.json                 # 编译 spec 里的 script_body_file
    python3 wrap_build.py spec.json --emit 完整.cs   # 只生成完整源文件不编译 (用作手动粘贴的退路)

需要: dotnet SDK (编译模式)。退出码 0 = 编译通过。
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

TEMPLATE_HEAD = '''using System;
using System.Collections;
using System.Collections.Generic;

using Rhino;
using Rhino.Geometry;

using Grasshopper;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;

/// <summary>
/// This class will be instantiated on demand by the Script component.
/// </summary>
public class Script_Instance : GH_ScriptInstance
{
#region Utility functions
  /// <summary>Print a String to the [Out] Parameter of the Script component.</summary>
  /// <param name="text">String to print.</param>
  private void Print(string text) { __out.Add(text); }
  /// <summary>Print a formatted String to the [Out] Parameter of the Script component.</summary>
  /// <param name="format">String format.</param>
  /// <param name="args">Formatting parameters.</param>
  private void Print(string format, params object[] args) { __out.Add(string.Format(format, args)); }
  /// <summary>Print useful information about an object instance to the [Out] Parameter of the Script component.</summary>
  /// <param name="obj">Object instance to parse.</param>
  private void Reflect(object obj) { __out.Add(GH_ScriptComponentUtilities.ReflectType_CS(obj)); }
  /// <summary>Print the signatures of all the methods on an object instance to the [Out] Parameter of the Script component.</summary>
  /// <param name="obj">Object instance to parse.</param>
  /// <param name="method_name">Method name filter.</param>
  private void Reflect(object obj, string method_name) { __out.Add(GH_ScriptComponentUtilities.ReflectType_CS(obj, method_name)); }
#endregion

#region Members
  /// <summary>Gets the current Rhino document.</summary>
  private RhinoDoc RhinoDocument { get { return __rhinoDocument; } }
  /// <summary>Gets the Grasshopper document that owns this script.</summary>
  private GH_Document GrasshopperDocument { get { return __ghdoc; } }
  /// <summary>Gets the Grasshopper script component that owns this script.</summary>
  private IGH_Component Component { get { return __component; } }
  /// <summary>Gets the current iteration count. The first call to RunScript() is associated with Iteration=0.
  /// Any subsequent call within the same solution will increment the Iteration count.</summary>
  private int Iteration { get { return __iteration; } }
#endregion

  /// <summary>
  /// This procedure contains the user code. Input parameters are provided as regular arguments,
  /// Output parameters as ref arguments. You don't have to assign output parameters,
  /// they will have a default value.
  /// </summary>
  private void RunScript('''

TEMPLATE_TAIL = ''')
  {
'''

TEMPLATE_END = '''
  }

  // <Custom additional code> 

  // </Custom additional code> 
}'''


def wrap(spec, body):
    sig_in = ", ".join("double " + s["var"] for s in spec["sliders"])
    sig_out = ", ".join("ref object " + o["name"] for o in spec["outputs"])
    return TEMPLATE_HEAD + sig_in + ", " + sig_out + TEMPLATE_TAIL + body + TEMPLATE_END


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="spec.json (需含 sliders/outputs/script_body_file)")
    ap.add_argument("--emit", help="只输出完整源文件到该路径, 不编译")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    import os as _os
    _bf = spec["script_body_file"]
    if not _os.path.isabs(_bf):
        _bf = _os.path.join(_os.path.dirname(_os.path.abspath(args.spec)), _bf)
    body = open(_bf, encoding="utf-8").read()
    full = wrap(spec, body)

    here = os.path.dirname(os.path.abspath(__file__))
    if args.emit:
        open(args.emit, "w", encoding="utf-8").write(full)
        print(f"✅ 完整源文件已写出: {args.emit} (可全选粘贴进 GH 的 C# 编辑器)")
        return

    if not shutil.which("dotnet"):
        print("⚠️ 未找到 dotnet, 跳过编译验证。建议安装 .NET SDK 8+, 或至少人工复查语法。", file=sys.stderr)
        sys.exit(0)

    # 在临时目录构建: 某些输出目录(挂载盘)不支持 dotnet 的文件写入方式
    import tempfile
    workdir = tempfile.mkdtemp(prefix="ghx_compile_")
    for f in ("Stubs.cs", "cstest.csproj"):
        shutil.copy(os.path.join(here, f), workdir)
    open(os.path.join(workdir, "ScriptSource.cs"), "w", encoding="utf-8").write(full)
    r = subprocess.run(["dotnet", "build", "-v", "q"], cwd=workdir,
                       capture_output=True, text=True)
    tail = "\n".join((r.stdout + r.stderr).strip().split("\n")[-12:])
    if r.returncode == 0:
        print("✅ 编译通过 (LangVersion=5, 模拟 GH 包装)")
    else:
        print("❌ 编译失败:\n" + tail)
        sys.exit(1)


if __name__ == "__main__":
    main()
