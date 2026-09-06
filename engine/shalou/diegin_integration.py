"""shalou.diegin_integration — 迭进引擎桥接（shalou ↔ diegin）

架构角色：
  Shalou 是迭进的语义记忆引擎（权威存储），本模块是 RuleEngine 之外
  给迭进工作流（call_diegin.py / main.py）提供的 Shalou 访问适配层。

数据流：
  pre_check()  → memory_format_context()  → 注入历史语义上下文到裁决
  post_review() → memory_archive()          → 决策归档到 Shalou codex 空间
  main.py       → memory_archive()          → 行为/反馈/复盘归档
  main.py       → memory_search()           → 语义检索（别名 mempalace_search）
  main.py       → get_memory_stats()        → 记忆统计
  main.py       → close_memory()            → 关闭时清理

后端：
  codex_adapter.CodexMemoryAdapter → Shalou 核心实例

不再有 MemPalace。Shalou 是唯一记忆后端。
"""
from __future__ import annotations
import json, os
import re as _re
from datetime import datetime
from typing import Any, Dict, List, Optional
from .codex_adapter import CodexMemoryAdapter

_MEMORY_ADAPTER: Optional[CodexMemoryAdapter] = None

# P1 写入脱敏（防敏感内容永久沉淀进记忆库）：token/凭证命中即替换为占位符
# 与 checkpush SENSITIVE_PATTERNS 同源；路径类不脱敏（语义检索需要路径上下文）
_SANITIZE_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{20,}", "[REDACTED_GHP]"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "[REDACTED_PAT]"),
    (r"gho_[A-Za-z0-9]{20,}", "[REDACTED_GHO]"),
    (r"ghs_[A-Za-z0-9]{20,}", "[REDACTED_GHS]"),
    (r"ghr_[A-Za-z0-9]{20,}", "[REDACTED_GHR]"),
    # 负向前瞻排除已脱敏占位符：保证脱敏幂等 + 扫描不误报
    # 字符串拼接避免审计自指（源码不出现连续 "x-access-token:" 字面量）
    (r"x-access" + r"-token:(?!\[REDACTED\])[^\s@]+@", r"x-access" + r"-token:[REDACTED]@"),
    (r"sk-[A-Za-z0-9]{20,}", "[REDACTED_SK]"),
    (r"AIza[0-9A-Za-z_-]{20,}", "[REDACTED_AIZA]"),
    (r"(?i)(authorization\s*[:=]\s*)(?:token|bearer)\s+[A-Za-z0-9\-._~+/]{20,}", r"\1[REDACTED]"),
]


def sanitize_text(text: str) -> str:
    """记忆库写入前脱敏（P1 防线）：token/凭证命中即替换为占位符，防止泄露内容落库"""
    if not text:
        return text
    for _p, _r in _SANITIZE_PATTERNS:
        try:
            text = _re.sub(_p, _r, text)
        except Exception:
            pass
    return text


# [TOKEN 治理 2026-08-28] 注入噪声过滤：strike 原始 JSON、post_tool 命令转储、含转义路径的 JSON 规则体
# 每轮重复命中且为机器 JSON（含完整命令/转义路径），对模型无语义价值却持续占 token；仅过滤注入面，不触碰检索裁决。
_NOISE_MARKERS = (
    '"count"', 'first_seen', 'last_detail',
    'exit \u2295',
    'post_tool: tool=',
    '\\\\users\\\\',
)

def _is_noise_unit(text):
    if not text:
        return True
    return any(_m in text for _m in _NOISE_MARKERS)

def _clean_mem_text(text, limit=150):
    """联想/检索注入文本清洗：去噪声、去 [联想] 前缀、JSON 规则体提取可读 name、折叠空白、限长；垃圾返回空串。"""
    t = (text or "").strip()
    if not t or _is_noise_unit(t):
        return ""
    parts = [p.strip() for p in t.split(" ⊕ ")]
    cleaned = []
    for p in parts:
        if p.startswith("[联想] "):
            p = p[len("[联想] "):].strip()
        if p.startswith("{"):
            _nm = ""
            _sc = ""
            try:
                _o = json.loads(p)
                if isinstance(_o, dict):
                    _nm = str(_o.get("name", "") or "").strip()
                    _sc = str(_o.get("scene", "") or "").strip()
            except Exception:
                # 截断 JSON（core.associate 取 text[:120]）无法整体解析 → 正则提取可读字段
                _m1 = _re.search(r'"name"\s*:\s*"([^"]*)"', p)
                _m2 = _re.search(r'"scene"\s*:\s*"([^"]*)"', p)
                if _m1:
                    _nm = _m1.group(1).strip()
                if _m2:
                    _sc = _m2.group(1).strip()
            if _nm:
                p = _nm + ("（" + _sc[:40] + "）" if _sc else "")
        p = p.replace("\r", " ").replace("\n", " ")
        p = _re.sub(r"\s+", " ", p).strip()
        if p:
            cleaned.append(p)
    t = " ⊕ ".join(cleaned)
    if len(t) > limit:
        t = t[:limit] + "…"
    return t

