"""Local onboarding server. Runs with Python's standard library only."""
import argparse
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser

ROOT = Path(__file__).resolve().parent
FIELDS = {'DISCORD_TOKEN','DEFAULT_LLM_TYPE','GEMINI_API_KEY','GEMINI_MODEL','SERPAPI_API_KEY',
          'LMSTUDIO_API_URL','LMSTUDIO_API_KEY','LMSTUDIO_MODEL','LMSTUDIO_MODEL_KEY','LMSTUDIO_CONTEXT_LENGTH'}
SECRET_FIELDS = {'DISCORD_TOKEN','GEMINI_API_KEY','SERPAPI_API_KEY','LMSTUDIO_API_KEY'}
DEFAULTS = {'DEFAULT_LLM_TYPE':'gemini','GEMINI_MODEL':'gemini-2.5-flash',
            'LMSTUDIO_API_URL':'http://127.0.0.1:1234','LMSTUDIO_MODEL':'discord-local',
            'LMSTUDIO_MODEL_KEY':'qwen/qwen3.5-9b','LMSTUDIO_CONTEXT_LENGTH':'32768'}
BOT_PERMISSIONS = sum(1 << bit for bit in (10,11,14,15,16,20,21))


def read_settings(root):
    values = dict(DEFAULTS)
    path = Path(root)/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            match = re.match(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)',line)
            if not match:
                continue
            value = match[2].strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'":
                quote=value[0]
                value=value[1:-1].replace('\\'+quote,quote).replace('\\\\','\\')
            else:
                value=value.split(' #',1)[0].rstrip()
            values[match[1]]=value
    return values


def public_settings(root):
    values=read_settings(root)
    return {key:bool(values.get(key)) if key in SECRET_FIELDS else values.get(key,'') for key in FIELDS}


def save_settings(root, supplied):
    if not isinstance(supplied,dict) or set(supplied)-FIELDS:
        raise ValueError('包含未支援的設定')
    for value in supplied.values():
        if not isinstance(value,str) or len(value)>4096 or any(c in value for c in '\r\n\x00'):
            raise ValueError('設定必須是單行文字')
    values=read_settings(root)
    updates={k:v.strip() for k,v in supplied.items() if v.strip() or k not in SECRET_FIELDS}
    values.update(updates)
    if values['DEFAULT_LLM_TYPE'] not in ('gemini','local'):
        raise ValueError('請選擇 Gemini 或本機模型')
    endpoint=urlsplit(values['LMSTUDIO_API_URL'])
    if endpoint.scheme!='http' or endpoint.hostname not in ('127.0.0.1','localhost','::1') or endpoint.username or endpoint.password:
        raise ValueError('LM Studio 僅接受本機 HTTP 網址')
    if not values['LMSTUDIO_CONTEXT_LENGTH'].isdigit() or not 4096<=int(values['LMSTUDIO_CONTEXT_LENGTH'])<=262144:
        raise ValueError('上下文長度須為 4096–262144')
    updates.update({'DEV_MODE':'False','ENABLE_FALLBACK':'False','LMSTUDIO_ENABLE_THINKING':'false'})
    path=Path(root)/'.env'
    lines=path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
    seen=set()
    for i,line in enumerate(lines):
        match=re.match(r'\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=',line)
        if match and match[1] in updates:
            key=match[1]; seen.add(key)
            encoded=updates[key].replace('\\','\\\\').replace("'","\\'")
            lines[i]=f"{key}='{encoded}'"
    for key,value in updates.items():
        if key not in seen:
            encoded=value.replace('\\','\\\\').replace("'","\\'")
            lines.append(f"{key}='{encoded}'")
    temporary=path.with_name('.env.setup.tmp')
    temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if os.name!='nt': temporary.chmod(0o600)
    temporary.replace(path)


