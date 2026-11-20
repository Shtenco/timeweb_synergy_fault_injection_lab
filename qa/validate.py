import json,re,hashlib,zipfile
from pathlib import Path
from docx import Document
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
report={'root':str(ROOT),'articles':[],'experiment_assertions':{},'notes':[]}
for num,stem in [(16,'16_exactly_once_sqlite'),(17,'17_fault_injection_two_replicas')]:
 md=(ROOT/'manuscripts_md'/f'{stem}.md').read_text()
 h=BeautifulSoup((ROOT/'html'/f'{stem}_body.html').read_text(),'html.parser')
 doc=Document(ROOT/'word'/f'{stem}.docx')
 images=re.findall(r'!\[([^]]+)\]\(([^)]+)\)',md)
 headers=re.findall(r'^(#{1,3})\s+(.*)$',md,re.M)
 links=re.findall(r'(?<!!)\[[^]]+\]\((https?://[^)]+)\)',md)
 text_before_first_img=md[:md.find('![')]
 intro=text_before_first_img.split('\n\n')[1:]
 errs=[]
 if len(md)<10000 or len(md)>20000:errs.append('length not in 10-20k')
 if len(images)<len(md)/1000:errs.append('under 1 image per 1000 characters')
 if len(doc.inline_shapes)!=len(images):errs.append('docx embedded images count mismatch')
 if len(h.find_all('img'))!=len(images):errs.append('html img count mismatch')
 if not all(x.startswith('❯') for level,x in headers if len(level)<=2):errs.append('headings prefix')
 if not (2<=len(intro)<=4):errs.append('intro paras')
 if '## ❯ Итоги' not in md:errs.append('no conclusions')
 if len(links)<4:errs.append('sources missing')
 for alt,ref in images:
  pp=ROOT/'manuscripts_md'/ref
  if not pp.exists():errs.append(f'missing image {pp}')
 if 'КДПВ' not in md:errs.append('no cover')
 report['articles'].append({'article':num,'characters':len(md),'images':len(images),'docx_embedded':len(doc.inline_shapes),'html_img':len(h.find_all('img')),'source_links':len(links),'intro_paragraphs':len(intro),'headings':len(headers),'violations':errs})
for i,file in [(16,'exactly_once_results.json'),(17,'fault_injection_results.json')]:
 data=json.loads((ROOT/'results'/str(i)/file).read_text());report['experiment_assertions'][str(i)]=data['all_assertions_passed']
 if i==16:
  assert all(r['effects']==200 if r['mode']=='idempotent' else r['effects']==800 for r in data['rows'])
  assert data['payload_conflict']['rejected']
  assert data['crash_probes']['before']['effects_after_redelivery_twice']==1
 if i==17:
  assert len(data['summaries'])==6
  assert all(r['success']==120 for r in data['summaries'] if r['mode']=='retry_failover')
  assert all(r['success']==91 for r in data['summaries'] if r['mode']=='no_retry')
(ROOT/'qa'/'VALIDATION.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
assert all(not x['violations'] for x in report['articles'])
