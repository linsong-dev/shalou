#!/usr/bin/env python3
"""迁移 MemPalace + TdxClaw 数据到 Shalou · 流动的记忆

迁移源:
  1. palace_data/convos/ — 旧 MemPalace 对话记忆 (35 个 .md 文件)
  2. MEMORY.md — 辰渊长期记忆
  3. memory_v2 workspace — TdxClaw 新版记忆

用法:
    python migrate_mempalace_to_v2.py [--dry-run] [--mempalace-dir PATH]
"""
import os, sys, glob, json, argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "engine")))
from shalou.codex_adapter import CodexMemoryAdapter


DATA_SOURCES = [
    # 源1: MemPalace palace_data/convos/
    {
        "name": "MemPalace convos",
        "path": r"E:\Tdxclaw_v1.0.28\备份-0710\.openclaw-tdxclaw\skills\mempalace-openclaw\palace_data\convos",
        "glob": "*.md",
        "space": "codex",
        "source": "migrate_mempalace",
        "tag": ["archive", "mempalace"]
    },
    # 源2: MEMORY.md 长期记忆
    {
        "name": "MEMORY.md 长期记忆",
        "path": r"E:\Tdxclaw_v1.0.28\备份-0710\.openclaw-tdxclaw\workspace\MEMORY.md",
        "type": "single_file",
        "space": "codex",
        "source": "migrate_memory_md",
        "tag": ["archive", "long_term_memory"]
    },
    # 源3: workspace/memory_v2 源码文件 (作为配置参考)
    {
        "name": "memory_v2 source (config)",
        "path": r"E:\Tdxclaw_v1.0.28\备份-0710\.openclaw-tdxclaw\workspace\memory_v2",
        "glob": "*.py",
        "space": "codex",
        "source": "migrate_memory_v2_src",
        "tag": ["archive", "memory_v2_source"]
    },
]


def scan_source(source: dict) -> list:
    """扫描单个数据源"""
    records = []
    spath = source["path"]

    if source.get("type") == "single_file":
        if os.path.exists(spath):
            try:
                with open(spath, "r", encoding="utf-8") as f:
                    content = f.read()[:3000]
                key = f"migrated_{os.path.basename(spath).replace('.', '_')}"
                records.append({
                    "key": key,
                    "content": content,
                    "source": source["source"],
                    "space": source["space"],
                    "tags": source["tag"],
                })
                print(f"  [SCAN] {source['name']}: 1 条记录")
            except Exception as e:
                print(f"  [WARN] {source['name']}: 读取失败 {e}")
        else:
            print(f"  [SKIP] {source['name']}: 路径不存在")
        return records

    if not os.path.isdir(spath):
        print(f"  [SKIP] {source['name']}: 路径不存在")
        return records

    file_pattern = source.get("glob", "*")
    files = glob.glob(os.path.join(spath, file_pattern))
    files.sort()

    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()[:2000]
            if not content.strip():
                continue
            name = os.path.basename(fp).replace(".", "_")
            key = f"migrated_{name[:60]}"
            records.append({
                "key": key,
                "content": content,
                "source": source["source"],
                "space": source["space"],
                "tags": source["tag"],
            })
        except Exception as e:
            print(f"  [WARN] 跳过 {fp}: {e}")

    print(f"  [SCAN] {source['name']}: {len(records)} 条记录")
    return records


def main():
    parser = argparse.ArgumentParser(description="迁移旧数据到 Shalou · 流动的记忆")
    parser.add_argument("--dry-run", action="store_true", help="仅预览不写入")
    args = parser.parse_args()

    all_records = []
    print("=== 扫描数据源 ===\n")
    for source in DATA_SOURCES:
        records = scan_source(source)
        all_records.extend(records)

    total = len(all_records)
    print(f"\n=== 共 {total} 条记录待迁移 ===")
    if total == 0:
        print("[INFO] 无数据需要迁移")
        return

    if args.dry_run:
        print("\n[DONE] DRY-RUN 完成，未写入任何数据")
        return

    print("\n=== 执行迁移 ===")
    count = 0
    with CodexMemoryAdapter() as adapter:
        for rec in all_records:
            ok = adapter.archive(rec["key"], rec["content"], source=rec["source"])
            if ok:
                count += 1
            else:
                print(f"  [WARN] 迁移失败: {rec['key'][:40]}")
    
    print(f"\n[DONE] 迁移完成！已写入 {count}/{total} 条记录到 Shalou")
    print(f"[INFO] 存储路径: ~/.codex/shalou/memory.db")

    # Show stats
    stats = CodexMemoryAdapter().stats()
    print(f"[INFO] Shalou 当前状态: {stats}")


if __name__ == "__main__":
    main()
