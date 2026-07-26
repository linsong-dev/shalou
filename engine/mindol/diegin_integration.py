"""mindol.diegin_integration — 迭进引擎桥接（mindol ↔ diegin）

架构角色：
  Mindol 是迭进的语义记忆引擎（权威存储），本模块是 RuleEngine 之外
  给迭进工作流（call_diegin.py / main.py）提供的 Mindol 访问适配层。

数据流：
  pre_check()  → memory_format_context()  → 注入历史语义上下文到裁决
  post_review() → memory_archive()          → 决策归档到 Mindol codex 空间
  main.py       → memory_archive()          → 行为/反馈/复盘归档
  main.py       → memory_search()           → 语义检索（别名 mempalace_search）
  main.py       → get_memory_stats()        → 记忆统计
  main.py       → close_memory()            → 关闭时清理

后端：
  codex_adapter.CodexMemoryAdapter → Mindol 核心实例

不再有 MemPalace。Mindol 是唯一记忆后端。
"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional
from .codex_adapter import CodexMemoryAdapter

_MEMORY_ADAPTER: Optional[CodexMemoryAdapter] = None

def _get_adapter() -> CodexMemoryAdapter:
    """获取/初始化 Mindol 适配器（单例懒加载）"""
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER is None:
        _MEMORY_ADAPTER = CodexMemoryAdapter()
    return _MEMORY_ADAPTER

def memory_search(query: str, max_results: int = 5) -> List[Dict]:
    """语义搜索（对外别名: mempalace_search，兼容旧调用方）"""
    try: return _get_adapter().search(query, top_k=max_results)
    except Exception: return []

def memory_archive(rule_id: str, decision: str, context: Dict = None) -> bool:
    """归档决策记录到 Mindol（对外别名: dgen_archive，兼容旧调用方）"""
    try:
        content = f"[{rule_id}] {decision}"
        if context: content += f" | ctx: {json.dumps(context, ensure_ascii=False)[:200]}"
        return _get_adapter().archive(rule_id, content)
    except Exception: return False

def memory_format_context(query: str = "", top_k: int = 3) -> str:
    """格式化记忆上下文，用于注入到 pre_check() 裁决结果"""
    try:
        a = _get_adapter()
        r = a.search(query, top_k=top_k) if query else []
        return a.format_context(r)
    except Exception: return ""

def get_memory_stats() -> Dict[str, int]:
    """获取各空间统计"""
    try: return _get_adapter().stats()
    except Exception: return {}

def save_chat(text: str, source: str = "user", metadata: dict = None) -> bool:
    """保存对话内容到 Mindol raw_chat 空间
    同时同步到 codex 空间保证检索覆盖。
    在 pre_check() 入口处由 diegin 自动调用。
    """
    try:
        adapter = _get_adapter()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = f"chat_{ts}_{hash(text) % 10000:04d}"
        core = adapter._ensure_core()
        # 写入 raw_chat 空间
        core.add_unit(
            text=text[:2000],
            source=source,
            uid=uid,
            space=core.SPACE_RAW_CHAT,
            metadata={"source": source, "saved_at": datetime.now().isoformat(), **(metadata or {})}
        )
        # 同步到 codex 空间 (保持向后兼容)
        codex_uid = f"chat_codex_{ts}_{hash(text) % 10000:04d}"
        core.add_unit(
            text=text[:2000],
            source=f"chat_{source}",
            uid=codex_uid,
            space=core.SPACE_CODEX,
            metadata={"source": source, "saved_at": datetime.now().isoformat(), **(metadata or {})}
        )
        core.save()
        return True
    except Exception:
        return False

def close_memory():

    """关闭 Mindol 连接"""
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER: _MEMORY_ADAPTER.close(); _MEMORY_ADAPTER = None