def _get_adapter() -> CodexMemoryAdapter:
    """获取/初始化 Shalou 适配器（单例懒加载）"""
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER is None:
        _MEMORY_ADAPTER = CodexMemoryAdapter()
    return _MEMORY_ADAPTER

# v3.6: 检索缓存（同进程内同 query 不重复计算）+ 超时熔断
import threading as _thr
_SEARCH_CACHE: Dict[str, List[Dict]] = {}
_SEARCH_TIMEOUT = 2.5

def _search_with_timeout(query: str, max_results: int) -> List[Dict]:
    """带超时熔断的 Shalou 检索：超时返回空，不阻塞迭进实时链路"""
    if not query:
        return []
    if query in _SEARCH_CACHE:
        return _SEARCH_CACHE[query]
    result_box = []
    def _do():
        try:
            result_box.append(_get_adapter().search(query, top_k=max_results))
        except Exception:
            result_box.append([])
    t = _thr.Thread(target=_do, daemon=True)
    t.start()
    t.join(_SEARCH_TIMEOUT)
    if t.is_alive():
        return []  # 超时熔断：返回空，不阻塞
    r = result_box[0] if result_box else []
    _SEARCH_CACHE[query] = r
    return r

def memory_search(query: str, max_results: int = 5) -> List[Dict]:
    """语义搜索（对外别名: mempalace_search，兼容旧调用方）"""
    try: return _search_with_timeout(query, max_results)
    except Exception: return []

# [TOKEN 治理 2026-08-31] 写侧降噪：JSON 全文/长命令转储不落 Shalou（语义检索只需可读摘要）
_ARCHIVE_DECISION_LIMIT = 240
_ARCHIVE_CONTEXT_LIMIT = 120
_ARCHIVE_TOTAL_LIMIT = 420

def _archive_summary(decision: str) -> str:
    """把归档 decision 压缩为可读摘要：JSON 提取核心字段，命令折叠空白，超限截断。"""
    d = (decision or "").strip()
    if not d:
        return ""
    if d.startswith("{") or d.startswith("["):
        try:
            obj = json.loads(d)
            if isinstance(obj, dict):
                picks = []
                for key in ("action", "status", "summary", "intent_summary", "completion_criteria",
                            "reason", "result", "report", "decision", "task_id", "task_type"):
                    v = obj.get(key)
                    if v is None:
                        continue
                    if isinstance(v, (dict, list)):
                        v = json.dumps(v, ensure_ascii=False)[:60]
                    picks.append(f"{key}={str(v)[:60]}")
                if picks:
                    d = " | ".join(picks)
            elif isinstance(obj, list):
                d = f"list({len(obj)} items)"
        except Exception:
            pass
    d = d.replace("\r", " ").replace("\n", " ")
    d = _re.sub(r"\s+", " ", d).strip()
    if len(d) > _ARCHIVE_DECISION_LIMIT:
        d = d[:_ARCHIVE_DECISION_LIMIT - 1] + "…"
    return d

def memory_archive(rule_id: str, decision: str, context: Dict = None) -> bool:
    """归档决策记录到 Shalou（对外别名: dgen_archive，兼容旧调用方）。
    [TOKEN 治理 2026-08-31] 写侧降噪：不落 JSON 全文/命令转储，只落可读摘要。"""
    try:
        content = f"[{rule_id}] {_archive_summary(decision)}"
        if context:
            try:
                ctx_str = json.dumps(context, ensure_ascii=False)
                if len(ctx_str) > _ARCHIVE_CONTEXT_LIMIT:
                    ctx_str = ctx_str[:_ARCHIVE_CONTEXT_LIMIT] + "…"
                content += f" | ctx: {ctx_str}"
            except Exception:
                pass
        if len(content) > _ARCHIVE_TOTAL_LIMIT:
            content = content[:_ARCHIVE_TOTAL_LIMIT] + "…"
        return _get_adapter().archive(rule_id, content)
    except Exception: return False

def memory_format_context(query: str = "", top_k: int = 3) -> str:
    """格式化记忆上下文，用于注入到 pre_check() 裁决结果
    [TOKEN 治理 2026-08-28] 注入前过滤噪声单元（strike JSON / post_tool 转储 / 转义路径）。"""
    try:
        a = _get_adapter()
        r = _search_with_timeout(query, top_k) if query else []
        r = [x for x in r if not _is_noise_unit(str(x.get("text", "")))]
        return a.format_context(r)
    except Exception: return ""

def memory_decay() -> Dict:
    """记忆代谢（v3.7.2）：时间衰减 + 自动休眠，供每日维护调用。

    返回统计 {decayed, dormant, skipped}；失败返回空字典（不阻断维护任务）。
    """
    try:
        return _get_adapter()._ensure_core().decay_and_dormancy()
    except Exception:
        return {}

def get_memory_stats() -> Dict[str, int]:
    """获取各空间统计"""
    try: return _get_adapter().stats()
    except Exception: return {}

def memory_set_mood(val: float, source: str = "") -> float:
    """注入情绪标量（自照镜 courage → Shalou mood），驱动检索空间权重调制。
    失败静默（不阻断主链路）。"""
    try:
        return _get_adapter().set_mood(val, source)
    except Exception:
        return 0.0

