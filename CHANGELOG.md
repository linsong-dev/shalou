# Changelog · Mindol 曼兜

## 3.9.6 (2026-08-20)

- feat: 与迭进内置版对齐（恢复独立可用性）——情绪调制（mood 标量 + 检索空间权重 ±15%，courage 注入）、跨空间联想（associate）、写入去重（save_chat 单写）
- perf: 记忆治理对齐——分档保留期维护脚本、decay_and_dormancy 每日调度（迭进 3.9.5/3.9.6 同步）
- 版本策略：独立插件恢复与迭进同版本号（3.9.6），代码同一来源，可单独使用、可组合使用

## 1.0.0 (2026-08-10)

- feat: 独立语义版本号（不再沿用迭进版本号）
- fix: 记忆库写入脱敏 P1——diegin_integration 新增 sanitize_text 并接入 save_chat（0f18f6e）
- perf: 检索 archived 过滤 / score 封顶 / embed 缓存 / SQLite 性能与静默化 / 超时熔断（2770ec5）
