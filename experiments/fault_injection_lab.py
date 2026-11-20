#!/usr/bin/env python3
"""Controlled two-replica localhost HTTP resilience lab; no external network access."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
import csv, json, multiprocessing, socket, statistics, sys, time
from pathlib import Path

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path=urlparse(self.path)
        if path.path=='/health':
            payload=b'OK';self.send_response(200);self.end_headers();self.wfile.write(payload);return
        q=parse_qs(path.query)
        idx=int(q.get('id',['0'])[0]); attempt=int(q.get('attempt',['0'])[0])
        if idx%10==0 and attempt==0:
            self.send_response(503);self.end_headers();return
        if idx%10==1 and attempt==0: time.sleep(.075)
        try:
            self.send_response(200);self.end_headers();self.wfile.write(f'OK:{idx}'.encode())
        except (BrokenPipeError,ConnectionResetError): pass
    def log_message(self,*args): pass

def serve(port):
    s=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    s.serve_forever(poll_interval=.01)

def freeport():
    s=socket.socket();s.bind(('127.0.0.1',0));n=s.getsockname()[1];s.close();return n

def start_replica(port):
    p=multiprocessing.Process(target=serve,args=(port,),daemon=True);p.start()
    for _ in range(150):
        try:
            with urlopen(f'http://127.0.0.1:{port}/health',timeout=.05) as r:
                if r.status==200: return p
        except Exception: time.sleep(.01)
    raise RuntimeError('replica not ready')

def stop_replica(p):
    if p and p.is_alive(): p.terminate();p.join(timeout=2)
    if p and p.is_alive(): p.kill();p.join(timeout=2)

def percentile(a,q):
    a=sorted(a);i=(len(a)-1)*q/100;j=int(i);k=min(len(a)-1,j+1);return a[j]+(a[k]-a[j])*(i-j)

def request(port,idx,attempt,timeout):
    with urlopen(f'http://127.0.0.1:{port}/work?id={idx}&attempt={attempt}',timeout=timeout) as r:
        return r.status,r.read().decode()

def run_mode(out,run_id,mode,n=120):
    ports=[freeport(),freeport()]
    procs=[start_replica(p) for p in ports]
    errors={}; latencies=[]; attempts=[]; outcomes=[]; dead={}
    t0=time.perf_counter()
    try:
        for idx in range(n):
            # Three real process failures, injected before the next request. Four requests pass before restart.
            if idx in [25,50,75]:
                replica=idx%2;stop_replica(procs[replica]);procs[replica]=None;dead[replica]=idx+4
            for replica,until in list(dead.items()):
                if idx>=until:
                    procs[replica]=start_replica(ports[replica]);del dead[replica]
            since=time.perf_counter();success=False;seen=[]
            for attempt in range(3 if mode=='retry_failover' else 1):
                replica=(idx+attempt)%2
                try:
                    code,body=request(ports[replica],idx,attempt,.035)
                    if code==200 and body==f'OK:{idx}': success=True;break
                    seen.append('bad_body')
                except HTTPError as e: seen.append(f'http_{e.code}')
                except (URLError,TimeoutError,OSError,ConnectionError) as e:
                    err='timeout' if 'timed out' in str(e).lower() or isinstance(e,TimeoutError) else 'connection'
                    seen.append(err)
            elapsed=(time.perf_counter()-since)*1000
            latencies.append(elapsed);attempts.append(attempt+1)
            for err in seen: errors[err]=errors.get(err,0)+1
            outcomes.append({'run':run_id,'mode':mode,'request':idx,'success':int(success),'attempts':attempt+1,'latency_ms':round(elapsed,3),'errors':'|'.join(seen)})
    finally:
        for p in procs: stop_replica(p)
    summary={'run':run_id,'mode':mode,'requests':n,'success':sum(x['success'] for x in outcomes),'failed':n-sum(x['success'] for x in outcomes),'success_rate':round(sum(x['success'] for x in outcomes)/n,5),'retry_attempts_extra':sum(attempts)-n,'p50_request_ms':round(percentile(latencies,50),3),'p95_request_ms':round(percentile(latencies,95),3),'mean_request_ms':round(statistics.mean(latencies),3),'elapsed_s':round(time.perf_counter()-t0,3),'injected_process_terminations':3,'injected_first_attempt_faults':'503 for id%10==0; 75ms delayed response for id%10==1','errors':errors}
    return summary,outcomes

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    summaries=[];details=[]
    for i in range(3):
        for mode in ['no_retry','retry_failover']:
            summary,items=run_mode(out,i,mode)
            summaries.append(summary); details.extend(items)
    assert sum(r['injected_process_terminations'] for r in summaries)==18
    assert all(r['success']==r['requests'] for r in summaries if r['mode']=='retry_failover')
    result={'study':'two real localhost HTTP replica processes with controlled failures','limitations':'single host, no external state changes, deterministic fault pattern, no real multi-host network partitions','python':sys.version.split()[0],'summaries':summaries,'all_assertions_passed':True}
    (out/'fault_injection_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    with (out/'fault_injection_requests.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,details[0].keys());w.writeheader();w.writerows(details)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',default='results');a=p.parse_args()
    run(a.out)
