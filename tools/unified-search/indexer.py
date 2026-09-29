#!/usr/bin/env python3
import argparse, csv, hashlib, json, os, re, sqlite3, sys, zipfile
from pathlib import Path
from datetime import datetime

EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?972[- .]?)?(?:0?\d{1,2})[- .]?\d{3}[- .]?\d{4}(?!\d)")
SENSITIVE = re.compile(r"(?i)(pass(word)?|pwd|secret|token|cvv|cvc|card(_| )?num|credit|api[_-]?key|private[_-]?key)")
ID_HINTS = re.compile(r"(?i)(email|mail|phone|mobile|tel|cell|username|user_name|id_card|passport|customer|account|login|מספר|טלפון|אימייל|דוא.?ל)")
DELIMS = [',',';','\t','|',':']

def norm(v):
    v = str(v or '').strip().strip('"').strip("'").lower()
    v = re.sub(r'\s+', ' ', v)
    return v

def identifier_values(key, value):
    k, v = norm(key), str(value or '').strip()
    if not v or SENSITIVE.search(k): return []
    out=[]
    if EMAIL_RE.fullmatch(v): out.append(('email', norm(v)))
    if ID_HINTS.search(k):
        nv = re.sub(r'[^\w@.+-]', '', v, flags=re.UNICODE).lower()
        if nv and len(nv)>=3: out.append(('field:'+k[:60], nv))
    for m in PHONE_RE.findall(v):
        digits=re.sub(r'\D','',m)
        if len(digits)>=8: out.append(('phone', digits[-10:]))
    # Also capture emails/phones embedded in free text.
    for m in EMAIL_RE.findall(v): out.append(('email', norm(m)))
    for m in PHONE_RE.findall(v):
        digits=re.sub(r'\D','',m)
        if len(digits)>=8: out.append(('phone', digits[-10:]))
    return list(dict.fromkeys(out))

def safe_value(k,v):
    if SENSITIVE.search(norm(k)): return '[HIDDEN_SENSITIVE_FIELD]'
    s=str(v if v is not None else '').strip()
    return s[:2000]

def db_init(db):
    db.executescript('''
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS source(id INTEGER PRIMARY KEY, path TEXT UNIQUE, kind TEXT, bytes INTEGER, rows INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS record(id INTEGER PRIMARY KEY, source_id INTEGER, row_no INTEGER, preview TEXT, FOREIGN KEY(source_id) REFERENCES source(id));
    CREATE TABLE IF NOT EXISTS field(id INTEGER PRIMARY KEY, record_id INTEGER, key TEXT, value TEXT, norm TEXT, FOREIGN KEY(record_id) REFERENCES record(id));
    CREATE TABLE IF NOT EXISTS ident(id INTEGER PRIMARY KEY, record_id INTEGER, kind TEXT, value TEXT, UNIQUE(record_id,kind,value));
    CREATE INDEX IF NOT EXISTS ix_ident ON ident(kind,value);
    CREATE INDEX IF NOT EXISTS ix_field_norm ON field(norm);
    CREATE INDEX IF NOT EXISTS ix_record_source ON record(source_id);
    ''')

def add_record(db, source_id, row_no, data):
    clean={str(k): safe_value(k,v) for k,v in data.items() if str(v or '').strip()}
    if not clean: return 0
    preview=json.dumps(clean, ensure_ascii=False)[:4000]
    cur=db.execute('INSERT INTO record(source_id,row_no,preview) VALUES(?,?,?)',(source_id,row_no,preview)); rid=cur.lastrowid
    for k,v in clean.items():
        db.execute('INSERT INTO field(record_id,key,value,norm) VALUES(?,?,?,?)',(rid,k,v,norm(v)))
        for kind,val in identifier_values(k,v):
            db.execute('INSERT OR IGNORE INTO ident(record_id,kind,value) VALUES(?,?,?)',(rid,kind,val))
    return 1

def source(db,p):
    kind=p.suffix.lower().lstrip('.') or 'text'
    cur=db.execute('INSERT OR IGNORE INTO source(path,kind,bytes) VALUES(?,?,?)',(str(p),kind,p.stat().st_size))
    return db.execute('SELECT id FROM source WHERE path=?',(str(p),)).fetchone()[0]

