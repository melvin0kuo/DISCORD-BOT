# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Bot

```bash
python main.py
```

Install dependencies:
```bash
pip install -r requirements.txt
```

The bot requires a `.env` file with at minimum `DISCORD_TOKEN` and `GEMINI_API_KEY`. See `config.py` for all supported environment variables.

## Architecture Overview

This is a Python Discord bot (`discord.py` 2.x) built around an `EnhancedBot` subclass that loads five cogs at startup:

- **`cogs/conversation.py`** — Core AI chat. Responds to DMs, mentions, and replies to the bot. Uses `LLMHandler` which calls the Gemini API with streaming. Includes LLM-based prompt injection detection.
- **`cogs/music.py`** — Music playback via `wavelink` (Lavalink client). Manages a custom `MusicQueue` with loop, shuffle, and history. Uses `LavalinkServerManager` to auto-discover and switch public Lavalink servers.
- **`cogs/slash_commands.py`** — Additional slash/hybrid commands, including manual Lavalink server switching.
- **`cogs/user_management.py`** — Slash commands for user profiles: `/設定個人資料`, `/個人資料`, tags, etc.
- **`cogs/conversation_memory_commands.py`** — Slash commands for viewing/exporting the conversation memory system.

### Key Utilities

- **`utils/llm_handler.py` (`LLMHandler`)** — All Gemini API calls live here. Maintains per-user per-channel conversation history in-memory, pulls user context from `UserDatabase` and `ConversationMemory`, and injects it into the system prompt for personalized responses. Currently hardcoded to Gemini only despite `config.py` having OpenAI/Anthropic keys.
- **`utils/user_database.py` (`UserDatabase`)** — SQLite-backed store for user profiles, key-value data, tags, and interaction logs. Singleton exported as `user_db`.
- **`utils/conversation_memory.py` (`ConversationMemory`)** — Persists conversation turns to SQLite (via `user_db`) and builds context strings (recent turns + summaries + topic insights) injected into LLM prompts.
- **`utils/lavalink_manager.py` (`LavalinkServerManager`)** — Fetches public Lavalink server lists, caches them in `data/lavalink_servers.json`, and provides health-checked failover. Singleton exported as `lavalink_manager`.
- **`utils/reloader.py`** — `watchdog`-based hot-reload: when `DEV_MODE=True`, any `.py` file change triggers a full config + cog reload with 1.5s debounce.
- **`config.py`** — All configuration. Reads from `.env` via `python-dotenv`. `LLM_SYSTEM_PROMPT` defines the bot's character (島田愛里壽 from Girls und Panzer).

### Data Flow for AI Responses

1. `on_message` in `Conversation` cog detects trigger (DM / mention / reply)
2. Prompt injection check via `LLMHandler.is_prompt_injection_attack()`
3. `LLMHandler.get_llm_response_stream()` builds context: system prompt + user memory/tags/data from `UserDatabase` + recent conversation context from `ConversationMemory`
4. Streams Gemini response back to Discord with live message edits
5. Completed turn saved to `ConversationMemory` and `UserDatabase` interaction log

### Database

Single SQLite file `user_memory.db` shared by `UserDatabase` and `ConversationMemory`. Tables: `users`, `user_data` (key-value), `user_tags`, `user_interactions`, `conversation_turns`, `conversation_summaries`.

## Owner-Only Prefix Commands

- `!reload_config` — Hot-reload `.env` + `config.py`
- `!reload_cogs` — Reload all cogs
- `!full_reload` — Config + cogs + bot presence
- `!sync_commands` — Force re-sync slash commands to Discord

## Important Notes

- Slash commands can take 1–15 minutes to propagate after `!sync_commands`
- `lavamusic/` and `llama-cpp-python/` are git submodules; ignore them unless working on music or local model features
- The `models/` directory contains a large GGUF model file; local model support is currently commented out in `config.py`
- All UI strings and log messages are in Traditional Chinese (繁體中文)
