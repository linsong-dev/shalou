# Changelog · Mindol 曼兜

## 1.0.0 (2026-08-10)

- feat: 独立语义版本号（不再沿用迭进版本号）
- fix: 记忆库写入脱敏 P1——diegin_integration 新增 sanitize_text 并接入 save_chat（0f18f6e）
- perf: 检索 archived 过滤 / score 封顶 / embed 缓存 / SQLite 性能与静默化 / 超时熔断（2770ec5）