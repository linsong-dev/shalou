<p align="center">
  <img src="assets/logo.svg" width="200" alt="Mindol">
</p>

<h1 align="center">Mindol</h1>

<p align="center">
  <b>An in-memory semantic memory engine</b><br>
  Zero external model dependencies · fully local · plug and play
</p>

<p align="center">
  [![中文](https://img.shields.io/badge/中文-README-red)](README.md) | [![EN](https://img.shields.io/badge/EN-README-blue)](README.en.md) |
  <a href="https://github.com/linsong-dev/mindol/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License">
  </a>
  <img src="https://img.shields.io/badge/version-3.9.6-brightgreen" alt="Version">
  <img src="https://img.shields.io/badge/python-3.8+-orange" alt="Python">
  <img src="https://img.shields.io/badge/dependencies-numpy%20only-brightgreen" alt="Deps">
</p>

---

## What Mindol Is in 30 Seconds

Mindol is a **memory engine built on an in-memory environment**. All data is loaded into memory (numpy arrays) for retrieval; SQLite is only the persistence layer. No API key, GPU, or network required.

```
[Memory] numpy arrays ← retrieval happens here (~2ms)
   ↑ load           ↓ save
[Disk] SQLite (WAL) ← persistence only
```

## Features

- **In-memory**: all data lives in numpy arrays; pure in-memory retrieval at ~2ms/query
- **Zero external dependencies**: pure Python + numpy, no API keys
- **n-gram hashed vectorization**: no embedding models; SHA256 hashing (~0.01ms)
- **Framework-agnostic**: works standalone with a plain `import`
- **8 spaces**: raw_file / raw_chat / rule / pattern / abstract / trade / codex / state
- **SQLite persistence**: WAL mode, load on start / save on close; retrieval never touches disk
- **Fully in-memory mode**: `persist=False` runs with zero file I/O

## Quick Start

### Install
```bash
pip install numpy
```

### Usage
```python
from mindol.core import Mindol

# Pure in-memory mode (no disk writes)
core = Mindol(persist=False)

# Write a memory
core.add_unit(text="Deep learning training needs a GPU", source="chat", space="codex")

# Retrieve (in-memory numpy dot product)
results = core.retrieve("GPU training", top_k=5)
for unit, score in results:
    print(f"[{score:.2f}] {unit.text[:60]}")

# Persistent mode (auto load/save SQLite)
core = Mindol(persist=True)
```

## Working with Diegin

As the long-term memory backend for [Diegin DGEN](https://github.com/linsong-dev/diegin-skill):

```python
from mindol.diegin_integration import memory_archive, memory_search
memory_archive("rule_001", "Coding rule: always use UTF-8 without BOM")
results = memory_search("coding rule")
```

## Verify Installation

```bash
python tests/mindol/test_core.py
```

Expected output:
```
=== Mindol Test Suite ===
  [PASS] vectorizer  [PASS] models
  [PASS] core lifecycle  [PASS] persistence
  [PASS] codex adapter  [PASS] diegin integration
=== ALL TESTS PASSED ===
```

## Project Structure

```
mindol/
├── engine/mindol/       Python core modules
│   ├── core.py              Mindol engine
│   ├── vectorizer.py        n-gram hashed vectorizer
│   ├── models.py            data models
│   ├── codex_adapter.py     Codex adapter (optional)
│   └── diegin_integration.py Diegin bridge (optional)
├── tests/               Tests (test_core.py, 6/6 pass)
├── scripts/             Migration/deploy scripts
├── assets/              Logo
└── LICENSE              Apache 2.0
```

## Performance

| Item | Mindol | Traditional embedding |
|:------|:------|:--------------|
| Vectorization | ~0.01ms (SHA256) | 50–200ms (API) |
| Retrieval | ~2ms (numpy dot) | network + API latency |
| Offline | ✅ | ❌ |
| Dependencies | numpy only | GPU / API key |

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/linsong-dev">linsong-dev</a></sub>
</p>