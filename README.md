<p align="center">
  <img src="assets/logo.svg" width="200" alt="Shalou">
</p>

<h1 align="center">Shalou · 流动的记忆</h1>

<p align="center">
  <b>基于内存的语义记忆引擎</b><br>
  零外部模型依赖 · 纯本地运行 · 即插即用
</p>

<p align="center">
  [![EN](https://img.shields.io/badge/EN-README-blue)](README.en.md) | [![中文](https://img.shields.io/badge/中文-README-red)](README.md) | <a href="https://github.com/linsong-dev/shalou/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-orange" alt="Python">
  <img src="https://img.shields.io/badge/dependencies-numpy%20only-brightgreen" alt="Deps">
</p>

---

> **定位（v3.9.12）**：通用语义记忆底座，独立于任何智能体框架。迭进（diegin）通过 venv 包接入本引擎（非自包含组合）；两插件版本前缀联动一致（checkpush 门禁校验）。

## 30 秒看懂 Shalou

Shalou 是**基于内存环境**的语义记忆引擎。所有数据加载到内存（numpy 数组）后检索，SQLite 仅做持久化层。不需要任何 API Key、GPU、网络。

`
[内存] numpy 数组 ← 检索在这里（~2ms）
   ↑ 加载          ↓ 保存
[磁盘] SQLite (WAL) ← 仅做持久化
`

## 特点

- **基于内存**：数据全部在 numpy 数组中，纯内存检索，~2ms/次
- **零外部依赖**：纯 Python + numpy，不需要任何 API Key
- **n-gram 哈希向量化**：不调用 embedding 模型，SHA256 哈希（~0.01ms）
- **独立运作**：不绑定任何框架，单独 import 即可使用
- **8 空间管理**：raw_file / raw_chat / rule / pattern / abstract / trade / codex / state
- **SQLite 持久化**：WAL 模式，启动加载、关闭保存，检索不经过磁盘
- **可纯内存运行**：persist=False 完全无文件 IO

## 快速开始

### 安装
`ash
pip install numpy
`

### 使用
`python
from shalou.core import Shalou

# 纯内存模式（不写磁盘）
core = Shalou(persist=False)

# 写入记忆
core.add_unit(text="深度学习训练需要 GPU", source="chat", space="codex")

# 检索（走内存 numpy dot product）
results = core.retrieve("GPU 训练", top_k=5)
for unit, score in results:
    print(f"[{score:.2f}] {unit.text[:60]}")

# 持久化模式（自动加载/保存 SQLite）
core = Shalou(persist=True)
`

## 与迭进配合

作为 [迭进 DGEN](https://github.com/linsong-dev/diegin-skill) 的长时记忆后端：

`python
from shalou.diegin_integration import memory_archive, memory_search
memory_archive("rule_001", "编码规则：统一使用 UTF-8 无 BOM")
results = memory_search("编码规则")
`

## 验证安装

`ash
python tests/shalou/test_core.py
`

预期输出：
`
=== Shalou Test Suite ===
  [PASS] vectorizer  [PASS] models
  [PASS] core lifecycle  [PASS] persistence
  [PASS] codex adapter  [PASS] diegin integration
=== ALL TESTS PASSED ===
`

## 项目结构

`
shalou/
├── engine/shalou/       Python 核心模块
│   ├── core.py              Shalou 引擎
│   ├── vectorizer.py        n-gram 哈希向量化器
│   ├── models.py            数据模型
│   ├── codex_adapter.py     Codex 适配（可选）
│   └── diegin_integration.py 迭进桥接（可选）
├── tests/               测试（test_core.py 6 项全过）
├── scripts/             迁移/部署脚本
├── assets/              Logo
└── LICENSE              Apache 2.0
`

## 性能

| 对比项 | Shalou | 传统 embedding |
|:------|:------|:--------------|
| 向量化 | ~0.01ms（SHA256） | 50-200ms（API） |
| 检索 | ~2ms（numpy dot） | 网络+API 延迟 |
| 离线 | ✅ | ❌ |
| 依赖 | numpy 而已 | GPU / API Key |

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/linsong-dev">linsong-dev</a></sub>
</p>
