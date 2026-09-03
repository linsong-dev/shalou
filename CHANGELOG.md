# Changelog · Mindol 曼兜

## 3.9.11+ 版本前缀对齐 (2026-09-03)

- chore: 与迭进 3.9.11 版本前缀对齐（迭进×Mindol 联动门禁要求前缀一致），无代码变更；plugin.json / pyproject.toml / CHANGELOG 同步


## 3.9.10+ TOKEN 治理·记忆条目注入清洗 (2026-08-28)

- fix: format_context 源头清洗——新增 `_clean_mem_entry` 统一记忆条目清洗出口：JSON 规则/模式/交易体提取可读 name/id/scene 注入（正文 JSON 不注入）；命令转储截首段语义（`post_tool: tool=Bash`）；绝对路径脱敏 `<path>`；无可读字段的 JSON 整条剔除；实测真实检索注入 456 字符 JSON 垃圾 → 186 字符可读 rule id
- fix: 截断 JSON（core 取 text[:120]/[:500]）正则提取可读字段兜底；多条目 format_context 不再裸拼 text[:200]
- 边界: 仅收敛注入面（format_context）；检索裁决输入（memory_search）保持原样，不改变 P6 裁决
- 验证: py_compile 通过；diegin test_all 33/33；真实检索冒烟（JSON 全剔除）；四副本同步

## 3.9.6 (2026-08-20)

- feat: 与迭进内置版对齐（恢复独立可用性）——情绪调制（mood 标量 + 检索空间权重 ±15%，courage 注入）、跨空间联想（associate）、写入去重（save_chat 单写）
- perf: 记忆治理对齐——分档保留期维护脚本、decay_and_dormancy 每日调度（迭进 3.9.5/3.9.6 同步）
- 版本策略：独立插件恢复与迭进同版本号（3.9.6），代码同一来源，可单独使用、可组合使用

## 1.0.0 (2026-08-10)

- feat: 独立语义版本号（不再沿用迭进版本号）
- fix: 记忆库写入脱敏 P1——diegin_integration 新增 sanitize_text 并接入 save_chat（0f18f6e）
- perf: 检索 archived 过滤 / score 封顶 / embed 缓存 / SQLite 性能与静默化 / 超时熔断（2770ec5）

