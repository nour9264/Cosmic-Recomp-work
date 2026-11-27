"""Execute our actual authored bytecode against a bounded model of the VM API.

This checks state/resource transactions, not rendering or real game behavior.
"""
import copy
import json
import struct
from prepare_all_aliens_candidate import (
    ROOT,Code,crc,authored,decode,records,transform_globals,BASE,EXTRA,READY,
    PENDING,PAGE,ACTIVE)

class VM:
    def __init__(self,preset):
        self.functions={h:(a,c) for h,a,c in authored()}
        self.page=-1;self.events=[];self.pending=[];self.globals={}
        self.globals[crc('gFormHotKey')]={i:{crc('formID'):v} for i,v in enumerate(preset,1)}
        self.globals[crc('gFormData')]={i:{crc('characterFile'):'g_'+str(i),
          0x7fb535f8:'atk_'+str(i),crc('character'):'character_'+str(i)} for i in range(1,12)}
        self.globals[0x0bfbfd2d]='data';self.globals[0x79c61e79]='desc'
        mission={}
        def load(*args):
            self.events.append(('load',args[1],args[2]));self.pending.append(args[3])
        def unload(*args):self.events.append(('unload',args[1],args[2]))
        mission[0xbc35779c]=load;mission[0x1a7328ab]=load
        mission[crc('unloaddata')]=unload;mission[crc('unloaddesc')]=unload
        self.globals[0xf3d407b1]={crc('getcurrentmission'):lambda *_:mission}
        self.globals[0x93aca275]={crc('removecharacter'):lambda *args:self.events.append(('remove',args[1]))}
        self.globals[0x2712f51f]={0x5e89deba:lambda *args:self.events.append(('sound',args[1]))}
        self.globals[crc('overlay')]={crc('cosmic_all_aliens_page'):lambda *_:self.page,
          crc('cosmic_all_aliens_trace'):lambda *_:None}
        for h in self.functions:self.globals[h]=h
    def run(self,name,args=()):
        identity=crc(name) if isinstance(name,str) else name
        expected,code=self.functions[identity];assert len(args)==expected
        words,decoded=decode(code);sizes={p:(decoded[i+1][0] if i+1<len(decoded) else len(words))-p for i,(p,k) in enumerate(decoded)}
        r=dict(enumerate(args));pc=0;steps=0
        def read(reg):return r.get(reg)
        def truth(value):return value is not None and value is not False
        while pc<len(words):
            steps+=1;assert steps<10000,'Unbounded authored script'
            w=words[pc];kind=w&255;a=(w>>8)&255;b=(w>>16)&255;d=w>>24
            advance=sizes[pc]
            if kind==1:r[a]=None
            elif kind==2:r[a]=bool(b)
            elif kind==3:r[a]=struct.unpack('>f',struct.pack('>I',words[pc+1]))[0]
            elif kind==4:r[a]=code[(pc+1)*4:(pc+advance)*4].split(b'\x00',1)[0].decode('ascii')
            elif kind==5:r[a]=words[pc+1]
            elif kind==6:r[b]=read(a)
            elif kind==7:r[a]=self.globals.get(words[pc+1])
            elif kind==8:self.globals[words[pc+1]]=read(a)
            elif kind in (0x0a,0x0b,0x0c,0x0d,0x10,0x11,0x12,0x13):
                left,right=read(a),read(b)
                r[d]={0x0a:lambda:left+right,0x0b:lambda:left-right,0x0c:lambda:left*right,0x0d:lambda:left/right,
                      0x10:lambda:left==right,0x11:lambda:left!=right,
                      0x12:lambda:left<right,0x13:lambda:left>right}[kind]()
            elif kind==0x16:r[a]={}
            elif kind==0x17:r[b]=read(a).get(words[pc+1])
            elif kind==0x18:r[d]=read(a).get(read(b))
            elif kind==0x19:read(a)[words[pc+1]]=read(b)
            elif kind==0x1a:read(a)[read(b)]=read(d)
            elif kind==0x1d:pc=w>>8;continue
            elif kind==0x1f:
                if not truth(read(a)):pc=w>>16;continue
            elif kind==0x20:
                function=read(a);arguments=tuple(read(b+i) for i in range(d))
                r[words[pc+1]]=function(*arguments) if callable(function) else self.run(function,arguments)
            elif kind==0x21:return None
            elif kind==0x22:return read(a)
            else:raise AssertionError('Unmodeled authored opcode '+hex(kind))
            pc+=advance
    def slots(self):return [self.globals[crc('gFormHotKey')][i][crc('formID')] for i in range(1,5)]
    def complete(self):
        callbacks=self.pending;self.pending=[]
        for callback in callbacks:self.run(callback,[True])

cases=0
for preset in ([4,5,7,10],[11,1,6,9],[1,2,3,4]):
    vm=VM(preset);vm.run('CosmicAlienUpdate');assert vm.slots()==preset and not vm.events
    vm.page=0;vm.run('CosmicAlienUpdate');assert len(vm.pending)==14 and vm.slots()==preset
    assert sorted(vm.globals[crc(EXTRA)].values())==sorted(set(range(1,12))-set(preset))
    vm.page=1;vm.run('CosmicAlienUpdate');assert vm.slots()==preset,'Must wait for both resources'
    vm.complete();assert vm.globals[crc(READY)] is True
    vm.run('CosmicAlienUpdate');assert vm.slots()==[vm.globals[crc(EXTRA)][i] for i in range(1,5)]
    vm.page=2;vm.run('CosmicAlienUpdate');assert vm.slots()==[vm.globals[crc(EXTRA)][i] for i in range(5,8)]+[None]
    vm.run('CosmicAlienUpdate');assert len([e for e in vm.events if e[0]=='sound'])==2,'No held-trigger sound spam'
    vm.page=0;vm.run('CosmicAlienUpdate');assert vm.slots()==preset
    vm.page=1;vm.run('CosmicAlienUpdate');vm.page=-1;vm.run('CosmicAlienUpdate');assert vm.slots()==preset
    original_forms=copy.deepcopy(vm.globals[crc('gFormData')])
    vm.run('CosmicAlienUnload');assert vm.slots()==preset
    assert vm.globals[crc('gFormData')]==original_forms,'Do not destroy original form definitions'
    loaded=sorted(e[1:] for e in vm.events if e[0]=='load')
    unloaded=sorted(e[1:] for e in vm.events if e[0]=='unload')
    assert loaded==unloaded and len(loaded)==14
    assert vm.globals[crc(ACTIVE)] is None
    before=copy.deepcopy(vm.events);vm.run('CosmicAlienUnload');assert vm.events==before
    cases+=1
