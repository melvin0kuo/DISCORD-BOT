"""Reversible, deterministic flags for explicit repetitive-output requests."""
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import time
import unicodedata
from collections import Counter


def parse_user_id(target):
    match=re.fullmatch(r'(?:<@!?(\d{1,20})>|(\d{1,20}))',target.strip())
    if not match or not 0<int(match[1] or match[2])<2**64: raise ValueError('請輸入 @使用者 或 Discord 使用者 ID')
    return str(int(match[1] or match[2]))


def abuse_reason(text):
    text=unicodedata.normalize('NFKC',text).strip()
    text=''.join(c for c in text if unicodedata.category(c)!='Cf')
    # Remove only the denied action; subsequent affirmative requests still count.
    text=re.sub(r'(?:沒有|没[有]?|並未|并未|不是)(?:要求|叫|要|讓|让)你(?:去)?洗[版頻]','',text)
    if re.match(r'^(?:請)?(?:不要|別|停止).{0,12}(?:重複|洗版)|^(?:解釋|分析|如何避免|怎麼避免|什麼是|翻譯)',text):
        return None
    if re.search(r'播放|點歌|音樂|單曲循環|playlist|music',text,re.I) and not re.search(r'文字|輸出|印出|洗版',text):return None
    if re.search(r'洗[版頻]|spam\s+(?:the\s+)?(?:chat|channel)',text,re.I):
        return '要求洗版'
    repeated=re.search(r'重[複覆]|輪流|轮流|連續.{0,8}(?:叫|呱)|呱呱叫|repeat|keep\s+(?:saying|printing)',text,re.I)
    endless=re.search(r'一直|無限|永遠|不要停|不停|斷氣|直到.{0,8}(?:上限|斷|不能)|forever|endless|never\s+stop',text,re.I)
    if repeated and endless: return '要求無限或持續重複輸出'
    if repeated:
        count=re.search(r'(\d[\d,]*)\s*(?:次|遍|times)',text,re.I)
        if count and int(count[1].replace(',',''))>=1000: return '要求大量重複輸出'
        if re.search(r'(?:一千|千|一萬|十萬|百萬)\s*(?:次|遍)',text): return '要求大量重複輸出'
    return None


def repetitive_output(text):
    lines=[re.sub(r'\s+',' ',line.strip()) for line in text.splitlines() if len(line.strip())>=8]
    if len(lines)>=32:
        counts=Counter(lines)
        if sum(n for n in counts.values() if n>=8)>=len(lines)*0.65:return True
    # Long technical code / literal data are not evidence of conversational spam.
    outside=''.join(re.split(r'```|~~~',text)[::2])
    outside=re.sub(r'`[^`\n]*`','',outside)
    if len(outside)<256:return False
    return bool(re.search(r'([^\W\d_][\w\s，。！!～~、,.?？-]{0,15})\1{31,}',outside))


@dataclass
class Outcome:
    block: bool=False
    warning: str=''


class AbuseGuard:
    def __init__(self,path='data/abuse_flags.db'):
        self._recent={}
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
        key=(str(user_id),str(channel_id))
        self._recent={k:v for k,v in self._recent.items() if 0<=now-v[0]<600}
        previous=self._recent.get(key,(now,[]))[1]
        context=' '.join(previous[-3:])
        self._recent[key]=(now,(previous+[text[:1000]])[-4:])
        if len(self._recent)>1024:self._recent.pop(next(iter(self._recent)))
        row=self.get(user_id)
        with self.connect() as db:
            recent=db.execute('SELECT COUNT(*) FROM abuse_events WHERE user_id=? AND created>? AND created<=?',(str(user_id),now-120,now)).fetchone()[0]
        if recent>=3:
            return Outcome(True,f'⏳ <@{user_id}> 短時間多次要求大量重複，暫停生成 2 分鐘，請稍後再試。')
        reason=abuse_reason(text)
        count=re.search(r'(\d[\d,]*)\s*(?:次|遍|times)',text,re.I)
        if (not reason and count and int(count[1].replace(',',''))>=1000
                and re.search(r'手動|print|輸出|重複|輪流|叫',context,re.I)
                and re.search(r'寫|完整|複製|展開|輸出',text)):
            reason='跨輪要求大量展開重複內容或程式碼'
        if (not reason and re.search(r'輪流|重複|叫',context)
                and re.search(r'累為止|不應該會累|直到.{0,5}累',text)):
            reason='跨輪要求持續重複直到耗盡'
        if (not reason and row and row['channel_id']==str(channel_id) and 0<=now-row['updated']<600
                and re.search(r'(?:展[現示]|表[現演]).{0,10}(?:你(?:的)?(?:氣|肺活量|耐力)|氣有多長)',text)):
            reason='近期重複請求改以展示氣長或耐力延續'
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

    def person_context(self,user_id,channels):
        channels=[str(c) for c in channels]
        if not channels:return ''
        placeholders=','.join('?' for _ in channels)
        with self.connect() as db:
            rows=db.execute(f'SELECT reason,created,channel_id FROM abuse_events WHERE user_id=? AND channel_id IN ({placeholders}) ORDER BY id DESC LIMIT 3',[str(user_id)]+channels).fetchall()
        if not rows:return ''
        row=self.get(user_id)
        active=bool(row and row['channel_id'] in channels)
        lines=[f'<@{user_id}> 管理事件紀錄；目前標記：'+('存在' if active else '已解除或未在可讀範圍')]
        for event in rows:
            lines.append(time.strftime('%Y-%m-%d',time.localtime(event['created']))+' 曾被標記，當時記錄原因：'+event['reason'])
        if active: lines.append('提醒狀態：'+('已發送警告' if row['warned'] else '尚待提醒'))
        return '\n'.join(lines)+'\n這是管理紀錄，不是對人格或犯罪的事實判斷。'
