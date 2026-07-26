"""mindol.core — Mindol 曼兜 语义记忆引擎（替代 MemPalace）"""
from __future__ import annotations
import json, os, re, sqlite3, threading, time, hashlib
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
        self._db: Optional[sqlite3.Connection] = None
        if persist:
            self._init_persistence()
            self._load()

    def _init_persistence(self):
        os.makedirs(self._storage_path, exist_ok=True)
        db_path = os.path.join(self._storage_path, "memory.db")
        self._db = sqlite3.connect(db_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS memory_units (uid TEXT PRIMARY KEY, space TEXT NOT NULL, text TEXT NOT NULL, source TEXT NOT NULL, path TEXT DEFAULT '', metadata TEXT DEFAULT '{}', timestamp REAL DEFAULT 0, embedding BLOB)")
        self._db.execute("CREATE TABLE IF NOT EXISTS relations (source_uid TEXT NOT NULL, target_uid TEXT NOT NULL, relation_type TEXT NOT NULL, weight REAL DEFAULT 1.0, PRIMARY KEY (source_uid, target_uid, relation_type))")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_uid)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_units_space ON memory_units(space)")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.commit()

    def add_unit(self, text: str, source: str, uid: str = "",
                 space: str = "", path: str = "", metadata: Dict = None) -> MemoryUnit:
        with self._lock:
            if self._text_clean: text = self._clean_re.sub("", text)
            if not uid: uid = hashlib.sha256(text.encode()).hexdigest()[:16]
            if not space: space = self._classify_space(source)
            vec = self._vectorizer.embed(text)
            unit = MemoryUnit(uid=uid, text=text, source=source, space=space, path=path,
                              metadata=metadata or {}, timestamp=time.time(), embedding=vec)
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
                self._db.commit()

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
        emb = unit.embedding.tobytes() if unit.embedding is not None else b""
        _mem_sql = "INSERT OR REPLACE INTO memory_units VALUES (?,?,?,?,?,?,?,?)"
        self._db.execute(_mem_sql,
                         (unit.uid, space, unit.text, unit.source, unit.path,
                          json.dumps(unit.metadata, ensure_ascii=False), unit.timestamp, emb))
        self._db.commit()

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
            if self._vectorizer and hasattr(self._vectorizer, "calc_similarity"):
                kb = np.zeros(len(sp.memory_units), dtype=np.float32)
                for i, u in enumerate(sp.memory_units):
                    jsim = self._vectorizer.calc_similarity(query, u.text)
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
                score = float(sims[idx]) * w
                if score > 0: candidates.append((sp.memory_units[idx], score))
        ext = self._relation_extend(candidates, top_k)
        candidates.extend(ext)
        pri = {"trade": 0, "pattern": 1, "rule": 2, "codex": 3, "raw_chat": 3, "raw_file": 3, "abstract": 4}
        seen = set(); results = []
        for u, s in sorted(candidates, key=lambda x: (-x[1], pri.get(x[0].space, 5))):
            if u.uid not in seen:
                seen.add(u.uid); results.append((u, s))
            if len(results) >= top_k * 3: break
        return results[:top_k]

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
                        ext.append((sp.memory_units[oidx], s * rel.weight * 0.7))
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
            return False

    def save(self):
        if not self._db: return
        with self._lock:
            for sn, sp in self._spaces.items():
                for u in sp.memory_units: self._persist_unit(u, sn)
            self._db.commit()

    def _load(self):
        if not self._db: return
        try:
            for row in self._db.execute("SELECT uid, space, text, source, path, metadata, timestamp, embedding FROM memory_units").fetchall():
                uid, space, text, source, path, mj, ts, emb = row
                meta = json.loads(mj) if mj else {}
                vec = np.frombuffer(emb, dtype=np.float32) if emb else None
                u = MemoryUnit(uid=uid, text=text, source=source, space=space, path=path,
                               metadata=meta, timestamp=ts or 0.0, embedding=vec)
                sp = self._spaces.get(space)
                if sp is not None:
                    sp.uid_to_idx[uid] = len(sp.memory_units); sp.memory_units.append(u)
            for sn in self._spaces: self._rebuild_index(sn)
            for r in self._db.execute("SELECT source_uid, target_uid, relation_type, weight FROM relations").fetchall():
                self._relations.append(SemanticRelation(*r))
                self._relation_index.setdefault(r[0], []).append(len(self._relations)-1)
                self._relation_index.setdefault(r[1], []).append(len(self._relations)-1)
        except Exception as e:
            print(f"[Mindol] Load warning: {e}")

    def close(self):
        if self._db: self.save(); self._db.close(); self._db = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


