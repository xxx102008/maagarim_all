#!/usr/bin/env python3
import json, sqlite3, sys
from flask import Flask, request, jsonify, render_template_string

DB=sys.argv[1] if len(sys.argv)>1 else 'unified.sqlite'
app=Flask(__name__)
HTML='''<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8"><title>מאחד המאגרים</title><style>body{font-family:Arial,sans-serif;max-width:1100px;margin:30px auto;padding:0 18px;background:#f6f8fb;color:#172033}h1{margin-bottom:4px}.sub{color:#526070}form{display:flex;gap:8px;margin:24px 0}input{flex:1;padding:13px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}button{padding:12px 22px;border:0;border-radius:8px;background:#1d4ed8;color:white;font-size:16px;cursor:pointer}.card{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 2px 8px #00000008}.pill{display:inline-block;background:#e0ecff;color:#174ea6;border-radius:20px;padding:4px 9px;margin:3px;font-size:13px}.source{color:#64748b;font-size:13px}.kv{display:grid;grid-template-columns:180px 1fr;gap:4px 12px;margin-top:10px}.k{font-weight:bold;color:#475569}.warn{background:#fff7ed;border:1px solid #fed7aa;padding:10px;border-radius:8px}</style><body><h1>חיפוש מאוחד בין המאגרים</h1><div class="sub">חיפוש מקומי בלבד. התוצאות מקובצות לפי מזהים תואמים ומציגות מאיזה קובץ הגיע כל נתון.</div><form onsubmit="search(event)"><input id="q" placeholder="למשל: כתובת אימייל, טלפון או שם משתמש"><button>חיפוש</button></form><div id="out"></div><script>async function search(e){e.preventDefault();let q=document.getElementById('q').value.trim(),o=document.getElementById('out');if(!q)return;o.innerHTML='מחפש...';let r=await fetch('/api/search?q='+encodeURIComponent(q));let d=await r.json();if(!d.groups.length){o.innerHTML='<div class="card">לא נמצאו התאמות.</div>';return}o.innerHTML='<div class="warn">נמצאו '+d.total+' רשומות ב-'+d.groups.length+' קבוצות התאמה.</div>'+d.groups.map(g=>`<div class="card"><div><b>מזהים תואמים:</b> ${g.identifiers.map(x=>`<span class="pill">${esc(x.kind)}: ${esc(x.value)}</span>`).join('')}</div>${g.records.map(r=>`<div class="card"><div class="source">${esc(r.source)} · שורה ${r.row_no}</div><div class="kv">${Object.entries(r.data).map(([k,v])=>`<div class="k">${esc(k)}</div><div>${esc(v)}</div>`).join('')}</div></div>`).join('')}</div>`).join('')}function esc(s){return String(s).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}</script></body></html>'''

def conn():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
@app.get('/')
def home(): return render_template_string(HTML)
@app.get('/api/search')
def search():
 q=request.args.get('q','').strip().lower(); c=conn()
 if not q:return jsonify(groups=[],total=0)
 digits=''.join(ch for ch in q if ch.isdigit())
 vals=[q];
 if digits and len(digits)>=8: vals.append(digits[-10:])
 marks=','.join('?'*len(vals))
 rows=c.execute(f'''SELECT DISTINCT i.record_id,i.kind,i.value,r.source_id,r.row_no,s.path
      FROM ident i JOIN record r ON r.id=i.record_id JOIN source s ON s.id=r.source_id
      WHERE i.value IN ({marks}) OR i.value LIKE ?''', vals+[q+'%']).fetchall()
 ids=[r['record_id'] for r in rows]; groups={}
 for r in rows:
  root=next((x for x,g in groups.items() if r['record_id'] in g['record_ids']),r['record_id'])
  groups.setdefault(root,{'record_ids':set(),'identifiers':[],'records':[]})['record_ids'].add(r['record_id']); groups[root]['identifiers'].append({'kind':r['kind'],'value':r['value']})
 for g in groups.values():
  for rid in g['record_ids']:
   rr=c.execute('SELECT r.row_no,s.path FROM record r JOIN source s ON s.id=r.source_id WHERE r.id=?',(rid,)).fetchone(); data={x['key']:x['value'] for x in c.execute('SELECT key,value FROM field WHERE record_id=?',(rid,))}
   g['records'].append({'source':rr['path'],'row_no':rr['row_no'],'data':data})
 for g in groups.values(): del g['record_ids']; g['identifiers']=list({(x['kind'],x['value']):x for x in g['identifiers']}.values())
 c.close(); return jsonify(groups=list(groups.values()),total=sum(len(g['records']) for g in groups.values()))
if __name__=='__main__': app.run(host='0.0.0.0',port=5000)
