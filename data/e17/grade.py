import sys,os,re,json,subprocess
E=os.path.dirname(os.path.abspath(__file__)); ID,W=sys.argv[1],os.path.abspath(sys.argv[2])
t=[json.loads(l) for l in open(E+"/tasks.jsonl")]; t=[x for x in t if x["id"]==ID][0]
env=dict(os.environ,PATH=E+"/repo/.venv/bin:"+os.environ["PATH"],PYTHONPATH=W,PYTHONDONTWRITEBYTECODE="1")
r=subprocess.run([E+"/repo/.venv/bin/python","-m","pytest","tests",*t["p2p_ignore"],"-q","-rA","--tb=no","-p","no:cacheprovider","-n","2"],cwd=W,env=env,capture_output=True,text=True)
res={m.group(2):m.group(1) for l in r.stdout.splitlines() if (m:=re.match(r"(PASSED|FAILED|ERROR) (\S+)",l))}
f2p_ok=all(res.get(x)=="PASSED" for x in t["f2p"])
excl=set(t["p2p_exclude"])|set(t["f2p"])
bad=sorted(x for x,s in res.items() if s!="PASSED" and x not in excl)
if not res: bad=["<no tests collected / pytest crashed>"]
print(json.dumps(dict(f2p_pass=f2p_ok,p2p_pass=not bad,failed_tests=sorted(x for x in t["f2p"] if res.get(x)!="PASSED")+bad)))
