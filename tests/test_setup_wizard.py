import importlib
from pathlib import Path
import json
import threading
import urllib.error
import urllib.request

import pytest


def test_save_preserves_unrelated_settings_and_blank_secrets(tmp_path):
    wizard=importlib.import_module('setup_wizard')
    env=tmp_path/'.env'
    env.write_text("# existing\nDISCORD_TOKEN='keep-me'\nCUSTOM_VALUE=hello\n",encoding='utf-8')
    wizard.save_settings(tmp_path,{'DISCORD_TOKEN':'','DEFAULT_LLM_TYPE':'gemini','GEMINI_API_KEY':'test-secret'})
    result=env.read_text(encoding='utf-8')
    assert "DISCORD_TOKEN='keep-me'" in result
    assert 'CUSTOM_VALUE=hello' in result
    assert wizard.read_settings(tmp_path)['GEMINI_API_KEY']=='test-secret'
    assert 'test-secret' not in str(wizard.public_settings(tmp_path))


@pytest.mark.parametrize('values', [{'DISCORD_TOKEN':'a\nINJECT=true'}, {'DEFAULT_LLM_TYPE':'bad'}, {'UNKNOWN':'x'}, {'LMSTUDIO_API_URL':'http://remote.example:1234'}, {'LMSTUDIO_CONTEXT_LENGTH':'-1'}])
def test_bad_configuration_rejected(tmp_path,values):
    wizard=importlib.import_module('setup_wizard')
    with pytest.raises(ValueError): wizard.save_settings(tmp_path,values)
    assert not (tmp_path/'.env').exists()


def test_only_predefined_actions_allowed(tmp_path):
    wizard=importlib.import_module('setup_wizard')
    with pytest.raises(ValueError): wizard.action_commands('run-anything',tmp_path)
    commands=wizard.action_commands('install',tmp_path)
    assert all(isinstance(command,list) for command in commands)
    assert any('requirements-bot.txt' in ' '.join(command) for command in commands)


def test_session_and_origin_checks():
    wizard=importlib.import_module('setup_wizard')
    assert wizard.authorized('abc','abc','http://127.0.0.1:8765','127.0.0.1:8765')
    assert not wizard.authorized('abc','wrong','http://127.0.0.1:8765','127.0.0.1:8765')
    assert not wizard.authorized('abc','abc','https://evil.example','127.0.0.1:8765')
    assert not wizard.authorized('abc','abc','http://127.0.0.1:8765','evil.example:8765')


def test_invite_includes_history_embeds_and_files_without_admin():
    import setup_wizard as wizard
    for bit in (10,11,14,15,16,20,21): assert wizard.BOT_PERMISSIONS & (1 << bit)
    assert not wizard.BOT_PERMISSIONS & (1 << 3)


def test_bot_detection_does_not_block_unrelated_main_scripts(tmp_path):
    import setup_wizard as wizard
    assert not wizard.matches_bot_process({'CommandLine':'python main.py','ExecutablePath':'unrelated/python.exe'},tmp_path)
    assert wizard.matches_bot_process({'CommandLine':f'python "{tmp_path / "main.py"}"'},tmp_path)
    assert wizard.matches_bot_process({'CommandLine':'python main.py','ExecutablePath':wizard.bot_python(tmp_path)},tmp_path)


def test_http_boundary_and_secret_masking(tmp_path):
    import setup_wizard as wizard
    app=wizard.Wizard(tmp_path)
    server=wizard.ThreadingHTTPServer(('127.0.0.1',0),wizard.make_handler(app))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    def request(path,data=None,token=None,origin=None):
        headers={'Content-Type':'application/json','X-Setup-Token':token or app.token,'Origin':origin or base}
        req=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        return urllib.request.urlopen(req,timeout=5)
    try:
        for headers in ({'token':'wrong'},{'origin':'https://evil.example'}):
            with pytest.raises(urllib.error.HTTPError) as error: request('/api/settings',{'DISCORD_TOKEN':'bad'},**headers)
            assert error.value.code==403
        with request('/api/settings',{'DISCORD_TOKEN':'private-token'}) as response: assert response.status==200
        with request('/api/state') as response:
            body=response.read().decode()
            assert 'private-token' not in body
            assert json.loads(body)['settings']['DISCORD_TOKEN'] is True
        with request('/') as response:
            assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
            assert '部署工作台' in response.read().decode()
        with pytest.raises(urllib.error.HTTPError) as error: request('/api/action',{'action':'exec'})
        assert error.value.code==400
    finally:
        server.shutdown();server.server_close();thread.join(timeout=3)
