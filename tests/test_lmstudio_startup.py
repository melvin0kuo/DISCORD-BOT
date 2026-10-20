import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_existing_model_is_reused_without_loading(monkeypatch):
    import setup_local_lmstudio as setup
    run = Mock(return_value=SimpleNamespace(stdout=json.dumps([{'identifier': 'discord-local'}])))
    monkeypatch.setattr(setup.subprocess, 'run', run)
    monkeypatch.setattr(setup, 'find_lms', lambda: 'lms.exe')
    setup.ensure_lmstudio('discord-local', 'qwen/qwen3.5-9b', 8192)
    assert not any('load' in call.args[0] for call in run.call_args_list)
    assert any('--bind' in call.args[0] and '127.0.0.1' in call.args[0] for call in run.call_args_list)


def test_missing_model_loads_configured_identifier(monkeypatch):
    import setup_local_lmstudio as setup
    run = Mock(return_value=SimpleNamespace(stdout='[]'))
    monkeypatch.setattr(setup.subprocess, 'run', run)
    monkeypatch.setattr(setup, 'find_lms', lambda: 'lms.exe')
    setup.ensure_lmstudio('discord-local', 'qwen/qwen3.5-9b', 8192)
    commands = [call.args[0] for call in run.call_args_list]
    load = next(command for command in commands if 'load' in command)
    assert load[2] == 'qwen/qwen3.5-9b'
    assert load[load.index('--identifier') + 1] == 'discord-local'


def test_missing_cli_reports_setup_error(monkeypatch):
    import setup_local_lmstudio as setup
    monkeypatch.setattr(setup, 'find_lms', lambda: None)
    with pytest.raises(RuntimeError, match='LM Studio'):
        setup.ensure_lmstudio('discord-local', 'qwen/qwen3.5-9b', 8192)


def test_model_with_smaller_context_is_reloaded(monkeypatch):
    import setup_local_lmstudio as setup
    run = Mock(return_value=SimpleNamespace(stdout=json.dumps([
        {'identifier': 'discord-local', 'contextLength': 8192, 'parallel': 4}])))
    monkeypatch.setattr(setup.subprocess, 'run', run)
    monkeypatch.setattr(setup, 'find_lms', lambda: 'lms.exe')
    setup.ensure_lmstudio('discord-local', 'qwen/qwen3.6-27b', 32768)
    commands = [call.args[0] for call in run.call_args_list]
    assert ['lms.exe', 'unload', 'discord-local'] in commands
    load = next(command for command in commands if 'load' in command)
    assert load[load.index('--context-length') + 1] == '32768'
    assert load[load.index('--parallel') + 1] == '1'