for preset in ([1,1,2,3],[None,1,2,3],[17,1,2,3]):
    vm=VM(preset);vm.page=0;vm.run('CosmicAlienUpdate')
    assert not vm.events and vm.slots()==preset;cases+=1
# A change made with the R3 form screen stays: the saved four follow it, and paging back returns to the changed four.
vm=VM([1,2,3,4]);vm.page=0;vm.run('CosmicAlienUpdate');vm.complete();vm.page=-1
vm.globals[crc('gFormHotKey')][1][crc('formID')]=9
vm.run('CosmicAlienUpdate');assert vm.slots()==[9,2,3,4],'R3 change must not be undone'
loads=lambda:[e for e in vm.events if e[0]=='load']
assert len(loads())==14 and vm.globals[crc(BASE)][1]==9,'the saved four take the change at once'
# Paging right after the swap must neither undo it nor skip it.
vm.page=1;vm.run('CosmicAlienUpdate');assert vm.slots()==[5,6,7,8],'extras must not repeat the current four'
vm.page=0;vm.run('CosmicAlienUpdate');assert vm.slots()==[9,2,3,4],'paging right after a swap keeps it'
assert len(loads())==14
n=0
while len(loads())==14 and n<400:
    vm.page=-1;vm.run('CosmicAlienUpdate');n+=1
assert 100<n<=200 and len(loads())==16,'a form that left the four is loaded again only after the change has settled'
assert vm.globals[crc(READY)] is False,'pages wait for the reload'
vm.page=1;vm.run('CosmicAlienUpdate');assert vm.slots()==[9,2,3,4],'pages wait while loading'
vm.complete();assert vm.globals[crc(READY)] is True
vm.run('CosmicAlienUpdate')
assert vm.slots()==[5,6,7,8],'extras must not repeat the current four'
vm.page=2;vm.run('CosmicAlienUpdate');assert vm.slots()==[10,11,1,None],'the swapped-out form is on the last page'
vm.page=0;vm.run('CosmicAlienUpdate');assert vm.slots()==[9,2,3,4],'paging back keeps the changed four'
unloads=lambda:[e for e in vm.events if e[0]=='unload']
vm.run('CosmicAlienUnload');assert not [e for e in unloads() if e[2]=='g_9'],'forms in the four are unloaded by the game'
assert [e for e in unloads() if e[2]=='g_1'],'the reloaded form is unloaded with the others'
assert [e for e in unloads() if e[2]=='g_5'],'the other extras are unloaded'
cases+=1
# Several swaps in a row, one of them undone: only the forms that really are out of the four come back.
vm=VM([1,2,3,4]);vm.page=0;vm.run('CosmicAlienUpdate');vm.complete();vm.page=-1
hot=vm.globals[crc('gFormHotKey')]
for slot,form in ((1,9),(2,10),(1,1)):
    hot[slot][crc('formID')]=form;vm.run('CosmicAlienUpdate')
n=0
while len([e for e in vm.events if e[0]=='load'])==14 and n<400:
    vm.run('CosmicAlienUpdate');n+=1
reloaded=[e[2] for e in vm.events if e[0]=='load'][14:]
assert vm.slots()==[1,10,3,4] and sorted(reloaded)==['atk_2','atk_9','g_2','g_9'],reloaded
cases+=1

import os
from pathlib import Path
# Fixtures stay outside the repository when testing the curated release source.
scripts=Path(os.environ.get('COSMIC_ORIGINAL_SCRIPTS',str(ROOT/'originals/global/scripts')))
original=(scripts/'globals.ds').read_bytes()
candidate=transform_globals(original)
old={h:(a,c) for h,a,c in records(original)};new={h:(a,c) for h,a,c in records(candidate)}
changed={h for h in old if old[h]!=new[h]}
assert changed=={crc('switch_form_update'),crc('destroy_form_switching'),0xa67003d2}
for h,(a,code) in new.items():
    w,tokens=decode(code);boundaries={p for p,k in tokens}|{len(w)}
    for p,k in tokens:
        if k in (0x1d,0x1e,0x1f):assert w[p]>>(8 if k==0x1d else 16) in boundaries
out=ROOT/'build/diagnostics/all-aliens-script-20261023'
out.mkdir(parents=True,exist_ok=True)
(out/'state-proof.json').write_text(json.dumps({'passed':True,'preset_cases':cases,
  'verified':['disabled preserves preset','loads only seven missing forms',
    'waits for fourteen resource callbacks','4+4+3 page mapping','one sound per change',
    'disable and mission exit restore preset','balanced data/descriptor references',
    'invalid presets refused','all original VM branch destinations remain token boundaries'],
  'real_gameplay_validated':False},indent=2))
print('Authored VM state/resource proof passed:',cases,'presets; real gameplay remains unverified.')