def memory_get_mood() -> Dict[str, float]:
    try:
        return _get_adapter().get_mood()
    except Exception:
        return {"mood": 0.0, "source": ""}

def memory_associate(query: str, top_k: int = 3) -> List[Dict]:
    """跨空间联想候选（供预策/恒常门参考；检索失败静默返回空）。
    [TOKEN 治理 2026-08-28] 注入前剔除 strike JSON/命令转储噪声、清洗并去重，返回纯文本。"""
    try:
        out = []
        for a in _get_adapter().associate(query, top_k=top_k * 4):
            t = _clean_mem_text(str(a.get("text", "")))
            if t and t not in out:
                out.append(t)
            if len(out) >= top_k:
                break
        return [{"text": t, "space": "associate"} for t in out]
    except Exception:
        return []

def save_chat(text: str, source: str = "user", metadata: dict = None) -> bool:
    """保存对话内容到 Shalou raw_chat 空间（单写）。
    [PERF-C 2026-08-20] 去掉 codex 空间双写——retrieve 默认遍历全空间检索，
    raw_chat 已被覆盖，双写纯冗余（每工具调用省 1 条写入）。"""
    try:
        text = sanitize_text(text)  # P1 写入脱敏：token/凭证不落库
        adapter = _get_adapter()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = f"chat_{ts}_{hash(text) % 10000:04d}"
        core = adapter._ensure_core()
        core.add_unit(
            text=text[:2000],
            source=source,
            uid=uid,
            space=core.SPACE_RAW_CHAT,
            metadata={"source": source, "saved_at": datetime.now().isoformat(), **(metadata or {})}
        )
        core.save()
        return True
    except Exception:
        return False

def close_memory():

    """关闭 Shalou 连接"""
    global _MEMORY_ADAPTER
    if _MEMORY_ADAPTER: _MEMORY_ADAPTER.close(); _MEMORY_ADAPTER = None


def case_uid(text: str) -> str:
    """case_prototype 稳定 uid：与 core.add_unit 默认 uid 同源（sha256(text)[:16]），保证幂等。"""
    import hashlib
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()[:16]


def write_case_prototype(text, source="case_prototype", metadata=None, uid_seed=None) -> str:
    """沙漏接口协议·写入（B 方案）：叙事经验/验证场景沉淀为 case_prototype 原型单元。
    连续成功(consecutive_success>=3)由 scan_case_prototypes 消费→举一反三迁移申请。
    幂等：同 text 同 uid（INSERT OR REPLACE），重复登记不产生垃圾。"""
    try:
        text = sanitize_text(str(text)[:2000])
        if not text:
            return ""
        core = _get_adapter()._ensure_core()
        uid = case_uid(str(uid_seed or text))
        meta = {"consecutive_success": 0, "total_success": 0, "total_fail": 0,
                "source": str(source)[:40], "created_at": datetime.now().isoformat(),
                **dict(metadata or {})}
        # 幂等登记不吞战绩：同 uid 已存在时沿用连续成功/总成功/总失败等战绩字段（重复登记不重置计数）
        _old_unit = core.get_unit(uid)
        if _old_unit is not None and getattr(_old_unit, "metadata", None):
            _old_meta = dict(_old_unit.metadata or {})
            for _k in ("consecutive_success", "total_success", "total_fail",
                       "last_outcome_at", "last_note", "created_at"):
                if _k in _old_meta:
                    meta[_k] = _old_meta[_k]
        u = core.add_unit(text=text, source=str(source)[:40], uid=uid,
                          space=core.SPACE_CASE_PROTOTYPE, metadata=meta)
        core.save()
        return u.uid
    except Exception:
        return ""


def record_case_outcome(uid, ok=True, note="") -> dict:
    """沙漏接口协议·计数：case_prototype 原型单次执行结果。
    成功 → consecutive_success+1；失败 → 连续成功清零。
    promotable=True 表示达到规则化阈值(3)。"""
    try:
        core = _get_adapter()._ensure_core()
        u = core.get_unit(uid)
        if u is None:
            return {"found": False, "uid": uid}
        m = dict(u.metadata or {})
        if ok:
            m["consecutive_success"] = int(m.get("consecutive_success", 0) or 0) + 1
            m["total_success"] = int(m.get("total_success", 0) or 0) + 1
        else:
            m["consecutive_success"] = 0
            m["total_fail"] = int(m.get("total_fail", 0) or 0) + 1
        m["last_outcome_at"] = datetime.now().isoformat()
        if note:
            m["last_note"] = str(note)[:120]
        core.set_unit_metadata(uid, m)
        core.save()
        return {"found": True, "uid": uid, "ok": bool(ok),
                "consecutive_success": int(m.get("consecutive_success", 0) or 0),
                "total_success": int(m.get("total_success", 0) or 0),
                "total_fail": int(m.get("total_fail", 0) or 0),
                "promotable": int(m.get("consecutive_success", 0) or 0) >= 3}
    except Exception:
        return {"found": False, "uid": uid, "error": True}
