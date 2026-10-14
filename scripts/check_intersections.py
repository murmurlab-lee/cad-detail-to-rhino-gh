#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_intersections.py — 构件包围盒两两相交检查

交付 .3dm 前必跑。区分两类相交:
  - 有意相交 (白名单): 嵌埋关系, 如钢网埋在砂浆里、肋互相交叉、开启槽开在铺装里
  - 意外相交: 设计错误, 必须改几何

用法 (作为模块):
    from check_intersections import check
    boxes = [("底板", (-280,-280,-80, 280,280,-70)), ...]   # (标签, bbox)
    collisions = check(boxes, whitelist=[("钢网","砂浆")])
    # collisions = [(labelA, labelB), ...] 应为空

用法 (命令行, 读 JSON):
    python3 check_intersections.py boxes.json
    # boxes.json: {"boxes": [{"label": "底板", "bbox": [x0,y0,z0,x1,y1,z1]}, ...],
    #              "whitelist": [["钢网", "砂浆"], ...]}
"""
import json
import sys


def _overlap(a, b):
    return all(a[i] < b[i + 3] and b[i] < a[i + 3] for i in range(3))


def check(boxes, whitelist=()):
    """boxes: [(label, (x0,y0,z0,x1,y1,z1)), ...]
    whitelist: [(labelA, labelB), ...] 或 [(前缀A, 前缀B)], 按标签前缀匹配
    返回非白名单的相交对 [(labelA, labelB), ...]
    """
    def allowed(la, lb):
        for wa, wb in whitelist:
            if (la.startswith(wa) and lb.startswith(wb)) or (la.startswith(wb) and lb.startswith(wa)):
                return True
        return False

    collisions = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            la, ba = boxes[i]
            lb, bb = boxes[j]
            if _overlap(ba, bb) and not allowed(la, lb):
                collisions.append((la, lb))
    return collisions


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    boxes = [(b["label"], tuple(b["bbox"])) for b in spec["boxes"]]
    wl = [tuple(p) for p in spec.get("whitelist", [])]
    cols = check(boxes, wl)
    if cols:
        print(f"❌ {len(cols)} 处意外相交:")
        for a, b in cols:
            print(f"   {a} × {b}")
        sys.exit(1)
    print(f"✅ {len(boxes)} 个构件, 无意外相交 (白名单 {len(wl)} 对)")


if __name__ == "__main__":
    main()
