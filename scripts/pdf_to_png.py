#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pdf_to_png.py — CAD 矢量 PDF 读图预处理

CAD 导出的 PDF 常为纯矢量 (read_file 直接读会显示"空"), 且线宽极细、对比度低。
流程: pdftoppm 栅格化 → 阈值增强 (把非白像素加深) → 供视觉读图。

用法:
    python3 pdf_to_png.py 图纸.pdf -o 输出目录 [--dpi 150] [--no-enhance]

依赖: poppler-utils (pdftoppm), PIL, numpy
输出: 每页一个 .png, 增强版加 _enh 后缀
"""
import argparse
import os
import subprocess
import sys


def enhance(src, dst, dark=250, factor=0.25):
    """阈值增强: 灰度值 < dark 的像素乘 factor 加深, 其余拉白"""
    import numpy as np
    from PIL import Image
    a = np.array(Image.open(src).convert("L"))
    a = np.where(a < dark, (a * factor).clip(0, 255), 255).astype("uint8")
    Image.fromarray(a).save(dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--outdir", default=".")
    ap.add_argument("--dpi", type=int, default=150, help="栅格化分辨率, 标注密集可提到 200-300")
    ap.add_argument("--no-enhance", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.pdf))[0]
    prefix = os.path.join(args.outdir, stem)
    subprocess.run(["pdftoppm", "-png", "-r", str(args.dpi), args.pdf, prefix], check=True)

    pages = sorted(f for f in os.listdir(args.outdir)
                   if f.startswith(stem) and f.endswith(".png") and "_enh" not in f)
    outs = []
    for f in pages:
        p = os.path.join(args.outdir, f)
        if args.no_enhance:
            outs.append(p)
        else:
            ep = p.replace(".png", "_enh.png")
            enhance(p, ep)
            outs.append(ep)
    print("生成页面:")
    for o in outs:
        print("  " + o)
    print("\n提示: 标注字太小看不清时, 提高 --dpi 重跑; 或用 PIL 对局部区域再裁切放大。")


if __name__ == "__main__":
    main()
