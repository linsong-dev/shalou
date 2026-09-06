"""shalou.codex_adapter - Codex integration adapter"""
from __future__ import annotations
import json, os
import re as _re
from datetime import datetime
from typing import Any, Dict, List, Optional
from .core import Shalou


import os as _os

def _default_storage_path() -> str:
    """Get the default shalou storage path for Codex."""
    return _os.path.join(
        _os.environ.get("CODEX_HOME", _os.path.expanduser("~/.codex")),
        "shalou"
    )


# [TOKEN 治理 2026-08-28] 记忆条目注入清洗（源头统一出口）
# 问题：rule/pattern/trade/codex 空间大量 JSON 规则体与命令转储被裸拼进注入（format_context text[:200]），
#       每轮重复占用 token。此处统一：JSON 规则体→提取可读 name/id/scene；命令转储→取首段语义；路径→<path>。
_CMD_DUMP_MARKERS = ("post_tool:", " tool=", " cmd=", " command=", " exit=", " exit \u2295", "node E:", ".ps1", ".mjs")
_JSON_NAME_FIELDS = ("name", "id")
_JSON_SCENE_FIELDS = ("scene", "summary", "intent_summary")


def _clean_mem_entry(text: str, space: str = "", limit: int = 120) -> str:
    """记忆条目注入清洗：清洗后为空串 = 该条剔除（调用方跳过）。
    JSON 规则体提取可读字段；命令转储截首段；路径脱敏；折叠空白限长。"""
    try:
        t = str(text or "").strip()
        if not t:
            return ""
        # 1) JSON 规则/模式/交易体 → 提取可读字段注入（正文 JSON 不注入）
        if t.startswith("{"):
            name = ""
            scene = ""
            try:
                _o = json.loads(t)
                if isinstance(_o, dict):
                    for _k in _JSON_NAME_FIELDS:
                        if _o.get(_k):
                            name = str(_o[_k]).strip()
                            break
                    for _k in _JSON_SCENE_FIELDS:
                        if _o.get(_k):
                            scene = str(_o[_k]).strip()
                            break
            except Exception:
                # 截断 JSON（core 取 text[:120]/[:500]）无法整体解析 → 正则提取可读字段
                for _k in _JSON_NAME_FIELDS + _JSON_SCENE_FIELDS:
                    _m = _re.search(r'"%s"\s*:\s*"([^"]*)"' % _k, t)
                    if _m and not name and _k in _JSON_NAME_FIELDS:
                        name = _m.group(1).strip()
                    elif _m and not scene and _k in _JSON_SCENE_FIELDS:
                        scene = _m.group(1).strip()
            if not name:
                return ""  # 无可读语义的 JSON → 机器噪声，整条剔除
            t = name
            if scene and scene != name:
                t += "（" + scene[:60] + "）"
        # 2) 命令转储 → 取首段可读语义（截断 tool=/cmd=/exit= 及之后）
        elif any(_m in t for _m in _CMD_DUMP_MARKERS):
            _head = t
            # post_tool: tool=Bash decision=... → 提取 tool= 名称
            _mt = _re.search(r"post_tool:\s*tool=([A-Za-z0-9_]+)", _head)
            if _mt:
                _head = "post_tool: tool=" + _mt.group(1)
            else:
                for _sep in (" | ", " ⊕ ", " tool=", " cmd=", " command=", " exit="):
                    if _sep in _head:
                        _head = _head.split(_sep)[0]
                        break
            t = _head.strip()
            if not t:
                return ""
        # 3) 绝对路径脱敏
        t = _re.sub(r"[A-Za-z]:\\[^\s\"']*", "<path>", t)
        # 4) 折叠空白 + 限长
        t = _re.sub(r"\s+", " ", t).strip()
        if len(t) > limit:
            t = t[:limit] + "…"
        return t
    except Exception:
        return ""


class CodexMemoryAdapter:
    def __init__(self, storage_path: str = ""):
        self._storage_path = storage_path or _default_storage_path()
        self._core: Optional[Shalou] = None

    def _ensure_core(self) -> Shalou:
        if self._core is None:
            self._core = Shalou(storage_path=self._storage_path, persist=True)
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
            _clean = _clean_mem_entry(str(r.get("text", "")), space=str(r.get("space", "")))
            if not _clean:
                continue  # 噪声条目剔除（JSON 无可读字段 / 纯命令转储）
            lines.append(f"  [{min(r.get('score', 0.0), 1.0):.0%}][{r.get('space', '')}] {_clean}")
        if len(lines) <= 2:
            return ""  # 全部剔除 → 无有效记忆，不注入
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
