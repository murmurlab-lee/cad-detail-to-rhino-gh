#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rhino3dm_helpers.py — rhino3dm 建模辅助函数 (已踩坑验证版)

用法:
    from rhino3dm_helpers import new_file, box, ring, add_to_layer, write_dual

关键 API 事实 (踩坑记录):
  - rhino3dm.Box(...) 只接受 BoundingBox, 不接受 Plane+Interval
  - Brep.CreateFromBox(box) 把盒体转 Brep; Mesh.CreateFromBox 不存在
  - File3dm.Write(path, 7) 第二参数=版本号, 7 即 Rhino 7 格式
  - 内核/环境重启后 rhino3dm 可能丢失: ensure_rhino3dm() 处理
"""
import sys


def ensure_rhino3dm():
    """导入 rhino3dm, 失败时尝试常见用户路径"""
    try:
        import rhino3dm
        return rhino3dm
    except ModuleNotFoundError:
        for p in ("/home/kimi/.local/lib/python3.12/site-packages",
                  "/home/kimi/.local/lib/python3.11/site-packages"):
            if p not in sys.path:
                sys.path.append(p)
        import rhino3dm
        return rhino3dm


r3 = ensure_rhino3dm()


def box(x0, y0, z0, x1, y1, z1):
    """轴对齐盒体 → Brep"""
    b = r3.Box(r3.BoundingBox(x0, y0, z0, x1, y1, z1))
    return r3.Brep.CreateFromBox(b)


def ring(lst, inner, outer, z0, z1):
    """方形环 (4 块盒体) 追加到 lst。inner/outer=内外半宽, z0<z1"""
    lst.append(box(-outer, inner, z0, outer, outer, z1))
    lst.append(box(-outer, -outer, z0, outer, -inner, z1))
    lst.append(box(inner, -inner, z0, outer, inner, z1))
    lst.append(box(-outer, -inner, z0, -inner, inner, z1))


def new_file(layers):
    """创建 File3dm 并建图层。

    layers: [(名称, (r,g,b)), ...]  返回 (file3dm, {名称: layer_index})
    注意: Layer.Color 直接赋 (r,g,b,a) 四元组即可, 不需要 System.Drawing。
    """
    f = r3.File3dm()
    f.Settings.ModelUnitSystem = r3.UnitSystem.Millimeters
    idx = {}
    for i, (name, (r, g, b)) in enumerate(layers):
        layer = r3.Layer()
        layer.Name = name
        layer.Color = (r, g, b, 255)
        f.Layers.Add(layer)
        idx[name] = i
    return f, idx


def add_to_layer(f3dm, breps, layer_index, name_prefix=None):
    """把一组 Brep 加入指定图层"""
    for i, brep in enumerate(breps):
        attr = r3.ObjectAttributes()
        attr.LayerIndex = layer_index
        if name_prefix:
            attr.Name = f"{name_prefix}_{i + 1}"
        f3dm.Objects.AddBrep(brep, attr)


def write_dual(f3dm, path):
    """双版本写出, 文件名显式带版本号 (不留无版本号文件, 避免 R7 用户误开 R8 主文件)。

    传入 xxx.3dm → 产出 xxx_Rhino8.3dm + xxx_Rhino7.3dm, 返回 (p8, p7)。
    传入已带 _Rhino8 后缀的路径则直接使用。
    交付规则 (v1.1 起): 只交付 xxx_Rhino7.3dm, R8 版留工作目录备用。
    """
    import os
    stem, ext = os.path.splitext(path)
    if stem.endswith("_Rhino8"):
        p8 = path
        p7 = stem[:-7] + "_Rhino7" + ext
    else:
        p8 = stem + "_Rhino8" + ext
        p7 = stem + "_Rhino7" + ext
    f3dm.Write(p8)      # Rhino 8 (rhino3dm 默认)
    f3dm.Write(p7, 7)   # Rhino 7
    return p8, p7
