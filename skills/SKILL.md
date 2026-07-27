---
name: mindol
description: Mindol 曼兜 — 三层语义图记忆引擎。n-gram 哈希向量化 + SQLite 持久化，零外部模型依赖。作为迭进（diegin）的长时记忆后端，提供语义检索、多空间记忆管理、迭进桥接。
---

# Mindol 曼兜 — 语义记忆系统

## 概述
Mindol 是一个轻量级语义记忆引擎，基于 n-gram 哈希向量化和 SQLite 持久化。
替代 MemPalace，作为迭进（diegin）的长时记忆后端。

## 核心能力
- **语义记忆**：n-gram 哈希向量化，零外部模型依赖
- **多空间管理**：raw_file / raw_chat / rule / pattern / abstract / trade / codex / state
- **语义检索**：Jaccard + cosine 混合相似度计算
- **Codex 适配**：即插即用集成到 Codex 对话上下文
- **迭进桥接**：与 diegin 引擎无缝配合，提供决策记忆

## 架构
```
Mindol ──→ SQLite (WAL模式) ──→ JSON 副本
  │
  ├─ rule     (200+ 条规则)
  ├─ pattern  (成功模式)
  ├─ trade    (strike + relation)
  ├─ state    (阶段状态)
  └─ codex    (决策归档)
```

## 使用方式
```python
from mindol.core import Mindol
core = Mindol()
core.add_unit(text="...", source="chat", space="codex")
results = core.retrieve("query", top_k=5)
```
