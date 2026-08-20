"""mindol.models"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import numpy as np

@dataclass
class MemoryUnit:
    uid: str
    text: str
    source: str
    space: str = ""
    path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    embedding: Optional[np.ndarray] = None
    # 状态动力学四字段（v3.7 增量·最小步）
    # strength: 当前强度（初始按重要性，检索排序 = 相似度 × 强度）
    # status: active / dormant（休眠不参与检索，保留数据）
    # last_accessed / access_count: 使用痕迹（供后续衰减/提取即刷新）
    strength: float = 1.0
    status: str = "active"
    last_accessed: float = 0.0
    access_count: int = 0
    def to_dict(self) -> dict:
        d = asdict(self)
        if self.embedding is not None:
            d["embedding"] = self.embedding.tolist()
        return d

@dataclass
class MemorySpace:
    name: str
    memory_units: List[MemoryUnit] = field(default_factory=list)
    index: Optional[np.ndarray] = None
    uid_to_idx: Dict[str, int] = field(default_factory=dict)
    @property
    def size(self) -> int: return len(self.memory_units)

@dataclass
class SemanticRelation:
    source_uid: str
    target_uid: str
    relation_type: str
    weight: float = 1.0
