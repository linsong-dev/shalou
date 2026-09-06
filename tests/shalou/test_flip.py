# -*- coding: utf-8 -*-
"""L1 沙漏翻转/360度停驻/读写平衡协议（2026-09-06 人工受权实施）"""
import os
import tempfile

import pytest

from shalou import flip as F


@pytest.fixture(autouse=True)
def _restore_params():
    """每个用例后恢复模块参数，防用例间串扰"""
    saved = {k: getattr(F, k) for k in ("MIN_FLIP_INTERVAL_MIN", "RW_FLIP_RATIO", "RW_MIN_OPS", "AUTO_FLIP_DEFAULT")}
    yield
    for k, v in saved.items():
        setattr(F, k, v)


def _dir():
    return tempfile.mkdtemp(prefix="flip_")


def test_write_dominant_triggers_natural_and_state():
    F.MIN_FLIP_INTERVAL_MIN = 0
    F.RW_FLIP_RATIO = 2.0
    d = _dir()
    for _ in range(8):
        F.record_io("write", d)
    ev = F.evaluate(d)
    assert ev["triggered"] is True
    assert ev["flip_type"] == "natural"
    ex = F.execute_flip("natural", storage_dir=d, source="pytest")
    assert ex["ok"] is True
    assert ex["to_angle"] == 180.0
    h = F.health(d)
    assert h["mode"] == "upside_down"
    assert h["flip_count"] == 1
    assert os.path.exists(F.event_path(d))


def test_read_dominant_triggers_reverse():
    F.MIN_FLIP_INTERVAL_MIN = 0
    F.RW_FLIP_RATIO = 2.0
    d = _dir()
    for _ in range(8):
        F.record_io("read", d)
    ev = F.evaluate(d)
    assert ev["triggered"] is True
    assert ev["flip_type"] == "reverse"
    ex = F.execute_flip("reverse", storage_dir=d, source="pytest")
    assert ex["ok"] is True
    assert ex["to_angle"] == 0.0


def test_balance_no_trigger_under_sample_threshold():
    F.MIN_FLIP_INTERVAL_MIN = 0
    d = _dir()
    for _ in range(3):
        F.record_io("read", d)
    ev = F.evaluate(d)
    assert ev["triggered"] is False


def test_cooldown_blocks_frequent_flip():
    d = _dir()
    F.MIN_FLIP_INTERVAL_MIN = 120
    ex1 = F.execute_flip("natural", storage_dir=d, source="pytest")
    assert ex1["ok"] is True
    ex2 = F.execute_flip("reverse", storage_dir=d, source="pytest")
    assert ex2["ok"] is False


def test_arbitrary_angle_parking():
    d = _dir()
    r = F.set_angle(90.0, d, source="pytest")
    assert r["ok"] is True
    assert r["mode"] == "side"
    r2 = F.set_angle(45.0, d, source="pytest")
    assert r2["ok"] is True
    assert r2["mode"] == "arbitrary"
    assert "任意角度" in r2["direction"]["label"]
    r3 = F.set_angle(0.0, d, source="pytest")
    assert r3["ok"] is True
    assert r3["mode"] == "upright"


def test_flow_heartbeat_and_stall_metrics():
    d = _dir()
    F.heartbeat(5, d, has_user_input=True)
    F.record_io("write", d)
    h = F.health(d)
    assert h["angle"] == 0.0
    assert h["stall"] is False
    assert "flow_rate_10min" in h