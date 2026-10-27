"""Persistent per-user rolling generation budgets; quota is not misconduct."""
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time


@dataclass(frozen=True)
class Allowance:
    seconds: float
    characters: int
    blocked: bool


class GenerationBudget:
    # window seconds, request count, generation seconds, generated characters
    WINDOWS=((600,12,180,16000),(3600,40,600,48000))

    def __init__(self,path='data/generation_usage.db'):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS generation_usage (user_id TEXT, channel_id TEXT, finished REAL, seconds REAL, characters INTEGER, outcome TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS generation_usage_user_time ON generation_usage(user_id,finished)')
            db.execute('CREATE TABLE IF NOT EXISTS generation_events (user_id TEXT, channel_id TEXT, created REAL, reason TEXT)')
            db.execute('CREATE INDEX IF NOT EXISTS generation_events_user_time ON generation_events(user_id,created)')
        self._pruned=0

    def connect(self):
        return sqlite3.connect(self.path,timeout=5)

    def allowance(self,user_id,*,now=None):
        now=time.time() if now is None else now
        seconds=120.0;characters=24000;blocked=False
        with self.connect() as db:
            for window,count_limit,seconds_limit,character_limit in self.WINDOWS:
                count,spent,chars=db.execute('SELECT COUNT(*),COALESCE(SUM(seconds),0),COALESCE(SUM(characters),0) FROM generation_usage WHERE user_id=? AND finished>? AND finished<=?',(str(user_id),now-window,now)).fetchone()
                seconds=min(seconds,seconds_limit-spent)
                characters=min(characters,character_limit-chars)
                blocked=blocked or count>=count_limit
        return Allowance(max(0,seconds),max(0,characters),blocked or seconds<=0 or characters<=0)

    def record(self,user_id,channel_id,finished,seconds,characters,outcome):
        with self.connect() as db:
            db.execute('INSERT INTO generation_usage VALUES(?,?,?,?,?,?)',(str(user_id),str(channel_id),finished,max(0,seconds),max(0,characters),outcome))
            if outcome not in ('complete','cancelled','error'):
                db.execute('INSERT INTO generation_events VALUES(?,?,?,?)',(str(user_id),str(channel_id),finished,outcome))
            if finished-self._pruned>=3600:
                db.execute('DELETE FROM generation_usage WHERE finished<?',(finished-30*86400,))
                db.execute('DELETE FROM generation_events WHERE created<?',(finished-30*86400,))
                self._pruned=finished

    def reject(self,user_id,channel_id,*,now=None):
        now=time.time() if now is None else now
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM generation_events WHERE user_id=? AND reason=? AND created>?',(str(user_id),'quota',now-60)).fetchone():
                db.execute('INSERT INTO generation_events VALUES(?,?,?,?)',(str(user_id),str(channel_id),now,'quota'))
