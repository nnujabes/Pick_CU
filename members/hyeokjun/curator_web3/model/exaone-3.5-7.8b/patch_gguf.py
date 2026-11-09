import json,os,struct,sys
sys.path.insert(0,os.path.expanduser('~/pickcu_gguf/llama.cpp/gguf-py'))
from gguf import GGUFReader
p=os.path.expanduser('~/pickcu_gguf_exa/pickcu-exa-bf16.gguf')
cfg=json.load(open('base_config.json')); print({k:cfg.get(k) for k in ['rope_theta','layer_norm_epsilon','rms_norm_eps','intermediate_size','num_key_value_heads','max_position_embeddings']})
r=GGUFReader(p,'r'); last=r.tensors[-1].field; end=last.offset+sum(int(x.nbytes) for x in last.parts); start=min(t.data_offset for t in r.tensors); del r
old=b'exaone.attention.layer_norm_epsilon'; new=b'exaone.attention.layer_norm_rms_epsilon'
with open(p,'r+b') as f:
    h=f.read(end); pat=struct.pack('<Q',len(old))+old
    if h.count(struct.pack('<Q',len(new))+new)==0:
        assert h.count(pat)==1 and end+len(new)-len(old)<=start
        nh=h.replace(pat,struct.pack('<Q',len(new))+new); f.seek(0); f.write(nh); f.flush(); os.fsync(f.fileno()); print('renamed key, header',end,'->',len(nh),'data',start)
r=GGUFReader(p,'r+'); f=r.fields
print('rms',f['exaone.attention.layer_norm_rms_epsilon'].parts[-1].tolist(),'tensors',len(r.tensors),'first offset',r.tensors[0].data_offset)
th=cfg.get('rope_theta'); fld=f['exaone.rope.freq_base']; cur=float(fld.parts[-1][0])
if th is not None and abs(th-cur)>1e-3: fld.parts[-1][0]=th; print('rope theta patched',cur,'->',th)
else: print('rope theta ok',cur,th)
