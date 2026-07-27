---
name: mindol
description: "Mindol 曼兜 — 基于内存环境的语义记忆引擎。零外部模型依赖，纯本地运行。所有数据加载到内存(numpy)后检索，SQLite 仅用作持久化层。n-gram 哈希向量化 + 多空间管理，独立于任何框架。"
---

# Mindol 曼兜 — 基于内存的语义记忆引擎

## 概述
Mindol 是一个**基于内存环境**的语义记忆引擎。所有记忆加载到内存（numpy 数组）后检索，不涉及磁盘 IO。SQLite 仅作持久化层（启动时加载，关闭时保存），检索走内存。

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
│                 Mindol (内存环境)                   │
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
from mindol.core import Mindol

# 内存模式（不写磁盘）
core = Mindol(persist=False)

# 持久化模式（SQLite 自动加载/保存）
core = Mindol(persist=True)

# 写入记忆 → 存入内存
core.add_unit(text="深度学习训练需要 GPU", source="chat", space="codex")

# 检索记忆 → 内存中 numpy 计算，不查 SQLite
results = core.retrieve("GPU 训练", top_k=5)
for unit, score in results:
    print(f"  [{score:.2f}] {unit.text[:60]}")
```

## 与 diegin 配合（可选）

作为迭进的长时记忆后端，决策记忆和规则检索走 Mindol 内存环境：

```python
from mindol.diegin_integration import memory_archive, memory_search
memory_archive("rule_001", "编码规则: UTF-8 无 BOM")
results = memory_search("编码")  # 走内存检索
```