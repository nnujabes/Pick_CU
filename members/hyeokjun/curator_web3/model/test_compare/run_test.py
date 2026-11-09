import collections,csv,json,os,sys,time,urllib.request as u
REPO=os.path.expanduser('~/Daive-LLM/pickcu')
sys.path.insert(0,REPO+'/members/hayoung/finetune_v1/code')
import query_parser as qp
W=os.path.expanduser('~/pickcu_gguf_exa/test')
rows=list(csv.DictReader(open(W+'/test_pair_v3_240.csv',encoding='utf-8-sig')))
K={"열량":"calories","단백질":"protein","나트륨":"sodium","탄수화물":"carbs","당류":"sugar","지방":"fat"}; D={"높음":"high","낮음":"low"}
print('rows',len(rows),'situations',len({r['상황ID'] for r in rows}),flush=True)
def gen(m,s,t):
    b=json.dumps({"model":m,"system":s,"prompt":t,"stream":False,"keep_alive":"30m","options":{"temperature":0,"num_predict":128}}).encode()
    return json.load(u.urlopen(u.Request('http://127.0.0.1:11434/api/generate',b,{'Content-Type':'application/json'}),timeout=300))['response']
runs=[('ax','pickcu-ax:q5_k_m','train',qp.TRAIN_SYSTEM_PROMPT),('exa','pickcu-exa:q5_k_m','train',qp.TRAIN_SYSTEM_PROMPT),('ax','pickcu-ax:q5_k_m','service',qp.SYSTEM_PROMPT),('exa','pickcu-exa:q5_k_m','service',qp.SYSTEM_PROMPT)]
res={}
for name,m,pn,sp in runs:
    gen(m,sp,'워밍업'); t0=time.time(); out=[]
    for r in rows:
        g1=(K[r['성분1']],D[r['방향1']]); g2=(K[r['성분2']],D[r['방향2']])
        raw=gen(m,sp,r['입력 문장']); p,why=qp.parse_model_response(raw)
        pred={(K[a],b) for a,b in p.items()} if p else None
        out.append({'s':r['상황ID'],'t':r['입력 문장'],'gold':[g1,g2],'pred':sorted(pred) if pred else None,'ok':pred=={g1,g2},'first':bool(pred and g1 in pred),'second':bool(pred and g2 in pred),'why':why,'raw':raw})
    el=time.time()-t0; n=len(out)
    s={'model':name,'prompt':pn,'correct':sum(x['ok'] for x in out),'acc':round(sum(x['ok'] for x in out)/n,4),'first':sum(x['first'] for x in out),'second':sum(x['second'] for x in out),'fmt':sum(x['pred'] is None for x in out),'sec':round(el/n,2)}
    bys=collections.Counter(); 
    for x in out:
        if x['ok']: bys[x['s']]+=1
    s['by_situation']={k:bys[k] for k in sorted({x['s'] for x in out})}
    res[f'{name}_{pn}']=out; print(json.dumps(s,ensure_ascii=False),flush=True)
    json.dump(s,open(f'{W}/summary_{name}_{pn}.json','w',encoding='utf-8'),ensure_ascii=False); json.dump(out,open(f'{W}/rows_{name}_{pn}.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
for pn in ['train','service']:
    a,e=res[f'ax_{pn}'],res[f'exa_{pn}']
    aonly=sum(x['ok'] and not y['ok'] for x,y in zip(a,e)); eonly=sum(y['ok'] and not x['ok'] for x,y in zip(a,e)); both=sum(x['ok'] and y['ok'] for x,y in zip(a,e)); same=sum(x['pred']==y['pred'] for x,y in zip(a,e))
    print(json.dumps({'prompt':pn,'both_correct':both,'ax_only':aonly,'exa_only':eonly,'same_pred':same},ensure_ascii=False),flush=True)
    wrong=collections.Counter(tuple(map(tuple,y['gold'])) for x,y in zip(a,e) if x['ok'] and not y['ok'])
    print('exa_miss_ax_ok_top',wrong.most_common(3),flush=True)
print('FINISHED',flush=True)
