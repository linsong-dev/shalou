# Mindol 曼兜 — 语义记忆系统

> 三层语义图记忆引擎，零外部模型依赖

## 特点

- **零外部模型依赖**：纯 Python + numpy 实现，基于 n-gram 哈希向量化
- **三层语义图架构**：基础记忆层 → 抽象记忆层 → 检索层
- **多空间管理**：raw_file / raw_chat / rule / pattern / abstract / trade / codex
- **语义关系网络**：记忆单元间的关联关系追踪与传播
- **SQLite 持久化**：WAL 模式，高效读写
- **Codex 适配器**：即插即用集成到 Codex 对话上下文
- **迭进桥接**：与 diegin 引擎无缝配合

## 结构

```
mindol/
├── .codex-plugin/plugin.json   — Codex 插件清单
├── skills/SKILL.md             — Codex 技能指令
├── engine/mindol/           — Python 核心模块
│   ├── __init__.py             — 包入口
│   ├── core.py                 — Mindol 引擎
│   ├── vectorizer.py           — n-gram 哈希向量化器
│   ├── models.py               — 数据模型
│   ├── codex_adapter.py        — Codex 集成适配器
│   ├── diegin_integration.py   — 迭进引擎桥接
│   └── tools/                  — 工具集
│       ├── track_rule.py       — 规则追踪
│       ├── update_decision_log.py
│       ├── write_evolution.py
│       └── diegin_search.py    — 遗传算法参数搜索
├── tests/mindol/            — 测试
├── scripts/                    — 迁移脚本
├── requirements.txt
└── README.md
```

## 使用

```python
from mindol import Mindol
core = Mindol(storage_path="~/.codex/mindol")
core.add_unit(text="记忆内容", source="chat", space="codex")
results = core.retrieve("查询词", top_k=5)
```

## Codex 集成

```python
from mindol.codex_adapter import CodexMemoryAdapter
adapter = CodexMemoryAdapter()
adapter.save_context("对话上下文", source="codex")
results = adapter.search("查询")
print(adapter.format_context(results))
```
