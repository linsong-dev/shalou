---
name: "mindol"
description: |
  Mindol 曼兜 — 语义记忆引擎组件库（静默后端）。
  定位：非主动技能，而是作为迭进（diegin）的长时记忆后端自动工作。
  零外部模型依赖，n-gram 哈希向量化 + SQLite 持久化。
  提供语义检索、多空间记忆管理、语义关系网络。
  可通过桥接自动服务每轮对话，也可单独作为 Python 库使用。
author: "林松"
repository: "https://github.com/linsong-dev/mindol.git"
metadata:
  version: "1.0.0"
  date: "2026-07-10"
---

## 一、概述

Mindol 曼兜 是一个轻量级语义记忆引擎，基于 n-gram 哈希向量化和 SQLite 持久化。

### 🎯 定位

| 角色 | 说明 |
|:-----|:-----|
| **本质** | **记忆引擎组件库**，非主动激活技能 |
| **默认方式** | 通过迭进（diegin）自动接入每轮对话 — 对用户透明 |
| **独立使用** | `from mindol import Mindol` 直接调用 |
| **UI 中可见** | 是，但需知悉：它是静默后端，不主动激活 |

> ⚡ 在 UI 插件列表中可见"Mindol 曼兜"条目，但其角色是**引擎组件**而非主动技能。
> 就像一辆车的发动机 — 你不需要主动操作它，它自动工作。

### 核心特点同前
- **零外部模型依赖** — 无需 LLM / HuggingFace / ONNX，纯 Python + numpy
- **三层语义图架构** — 基础记忆层 → 抽象记忆层 → 检索层
- **语义关系网络** — 记忆单元间的关联关系追踪与传播
- **多空间管理** — 7 个独立记忆空间（codex/rule/pattern/trade/chat/file/abstract）
- **即用即走** — `pip install` + 一行 import 即可使用

**与迭进（diegin）的关系：**
Mindol 本身是独立记忆库，通过 `diegin_integration.py` 桥接迭进引擎。
迭进使用 Mindol 作为长时记忆后端（替代原 MemPalace）。

---

## 二、使用方式

### 2.1 在 Codex 对话中直接使用

```python
from mindol import Mindol

# 初始化（默认存储 ~/.codex/mindol/memory.db）
core = Mindol()

# 写入记忆
core.add_unit(text="这是需要记住的内容", source="chat", space="codex")

# 语义检索
results = core.retrieve("搜索关键词", top_k=5)
for unit, score in results:
    print(f"[{score:.0%}] {unit.text[:200]}")
```

### 2.2 使用 Codex 适配器（推荐）

```python
from mindol.codex_adapter import CodexMemoryAdapter

adapter = CodexMemoryAdapter()
uid = adapter.save_context("对话上下文", source="codex")
results = adapter.search("查询", top_k=5)
print(adapter.format_context(results))
adapter.close()
```

### 2.3 自动上下文注入

在对话开始时，自动检索相关记忆：

```python
from mindol.diegin_integration import memory_format_context

# 自动从 ~/.codex/mindol/ 检索与当前任务相关的历史记忆
ctx = memory_format_context(query="当前任务描述")
if ctx:
    print(ctx)  # 打印相关记忆供参考
```

---

## 三、存储结构

```
~/.codex/mindol/
├── memory.db         # SQLite 数据库（WAL 模式）
└── (插件运行自动创建)
```

### 空间分类

| 空间 | 用途 | 权重 |
|:-----|:-----|:----:|
| codex | 通用 Codex 对话上下文 | 1.0 |
| rule | 拦截规则记忆 | 1.5 |
| pattern | 成功模式记忆 | 1.3 |
| trade | 交易决策记忆 | 1.8 |
| raw_chat | 原始聊天对话 | 0.8 |
| raw_file | 原始文件内容 | 0.7 |
| abstract | 抽象提炼记忆 | 1.2 |

---

## 四、语义检索机制

Mindol 使用混合检索策略：

1. **向量相似度** — n-gram 哈希向量（256维）余弦相似度
2. **关键词匹配** — 文本关键词命中加分
3. **关系传播** — 通过语义关系网络扩展关联记忆
4. **空间权重** — 不同记忆空间有不同权重（如 trade 空间权重 1.8）

---

## 五、与迭进引擎的集成

Mindol 已作为迭进（diegin）的默认记忆后端。

```python
from mindol.diegin_integration import (
    memory_search,          # 替代原 mempalace_search()
    memory_archive,         # 替代原 dgen_archive()
    memory_format_context,  # 格式化记忆上下文
    get_memory_stats,       # 获取记忆统计
    close_memory,           # 关闭连接
)

# 归档迭进决策
memory_archive("rule_001", "拦截规则记录", {"source": "auto"})

# 检索相关记忆
results = memory_search("相关规则", max_results=5)

# 获取统计
stats = get_memory_stats()
```

---

## 六、数据迁移

从旧 MemPalace 迁移到 Mindol：

```bash
python scripts/migrate_mempalace_to_v2.py
```

支持从以下来源迁移：
- MemPalace palace_data/convos/（对话日志）
- MEMORY.md（长期记忆）
- memory_v2 workspace（旧版配置）

---

## 七、技术架构

```
mindol-skill/
├── .codex-plugin/plugin.json       — Codex 插件清单
├── skills/SKILL.md                 ⭐ 本文件
├── engine/mindol/                  — Python 核心包
│   ├── __init__.py                 → Mindol, CodexMemoryAdapter, memory_search...
│   ├── core.py                     → class Mindol（三层语义引擎 + SQLite）
│   ├── vectorizer.py               → n-gram 哈希向量化器（256维）
│   ├── models.py                   → MemoryUnit, MemorySpace, SemanticRelation
│   ├── codex_adapter.py            → CodexMemoryAdapter（Codex 集成适配器）
│   ├── diegin_integration.py       → 迭进桥接（mindol ↔ diegin）
│   └── tools/                      → 工具集
│       ├── track_rule.py
│       ├── update_decision_log.py
│       ├── write_evolution.py
│       └── diegin_search.py
├── tests/mindol/                   — 测试
├── scripts/                        — 迁移脚本
└── README.md / requirements.txt
```

---

## 八、指令

| 指令 | 效果 |
|:---|:---|
| 使用 Mindol | 在当前对话中激活语义记忆引擎 |
| Mindol 状态 | 查看当前记忆存储统计 |
| Mindol 检索 <查询> | 从记忆库中语义检索相关内容 |
| 记住 <内容> | 将内容存入 Mindol 记忆库 |
| 清空测试记忆 | 清理测试数据（保留迁移数据） |
