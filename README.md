# Mindol 曼兜 — 基于内存的语义记忆引擎

> **基于内存环境** · 零外部模型依赖 · n-gram 哈希向量化 · SQLite 仅做持久化

## 特点

- **基于内存环境**：数据全部加载到内存（numpy 数组）后检索，不涉及磁盘 IO，~2ms/次
- **独立运作**：不绑定 diegin/Codex/任何框架，单独 import 即可使用
- **零外部模型依赖**：纯 Python + numpy，不需要任何 API Key、GPU、网络
- **n-gram 哈希向量化**：不调用 embedding 模型，SHA256 哈希直接生成向量（~0.01ms/条）
- **SQLite 仅做持久化**：启动时从 SQLite 加载到内存，关闭时保存回 SQLite，检索不经过磁盘
- **可纯内存运行**：`persist=False` 时完全无文件 IO，适合嵌入式/临时场景
- **语义检索**：Jaccard + cosine 混合，对中文短文本友好
- **8 空间管理**：raw_file / raw_chat / rule / pattern / abstract / trade / codex / state

## 架构

```
[内存] Mindol Core
  ├── _spaces: Dict[str, MemorySpace]    ← 所有数据在这里
  │     ├── memory_units: List[MemoryUnit]
  │     └── index: numpy.ndarray         ← 检索在这里（numpy dot）
  ├── retrieve() → 纯内存计算，~2ms
  └── save() / _load() → 同步到 SQLite
       │
       ▼
[磁盘] SQLite (WAL 模式) — 仅做持久化
```

## 独立使用

```bash
pip install numpy
```

```python
from mindol.core import Mindol

# 纯内存模式（不写磁盘）
core = Mindol(persist=False)
core.add_unit(text="任意内容", source="chat", space="codex")
results = core.retrieve("查询词", top_k=5)

# 持久化模式（SQLite 自动加载）
core = Mindol(persist=True)
```

## 结构

```
mindol/
├── engine/mindol/           — Python 核心模块
│   ├── core.py              — Mindol 引擎（内存环境）
│   ├── vectorizer.py        — n-gram 哈希向量化器
│   ├── models.py            — 数据模型
│   ├── codex_adapter.py     — Codex 适配（可选）
│   └── diegin_integration.py— diegin 桥接（可选）
├── skills/SKILL.md
├── tests/
└── README.md
```