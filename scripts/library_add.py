#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""library_add.py — 构造库 (Detail Atlas) 建库与入库工具

架构 (2026-10 实测): 阿里云 OSS 默认域名强制 Content-Disposition: attachment, 无法直接
托管 HTML。因此页面 = 用户本地的单文件 index.html, 数据全部在 OSS (library.js + nodes/),
index.html 通过绝对 URL 引用 library.js。入库 = 上传节点文件 + 重建上传 library.js。

配置与数据 (跨会话持久, 不随 skill 安装目录):
  /mnt/agents/output/构造库/library_oss.json   OSS 连接配置 (含 AccessKey, 不上传)
  /mnt/agents/output/构造库/library_db.json    全部节点元数据 (重建索引的源)

用法:
  # 首次建库 (用户已建好空桶 + 专用 AccessKey 后):
  python3 library_add.py --init --bucket detail-atlas-data --region oss-cn-shanghai \
      --ak LTAIxxx --sk xxx --password 页面密码
  # 日常入库 (skill 第 9 阶段自动执行):
  python3 library_add.py --add --name 栏杆标准段 --category 楼梯 \
      --tags 金属栏杆,标准段 --spec spec.json --description "假设清单..." \
      --model xxx_Rhino7.3dm --ghx xxx_参数化.ghx --preview xxx_轴测.png \
      [--pdf 原始.pdf] [--refs 照片目录]

