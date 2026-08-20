"""mindol.core — Mindol 曼兜 语义记忆引擎（替代 MemPalace）"""
from __future__ import annotations
import json, os, re, sqlite3, threading, time, hashlib, math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from .vectorizer import SimpleVectorizer
from .models import MemoryUnit, MemorySpace, SemanticRelation

class Mindol:
    """Mindol 曼兜 - 三层语义记忆引擎"""
    SPACE_RAW_FILE = "raw_file"
    SPACE_RAW_CHAT = "raw_chat"
    SPACE_RULE = "rule"
    SPACE_PATTERN = "pattern"
    SPACE_ABSTRACT = "abstract"
    SPACE_TRADE = "trade"
    SPACE_CODEX = "codex"
    SPACE_STATE = "state"
    STRENGTH_MAX = 1.0
    BOOST_REFRESH = 0.05
    # v3.7.2 记忆代谢：仅经验类空间衰减（对话/模式/抽象），权威空间豁免
    DECAY_SPACES = (SPACE_RAW_CHAT, SPACE_CODEX, SPACE_PATTERN, SPACE_ABSTRACT)
    DECAY_RATE_DAILY = 0.02
    DORMANCY_THRESHOLD = 0.1

    def __init__(self, storage_path: str = "", vectorizer: Any = None,
                 persist: bool = True, text_clean: bool = True):
        self._storage_path = storage_path or os.path.join(
            os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")), "mindol"
        )
        self._vectorizer = vectorizer or SimpleVectorizer(dim=256)
        self._lock = threading.Lock()
        self._text_clean = text_clean
        self._clean_re = re.compile(
            "[\U0001F300-\U0010FFFF\u2700-\u27BF\u2600-\u26FF\uFE00-\uFE0F]"
        ) if text_clean else None
        self._spaces: Dict[str, MemorySpace] = {}
        for name in [self.SPACE_RAW_FILE, self.SPACE_RAW_CHAT, self.SPACE_RULE,
                     self.SPACE_PATTERN, self.SPACE_ABSTRACT, self.SPACE_TRADE, self.SPACE_CODEX, self.SPACE_STATE]:
            self._spaces[name] = MemorySpace(name=name)
        self._relations: List[SemanticRelation] = []
        self._relation_index: Dict[str, List[int]] = {}
        # [PERF-D 2026-08-20] 情绪调制：mood ∈ [-1, +1]，中性 0。
        # 正值=勇气/进取（courage 注入），负值=保守/收缩；检索时调制空间权重。
        self._mood: float = 0.0
        self._mood_source: str = ""
        self._db: Optional[sqlite3.Connection] = None
        if persist:
            self._init_persistence()
            self._load()

    def _init_persistence(self):
        os.makedirs(self._storage_path, exist_ok=True)
        db_path = os.path.join(self._storage_path, "memory.db")
        self._db = sqlite3.connect(db_path, check_same_thread=False, timeout=10.0)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS memory_units (uid TEXT PRIMARY KEY, space TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, path TEXT DEFAULT '', metadata TEXT DEFAULT '{}', timestamp REAL DEFAULT 0, embedding BLOB, strength REAL DEFAULT 1.0, status TEXT DEFAULT 'active', last_accessed REAL DEFAULT 0, access_count INTEGER DEFAULT 0)")
        # v3.7 增量·最小步：老库平滑迁移（加列带默认，零行为变化）
        _cols = {r[1] for r in self._db.execute("PRAGMA table_info(memory_units)").fetchall()}
        for _col, _ddl in (("strength", "REAL DEFAULT 1.0"), ("status", "TEXT DEFAULT 'active'"),
                           ("last_accessed", "REAL DEFAULT 0"), ("access_count", "INTEGER DEFAULT 0")):
            if _col not in _cols:
                self._db.execute("ALTER TABLE memory_units ADD COLUMN %s %s" % (_col, _ddl))
        self._db.execute("UPDATE memory_units SET last_accessed = timestamp WHERE last_accessed = 0 AND timestamp > 0")
        self._db.execute("CREATE TABLE IF NOT EXISTS relations (source_uid TEXT NOT NULL, target_uid TEXT NOT NULL, relation_type TEXT NOT NULL, weight REAL DEFAULT 1.0, PRIMARY KEY (source_uid, target_uid, relation_type))")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_uid)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_units_space ON memory_units(space)")
        self._db.commit()

    def add_unit(self, text: str, source: str, uid: str = "",
                 space: str = "", path: str = "", metadata: Dict = None) -> MemoryUnit:
        with self._lock:
            if self._text_clean: text = self._clean_re.sub("", text)
            if not uid: uid = hashlib.sha256(text.encode()).hexdigest()[:16]
            if not space: space = self._classify_space(source)
            vec = self._vectorizer.embed(text)
            meta = metadata or {}
            imp = float(meta.get("importance", 1.0))
            now = time.time()
            unit = MemoryUnit(uid=uid, text=text, source=source, space=space, path=path,
                              metadata=meta, timestamp=now, embedding=vec,
                              strength=max(0.1, min(1.0, 0.5 + 0.5 * imp)),
                              status="active", last_accessed=now, access_count=0)
            sp = self._spaces[space]
            if uid in sp.uid_to_idx:
                sp.memory_units[sp.uid_to_idx[uid]] = unit
            else:
                sp.uid_to_idx[uid] = len(sp.memory_units)
                sp.memory_units.append(unit)
            self._rebuild_index(space)
            if self._db: self._persist_unit(unit, space)
            return unit

    def add_relation(self, source_uid: str, target_uid: str, rel_type: str, weight: float = 1.0):
        with self._lock:
            rel = SemanticRelation(source_uid, target_uid, rel_type, weight)
            self._relations.append(rel)
            self._relation_index.setdefault(source_uid, []).append(len(self._relations) - 1)
            self._relation_index.setdefault(target_uid, []).append(len(self._relations) - 1)
            if self._db:
                _rel_sql = "INSERT OR REPLACE INTO relations VALUES (?,?,?,?)"
                self._db.execute(_rel_sql,
                                 (source_uid, target_uid, rel_type, weight))

    def _classify_space(self, source: str) -> str:
        return {"rule": self.SPACE_RULE, "pattern": self.SPACE_PATTERN, "trade": self.SPACE_TRADE,
                "chat": self.SPACE_RAW_CHAT, "abstract": self.SPACE_ABSTRACT, "codex": self.SPACE_CODEX, "state": self.SPACE_STATE
                }.get(source, self.SPACE_RAW_FILE)

    def _rebuild_index(self, space: str):
        sp = self._spaces[space]
        if not sp.memory_units: sp.index = None; return
        embs = [u.embedding for u in sp.memory_units if u.embedding is not None]
        sp.index = np.stack(embs) if embs else None

    def _persist_unit(self, unit: MemoryUnit, space: str):
        # 性能优化 v3.6.6: 去掉逐条 commit（每条 ~30ms），由 save()/close() 统一 commit
        emb = unit.embedding.tobytes() if unit.embedding is not None else b""
        _mem_sql = ("INSERT OR REPLACE INTO memory_units "
                    "(uid, space, text, source, path, metadata, timestamp, embedding, strength, status, last_accessed, access_count) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)")
        self._db.execute(_mem_sql,
                         (unit.uid, space, unit.text, unit.source, unit.path,
                          json.dumps(unit.metadata, ensure_ascii=False), unit.timestamp, emb,
                          unit.strength, unit.status, unit.last_accessed, unit.access_count))

    def retrieve(self, query: str, top_k: int = 10, spaces: List[str] = None) -> List[Tuple[MemoryUnit, float]]:
        qvec = self._vectorizer.embed(query)
        candidates = []
        target_spaces = spaces or list(self._spaces.keys())
        sw = {"trade": 1.3, "rule": 1.15, "pattern": 1.1, "codex": 1.0,
              "raw_chat": 1.0, "raw_file": 1.0, "abstract": 1.0}
        qterms = set(re.findall(r"[\w]+", query.lower()))
        stop_words = {"de", "le", "shi", "zai", "you", "he", "jiu", "bu", "ren",
                      "dou", "yi", "shang", "ye", "hen", "dao"}
        qterms = {t for t in qterms if t not in stop_words and len(t) >= 2}
        for sn in target_spaces:
            sp = self._spaces.get(sn)
            if sp is None or sp.index is None or sp.size == 0: continue
            sims = sp.index @ qvec
            w = sw.get(sn, 1.0)
            # [PERF-D] 情绪调制：courage 高→进取空间权重上调（trade/pattern/abstract），rule 下调
            _mw = self._mood_weights().get(sn, 1.0)
            w = w * _mw
            # v3.6: 性能修复——calc_similarity 只对 top 候选窗口增强（原来全量逐条计算导致检索 2.5s+）
            if self._vectorizer and hasattr(self._vectorizer, "calc_similarity"):
                win = min(len(sp.memory_units), max(top_k * 8, 16))
                if win < len(sp.memory_units):
                    idx_top = np.argpartition(-sims, win)[:win]
                else:
                    idx_top = np.arange(len(sp.memory_units))
                kb = np.zeros(len(sp.memory_units), dtype=np.float32)
                for i in idx_top:
                    jsim = self._vectorizer.calc_similarity(query, sp.memory_units[i].text)
                    if jsim > 0.1:
                        kb[i] = 0.3 * jsim
                sims = sims + kb
            elif qterms:
                kb = np.zeros(len(sp.memory_units), dtype=np.float32)
                for i, u in enumerate(sp.memory_units):
                    hits = sum(1 for t in qterms if t in u.text.lower())
                    if hits: kb[i] = 0.1 * hits
                sims = sims + kb
            if len(sims) <= top_k:
                indices = np.argsort(-sims)
            else:
                indices = np.argpartition(-sims, top_k)[:top_k]
                indices = indices[np.argsort(-sims[indices])]
            for idx in indices:
                u = sp.memory_units[idx]
                if u.status == "dormant": continue
                score = float(sims[idx]) * w * u.strength
                if score > 0: candidates.append((u, score))
        ext = self._relation_extend(candidates, top_k)
        candidates.extend(ext)
        pri = {"trade": 0, "pattern": 1, "rule": 2, "codex": 3, "raw_chat": 3, "raw_file": 3, "abstract": 4}
        seen = set(); results = []
        for u, s in sorted(candidates, key=lambda x: (-x[1], pri.get(x[0].space, 5))):
            if u.uid not in seen:
                seen.add(u.uid); results.append((u, s))
            if len(results) >= top_k * 3: break
        results = results[:top_k]
        # 提取即刷新（v3.7.1）：命中即记录使用痕迹 + 强度小幅提升（上限对齐初始化 1.0）
        if self._db and results:
            now = time.time()
            for u, _ in results:
                u.last_accessed = now
                u.access_count += 1
                u.strength = min(self.STRENGTH_MAX, u.strength + self.BOOST_REFRESH)
                self._db.execute("UPDATE memory_units SET strength=?, last_accessed=?, access_count=? WHERE uid=?",
                                 (u.strength, now, u.access_count, u.uid))
        return results

    def _relation_extend(self, candidates, top_k):
        ext = []
        seen = {u.uid for u, _ in candidates}
        for u, s in candidates:
            for ri in self._relation_index.get(u.uid, []):
                rel = self._relations[ri]
                oid = rel.target_uid if rel.source_uid == u.uid else rel.source_uid
                if oid in seen: continue
                for sn, sp in self._spaces.items():
                    oidx = sp.uid_to_idx.get(oid)
                    if oidx is not None:
                        ou = sp.memory_units[oidx]
                        if ou.status == "dormant": break
                        ext.append((ou, s * rel.weight * 0.7 * ou.strength))
                        seen.add(oid); break
        return ext

    def get_space(self, name): return self._spaces.get(name)
    def get_unit(self, uid):
        for sp in self._spaces.values():
            idx = sp.uid_to_idx.get(uid)
            if idx is not None: return sp.memory_units[idx]
        return None
    def space_stats(self): return {n: sp.size for n, sp in self._spaces.items()}

    def remove_unit(self, uid):
        with self._lock:
            for sn, sp in self._spaces.items():
                if uid in sp.uid_to_idx:
                    idx = sp.uid_to_idx.pop(uid)
                    sp.memory_units.pop(idx)
                    sp.uid_to_idx = {u.uid: i for i, u in enumerate(sp.memory_units)}
                    self._rebuild_index(sn)
                    if self._db:
                        self._db.execute("DELETE FROM memory_units WHERE uid=?", (uid,))
        self._db.commit()
        return True

    # ── 情绪调制（v3.8 / PERF-D）──────────────────────────────
    def set_mood(self, val: float, source: str = "") -> float:
        """设置全局情绪标量 [-1, +1]（自照镜勇气信号注入）。"""
        try:
            self._mood = max(-1.0, min(1.0, float(val)))
        except Exception:
            self._mood = 0.0
        self._mood_source = source or self._mood_source
        return self._mood

    def get_mood(self) -> Dict[str, float]:
        return {"mood": self._mood, "source": self._mood_source}

    def _mood_weights(self) -> Dict[str, float]:
        """情绪调制空间检索权重：courage 高→进取空间(trade/pattern/abstract)上调，
        rule 下调；courage 低/负→保守空间(rule)上调。幅度 ±15%。"""
        _m = self._mood
        return {
            self.SPACE_TRADE: 1.0 + 0.15 * _m,
            self.SPACE_PATTERN: 1.0 + 0.12 * _m,
            self.SPACE_ABSTRACT: 1.0 + 0.10 * _m,
            self.SPACE_RULE: 1.0 - 0.10 * _m,
            self.SPACE_RAW_CHAT: 1.0 + 0.03 * _m,
            self.SPACE_CODEX: 1.0,
            self.SPACE_RAW_FILE: 1.0,
            self.SPACE_STATE: 1.0,
        }

    def associate(self, query: str, top_k: int = 3) -> List[Dict]:
        """跨空间联想（PERF-D）：取各进取空间 top 候选，两两拼接产出
        「组合候选」——模拟不精确但有创造性的重组（零外部模型）。"""
        if not query.strip():
            return []
        _spaces = [self.SPACE_TRADE, self.SPACE_PATTERN, self.SPACE_ABSTRACT]
        _picks = {}
        for _sp in _spaces:
            _res = self.retrieve(query, top_k=2, spaces=[_sp])
            _picks[_sp] = [u.text[:120] for u, _ in _res]
        out = []
        _t = _picks.get(self.SPACE_TRADE, [])
        _p = _picks.get(self.SPACE_PATTERN, [])
        _a = _picks.get(self.SPACE_ABSTRACT, [])
        for _x in _t[:1]:
            for _y in (_p + _a)[:2]:
                out.append({"text": f"[联想] {_x} ⊕ {_y}", "space": "associate"})
        for _x in _p[:1]:
            for _y in _a[:1]:
                out.append({"text": f"[联想] {_x} ⊕ {_y}", "space": "associate"})
        return out[:top_k]

    
    def decay_and_dormancy(self, now=None, decay_rate=DECAY_RATE_DAILY,
                           dormancy_threshold=DORMANCY_THRESHOLD) -> dict:
        """记忆代谢（v3.7.2）：经验类空间按 last_accessed 时间衰减，低于阈值置 dormant。

        设计要点：
        - 只作用于 DECAY_SPACES（raw_chat/codex/pattern/abstract）——对话/行为/模式属经验，允许自然代谢；
          rule/trade/state 为权威/纪律内容，豁免衰减。
        - 强度公式：strength = strength * exp(-decay_rate * Δ天)，与提取即刷新（+0.05）形成涨跌平衡。
        - 休眠非删除：status=dormant 保留数据、不参与检索；幂等——dormant 单元不再衰减，重复调用无副作用。
        - 返回统计 {decayed, dormant, skipped}。
        """
        if not self._db:
            return {"decayed": 0, "dormant": 0, "skipped": 0}
        now = now if now is not None else time.time()
        stats = {"decayed": 0, "dormant": 0, "skipped": 0}
        with self._lock:
            updates = []
            for sn, sp in self._spaces.items():
                if sn not in self.DECAY_SPACES:
                    continue
                for u in sp.memory_units:
                    if u.status == "dormant":
                        stats["skipped"] += 1
                        continue
                    ref_ts = u.last_accessed or u.timestamp or now
                    dt_days = max(0.0, (now - ref_ts) / 86400.0)
                    if dt_days <= 0.0:
                        continue
                    new_s = u.strength * math.exp(-decay_rate * dt_days)
                    u.strength = new_s
                    if new_s < dormancy_threshold:
                        u.status = "dormant"
                        stats["dormant"] += 1
                    else:
                        stats["decayed"] += 1
                    updates.append((u.strength, u.status, u.uid))
            if updates:
                self._db.executemany(
                    "UPDATE memory_units SET strength=?, status=? WHERE uid=?", updates)
                self._db.commit()
        return stats

    def flush(self):
        """轻量提交：仅 commit 当前未提交事务（权威存储必须即时落盘，防止进程退出丢失）"""
        if not self._db:
            return
        with self._lock:
            try:
                self._db.commit()
            except Exception:
                pass

    def save(self):
        """提交未提交事务（增量持久化）。
        所有单元/关系已在 add_unit/add_relation/remove_unit 时即时 INSERT/DELETE，
        此处仅 commit 落盘——不再全量遍历重写（防每次对话 O(N) 重写 SQLite）。
        """
        if not self._db: return
        with self._lock:
            try:
                self._db.commit()
            except Exception:
                pass

    def _load(self):
        if not self._db: return
        try:
            for row in self._db.execute("SELECT uid, space, text, source, path, metadata, timestamp, embedding, strength, status, last_accessed, access_count FROM memory_units").fetchall():
                uid, space, text, source, path, mj, ts, emb, strength, status, last_accessed, access_count = row
                meta = json.loads(mj) if mj else {}
                vec = np.frombuffer(emb, dtype=np.float32) if emb else None
                u = MemoryUnit(uid=uid, text=text, source=source, space=space, path=path,
                               metadata=meta, timestamp=ts or 0.0, embedding=vec,
                               strength=float(strength) if strength is not None else 1.0,
                               status=status or "active",
                               last_accessed=float(last_accessed) if last_accessed else (ts or 0.0),
                               access_count=int(access_count) if access_count else 0)
                sp = self._spaces.get(space)
                if sp is not None:
                    sp.uid_to_idx[uid] = len(sp.memory_units); sp.memory_units.append(u)
            for sn in self._spaces: self._rebuild_index(sn)
            for r in self._db.execute("SELECT source_uid, target_uid, relation_type, weight FROM relations").fetchall():
                self._relations.append(SemanticRelation(*r))
                self._relation_index.setdefault(r[0], []).append(len(self._relations)-1)
                self._relation_index.setdefault(r[1], []).append(len(self._relations)-1)
        except Exception as e:
            # 静默加载告警：禁止向 stdout/stderr 输出，防止污染钩子 JSON 管道
            try:
                with open(os.path.join(self._storage_path, "load_warnings.log"), "a", encoding="utf-8") as _f:
                    _f.write(f"{time.time()} [Mindol] Load warning: {e}\n")
            except Exception:
                pass

    def close(self):
        if self._db: self.save(); self._db.close(); self._db = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()
