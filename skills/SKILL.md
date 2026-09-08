---
name: shalou
description: "Shalou · 流动的记忆 — 基于内存环境的语义记忆引擎。零外部模型依赖，纯本地运行。所有数据加载到内存(numpy)后检索，SQLite 仅用作持久化层。n-gram 哈希向量化 + 多空间管理，独立于任何框架。"
---

# Shalou · 流动的记忆 — 基于内存的语义记忆引擎

## 概述
Shalou 是一个**基于内存环境**的语义记忆引擎。所有记忆加载到内存（numpy 数组）后检索，不涉及磁盘 IO。SQLite 仅作持久化层（启动时加载，关闭时保存），检索走内存。

## 定位（v3.9.12）

- Shalou = 通用语义记忆底座，可适配任何智能体（迭进 / 其他框架 / 纯脚本）。
- 独立安装：`pip install -e .`（仓库根含 `pyproject.toml`），或作为独立 Codex 插件安装。
- 迭进接入：迭进运行时依赖本包（非自包含），两者版本前缀必须一致。

## 版本与迭进联动

- 当前版本：`v3.9.12+`（2026-09-06，L1 沙漏流动模型人工受权实施）；Python 包版本见 `pyproject.toml`。
- 迭进×Shalou 版本前缀联动：发布迭进前 checkpush 门禁校验两端插件 `plugin.json` 前缀一致（当前 `3.9.11`）。
- 完整宪法文档：《迭进 · 律令九章》《沙漏 · 流动的记忆》《迭进 · 沙漏统一运维手册》（2026-09-07 封笔终稿，存于迭进仓库 `references/`）。

## 沙漏流动模型（L1 · 翻转/停驻/读写平衡）

迭进第十章持行章按"沙漏侧压系数"做资源降级；本引擎提供配套流动模型（`shalou.flip`）：

- **五类翻转**：自然（写主导）/ 逆向（读主导｜规则沉积）/ 方向（自照镜方向偏离）/ 蓄势 / 主动（用户指令）。
- **360° 停驻**：0° 正放 / 90° 侧放 / 180° 倒放 / 任意角度（`set_angle`）；状态只写入 `flip_state.json`，不动 `memory.db` 两表与既有空间。
- **读写平衡**：`core.add_unit` / `retrieve` 内核打点；写>读→自然翻转、读>写→逆向翻转；沙量失衡/规则沉积/方向漂移触发。
- **原子操作与冷却**：冻结→快照→方向标志→审计（`flip_events.jsonl`）；自动翻转冷却默认 120 分钟。
- 健康接口：`health` 提供健康度与翻转监控（供持行章侧压系数输入）。

## 存储空间（11 空间注册）

文档定义 11 个核心空间（rule / pattern / trade / abstract / goal / case_prototype / anomaly_vault / codex / raw_chat / state / verification）。引擎已在 `core.py` 注册全部常量与别名路由（`codex_adapter` 按 key 前缀归位 goal/anomaly_vault/verification）；空空间仅在首次写入时落库。

## 核心优特点

| 特点 | 说明 |
|:-----|:------|
| **基于内存** | 数据全部加载到 numpy 数组后检索，纯内存计算，~2ms/次 |
| **独立运作** | 不绑定任何框架，单独 import 即可使用 |
| **零外部依赖** | 纯 Python + numpy，无 GPU 无 API Key 无网络 |
| **n-gram 哈希向量化** | 不调用 embedding 模型，SHA256 哈希直接生成向量（~0.01ms） |
| **SQLite 仅做持久化** | WAL 模式，启动时加载、关闭时保存，检索不经过磁盘 |
| **可纯内存运行** | `persist=False` 时完全无文件 IO，适合嵌入式场景 |

## 架构

```
┌──────────────────────────────────────────────────┐
│                 Shalou (内存环境)                   │
│                                                    │
│  memory_units: List[MemoryUnit]  ← 在内存中        │
│  index:       numpy.ndarray     ← 在内存中检索      │
│  retrieve:    numpy dot product ← 纯内存计算        │
│                                                    │
└──────────────────────┬───────────────────────────┘
                       │ 启动时加载 · 关闭时保存
                       ▼
               SQLite (WAL 模式)
               仅做持久化层
```

## 独立使用

```python
# pip install numpy
from shalou.core import Shalou

# 内存模式（不写磁盘）
core = Shalou(persist=False)

# 持久化模式（SQLite 自动加载/保存）
core = Shalou(persist=True)

# 写入记忆 → 存入内存
core.add_unit(text="深度学习训练需要 GPU", source="chat", space="codex")

# 检索记忆 → 内存中 numpy 计算，不查 SQLite
results = core.retrieve("GPU 训练", top_k=5)
for unit, score in results:
    print(f"  [{score:.2f}] {unit.text[:60]}")
```

## 与 diegin 配合（可选）

作为迭进的长时记忆后端，决策记忆和规则检索走 Shalou 内存环境：

```python
from shalou.diegin_integration import memory_archive, memory_search
memory_archive("rule_001", "编码规则: UTF-8 无 BOM")
results = memory_search("编码")  # 走内存检索
```