def index_delimited(db,p,sid):
    encs=['utf-8-sig','utf-16','cp1255','latin1']
    f=None
    for enc in encs:
      try: f=open(p,'r',encoding=enc,errors='replace',newline=''); sample=f.read(65536); f.seek(0); break
      except Exception: continue
    if not f: return 0
    try:
      try: dialect=csv.Sniffer().sniff(sample, delimiters=',;\t|:')
      except Exception: dialect=csv.excel; dialect.delimiter=',' if ',' in sample[:1000] else '\t'
      reader=csv.reader(f,dialect)
      first=next(reader,None)
      if not first: return 0
      # Treat first line as header if mostly non-numeric and unique.
      header=[x.strip() or f'col_{i+1}' for i,x in enumerate(first)]
      is_header=len(set(header))==len(header) and sum(bool(re.search('[A-Za-zא-ת_]',x)) for x in header)>=max(1,len(header)//3)
      rows=0
      if not is_header:
        data={f'col_{i+1}':v for i,v in enumerate(first)}; rows+=add_record(db,sid,1,data)
      for no,row in enumerate(reader,2 if is_header else 2):
        if not row: continue
        data={header[i] if i<len(header) else f'col_{i+1}':v for i,v in enumerate(row)}
        rows+=add_record(db,sid,no,data)
      return rows
    finally: f.close()

def index_text(db,p,sid):
    rows=0
    with open(p,'r',encoding='utf-8',errors='replace') as f:
      for no,line in enumerate(f,1):
        line=line.strip()
        if not line: continue
        vals=[]
        for m in EMAIL_RE.findall(line): vals.append(('email',m))
        for m in PHONE_RE.findall(line): vals.append(('phone',m))
        if not vals: continue
        data={'line': line[:4000]}
        rows += add_record(db,sid,no,data)
    return rows

def scan_sql(db,p,sid):
    # Streaming fallback: index emails/phones from every SQL line without executing SQL.
    return index_text(db,p,sid)

def process(db,p):
    sid=source(db,p); ext=p.suffix.lower()
    try:
      if ext in ('.csv','.tsv') or 'orders.csv' in p.name.lower(): n=index_delimited(db,p,sid)
      elif ext=='.xlsx':
        import openpyxl
        n=0
        for ws in openpyxl.load_workbook(p,read_only=True,data_only=True).worksheets:
          it=ws.iter_rows(values_only=True); hdr=next(it,None)
          if not hdr: continue
          hdr=[str(x or f'col_{i+1}') for i,x in enumerate(hdr)]
          for no,row in enumerate(it,2): n+=add_record(db,sid,no,{hdr[i] if i<len(hdr) else f'col_{i+1}':v for i,v in enumerate(row)})
      elif ext=='.sql': n=scan_sql(db,p,sid)
      elif ext in ('.txt','.log','.json','.xml'): n=index_text(db,p,sid)
      else: n=0
      db.execute('UPDATE source SET rows=? WHERE id=?',(n,sid)); db.commit(); return n
    except Exception as e:
      print(f'WARN {p}: {e}',file=sys.stderr); return 0

def main():
  ap=argparse.ArgumentParser(); ap.add_argument('root'); ap.add_argument('--db',default='unified.sqlite'); ap.add_argument('--limit-files',type=int); args=ap.parse_args()
  db=sqlite3.connect(args.db); db_init(db); files=[]
  for p in Path(args.root).rglob('*'):
    if p.is_file() and p.suffix.lower() in ('.csv','.tsv','.txt','.sql','.xlsx','.json','.xml','.log'): files.append(p)
  files=files[:args.limit_files] if args.limit_files else files
  print(f'Indexing {len(files)} readable files...')
  total=0
  for i,p in enumerate(files,1):
    n=process(db,p); total+=n; print(f'[{i}/{len(files)}] {p.name}: {n:,} records',flush=True)
  print(f'Done. {total:,} records. Database: {args.db}')
  db.close()
if __name__=='__main__': main()
