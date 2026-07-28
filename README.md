<p align="center">
  <img src="https://raw.githubusercontent.com/linsong-dev/mindol/master/assets/logo.svg" width="200" alt="Mindol">
</p>

<h1 align="center">Mindol 曼兜</h1>

<p align="center">
  <b>基于内存的语义记忆引擎</b><br>
  零外部模型依赖 · 纯本地运行 · 即插即用
</p>

<p align="center">
  <a href="https://github.com/linsong-dev/mindol/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-orange" alt="Python">
  <img src="https://img.shields.io/badge/dependencies-numpy%20only-brightgreen" alt="Deps">
</p>

---

## 30 秒看懂 Mindol

Mindol 是一个**基于内存环境**的语义记忆引擎。它不调用任何 embedding API，不需要 GPU，不需要网络——**pip install numpy 就能跑**。

所有记忆数据加载到内存（numpy 数组）后检索，SQLite 仅作为持久化层（启动时加载，关闭时保存）。检索不涉及磁盘 IO，纯内存计算，~2ms/次。

```
[内存] numpy 数组 ← 检索在这里（~2ms）
   ↑ 启动时加载    ↓ 关闭时保存
[磁盘] SQLite (WAL) ← 仅做持久化
```

---

## 特点

| | |
|:---|:---|
| **基于内存** | 数据全部加载到 numpy 数组，纯内存检索 |
| **零外部依赖** | 纯 Python + numpy，不需要任何 API Key |
| **n-gram 向量化** | 不调用 embedding 模型，SHA256 哈希直接生成向量（~0.01ms） |
| **独立运作** | 不绑定任何框架，单独 import 即可使用 |
| **8 空间管理** | raw_file / raw_chat / rule / pattern / abstract / trade / codex / state |
| **SQLite 持久化** | WAL 模式，启动加载、关闭保存，检索不经过磁盘 |
| **可纯内存运行** | `persist=False` 完全无文件 IO |

---

## 快速开始

```bash
pip install numpy
```

```python
from mindol.core import Mindol

# 纯内存模式
core = Mindol(persist=False)
core.add_unit(text="深度学习训练需要 GPU", source="chat", space="codex")

# 检索（走内存，不查 SQLite）
results = core.retrieve("GPU 训练", top_k=5)
for unit, score in results:
    print(f"[{score:.2f}] {unit.text[:60]}")
```

---

## 与迭进配合

作为 [迭进 DGEN](https://github.com/linsong-dev/diegin-skill) 的长时记忆后端：

```python
from mindol.diegin_integration import memory_archive, memory_search

memory_archive("rule_001", "编码规则：统一使用 UTF-8 无 BOM")
results = memory_search("编码规则")
```

---

## 性能对比

| 对比项 | Mindol | 传统 embedding |
|:------|:------|:--------------|
| 向量化速度 | ~0.01ms（SHA256 哈希） | 50-200ms（API 调用） |
| 外部依赖 | 零 | OpenAI Key / GPU |
| 可离线 | ✅ | ❌ |
| 单条检索 | ~2ms（numpy dot） | 网络延迟 + API 延迟 |

---

## 项目结构

```
mindol/
├── engine/mindol/       Python 核心模块
│   ├── core.py              Mindol 引擎
│   ├── vectorizer.py        n-gram 哈希向量化器
│   ├── models.py            数据模型
│   ├── codex_adapter.py     Codex 集成适配器（可选）
│   └── diegin_integration.py 迭进桥接（可选）
├── tests/               测试
├── scripts/             部署脚本
└── README.md
```

---

## 验证安装

```bash
python tests/mindol/test_core.py
```

预期输出：

```
=== Mindol Test Suite ===

  [PASS] vectorizer
  [PASS] models
  [PASS] core lifecycle
  [PASS] persistence
  [PASS] codex adapter
  [PASS] diegin integration

=== ALL TESTS PASSED ===
```

---

## 相关项目

- [迭进 DGEN](https://github.com/linsong-dev/diegin-skill) — AI 全域常驻自我迭代进化系统（使用 Mindol 作为记忆后端）

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/linsong-dev">linsong-dev</a></sub>
</p>