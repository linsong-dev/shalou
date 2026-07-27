"""Tests for mindol core modules"""
import os, sys, numpy as np

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_TEST_DIR, "..", "..", "engine")))

from mindol.vectorizer import SimpleVectorizer
from mindol.models import MemoryUnit, MemorySpace, SemanticRelation
from mindol.core import Mindol
from mindol.codex_adapter import CodexMemoryAdapter
from mindol.diegin_integration import memory_search, memory_archive, get_memory_stats, close_memory

_DB = os.path.join(_TEST_DIR, "_test_db")

def clean():
    for f in ["memory.db", "memory.db-wal", "memory.db-shm"]:
        p = os.path.join(_DB, f)
        if os.path.exists(p): os.remove(p)

def test_vectorizer():
    v = SimpleVectorizer()
    v1 = v.embed("hello world")
    v2 = v.embed("hello world again")
    v3 = v.embed("")
    assert v1.shape == (256,)
    assert v.embedding_dim() == 256
    assert abs(np.linalg.norm(v1) - 1.0) < 0.001
    assert np.linalg.norm(v3) == 0
    assert float(v1 @ v2) > 0.5
    print("  [PASS] vectorizer")

def test_models():
    mu = MemoryUnit(uid="t1", text="test", source="chat")
    assert mu.to_dict()["uid"] == "t1"
    ms = MemorySpace(name="test")
    assert ms.size == 0
    sr = SemanticRelation("a", "b", "similar", 0.8)
    assert sr.weight == 0.8
    print("  [PASS] models")

def test_core():
    clean()
    core = Mindol(storage_path=_DB, persist=False)
    assert len(core.space_stats()) == 8
    assert "codex" in core.space_stats()
    u1 = core.add_unit(text="test data 123", source="chat", uid="t1", space="codex")
    assert core.get_unit("t1") is not None
    r = core.retrieve("test", top_k=3)
    assert len(r) >= 1
    core.close()
    print("  [PASS] core lifecycle")

def test_persistence():
    clean()
    core = Mindol(storage_path=_DB, persist=True)
    core.add_unit(text="persist test", source="chat", uid="p1", space="codex")
    core.save(); core.close()
    core2 = Mindol(storage_path=_DB, persist=True)
    assert core2.get_unit("p1") is not None
    core2.close(); clean()
    print("  [PASS] persistence")

def test_adapter():
    clean()
    mem = CodexMemoryAdapter(storage_path=_DB)
    uid = mem.save_context("adapter test content", source="chat", space="codex")
    assert uid is not None
    r = mem.search("test", top_k=5)
    assert len(r) >= 1
    ok = mem.archive("test_key", "archive content")
    assert ok == True
    mem.close(); clean()
    print("  [PASS] codex adapter")

def test_integration():
    clean()
    ok = memory_archive("rule_001", "integration test", {"source": "test"})
    assert ok == True
    r = memory_search("integration", max_results=3)
    assert len(r) >= 1
    stats = get_memory_stats()
    assert isinstance(stats, dict)
    close_memory()
    print("  [PASS] diegin integration")

if __name__ == "__main__":
    print("=== Mindol Test Suite ===\n")
    for fn in [test_vectorizer, test_models, test_core, test_persistence, test_adapter, test_integration]:
        fn()
    print("\n=== ALL TESTS PASSED ===")
    clean()
