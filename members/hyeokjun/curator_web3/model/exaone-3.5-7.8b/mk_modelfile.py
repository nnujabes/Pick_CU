import os,sys
sys.path.insert(0,os.path.expanduser('~/Daive-LLM/pickcu/members/hayoung/finetune_v1/code'))
import query_parser as qp
T='FROM ./pickcu-exa-Q5_K_M.gguf\nTEMPLATE """[|system|]{{ .System }}[|endofturn|]\n[|user|]{{ .Prompt }}\n[|assistant|]"""\nSYSTEM """%s"""\nPARAMETER temperature 0\nPARAMETER num_predict 128\nPARAMETER stop "[|endofturn|]"\n'
open('Modelfile','w',encoding='utf-8').write(T%qp.SYSTEM_PROMPT)
open('Modelfile.train','w',encoding='utf-8').write(T%qp.TRAIN_SYSTEM_PROMPT)
print('prompts',len(qp.SYSTEM_PROMPT),len(qp.TRAIN_SYSTEM_PROMPT))
