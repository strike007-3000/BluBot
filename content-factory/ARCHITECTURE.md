# Архитектура: AI Content Factory

## Цель

Построить систему, которая умеет:
- собирать контент из разных источников (RSS + YouTube),
- выбирать только релевантный и уникальный материал,
- получать черновик через Codex/Claude,
- отправлять на ручной Telegram-апрув,
- публиковать в нужные каналы,
- вести воспроизводимую аналитику.

## Логическая схема

```text
Sources (RSS, YouTube, Telegram topic prompts, scripts/manual)
    │
    ├─ Ingestion
    ├─> Source health checks (Vanguard/SSRF-safe fetching)
    │
    ├─> Normalization & Dedup (URL + fingerprint)
    │
    ├─> Ranking / Scoring
    │     ├─ базовая оценка источника
    │     ├─ сигнальные ключи (ключевые слова/моменты)
    │     ├─ watchlist-усиление
    │     ├─ дедуп-лист + дедлайн
    │
    ├─> Synthesis (LLM: Codex/Claude/Gemini fallback)
    │
    ├─> Media Strategy (OG image -> AI image fallback)
    │
    ├─> Publication gate (high-confidence auto / Telegram approval)
    │
    └─> Multi-channel broadcast (Bluesky/Mastodon/Threads/Telegram)
          └─> Persistence & status + dashboard + interaction stage
```

## Встроенные домены для текущей системы

- **Ниши:** `Codex/OpenAI`, `Claude/Claude Code`, `n8n/Automation`, `AI Agents/MCP`, `Research`.
- **Ручной режим:** `/topic`, `/watch`, `/brief`.
- **Ключевая точка роста:** модуль `YouTube` для массового извлечения видео:
  - `mostPopular` по регионам,
  - поиск по темам,
  - русскоязычная семантика (cyrillic + language hints),
  - контроль freshness и минимальный порог просматриваемости.

## Папки, которые будем использовать

- `src/curator.py` — curation/summarize/media.
- `src/feed_vanguard.py` — health source control.
- `src/youtube_discovery.py` — новый слой source ingestion для видео.
- `src/telegram_gateway.py` — human-in-the-loop.
- `content-factory/` — архитектурная документация и конфигурации источников.

## Рекомендуемая следующая доработка

- Добавить отдельные score-профили: `news_profile`, `video_profile`, `longform_profile`.
- Вывести unified schema для любого `content object` (title, source, url, published_at, score, tags).
- Настроить единый `pipeline_budget` (например, `top_n=12` на профиль) и отдельный budget на Telegram-спам.
- Добавить retry-guard для YouTube API (per-region quota guard).
