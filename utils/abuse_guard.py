"""Reversible, deterministic flags for explicit repetitive-output requests."""
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import time
import unicodedata


def parse_user_id(target):
    match=re.fullmatch(r'(?:<@!?(\d{1,20})>|(\d{1,20}))',target.strip())
    if not match or not 0<int(match[1] or match[2])<2**64: raise ValueError('請輸入 @使用者 或 Discord 使用者 ID')
    return str(int(match[1] or match[2]))


def abuse_reason(text):
    text=unicodedata.normalize('NFKC',text).strip()
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    if re.match(r'^(?:請)?(?:不要|別|停止).{0,12}(?:重複|洗版)|^(?:解釋|分析|如何避免|怎麼避免|什麼是|翻譯)',text):
        return None
    if re.search(r'洗[版頻]|spam\s+(?:the\s+)?(?:chat|channel)',text,re.I):
        return '要求洗版'
    repeated=re.search(r'重[複覆]|連續.{0,8}(?:叫|呱)|呱呱叫|repeat|keep\s+(?:saying|printing)',text,re.I)
    endless=re.search(r'一直|無限|永遠|不要停|不停|斷氣|直到.{0,8}(?:上限|斷|不能)|forever|endless|never\s+stop',text,re.I)
    if repeated and endless: return '要求無限或持續重複輸出'
    if repeated:
        count=re.search(r'(\d[\d,]*)\s*(?:次|遍|times)',text,re.I)
        if count and int(count[1].replace(',',''))>=1000: return '要求大量重複輸出'
        if re.search(r'(?:一千|千|一萬|十萬|百萬)\s*(?:次|遍)',text): return '要求大量重複輸出'
    return None


@dataclass
class Outcome:
    block: bool=False
    warning: str=''


class AbuseGuard:
    def __init__(self,path='data/abuse_flags.db'):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS abuse_flags (
                user_id TEXT PRIMARY KEY, strikes INTEGER NOT NULL, reason TEXT NOT NULL,
                channel_id TEXT NOT NULL, updated REAL NOT NULL, active_until REAL NOT NULL,
                warned REAL NOT NULL DEFAULT 0, pending INTEGER NOT NULL DEFAULT 0)''')
            db.execute('''CREATE TABLE IF NOT EXISTS abuse_events (
                id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, channel_id TEXT NOT NULL,
                reason TEXT NOT NULL, created REAL NOT NULL, message_id TEXT NOT NULL DEFAULT '')''')

    def connect(self):
        db=sqlite3.connect(self.path,timeout=5); db.row_factory=sqlite3.Row; return db

    def get(self,user_id):
        with self.connect() as db:
            row=db.execute('SELECT * FROM abuse_flags WHERE user_id=?',(str(user_id),)).fetchone()
        return dict(row) if row else None

    def mark(self,user_id,channel_id,reason,*,now=None,pending=False,message_id=''):
        now=time.time() if now is None else now
        with self.connect() as db:
            db.execute('''INSERT INTO abuse_flags(user_id,strikes,reason,channel_id,updated,active_until,pending)
                VALUES(?,1,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET strikes=strikes+1,
                reason=excluded.reason,channel_id=excluded.channel_id,updated=excluded.updated,
                active_until=excluded.active_until,pending=MAX(pending,excluded.pending)''',
                (str(user_id),reason[:200],str(channel_id),now,now+600,int(pending)))
            db.execute('INSERT INTO abuse_events(user_id,channel_id,reason,created,message_id) VALUES(?,?,?,?,?)',
                       (str(user_id),str(channel_id),reason[:200],now,str(message_id)))

    def check(self,user_id,channel_id,text,*,now=None,message_id=''):
        now=time.time() if now is None else now
        row=self.get(user_id)
        reason=abuse_reason(text)
        followup=bool(row and row['channel_id']==str(channel_id) and row['active_until']>now
                      and re.fullmatch(r'(?:再多[點些一點]*|太短了?[吧啦]?|繼續|繼續呱|不要停|more|continue)[！!。.?？\s]*',text.strip(),re.I))
        if reason or followup:
            self.mark(user_id,channel_id,reason or '延續近期的重複洗版請求',now=now,message_id=message_id)
            row=self.get(user_id)
            warn=not row['warned'] or now-row['warned']>=60
            if warn:
                with self.connect() as db: db.execute('UPDATE abuse_flags SET warned=?,pending=0 WHERE user_id=?',(now,str(user_id)))
            return Outcome(True,f'⚠️ <@{user_id}> 偵測到大量／無限重複要求，本次不會執行。已記錄第 {row["strikes"]} 次；請改為正常問題或指定合理次數。' if warn else '')
        if row:
            notify=row['pending'] and (not row['warned'] or now-row['warned']>=60)
            with self.connect() as db:
                db.execute('UPDATE abuse_flags SET active_until=0,pending=0 WHERE user_id=?',(str(user_id),))
                if notify: db.execute('UPDATE abuse_flags SET warned=? WHERE user_id=?',(now,str(user_id)))
            if notify:
                return Outcome(False,f'⚠️ <@{user_id}> 先前的大量重複請求已記錄。請勿要求無限重複或洗版；正常提問仍可使用。')
        return Outcome()

    def clear(self,user_id):
        with self.connect() as db:
            changed=db.execute('DELETE FROM abuse_flags WHERE user_id=?',(str(user_id),)).rowcount
        return bool(changed)

    def acknowledge_warning(self,user_id):
        with self.connect() as db:
            db.execute('UPDATE abuse_flags SET pending=0,warned=? WHERE user_id=?',(time.time(),str(user_id)))
