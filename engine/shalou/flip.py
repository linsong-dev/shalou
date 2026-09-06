# -*- coding: utf-8 -*-
"""shalou.flip - 沙漏翻转 / 360度任意角度停驻 / 读写平衡协议（L1 结构级机制）

权威来源：E:/项目/沙漏 · 流动的记忆.txt §二(翻转机制)/§三.3(读写平衡协议)/§五(翻转状态管理)
落地原则（2026-09-05 L1 流程·人工受权实施）：
- 仅新增运行时方向/停驻状态与协调逻辑；**不动 memory.db 两表结构与既有空间**。
- 读写计数在 Shalou 内核瓶颈(add_unit=写 / retrieve=读)统一打点，反映真实读写频率。
- 翻转 = 沙漏模型方向标志翻转（0度正放 经验->执行 / 180度倒放 执行->经验），
  用于指导运行方向、待机停驻与资源治理；不改变 Shalou 实际存取语义。
- 自动翻转带冷却(默认>=120分钟)+最小样本(8次IO)，防频繁翻转失稳。
- 停驻/任意角度由用户或协调器显式 set_angle；侧放(90度)为待机，由持行章侧压系数治理资源。

状态文件：<shalou存储目录>/flip_state.json；审计日志：<shalou存储目录>/flip_events.jsonl
"""
from __future__ import annotations
import datetime as _dt
import json
import math
import os
import threading

# ── 参数（运维手册/沙漏文档口径；保守默认，防自动动作过频）──────────────────
RW_WINDOW_MIN = 10                 # 读写平衡统计窗口（分钟）
RW_FLIP_RATIO = 2.0                # 读写频率失衡触发阈值（一端 >= 另一端×该值）
RW_MIN_OPS = 8                     # 窗口最小样本数（不足不触发，防抖动）
MIN_FLIP_INTERVAL_MIN = 120        # 两次翻转最小间隔（适中频率：<=12次/天）
STALL_MINUTES = 15                 # 流动停滞判定（分钟无读写）
AUTO_FLIP_DEFAULT = True           # 自动翻转总开关（可用环境变量 SHALOU_FLIP_AUTO=0 关闭）
MODE_BY_ANGLE = {0: "upright", 90: "side", 180: "upside_down"}  # 其余=arbitrary
_STATE_FILE = "flip_state.json"
_EVENT_FILE = "flip_events.jsonl"
_MAX_EVENTS = 64
_MAX_SNAPS = 5
_MAX_HISTORY = 10

_LOCK = threading.Lock()

# 翻转类型 -> (目标角度, 语义, 文档出处)
FLIP_SPEC = {
    "natural":   (180.0, "执行产出累积/写主导 -> 倒放(180度)：沉淀提炼(执行->经验)", "沙漏§2.2自然翻转"),
    "reverse":   (0.0,   "读主导/规则沉积 -> 正放(0度)：经验重新激活到执行(经验->执行)", "沙漏§2.2逆向翻转"),
    "direction": (0.0,   "自照镜方向偏离 -> 方向校准后回到执行调用方向(经验->执行)", "沙漏§2.2方向翻转/§4.2方向漂移"),
    "accumulate":(180.0, "上腔经验累积 -> 倒放：新一轮泛化与精炼(沉淀)", "沙漏§2.2蓄势翻转"),
}


