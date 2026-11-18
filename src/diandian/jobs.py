"""Persistent, idempotent local requests; refresh never submits a second model call."""
import json,sqlite3,threading,time
from concurrent.futures import ThreadPoolExecutor

class JobConflict(ValueError): pass

class Jobs:
    def __init__(self,path,engine):
        self.engine=engine; self.lock=threading.RLock()
        self.conn=sqlite3.connect(str(path),check_same_thread=False)
        self.conn.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL,stage TEXT NOT NULL,result TEXT,created REAL,updated REAL)')
        self.conn.execute("UPDATE jobs SET status='interrupted',stage='本地服务已重启，请手动重试' WHERE status IN ('queued','running')")
        self.conn.commit(); self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='diandian-local')
    def get(self,rid):
        with self.lock:
            row=self.conn.execute('SELECT id,status,stage,result,created,updated FROM jobs WHERE id=?',(rid,)).fetchone()
        if not row: return None
        return {'request_id':row[0],'status':row[1],'stage':row[2],'result':json.loads(row[3]) if row[3] else None,'created_at':row[4],'updated_at':row[5]}
    def submit(self,rid,payload):
        encoded=json.dumps(payload,ensure_ascii=False,sort_keys=True)
        with self.lock:
            row=self.conn.execute('SELECT payload FROM jobs WHERE id=?',(rid,)).fetchone()
            if row:
                if row[0]!=encoded: raise JobConflict('同一请求标识不能用于不同内容')
                return self.get(rid)
            now=time.time()
            self.conn.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?)',(rid,encoded,'queued','等待处理',None,now,now)); self.conn.commit()
            self.pool.submit(self._execute,rid,payload)
        return self.get(rid)
    def _update(self,rid,status,stage,result=None):
        with self.lock:
            self.conn.execute('UPDATE jobs SET status=?,stage=?,result=?,updated=? WHERE id=?',(status,stage,json.dumps(result,ensure_ascii=False) if result is not None else None,time.time(),rid)); self.conn.commit()
    def _execute(self,rid,payload):
        self._update(rid,'running','正在处理')
        try:
            result=self.engine.run(payload,progress=lambda stage:self._update(rid,'running',stage))
        except Exception:
            result={'status':'ERROR','answer':'本地请求未完成，请手动重试。','products':[],'evidence':[],'usage':[],'trace':[]}
        self._update(rid,'completed','处理完成',result)
    def close(self):
        self.pool.shutdown(wait=True)
        with self.lock: self.conn.close()