def bot_python(root):
    return str(Path(root)/'.bot-venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))


def action_commands(action,root):
    root=Path(root); python=bot_python(root)
    commands={
        'install':[[sys.executable,'-m','venv',str(root/'.bot-venv')],
                   [python,'-m','pip','install','--upgrade','pip'],
                   [python,'-m','pip','install','-r',str(root/'requirements-bot.txt')]],
        'music':[[python,str(root/'setup_local_lavalink.py')]],
        'model':[[python,str(root/'setup_local_lmstudio.py')]],
    }
    if action not in commands: raise ValueError('不支援的動作')
    return commands[action]


def authorized(expected,provided,origin,host):
    return (host.startswith('127.0.0.1:') and origin==f'http://{host}'
            and isinstance(provided,str) and hmac.compare_digest(expected,provided))


def matches_bot_process(process,root):
    command=process.get('CommandLine') or ''
    normalize=lambda value: str(value).replace('\\','/').casefold()
    if normalize(Path(root).resolve()/'main.py') in normalize(command): return True
    return (normalize(process.get('ExecutablePath') or '')==normalize(bot_python(root))
            and bool(re.search(r'(?:^|[\s\\/])main\.py(?:[\s"]|$)',command)))


def another_bot_running(root=ROOT):
    if os.name!='nt': return False
    result=subprocess.run(['powershell','-NoProfile','-Command',
        "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Select-Object CommandLine,ExecutablePath | ConvertTo-Json -Compress"],
        capture_output=True,text=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode: raise ValueError('無法檢查既有 Bot 程序，請確認 Windows 程序查詢可用')
    processes=json.loads(result.stdout) if result.stdout.strip() else []
    if isinstance(processes,dict): processes=[processes]
    return any(matches_bot_process(process,root) for process in processes)


class Wizard:
    def __init__(self,root):
        self.root=Path(root); self.token=secrets.token_urlsafe(32)
        self.lock=threading.Lock(); self.busy=False; self.lines=[]; self.process=None
        self.status='準備開始'; self.success=None

    def log(self,line):
        for key,value in read_settings(self.root).items():
            if (key in SECRET_FIELDS or any(x in key for x in ('PASSWORD','SECRET','API_KEY'))) and value:
                line=line.replace(value,'[已遮蔽]')
        with self.lock: self.lines=(self.lines+[line])[-160:]

    def start(self,action):
        if action not in ('install','music','model','check','start','stop'):
            raise ValueError('不支援的動作')
        with self.lock:
            if self.busy: raise ValueError('目前工作仍在執行，請稍候')
            self.busy=True; self.success=None; self.status='執行中'; self.lines=[]
        threading.Thread(target=self.work,args=(action,),daemon=True).start()

    def request(self,url,headers=None):
        request=urllib.request.Request(url,headers=headers or {})
        with urllib.request.urlopen(request,timeout=12) as response:
            return json.load(response)

    def check(self):
        values=read_settings(self.root)
        if not Path(bot_python(self.root)).exists(): raise ValueError('請先完成安裝環境')
        token=values.get('DISCORD_TOKEN','')
        if not token: raise ValueError('尚未填寫 Discord Bot Token')
        bot=self.request('https://discord.com/api/v10/users/@me',{'Authorization':f'Bot {token}'})
        if not bot.get('bot'): raise ValueError('此 Token 不是機器人帳號')
        self.log('Discord Token：驗證成功')
        permissions=BOT_PERMISSIONS  # View, send, embeds, files, history, connect, speak.
        self.log(f"邀請連結：https://discord.com/oauth2/authorize?client_id={bot['id']}&permissions={permissions}&scope=bot%20applications.commands")
        if values['DEFAULT_LLM_TYPE']=='local':
            data=self.request(values['LMSTUDIO_API_URL'].rstrip('/')+'/v1/models',
                              {'Authorization':'Bearer '+values.get('LMSTUDIO_API_KEY','')})
            models=[row.get('id') for row in data.get('data',[])]
            if values['LMSTUDIO_MODEL'] not in models: raise ValueError('本機 API 可用，但尚未載入設定的聊天模型')
            self.log('LM Studio：API 與聊天模型可用（此檢查不保證工具呼叫／視覺能力）')
            if 'text-embedding-nomic-embed-text-v1.5' not in models:
                self.log('提醒：請在 LM Studio 載入 nomic embedding 模型，否則語義記憶不可用')
        else:
            key=values.get('GEMINI_API_KEY','')
            if not key: raise ValueError('尚未填寫 Gemini API Key')
            model=values.get('GEMINI_MODEL','gemini-2.5-flash')
            if not re.fullmatch(r'[A-Za-z0-9._-]+',model): raise ValueError('Gemini 模型名稱格式不正確')
            self.request('https://generativelanguage.googleapis.com/v1beta/models/'+model,{'x-goog-api-key':key})
            self.log('Gemini：Key 與模型查詢成功（生成額度需以實際對話確認）')
        if values.get('SERPAPI_API_KEY'):
            from urllib.parse import urlencode
            account=self.request('https://serpapi.com/account.json?'+urlencode({'api_key':values['SERPAPI_API_KEY']}))
            self.log('SerpApi：帳戶可用，剩餘搜尋 '+str(account.get('total_searches_left','請查看後台')))
        else: self.log('搜尋：使用 DuckDuckGo，無需金鑰')

    def work(self,action):
        try:
            if action=='check': self.check()
            elif action=='stop':
                if self.process and self.process.poll() is None:
                    if os.name=='nt':
                        subprocess.run(['taskkill','/PID',str(self.process.pid),'/T','/F'],check=True,
                                       capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
                    else: self.process.terminate()
                    self.process.wait(timeout=15)
                    self.log('已停止本精靈啟動的機器人')
                else: self.log('沒有由本精靈啟動的機器人')
            elif action=='start':
                if self.process and self.process.poll() is None: raise ValueError('機器人已在執行')
                if another_bot_running(self.root): raise ValueError('偵測到此專案的 Bot 程序；請先在原啟動視窗停止，避免重複登入')
                self.check()
                # Startup is explicit; do not terminate or replace another checkout's bot.
                log=self.root/'data'/'wizard-bot.log'; log.parent.mkdir(exist_ok=True)
                with log.open('ab') as output:
                    self.process=subprocess.Popen([bot_python(self.root),str((self.root/'main.py').resolve())],cwd=self.root,
                        stdout=output,stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                self.log(f'已啟動程序 PID {self.process.pid}；請在 Discord 確認上線，詳細紀錄：data/wizard-bot.log')
            else:
                if self.process and self.process.poll() is None:
                    raise ValueError('請先停止本精靈啟動的 Bot，再安裝或載入模型')
                for command in action_commands(action,self.root):
                    self.log('執行：'+Path(command[0]).name+' '+' '.join(command[1:]))
                    environment=os.environ.copy(); environment.update({'PYTHONUTF8':'1','PYTHONUNBUFFERED':'1'})
                    with subprocess.Popen(command,cwd=self.root,env=environment,stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0) as process:
                        for line in process.stdout: self.log(line.rstrip())
                        if process.wait()!=0: raise ValueError('步驟失敗，請查看上方紀錄並重試')
            self.status='步驟完成'; self.success=True
        except urllib.error.HTTPError as error:
            self.log(f'服務回應 HTTP {error.code}；請檢查 Token、API Key、帳戶權限與額度。')
            self.status='需要處理'; self.success=False
        except Exception as error:
            self.log(str(error) if isinstance(error,ValueError) else f'操作失敗：{type(error).__name__}，請確認網路與服務狀態')
            self.status='需要處理'; self.success=False
        finally:
            with self.lock: self.busy=False


def make_handler(wizard):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # No session URL or credentials in access logs.

        def reply(self,status,body,kind='application/json'):
            data=json.dumps(body,ensure_ascii=False).encode() if kind=='application/json' else body
            self.send_response(status)
            self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers(); self.wfile.write(data)

        def do_GET(self):
            path=urlsplit(self.path).path
            assets={'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if path in assets:
                filename,kind=assets[path]
                return self.reply(200,(ROOT/'setup_ui'/filename).read_bytes(),kind)
            if path=='/api/state':
                if not authorized(wizard.token,self.headers.get('X-Setup-Token'),self.headers.get('Origin',f"http://{self.headers.get('Host')}"),self.headers.get('Host','')):
                    return self.reply(403,{'error':'請從精靈啟動時開啟的頁面操作'})
                with wizard.lock:
                    state={'busy':wizard.busy,'status':wizard.status,'success':wizard.success,'logs':list(wizard.lines),
                           'running':bool(wizard.process and wizard.process.poll() is None)}
                state['settings']=public_settings(wizard.root)
                return self.reply(200,state)
            self.reply(404,{'error':'找不到頁面'})

        def do_POST(self):
            if not authorized(wizard.token,self.headers.get('X-Setup-Token'),self.headers.get('Origin',''),self.headers.get('Host','')):
                return self.reply(403,{'error':'請求驗證失敗'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=32768: raise ValueError('請求大小不正確')
                data=json.loads(self.rfile.read(length))
                if self.path=='/api/settings':
                    if wizard.busy: raise ValueError('請等待目前工作結束後再修改設定')
                    save_settings(wizard.root,data)
                elif self.path=='/api/action': wizard.start(data.get('action'))
                else: return self.reply(404,{'error':'找不到動作'})
                self.reply(200,{'ok':True})
            except (ValueError,TypeError,AttributeError): self.reply(400,{'error':'操作無效；請確認欄位、網址或等待目前工作結束'})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    wizard=Wizard(ROOT)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(wizard))
    url=f'http://127.0.0.1:{server.server_port}/#'+wizard.token
    print('本機設定精靈（請勿分享此網址）：'+url,flush=True)
    if not args.no_browser: webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__=='__main__': main()
