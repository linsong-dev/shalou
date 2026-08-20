"""mindol.codex_adapter - Codex integration adapter"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional
from .core import Mindol


import os as _os

def _default_storage_path() -> str:
    """Get the default mindol storage path for Codex."""
    return _os.path.join(
        _os.environ.get("CODEX_HOME", _os.path.expanduser("~/.codex")),
        "mindol"
    )


class CodexMemoryAdapter:
    def __init__(self, storage_path: str = ""):
        self._storage_path = storage_path or _default_storage_path()
        self._core: Optional[Mindol] = None

    def _ensure_core(self) -> Mindol:
        if self._core is None:
            self._core = Mindol(storage_path=self._storage_path, persist=True)
        return self._core

    def search(self, query: str, top_k: int = 5, spaces: List[str] = None) -> List[Dict]:
        """语义检索（[L4-防再生] 过滤 archived 规则/模式单元，消除上下文噪音）"""
        core = self._ensure_core()
        # 多取候选以便过滤 archived 后仍有足够结果
        _cand = core.retrieve(query, top_k=top_k * 4, spaces=spaces) if top_k else []
        _rule_spaces = (core.SPACE_RULE, core.SPACE_PATTERN)
        out = []
        for u, sc in _cand:
            if u.space in _rule_spaces:
                try:
                    _d = json.loads(u.text)
                    if isinstance(_d, dict) and _d.get("status") == "archived":
                        continue  # 已归档：保留可追溯但不再注入检索上下文
                except Exception:
                    pass  # 非 JSON 文本（聊天等）放行
            out.append({"text": u.text[:500], "score": round(float(sc), 4),
                        "space": u.space, "uid": u.uid, "source": u.source})
            if len(out) >= top_k:
                break
        return out

    def save_context(self, text: str, source: str = "codex", space: str = "codex", tags: List[str] = None) -> str:
        core = self._ensure_core()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = f"codex_{ts}_{hash(text) % 10000:04d}"
        u = core.add_unit(text=text, source=source, uid=uid, space=space,
                          metadata={"tags": tags or [], "saved_at": datetime.now().isoformat()})
        core.save()
        return u.uid

    def archive(self, key: str, content: str, source: str = "dgen_archive") -> bool:
        try:
            self.save_context(text=f"[{key}] {content}", source=source, space="codex", tags=["archive", key])
            return True
        except Exception:
            return False

    def format_context(self, results: List[Dict]) -> str:
        if not results: return ""
        lines = ["[MEM] Related memories:", ""]
        for r in results:
            lines.append(f"  [{min(r['score'], 1.0):.0%}][{r['space']}] {r['text'][:200]}")
        return "\n".join(lines)

    def set_mood(self, val: float, source: str = "") -> float:
        return self._ensure_core().set_mood(val, source)

    def get_mood(self) -> Dict[str, float]:
        return self._ensure_core().get_mood()

    def associate(self, query: str, top_k: int = 3) -> List[Dict]:
        """跨空间联想候选（供预策/恒常门参考）。"""
        try:
            return self._ensure_core().associate(query, top_k=top_k)
        except Exception:
            return []

    def stats(self) -> Dict[str, int]:
        return self._ensure_core().space_stats()

    def close(self):
        if self._core: self._core.close(); self._core = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
