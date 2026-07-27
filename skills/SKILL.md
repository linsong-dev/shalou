---
name: mindol
description: "Mindol 曼兜 — 三层语义图记忆引擎。零外部模型依赖，纯本地运行。独立于任何框架，可嵌入任何 Python 项目。n-gram 哈希向量化 + SQLite 持久化，提供语义检索、多空间记忆管理。"
---

# Mindol 曼兜 — 语义记忆引擎

## 概述
Mindol 是一个**独立运作**的轻量级语义记忆引擎。它不依赖任何外部 API、模型或框架——即插即用，可嵌入任何 Python 项目。

## 核心优特点

| 特点 | 说明 |
|:-----|:------|
| **独立运作** | 不绑定 diegin 或其他系统，单独 import 即可使用 |
| **零外部依赖** | 纯 Python + numpy，无需 GPU、无需 API Key、无需网络 |
| **n-gram 哈希向量化** | **不调用任何 embedding 模型**，SHA256 哈希直接生成向量（~0.01ms/条） |
| **语义检索** | Jaccard + cosine 混合，对中文短文本友好 |
| **多空间管理** | 8 个独立记忆空间（rule/pattern/trade/codex/raw_chat/raw_file/abstract/state） |
| **轻量嵌入** | 核心 <2000 行，pip install numpy 即可跑 |
| **SQLite 持久化** | WAL 模式，线程安全，零配置 |

## 独立使用（不需要 diegin）

```python
# 单独安装
# pip install numpy

from mindol.core import Mindol
core = Mindol()

# 写入记忆
core.add_unit(text="深度学习模型训练需要 GPU", source="chat", space="codex")

# 检索记忆
results = core.retrieve("GPU训练", top_k=5)
for unit, score in results:
    print(f"  [{score:.2f}] {unit.text[:60]}")
```

## 与 diegin 配合（可选）

作为迭进的长时记忆后端，提供决策记忆和规则检索：

```python
from mindol.diegin_integration import memory_archive, memory_search

memory_archive("rule_001", "编码规则: 统一使用 UTF-8 无 BOM")
results = memory_search("编码")
```

## 性能

| 对比项 | Mindol | 传统 embedding |
|:------|:------|:--------------|
| 向量化速度 | ~0.01ms（SHA256 哈希） | 50-200ms（API 调用） |
| 外部依赖 | 零 | OpenAI Key / GPU |
| 可离线 | ✅ | ❌ |
| 单条检索 | ~2ms（numpy dot） | 网络延迟 + API 延迟 |

## 安装

```bash
pip install numpy
```

然后把 `engine/mindol/` 复制到你的项目即可。