import importlib

import pytest


@pytest.fixture
def memory_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    database = importlib.import_module('utils.user_database')
    memory = importlib.import_module('utils.conversation_memory')
    db = database.UserDatabase(str(tmp_path / 'test.db'))
    db.add_or_update_user('1', 'Alice', 'Alice')
    monkeypatch.setattr(memory, 'user_db', db)
    return db, memory


@pytest.fixture
def handler(memory_db, monkeypatch):
    module = importlib.import_module('utils.llm_handler')
    monkeypatch.setattr(module, 'user_db', memory_db[0])
    monkeypatch.setattr(module, 'conversation_memory', memory_db[1].ConversationMemory())
    monkeypatch.setattr(module.config, 'GEMINI_API_KEY', 'test-key')
    monkeypatch.setattr(module.config, 'LMSTUDIO_API_URL', 'http://localhost:1234')
    monkeypatch.setattr(module.config, 'LMSTUDIO_API_KEY', '')
    monkeypatch.setattr(module.config, 'DEFAULT_LLM_TYPE', 'gemini')
    monkeypatch.setattr(module.config, 'ENABLE_FALLBACK', True)
    return module.LLMHandler('Duck')