def default_dir() -> str:
    return os.path.join(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")), "shalou")


def state_path(storage_dir: str = "") -> str:
    return os.path.join(storage_dir or default_dir(), _STATE_FILE)


def event_path(storage_dir: str = "") -> str:
    return os.path.join(storage_dir or default_dir(), _EVENT_FILE)


def _now() -> str:
    return _dt.datetime.now().isoformat()


def _ts_float(v) -> float:
    try:
        return _dt.datetime.fromisoformat(str(v)).timestamp()
    except Exception:
        return 0.0


def _load(path, default=None) -> dict:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else (default or {})
    except Exception:
        pass
    return default if isinstance(default, dict) else {}


def _save(path, data) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _append_event(path, ev: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _empty(angle: float = 0.0) -> dict:
    mode = MODE_BY_ANGLE.get(int(angle) if float(angle).is_integer() else -1, "arbitrary")
    if abs(float(angle) - 90.0) < 1e-6:
        mode = "side"
    return {
        "schema": 1,
        "angle": float(angle),
        "mode": mode,
        "direction": direction_text(float(angle)),
        "updated_ts": _now(),
        "auto_flip": AUTO_FLIP_DEFAULT,
        "flow": {"total_read": 0, "total_write": 0,
                 "last_io_ts": "", "last_io_kind": "",
                 "io": []},
        "round": {"last": 0, "user_input_last": 0},
        "flip": {"count": 0, "last": None, "events": []},
        "snapshots": [],
        "cooldown_until_ts": "",
    }


def _get(path: str, storage_dir: str = "") -> dict:
    st = _load(path)
    if not st:
        st = _empty()
        _save(path, st)
    return st


def direction_text(angle: float) -> dict:
    """由角度推导沙漏方向：0=正放(经验->执行)；180=倒放(执行->经验)；90=侧放(读写停驻)；其余=混合。"""
    a = float(angle) % 360.0
    if abs(a) < 1e-6 or abs(a - 360) < 1e-6:
        return {"source": "experience", "sink": "execution", "label": "正放(0度)"}
    if abs(a - 180.0) < 1e-6:
        return {"source": "execution", "sink": "experience", "label": "倒放(180度)"}
    if abs(a - 90.0) < 1e-6:
        return {"source": "", "sink": "", "label": "侧放(90度·读写停驻)"}
    w = round(min(1.0, max(0.0, a / 180.0)), 3)
    return {"source": "mixed", "sink": "mixed", "label": "任意角度(%.0f度)" % a, "write_share": w, "read_share": round(1 - w, 3)}


def record_io(kind: str, storage_dir: str = "") -> bool:
    """读写平衡计数（Shalou 内核瓶颈打点：add_unit=write / retrieve=read）。
    幂等、失败静默；每次操作原子落盘（tiny file + os.replace）。"""
    kind = "read" if str(kind).lower() in ("read", "r") else "write"
    path = state_path(storage_dir)
    try:
        with _LOCK:
            st = _get(path, storage_dir)
            fl = st.setdefault("flow", {})
            key = "total_read" if kind == "read" else "total_write"
            fl[key] = int(fl.get(key, 0) or 0) + 1
            fl["last_io_ts"] = _now()
            fl["last_io_kind"] = kind
            ioq = fl.setdefault("io", [])
            if not isinstance(ioq, list):
                ioq = []
            ioq.append({"ts": _now(), "kind": kind})
            fl["io"] = ioq[-_MAX_EVENTS:]
            st["updated_ts"] = _now()
            _save(path, st)
        return True
    except Exception:
        return False


def _window_counts(ioq, minutes: int = RW_WINDOW_MIN) -> dict:
    """统计最近 minutes 分钟内 读写次数（io 事件环）。"""
    if not isinstance(ioq, list) or not ioq:
        return {"read": 0, "write": 0, "ops": 0, "minutes": 0}
    cutoff = (_dt.datetime.now() - _dt.timedelta(minutes=minutes)).timestamp()
    r = w = 0
    for e in ioq[-_MAX_EVENTS:]:
        try:
            ts = _ts_float(e.get("ts"))
        except Exception:
            continue
        if ts >= cutoff:
            if e.get("kind") == "read":
                r += 1
            else:
                w += 1
    return {"read": r, "write": w, "ops": r + w, "minutes": minutes}


def heartbeat(round_no: int, storage_dir: str = "", has_user_input: bool = False) -> dict:
    """每轮入口打心跳（持行章 ch10_entry 调用）：记录轮次，供停滞判定与翻转冷却。"""
    path = state_path(storage_dir)
    try:
        with _LOCK:
            st = _get(path, storage_dir)
            r = st.setdefault("round", {})
            r["last"] = int(round_no or 0)
            if has_user_input:
                r["user_input_last"] = int(round_no or 0)
            st["updated_ts"] = _now()
            _save(path, st)
            return {"round": r.get("last", 0)}
    except Exception:
        return {}


def set_angle(angle: float, storage_dir: str = "", source: str = "manual",
              reason: str = "") -> dict:
    """360度任意角度停驻/方向设置（显式动作，走审计）。
    angle: 0~360；90=侧放(读写停驻/待机)；0/180/任意角度均合法。"""
    try:
        angle = float(angle)
    except Exception:
        return {"ok": False, "error": "angle 需为数值"}
    if angle < 0 or angle > 360:
        return {"ok": False, "error": "angle 需在 0~360 范围"}
    if angle > 180:
        angle = 360.0 - angle  # 归一化语义角(0..180)；>180 视为反向的 360-a
    path = state_path(storage_dir)
    with _LOCK:
        st = _get(path, storage_dir)
        before = {"angle": st.get("angle", 0.0), "mode": st.get("mode", "upright")}
        st["angle"] = float(angle)
        st["mode"] = MODE_BY_ANGLE.get(int(angle) if float(angle).is_integer() else -1, "arbitrary")
        if abs(float(angle) - 90.0) < 1e-6:
            st["mode"] = "side"
        st["direction"] = direction_text(float(angle))
        st["updated_ts"] = _now()
        _save(path, st)
    ev = {"ts": _now(), "kind": "park_or_set", "source": str(source)[:40],
          "angle": float(angle), "mode": st["mode"],
          "from": before, "reason": str(reason)[:200],
          "note": "沙漏§5.1/§2.4：角度停驻/方向显式设置（L1 授权实施）"}
    _append_event(event_path(storage_dir), ev)
    return {"ok": True, "angle": float(angle), "mode": st["mode"],
            "direction": st["direction"], "event": ev}


def evaluate(storage_dir: str = "", signals: dict = None,
             space_stats: dict = None) -> dict:
    """读写平衡评估：仅在样本充足+冷却已过时才返回触发建议；不自动执行。
    signals: {deposition_warning, direction_deviation, accumulate_hint}
    space_stats: Shalou 各空间条数（用于沙量失衡判断，可选）。"""
    st = _get(state_path(storage_dir), storage_dir)
    fl = st.get("flow", {}) or {}
    ioq = fl.get("io", []) or []
    wc = _window_counts(ioq)
    out = {"triggered": False, "flip_type": None, "reason": "", "window": wc}
    # 冷却检查
    cd = st.get("cooldown_until_ts", "") or ""
    if cd and _dt.datetime.now() < _dt.datetime.fromisoformat(cd):
        out["reason"] = "冷却中（距上次翻转<%.0f分钟）" % MIN_FLIP_INTERVAL_MIN
        return out
    if not (st.get("auto_flip", AUTO_FLIP_DEFAULT)):
        out["reason"] = "自动翻转已关闭(SHALOU_FLIP_AUTO=0)"
        return out
    sig = signals or {}
    # ① 规则沉积 -> 逆向翻转（持行章信号；经验->执行 重新激活）
    if sig.get("deposition_warning"):
        out.update({"triggered": True, "flip_type": "reverse",
                    "reason": "规则沉积警告：被遗忘规则重新激活到当前执行（沙漏§2.2逆向翻转）"})
        return out
    # ② 方向漂移 -> 方向翻转（自照镜信号）
    if sig.get("direction_deviation"):
        out.update({"triggered": True, "flip_type": "direction",
                    "reason": "自照镜方向偏离超阈值：翻转使方向信号重新成为驱动源（沙漏§2.2方向翻转）"})
        return out
    # ③ 经验累积 -> 蓄势翻转（显式上报）
    if sig.get("accumulate_hint"):
        out.update({"triggered": True, "flip_type": "accumulate",
                    "reason": "上腔经验累积达阈值：新一轮泛化与精炼（沙漏§2.2蓄势翻转）"})
        return out
    # ④ 读写频率失衡（沙漏§3.3 读写平衡协议）
    if wc["ops"] >= RW_MIN_OPS:
        if wc["write"] >= wc["read"] * RW_FLIP_RATIO:
            out.update({"triggered": True, "flip_type": "natural",
                        "reason": "写>读×%.1f（近%.0f分钟 写%d/读%d）：执行产出累积 -> 沉淀提炼翻转" % (
                            RW_FLIP_RATIO, wc["minutes"], wc["write"], wc["read"])})
            return out
        if wc["read"] >= wc["write"] * RW_FLIP_RATIO:
            out.update({"triggered": True, "flip_type": "reverse",
                        "reason": "读>写×%.1f（近%.0f分钟 读%d/写%d）：执行调用主导 -> 经验重新激活方向" % (
                            RW_FLIP_RATIO, wc["minutes"], wc["read"], wc["write"])})
            return out
    # ⑤ 沙量失衡（一端 > 另一端 3 倍；可选，需 space_stats）
    if isinstance(space_stats, dict):
        upper = sum(int(space_stats.get(k, 0) or 0) for k in ("rule", "pattern", "abstract", "trade"))
        lower = sum(int(space_stats.get(k, 0) or 0) for k in ("raw_chat", "codex", "case_prototype", "state", "raw_file"))
        if upper > 0 and lower > 0:
            r = upper / max(1, lower)
            if r >= 3.0:
                out.update({"triggered": True, "flip_type": "natural",
                            "reason": "沙量失衡 上腔/下腔=%.1f>=3：平衡两端分布（沙漏§4.2沙量失衡）" % r})
                return out
            if r <= 1.0 / 3.0:
                out.update({"triggered": True, "flip_type": "reverse",
                            "reason": "沙量失衡 下腔/上腔=%.1f>=3：平衡两端分布（沙漏§4.2沙量失衡）" % (1.0 / max(0.01, r))})
                return out
    out["reason"] = "读写频率平衡/样本不足（近%.0f分钟 读%d 写%d）" % (wc["minutes"], wc["read"], wc["write"])
    return out


def execute_flip(flip_type: str, storage_dir: str = "", reason: str = "",
                 source: str = "auto") -> dict:
    """翻转原子操作（沙漏§5.3）：冻结->快照->更新方向标志->恢复->审计。
    原子性：单进程锁 + JSON 临时文件 os.replace 原子替换；不触发跨库事务（无表结构改动）。"""
    if flip_type not in FLIP_SPEC:
        return {"ok": False, "error": "未知翻转类型: %s" % flip_type}
    target_angle, spec_txt, _src = FLIP_SPEC[flip_type]
    path = state_path(storage_dir)
    with _LOCK:
        st = _get(path, storage_dir)
        # 冷却二次校验（并发安全）
        cd = st.get("cooldown_until_ts", "") or ""
        if cd and _dt.datetime.now() < _dt.datetime.fromisoformat(cd):
            return {"ok": False, "error": "冷却中", "cooldown_until": cd}
        from_angle = float(st.get("angle", 0.0) or 0.0)
        from_mode = st.get("mode", "upright")
        # ① 冻结 + ② 保存快照（原子操作第 1-2 步）
        snaps = st.setdefault("snapshots", [])
        if not isinstance(snaps, list):
            snaps = []
        fl = st.get("flow", {}) or {}
        snaps.append({"ts": _now(), "from_angle": from_angle, "from_mode": from_mode,
                      "total_read": int(fl.get("total_read", 0) or 0),
                      "total_write": int(fl.get("total_write", 0) or 0)})
        st["snapshots"] = snaps[-_MAX_SNAPS:]
        # ③ 更新方向标志
        st["angle"] = target_angle
        st["mode"] = MODE_BY_ANGLE.get(int(target_angle), "arbitrary") if float(target_angle).is_integer() else "arbitrary"
        st["direction"] = direction_text(target_angle)
        st["cooldown_until_ts"] = (_dt.datetime.now() + _dt.timedelta(minutes=MIN_FLIP_INTERVAL_MIN)).isoformat()
        st["updated_ts"] = _now()
        fcnt = int(st.get("flip", {}).get("count", 0) or 0) + 1
        fev = {"ts": _now(), "type": flip_type, "from_angle": from_angle, "to_angle": target_angle,
               "from_mode": from_mode, "to_mode": st["mode"], "reason": str(reason or spec_txt)[:200],
               "source": str(source)[:40], "count": fcnt,
               "spec": spec_txt, "doc": _src,
               "first_round": ["检查新方向下待处理规则/模式/信号（沙漏§5.4）",
                               "有则按新方向优先级处理；无则触发自照镜轻量校准生成方向信号"]}
        fp = st.setdefault("flip", {})
        hist = fp.setdefault("events", [])
        if not isinstance(hist, list):
            hist = []
        hist.append(fev)
        fp["events"] = hist[-_MAX_HISTORY:]
        fp["count"] = fcnt
        fp["last"] = fev
        _save(path, st)
    _append_event(event_path(storage_dir), {"kind": "flip", **fev})
    return {"ok": True, **fev}


def maybe_flip(storage_dir: str = "", signals: dict = None,
               space_stats: dict = None, reason_override: str = "") -> dict:
    """协调器每轮入口：evaluate -> execute（带冷却/最小样本门）；无触发返回 {"ok": False}。"""
    ev = evaluate(storage_dir, signals=signals, space_stats=space_stats)
    if not ev.get("triggered"):
        return {"ok": False, "flip_type": None, "reason": ev.get("reason", "")}
    res = execute_flip(ev["flip_type"], storage_dir=storage_dir,
                       reason=reason_override or ev.get("reason", ""), source="auto_coordinator")
    return {"ok": bool(res.get("ok")), "flip_type": ev["flip_type"], "event": res}


def health(storage_dir: str = "", space_stats: dict = None) -> dict:
    """沙漏健康检查/翻转监控（运维接口，沙漏§7）：流动速率/翻转频率/两端分布/方向状态。"""
    st = _get(state_path(storage_dir), storage_dir)
    fl = st.get("flow", {}) or {}
    ioq = fl.get("io", []) or []
    wc = _window_counts(ioq, minutes=10)
    fp = st.get("flip", {}) or {}
    last = fp.get("last") or {}
    now = _dt.datetime.now()
    flip_24h = 0
    for e in (fp.get("events") or [])[-_MAX_HISTORY:]:
        try:
            if (now - _dt.datetime.fromisoformat(e.get("ts", ""))).total_seconds() <= 86400:
                flip_24h += 1
        except Exception:
            pass
    last_io = fl.get("last_io_ts", "") or ""
    stall = False
    if last_io:
        try:
            stall = (now - _dt.datetime.fromisoformat(last_io)).total_seconds() / 60 >= STALL_MINUTES
        except Exception:
            pass
    upper = lower = 0
    if isinstance(space_stats, dict):
        upper = sum(int(space_stats.get(k, 0) or 0) for k in ("rule", "pattern", "abstract", "trade"))
        lower = sum(int(space_stats.get(k, 0) or 0) for k in ("raw_chat", "codex", "case_prototype", "state", "raw_file"))
    dist = "n/a"
    if upper > 0 and lower > 0:
        dist = "%.2f" % (upper / max(1, lower))
    return {
        "principle": "持存·沙漏流动模型",
        "angle": st.get("angle", 0.0),
        "mode": st.get("mode", "upright"),
        "direction": st.get("direction", {}),
        "flow_rate_10min": {"read": wc["read"], "write": wc["write"], "total": wc["ops"]},
        "total_io": {"read": int(fl.get("total_read", 0) or 0), "write": int(fl.get("total_write", 0) or 0)},
        "stall": stall,
        "flip_count": int(fp.get("count", 0) or 0),
        "flip_last_24h": flip_24h,
        "flip_last": last,
        "sand_ratio_upper_lower": dist,
        "cooldown_until_ts": st.get("cooldown_until_ts", "") or "",
        "auto_flip": bool(st.get("auto_flip", AUTO_FLIP_DEFAULT)),
        "note": "翻转频率适中；沙量失衡阈值>=3（沙漏§7.1）；侧放(90度)资源治理由持行章侧压系数执行",
    }