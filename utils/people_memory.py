"""Attributed, channel-scoped remarks and deterministic Discord mention rendering."""
import json
from pathlib import Path
import re
import sqlite3
import time
import unicodedata


def _name(value):
    return unicodedata.normalize('NFKC',value).casefold().replace('_','').replace(' ','')


def readable_channels(message):
    if not message.guild:return [str(message.channel.id)]
    # The answer is visible to this channel's audience, not only to its requester.
    permissions=message.channel.permissions_for(message.author)
    return [str(message.channel.id)] if permissions.view_channel and permissions.read_message_history else []


def normalize_mentions(text,people):
    ids=set(people)
    def unwrap(match):
        value=match[1].strip()
        parsed=re.fullmatch(r'(?:<@!?(\d+)>|(\d+))',value)
        uid=(parsed[1] or parsed[2]) if parsed else None
        if uid in ids:return f'<@{uid}>'
        matches=aliases.get(value.lstrip('@').casefold(),set()) if value.startswith('@') else set()
        return f'<@{next(iter(matches))}>' if len(matches)==1 else match[0]
    # Fenced examples are preserved; inline code containing only a known mention is a display error.
    pieces=re.split(r'(```[\s\S]*?```|~~~[\s\S]*?~~~)',text)
    aliases={}
    for uid,names in people.items():
        for name in names:
            if len(name.strip())>=2:
                aliases.setdefault(name.casefold(),set()).add(uid)
                aliases.setdefault(name.casefold().replace('_',''),set()).add(uid)
    for i in range(0,len(pieces),2):
        part=re.sub(r'`([^`\n]+)`',unwrap,pieces[i])
        part=re.sub(r'<\s*@!?\s*(\d+)\s*>',lambda m:f'<@{m[1]}>' if m[1] in ids else m[0],part)
        blocks=re.split(r'(`[^`\n]*`|https?://[^\s<>]+|<@!?\d+>)',part)
        for j in range(0,len(blocks),2):
            value=blocks[j]
            # Work with tokens in one pass so names cannot rewrite a newly inserted mention.
            options=['@?'+re.escape(uid) for uid in ids]
            options += ['@?'+re.escape(name) for name,uids in aliases.items() if len(uids)==1]
            if options:
                def replace(match):
                    key=match[0].lstrip('@')
                    uid=key if key in ids else next(iter(aliases[key.casefold()]))
                    return f'<@{uid}>'
                value=re.sub(r'(?<![A-Za-z0-9_])(?:'+'|'.join(sorted(options,key=len,reverse=True))+r')(?![A-Za-z0-9_])',replace,value,flags=re.I)
            blocks[j]=value
        pieces[i]=''.join(blocks)
    return ''.join(pieces)


class PeopleMemory:
    def __init__(self,path='data/people_memory.db'):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS aliases(scope TEXT,user_id TEXT,alias TEXT,PRIMARY KEY(scope,user_id,alias))')
            db.execute('''CREATE TABLE IF NOT EXISTS remarks(scope TEXT,channel TEXT,subject TEXT,author TEXT,
                author_name TEXT,message TEXT,content TEXT,created REAL,UNIQUE(scope,subject,message))''')
            db.execute('CREATE INDEX IF NOT EXISTS remarks_lookup ON remarks(scope,subject,channel,created)')

    def connect(self):
        db=sqlite3.connect(self.path,timeout=5);db.row_factory=sqlite3.Row;return db

    def register(self,scope,uid,names):
        with self.connect() as db:
            for name in names:
                if name and 2<=len(name)<=100:
                    db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?,?)',(str(scope),str(uid),name))

    def people(self,scope):
        with self.connect() as db: rows=db.execute('SELECT user_id,alias FROM aliases WHERE scope=?',(str(scope),)).fetchall()
        people={}
        for row in rows: people.setdefault(row['user_id'],[]).append(row['alias'])
        return people

    def resolve(self,scope,text,people=None):
        people=people if people is not None else self.people(scope)
        found={uid for uid in re.findall(r'<@!?(\d+)>',text) if uid in people}
        aliases={}
        normalized=_name(text)
        for uid,names in people.items():
            for name in names:
                key=_name(name)
                if len(key)>=2: aliases.setdefault(key,set()).add(uid)
        for alias,ids in aliases.items():
            if len(ids)==1 and re.search(r'(?<![a-z0-9])'+re.escape(alias)+r'(?![a-z0-9])',normalized): found.update(ids)
        return sorted(found)

    def observe(self,scope,channel,author,author_name,message,text,people=None):
        from utils.conversation_security import protected_request,sanitize_output
        if len(text)>2000 or protected_request(text) or sanitize_output(text,owner=True)!=text: return
        if re.search(r'病史|診斷|罹患|精神病|性取向|宗教|政治傾向|身分證|住址|電話號碼|密碼|金鑰',text): return
        for sentence in re.split(r'(?<=[。！？!?；;\n])',text):
            if re.search(r'[?？]|是不是|怎麼|如何|為什麼|有沒有|[嗎呢]$',sentence.strip()): continue
            if not re.search(r'覺得|認為|說|評價|很|喜歡|討厭|擅長|常常|總是|是|愛',sentence): continue
            for subject in self.resolve(scope,sentence,people):
                with self.connect() as db:
                    db.execute('INSERT OR IGNORE INTO remarks VALUES(?,?,?,?,?,?,?,?)',
                        (str(scope),str(channel),subject,str(author),author_name[:100],str(message),sentence[:350],time.time()))
                    db.execute('DELETE FROM remarks WHERE rowid IN (SELECT rowid FROM remarks WHERE scope=? AND subject=? ORDER BY created DESC LIMIT -1 OFFSET 100)',(str(scope),subject))

    def context(self,scope,uid,channels):
        channels=[str(c) for c in channels]
        if not channels:return ''
        marks=','.join('?' for _ in channels)
        with self.connect() as db:
            rows=db.execute(f'SELECT * FROM remarks WHERE scope=? AND subject=? AND channel IN ({marks}) ORDER BY created DESC LIMIT 5',
                [str(scope),str(uid)]+channels).fetchall()
        return '\n'.join('【他人評論，非事實認定】'+json.dumps({'評論者':row['author_name'],'評論者ID':row['author'],
            '內容':row['content'],'日期':time.strftime('%Y-%m-%d',time.localtime(row['created'])),'來源頻道':row['channel'],'訊息ID':row['message']},ensure_ascii=False) for row in rows)

    def forget(self,scope,uid):
        with self.connect() as db:
            return db.execute('DELETE FROM remarks WHERE scope=? AND subject=?',(str(scope),str(uid))).rowcount
