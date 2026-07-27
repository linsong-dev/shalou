# Mindol 曼兜 — 语义记忆引擎

> **独立运作** · 零外部模型依赖 · n-gram 哈希向量化 · SQLite 持久化

## 特点

- **独立运作**：不绑定 diegin/Codex 或其他系统，单独 import 即可使用
- **零外部模型依赖**：纯 Python + numpy 实现，基于 n-gram 哈希向量化，不需要任何 API Key
- **语义检索**：Jaccard + cosine 混合相似度计算，对中文短文本友好
- **多空间管理**：raw_file / raw_chat / rule / pattern / abstract / trade / codex / state — 8 个独立记忆空间
- **SQLite 持久化**：WAL 模式，线程安全，零配置
- **快**：向量化 ~0.01ms，检索 ~2ms（纯本地 numpy dot product）
- **轻量**：核心 <2000 行
- **Codex 适配器**：即插即用集成到 Codex 对话上下文（可选）
- **迭进桥接**：作为 diegin 的长时记忆后端（可选）

## 独立使用

```python
pip install numpy

from mindol.core import Mindol
core = Mindol()
core.add_unit(text="任意记忆内容", source="chat", space="codex")
results = core.retrieve("查询词", top_k=5)
```

## 结构

```
mindol/
├── engine/mindol/           — Python 核心模块（独立可运行）
│   ├── core.py              — Mindol 引擎
│   ├── vectorizer.py        — n-gram 哈希向量化器
│   ├── models.py            — 数据模型
│   ├── codex_adapter.py     — Codex 集成适配器（可选）
│   └── diegin_integration.py— 迭进引擎桥接（可选）
├── skills/SKILL.md          — Codex 技能描述
├── tests/                   — 测试
└── README.md
```

## 迭进配合（可选）

```python
from mindol.diegin_integration import memory_search, memory_archive
memory_archive("rule_id", "内容")
results = memory_search("查询")
```