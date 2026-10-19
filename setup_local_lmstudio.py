"""啟動已安裝的 LM Studio，供 Windows 啟動腳本使用。"""

import json
import os
from pathlib import Path
import shutil
import subprocess


def find_lms():
    candidate = Path.home() / '.lmstudio' / 'bin' / ('lms.exe' if os.name == 'nt' else 'lms')
    return str(candidate) if candidate.is_file() else shutil.which('lms')


def ensure_lmstudio(identifier, model_key, context_length):
    cli = find_lms()
    if not cli:
        raise RuntimeError('請先安裝並開啟一次 LM Studio，再下載設定的模型')
    options = dict(check=True, capture_output=True, text=True, encoding='utf-8', timeout=180,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    subprocess.run([cli, 'server', 'start', '--bind', '127.0.0.1', '--port', '1234'], **options)
    result = subprocess.run([cli, 'ps', '--json'], **options)
    loaded = json.loads(result.stdout)
    if not any(model.get('identifier') == identifier for model in loaded):
        subprocess.run([cli, 'load', model_key, '--identifier', identifier,
                        '--context-length', str(context_length), '--gpu', 'max', '--yes'], **options)
    print(f'LM Studio 已就緒: {identifier} / http://127.0.0.1:1234', flush=True)


if __name__ == '__main__':
    import config
    if config.DEFAULT_LLM_TYPE.lower() in ('local', 'lmstudio'):
        try:
            ensure_lmstudio(config.LMSTUDIO_MODEL, config.LMSTUDIO_MODEL_KEY, config.LMSTUDIO_CONTEXT_LENGTH)
        except subprocess.CalledProcessError as error:
            raise SystemExit(f'LM Studio 啟動失敗: {error.stderr or error.stdout}')