仅依赖 requests。命名规则: NNN_名称 (按时间顺序编号), 同名自动加 _01/_02 后缀。
"""
import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import sys

import requests

STORE_DIR = "/mnt/agents/output/构造库"
CFG_PATH = os.path.join(STORE_DIR, "library_oss.json")
DB_PATH = os.path.join(STORE_DIR, "library_db.json")
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "assets", "library", "index.html")

CATEGORIES = ["基础", "结构", "屋顶", "楼地面", "墙面", "幕墙", "楼梯",
              "景观", "照明", "机电", "室内"]

CT = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
      ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
      ".pdf": "application/pdf", ".json": "application/json; charset=utf-8",
      ".3dm": "application/octet-stream", ".ghx": "application/octet-stream"}
DL_EXT = (".3dm", ".ghx", ".pdf")  # 强制下载: OSS 对默认域名本就强制 attachment, 显式声明保持一致


def cyrb53(s, seed=0):
    """与 index.html 内 JS 版一致的哈希 (密码只存哈希, 不存明文)"""
    M = 0xFFFFFFFF
    h1 = (0xdeadbeef ^ seed) & M
    h2 = (0x41c6ce57 ^ seed) & M
    for ch in s:
        c = ord(ch)
        h1 = ((h1 ^ c) * 2654435761) & M
        h2 = ((h2 ^ c) * 1597334677) & M
    h1 = ((h1 ^ (h1 >> 16)) * 2246822507) & M
    h1 = (h1 ^ (((h2 ^ (h2 >> 13)) * 3266489909) & M)) & M
    h2 = ((h2 ^ (h2 >> 16)) * 2246822507) & M
    h2 = (h2 ^ (((h1 ^ (h1 >> 13)) * 3266489909) & M)) & M
    return 4294967296 * (2097151 & h2) + h1


class OSS:
    """阿里云 OSS V1 签名 REST 客户端 (仅实现本工具需要的操作)"""

    def __init__(self, cfg):
        self.ak = cfg["ak"]
        self.sk = cfg["sk"]
        self.bucket = cfg["bucket"]
        self.region = cfg["region"]
        self.host = f"https://{self.bucket}.{self.region}.aliyuncs.com"

    def _req(self, method, resource, body=None, content_type="", headers=None):
        from email.utils import formatdate
        date = formatdate(usegmt=True)
        body = body or b""
        sts = "\n".join([method, "", content_type if body else "", date]) + "\n" + resource
        sig = base64.b64encode(
            hmac.new(self.sk.encode(), sts.encode(), hashlib.sha1).digest()).decode()
        h = {"Date": date, "Authorization": f"OSS {self.ak}:{sig}"}
        if body:
            h["Content-Type"] = content_type
        if headers:
            h.update(headers)
        path = "/" + resource.split("/", 2)[2]
        r = requests.request(method, self.host + path, data=body, headers=h)
        if r.status_code >= 300:
            raise RuntimeError(f"OSS {method} {path} -> {r.status_code}: {r.text[:300]}")
        return r

    def put(self, key, data, content_type, extra_headers=None):
        return self._req("PUT", f"/{self.bucket}/{key}", data, content_type, extra_headers)

    def put_file(self, key, local):
        ext = os.path.splitext(local)[1].lower()
        headers = {"Content-Disposition": "attachment"} if ext in DL_EXT else None
        with open(local, "rb") as f:
            self.put(key, f.read(), CT.get(ext, "application/octet-stream"), headers)

    def check(self):
        """验证凭据与桶可达 (GetBucketLocation)"""
        r = self._req("GET", f"/{self.bucket}/?location")
        return r.text


def load_cfg():
    if not os.path.exists(CFG_PATH):
        sys.exit("❌ 未找到 OSS 配置, 请先运行 --init 建库")
    return json.load(open(CFG_PATH, encoding="utf-8"))


def load_db():
    if os.path.exists(DB_PATH):
        return json.load(open(DB_PATH, encoding="utf-8"))
    return {"nodes": []}


def save_db(db):
    os.makedirs(STORE_DIR, exist_ok=True)
    json.dump(db, open(DB_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def rebuild_library_js(cfg, db):
    """从 db 重建 library.js 并上传"""
    base = f"https://{cfg['bucket']}.{cfg['region']}.aliyuncs.com"

    def abs_(n):
        """节点记录内的相对路径转绝对 URL"""
        n = dict(n)
        n["preview"] = base + "/" + n["preview"]
        f = dict(n["files"])
        for k in ("model", "ghx", "pdf"):
            if f.get(k):
                f[k] = dict(f[k], path=base + "/" + f[k]["path"])
        f["refs"] = [dict(r, path=base + "/" + r["path"]) for r in f.get("refs", [])]
        n["files"] = f
        return n

    nodes = [abs_(n) for n in db["nodes"]]
    js = ("// Detail Atlas 构造库数据 — 由 library_add.py 生成, 勿手改\n"
          "// 密码修改: 用 --password 重新生成哈希 (页面不含明文密码)\n"
          "const LIB_CONFIG = {\n  title: \"构造库\",\n  passwordHash: "
          + str(cfg["passwordHash"]) + ",\n};\n\n"
          "const CATEGORIES = " + json.dumps(CATEGORIES, ensure_ascii=False) + ";\n\n"
          "const NODES = " + json.dumps(nodes, ensure_ascii=False, indent=2) + ";\n")
    return js


def do_init(args):
    cfg = {"bucket": args.bucket, "region": args.region, "ak": args.ak, "sk": args.sk,
           "passwordHash": cyrb53(args.password)}
    oss = OSS(cfg)
    # 1) 验证凭据
    oss.check()
    print(f"✅ 凭据有效, 桶 {args.bucket} ({args.region}) 可达")
    # 2) 关公共访问封锁 + 公共读 + 静态托管
    body = (b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<PublicAccessBlockConfiguration><BlockPublicAccess>false</BlockPublicAccess>'
            b'</PublicAccessBlockConfiguration>')
    oss.put("?publicAccessBlock", body, "application/xml")
    oss._req("PUT", f"/{args.bucket}/?acl", b"", "", {"x-oss-acl": "public-read"})
    body = (b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<WebsiteConfiguration><IndexDocument><Suffix>index.html</Suffix></IndexDocument>'
            b'</WebsiteConfiguration>')
    oss.put("?website", body, "application/xml")
    print("✅ 已配置: 关闭公共访问封锁 / 公共读 / 静态网站托管")
    # 3) 初始 library.js + 入口 index.html
    os.makedirs(STORE_DIR, exist_ok=True)
    json.dump(cfg, open(CFG_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    db = load_db()
    save_db(db)
    oss.put("library.js", rebuild_library_js(cfg, db).encode("utf-8"),
            "application/javascript; charset=utf-8")
    tpl = open(TEMPLATE, encoding="utf-8").read()
    assert "__LIB_BASE__" in tpl, "模板缺少 __LIB_BASE__ 占位符"
    base = f"https://{args.bucket}.{args.region}.aliyuncs.com"
    html = tpl.replace("__LIB_BASE__", base)
    entry = os.path.join(STORE_DIR, "DetailAtlas_构造库_入口.html")
    open(entry, "w", encoding="utf-8").write(html)
    oss.put("index.html", html.encode("utf-8"), "text/html; charset=utf-8")
    print(f"✅ 建库完成: {len(db['nodes'])} 个节点")
    print(f"👉 把 {entry} 下载给用户 (双击即用, 数据自动来自 OSS)")


def kb(p):
    return round(os.path.getsize(p) / 1024)


def do_add(args):
    cfg = load_cfg()
    if args.category not in CATEGORIES:
        sys.exit(f"❌ 分类必须是: {'/'.join(CATEGORIES)}")
    db = load_db()
    oss = OSS(cfg)

    # 编号 + 同名后缀
    nid = max([int(n["id"]) for n in db["nodes"]] or [0]) + 1
    same = [n for n in db["nodes"] if n["name"].split("_")[0] == args.name]
    name = args.name if not same else f"{args.name}_{len(same):02d}"
    dirname = f"{nid:03d}_{name}"
    base_key = f"nodes/{dirname}"
    print(f"入库: {dirname} (分类 {args.category})")

    # 参数表
    params = []
    if args.spec:
        spec = json.load(open(args.spec, encoding="utf-8"))
        params = [{"nick": s["nick"], "min": s["min"], "max": s["max"], "def": s["value"]}
                  for s in spec.get("sliders", [])]

    files = {"refs": []}
    uploads = []  # (local, key)

    def add_file(local, key, fkey=None, label=None):
        uploads.append((local, key))
        if fkey:
            files[fkey] = {"path": key, "label": label or os.path.basename(local),
                           "kb": kb(local)}

    add_file(args.preview, f"{base_key}/preview.png")
    add_file(args.model, f"{base_key}/{os.path.basename(args.model)}", "model",
             "Rhino 7 模型 (.3dm)")
    add_file(args.ghx, f"{base_key}/{os.path.basename(args.ghx)}", "ghx",
             "Grasshopper 参数化 (.ghx)")
    if args.pdf:
        add_file(args.pdf, f"{base_key}/source.pdf", "pdf",
                 f"原始图纸 {os.path.basename(args.pdf)}")
    if args.refs:
        exts = (".png", ".jpg", ".jpeg")
        for i, f in enumerate(sorted(os.listdir(args.refs)), 1):
            if os.path.splitext(f)[1].lower() in exts:
                ext = os.path.splitext(f)[1].lower()
                key = f"{base_key}/refs/ref_{i:02d}{ext}"
                uploads.append((os.path.join(args.refs, f), key))
                files["refs"].append({"path": key, "kb": kb(os.path.join(args.refs, f))})

    node = {"id": f"{nid:03d}", "name": name, "dir": base_key,
            "category": args.category,
            "date": datetime.date.today().isoformat(),
            "tags": [t.strip() for t in args.tags.split(",") if t.strip()],
            "preview": f"{base_key}/preview.png", "files": files, "params": params,
            "description": args.description or ""}

    for local, key in uploads:
        oss.put_file(key, local)
        print(f"  ↑ {key}")
    oss.put(f"{base_key}/info.json", json.dumps(node, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8")
    db["nodes"].append(node)
    save_db(db)
    oss.put("library.js", rebuild_library_js(cfg, db).encode("utf-8"),
            "application/javascript; charset=utf-8")
    print(f"✅ 已入库并更新索引 (库内共 {len(db['nodes'])} 个节点), 用户刷新页面即可见")


def main():
    ap = argparse.ArgumentParser(description="Detail Atlas 构造库建库/入库")
    ap.add_argument("--init", action="store_true", help="首次建库")
    ap.add_argument("--add", action="store_true", help="节点入库")
    # init 参数
    ap.add_argument("--bucket"); ap.add_argument("--region")
    ap.add_argument("--ak"); ap.add_argument("--sk")
    ap.add_argument("--password", default="1234", help="页面密码 (默认 1234, 只存哈希)")
    # add 参数
    ap.add_argument("--name"); ap.add_argument("--category"); ap.add_argument("--tags", default="")
    ap.add_argument("--model"); ap.add_argument("--ghx"); ap.add_argument("--preview")
    ap.add_argument("--pdf"); ap.add_argument("--refs"); ap.add_argument("--spec")
    ap.add_argument("--description", default="")
    args = ap.parse_args()

    if args.init:
        for f in ("bucket", "region", "ak", "sk"):
            if not getattr(args, f):
                sys.exit(f"❌ --init 需要 --{f}")
        do_init(args)
    elif args.add:
        for f in ("name", "category", "model", "ghx", "preview"):
            if not getattr(args, f):
                sys.exit(f"❌ --add 需要 --{f}")
        do_add(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
