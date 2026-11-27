"""Author an optional VM extension; transform only verified local game scripts.

The source contains our assembler and patch locations, not original game code.
Loading uses the original mission's loaddata/loaddesc and completion callbacks.
Private integration candidate: not a claim of gameplay compatibility.
"""
import hashlib
import json
from pathlib import Path
import struct
from prepare_pause_menu_extension import crc, records

ROOT=Path(__file__).resolve().parents[1]

class Code:
    def __init__(self):self.words=[];self.labels={};self.fixups=[]
    def emit(self,*words):self.words.extend(words);return self
    def label(self,name):
        if name in self.labels:raise ValueError('Duplicate label '+name)
        self.labels[name]=len(self.words)
    def get(self,r,name):self.emit(r<<8|7,crc(name) if isinstance(name,str) else name)
    def put(self,r,name):self.emit(r<<8|8,crc(name) if isinstance(name,str) else name)
    def num(self,r,n):self.emit(r<<8|3,struct.unpack('>I',struct.pack('>f',n))[0])
    def boolean(self,r,b):self.emit(int(b)<<16|r<<8|2)
    def nil(self,r):self.emit(r<<8|1)
    def table(self,r):self.emit(r<<8|0x16)
    def move(self,d,s):self.emit(d<<16|s<<8|6)
    def field(self,d,s,name):self.emit(d<<16|s<<8|0x17,crc(name) if isinstance(name,str) else name)
    def fieldput(self,s,name,v):self.emit(v<<16|s<<8|0x19,crc(name) if isinstance(name,str) else name)
    def index(self,d,a,k):self.emit(d<<24|k<<16|a<<8|0x18)
    def store(self,a,k,v):self.emit(v<<24|k<<16|a<<8|0x1a)
    def binary(self,op,d,l,r):self.emit(d<<24|r<<16|l<<8|op)
    def false(self,r,label):self.fixups.append((len(self.words),label,16));self.emit(r<<8|0x1f)
    def jump(self,label):self.fixups.append((len(self.words),label,8));self.emit(0x1d)
    def call(self,name,args=(),result=20):
        for i,r in enumerate(args):self.move(40+i,r)
        self.get(30,name);self.emit(len(args)<<24|40<<16|30<<8|0x20,result)
    def method(self,obj,name,args=(),result=20):
        for i,r in enumerate(args):self.move(40+i,r)
        self.field(30,obj,name);self.emit(len(args)<<24|40<<16|30<<8|0x20,result)
    def native(self,name,result=20):
        self.get(29,'overlay');self.method(29,name,[29],result)
    def done(self):self.emit(0x21)
    def finish(self):
        for position,label,shift in self.fixups:
            self.words[position]|=self.labels[label]<<shift
        return struct.pack('>'+str(len(self.words))+'I',*self.words)

BASE='cosmic_alien_base';EXTRA='cosmic_alien_extra';READY='cosmic_alien_ready'
PENDING='cosmic_alien_pending';PAGE='cosmic_alien_page';ACTIVE='cosmic_alien_active'
EXTRA_COUNT='cosmic_alien_extra_count'
REMOVED='cosmic_alien_removed'   # forms that left the player's four and are waiting to be loaded again
# Form IDs reserved for aliens imported from Vilgax Attacks (Chromastone first).
IMPORTED_FORMS=[20,21,22,23]

def authored(disable_rath=False,preload_resources=False,four_arms_probe=False,matrix_upgrades=False):
    if four_arms_probe and (disable_rath or not preload_resources):
        raise ValueError('Four Arms probe requires the current preload profile')
    identities=list(range(1,12))
    if four_arms_probe:identities.append(19)
    extra_count=len(identities)-4-int(disable_rath)
    # Forms imported from Vilgax Attacks join the roster only when installed.
    imported=IMPORTED_FORMS if four_arms_probe else []
    max_extra=extra_count+len(imported)+4   # room for forms that leave the player's four and become extras
    result=[]
    def save(name,args,c):c.done();result.append((crc(name),args,c.finish()))
    # Callback follows the original mission loader's completion convention.
    c=Code();c.get(1,PENDING);c.false(1,'end');c.num(2,0)
    c.binary(0x13,3,1,2);c.false(3,'end');c.num(2,1)
    c.binary(0x0b,1,1,2);c.put(1,PENDING);c.num(2,0)
    c.binary(0x10,3,1,2);c.false(3,'notify_mission' if preload_resources else 'end');c.boolean(1,True);c.put(1,READY)
    if preload_resources:
        c.label('notify_mission')
        c.call(0x27d93546,[0])
        # Keep only one extra form's data/descriptor pair in flight.
        c.get(1,PENDING);c.num(2,0);c.binary(0x13,3,1,2);c.false(3,'end')
        c.get(2,'cosmic_alien_pair_pending');c.num(3,1);c.binary(0x0b,2,2,3)
        c.put(2,'cosmic_alien_pair_pending');c.num(3,0);c.binary(0x10,3,2,3)
        c.false(3,'end');c.call('CosmicAlienNext')
    c.label('end');save('CosmicAlienLoaded',1,c)

    c=Code();c.get(0,BASE);c.false(0,'end');c.get(1,'gFormHotKey')
    for i in range(1,5):
        c.num(2,i);c.index(3,0,2);c.index(4,1,2);c.fieldput(4,'formID',3)
    c.num(1,0);c.put(1,PAGE);c.label('end');save('CosmicAlienRestore',0,c)

    c=Code()
    if preload_resources:
        if matrix_upgrades:
            # Preload existing forms at the original safe mission-load
            # boundary, including when the player purchases tier 5 later
            # in this mission. The wheel input remains entitlement-gated.
            c.call('CosmicMasterControlSync')
        else:
            c.native('cosmic_all_aliens_enabled',15);c.num(14,1)
            c.binary(0x10,14,15,14);c.false(14,'end')
        c.get(13,ACTIVE);c.false(13,'start');c.jump('end');c.label('start')
        c.get(16,0x1729d192);c.false(16,'end');c.num(17,0)
        c.binary(0x13,17,16,17);c.false(17,'end')
    c.get(0,'gFormHotKey');c.false(0,'end')
    if disable_rath:
        c.call(0xe1003dc4,result=12);c.field(12,12,'Rath')
    # Refuse an incomplete/duplicate preset rather than guessing its semantics.
    for i in range(4):
        c.num(1,i+1);c.index(2,0,1);c.field(4+i,2,'formID');c.false(4+i,'end')
        c.num(1,0);c.binary(0x13,2,4+i,1);c.false(2,'end')
        c.num(1,12);c.binary(0x12,2,4+i,1)
        if four_arms_probe:
            c.false(2,'probe_form'+str(i));c.jump('valid_form'+str(i))
            c.label('probe_form'+str(i));c.num(1,19);c.binary(0x10,2,4+i,1)
        c.false(2,'end')
        if four_arms_probe:c.label('valid_form'+str(i))
        if disable_rath:c.binary(0x11,2,4+i,12);c.false(2,'end')
        for j in range(i):c.binary(0x11,2,4+i,4+j);c.false(2,'end')
    c.table(0);c.put(0,BASE)
    for i in range(4):c.num(1,i+1);c.store(0,1,4+i)
    c.table(0);c.put(0,EXTRA);c.num(8,1)
    for identity in identities:
        c.num(1,identity)
        if disable_rath:c.binary(0x11,2,1,12);c.false(2,'skip'+str(identity))
        for i in range(4):c.binary(0x11,2,1,4+i);c.false(2,'skip'+str(identity))
        c.store(0,8,1);c.num(2,1);c.binary(0x0a,8,8,2);c.label('skip'+str(identity))
    for identity in imported:
        c.num(1,identity);c.get(9,'gFormData');c.index(10,9,1);c.false(10,'skip'+str(identity))
        for i in range(4):c.binary(0x11,2,1,4+i);c.false(2,'skip'+str(identity))
        c.store(0,8,1);c.num(2,1);c.binary(0x0a,8,8,2);c.label('skip'+str(identity))
    if imported:
        c.num(2,1);c.binary(0x0b,9,8,2);c.put(9,EXTRA_COUNT)
        c.num(2,2);c.binary(0x0c,1,9,2);c.put(1,PENDING)
    else:c.num(1,extra_count*2);c.put(1,PENDING)
    c.boolean(1,False);c.put(1,READY)
    if preload_resources:
        c.get(1,PENDING);c.binary(0x0a,16,16,1);c.put(16,0x1729d192)
    c.boolean(1,True);c.put(1,ACTIVE);c.num(1,0);c.put(1,PAGE)
    if preload_resources:
        c.num(1,1);c.put(1,'cosmic_alien_next');c.call('CosmicAlienNext')
        c.jump('end')
    c.get(1,0xf3d407b1);c.method(1,'getcurrentmission',[1],2)
    c.get(3,EXTRA);c.get(4,'gFormData');c.get(5,'CosmicAlienLoaded')
    for i in range(1,extra_count+1):
        c.num(6,i);c.index(7,3,6);c.index(8,4,7)
        c.get(9,0x0bfbfd2d);c.field(10,8,'characterFile')
        c.method(2,0xbc35779c,[2,9,10,5])
        c.get(9,0x79c61e79);c.field(10,8,0x7fb535f8)
        c.method(2,0x1a7328ab,[2,9,10,5])
    c.label('end');save('CosmicAlienLoad',0,c)

    if preload_resources:
        c=Code();c.get(6,'cosmic_alien_next')
        if imported:c.get(1,EXTRA_COUNT);c.num(2,1);c.binary(0x0a,1,1,2)
        else:c.num(1,extra_count+1)
        c.binary(0x12,2,6,1);c.false(2,'end')
        c.num(1,1);c.binary(0x0a,1,6,1);c.put(1,'cosmic_alien_next')
        c.num(1,2);c.put(1,'cosmic_alien_pair_pending')
        c.get(1,0xf3d407b1);c.method(1,'getcurrentmission',[1],2)
        c.get(3,EXTRA);c.index(7,3,6);c.get(4,'gFormData');c.index(8,4,7)
        c.get(5,'CosmicAlienLoaded');c.get(9,0x0bfbfd2d);c.field(10,8,'characterFile')
        c.method(2,0xbc35779c,[2,9,10,5])
        c.get(9,0x79c61e79);c.field(10,8,0x7fb535f8)
        c.method(2,0x1a7328ab,[2,9,10,5])
        c.label('end');save('CosmicAlienNext',0,c)

    c=Code();c.get(0,ACTIVE);c.false(0,'end');c.call('CosmicAlienRestore')
    c.get(1,0xf3d407b1);c.method(1,'getcurrentmission',[1],2)
    c.get(3,EXTRA);c.get(4,'gFormData');c.get(25,BASE)
    for i in range(1,max_extra+1):
        c.num(6,i);c.index(7,3,6)
        c.false(7,'unloaded')
        # A form that is in the player's four now is unloaded by the game itself with the four.
        for j in range(1,5):
            c.num(26,j);c.index(27,25,26);c.binary(0x10,28,7,27)
            c.false(28,'not_in_four_%d_%d'%(i,j));c.jump('skip_unload_'+str(i));c.label('not_in_four_%d_%d'%(i,j))
        c.index(8,4,7)
        c.get(9,0x93aca275);c.field(10,8,'character')
        c.method(9,'removecharacter',[9,10])
        c.get(9,0x0bfbfd2d);c.field(10,8,'characterFile');c.boolean(11,True)
        c.method(2,'unloaddata',[2,9,10,11])
        c.get(9,0x79c61e79);c.field(10,8,0x7fb535f8)
        c.method(2,'unloaddesc',[2,9,10])
        c.label('skip_unload_'+str(i))
    c.label('unloaded')
    for name in [BASE,EXTRA,READY,PENDING,PAGE,ACTIVE,REMOVED]+([EXTRA_COUNT] if imported else []):c.nil(1);c.put(1,name)
    c.label('end');save('CosmicAlienUnload',0,c)

    # The saved four slots (BASE) follow whatever the player sets with the R3 form screen. Restoring them every frame
    # would undo that change in the slot table while the game has already loaded the new form in place of the old one,
    # so the old form's data is gone when its slot is used.
    # Keeps the saved four equal to the player's own four. Once a change has stood for a while (the game has finished
    # unloading the form that was swapped out) every form that left the four is loaded again as an extra, so it can be
    # paged to; its data is gone after the swap.
    c=Code();c.get(0,BASE);c.false(0,'end');c.get(1,'gFormHotKey');c.false(1,'end')
    c.boolean(12,False)
    for i in range(1,5):
        c.num(2,i);c.index(4,1,2);c.false(4,'end');c.field(3,4,'formID');c.false(3,'end')
        c.index(5,0,2);c.binary(0x11,6,3,5);c.false(6,'same_'+str(i));c.boolean(12,True);c.label('same_'+str(i))
    c.false(12,'idle')
    # A change: the saved four take it at once (paging must never put the old four back), the forms that left are queued
    # and the wait before they are loaded again starts over.
    c.get(13,REMOVED);c.false(13,'new_queue');c.jump('have_queue')
    c.label('new_queue');c.table(13);c.put(13,REMOVED);c.label('have_queue')
    for i in range(1,5):
        c.num(2,i);c.index(5,0,2)
        for j in range(1,5):
            c.num(2,j);c.index(4,1,2);c.field(3,4,'formID');c.binary(0x10,6,5,3)
            c.false(6,'differs_%d_%d'%(i,j));c.jump('kept_'+str(i));c.label('differs_%d_%d'%(i,j))
        for k in range(1,9):
            c.num(14,k);c.index(15,13,14);c.false(15,'put_%d_%d'%(i,k))
            c.binary(0x10,16,15,5);c.false(16,'next_%d_%d'%(i,k));c.jump('kept_'+str(i))
            c.label('put_%d_%d'%(i,k));c.store(13,14,5);c.jump('kept_'+str(i))
            c.label('next_%d_%d'%(i,k))
        c.label('kept_'+str(i))
    for i in range(1,5):
        c.num(2,i);c.index(4,1,2);c.field(3,4,'formID');c.store(0,2,3)
    c.num(7,0);c.put(7,'cosmic_alien_swap_wait');c.jump('end')
    c.label('idle')
    c.get(13,REMOVED);c.false(13,'end')
    c.get(7,'cosmic_alien_swap_wait');c.false(7,'init_wait');c.jump('have_wait')
    c.label('init_wait');c.num(7,0);c.label('have_wait')
    c.num(8,1);c.binary(0x0a,7,7,8);c.put(7,'cosmic_alien_swap_wait')
    c.num(8,150);c.binary(0x12,9,7,8);c.false(9,'due');c.jump('end')
    c.label('due')
    for k in range(1,9):
        c.num(14,k);c.index(5,13,14);c.false(5,'queue_done')
        for j in range(1,5):
            c.num(2,j);c.index(4,0,2);c.binary(0x10,6,5,4);c.false(6,'not_four_%d_%d'%(k,j));c.jump('skip_%d'%k)
            c.label('not_four_%d_%d'%(k,j))
        c.call('CosmicAlienReload',[5])
        c.label('skip_%d'%k)
    c.label('queue_done');c.nil(13);c.put(13,REMOVED);c.num(7,0);c.put(7,'cosmic_alien_swap_wait')
    c.label('end');save('CosmicAlienFollow',0,c)

    # Load one form again after it left the four and make sure it is on the extras list. Uses the original loader and a
    # callback that, unlike the mission-load one, does not report to the mission loader.
    c=Code();c.get(1,EXTRA);c.false(1,'end')
    for k in range(1,max_extra+1):
        c.num(2,k);c.index(3,1,2);c.false(3,'append_'+str(k))
        c.binary(0x10,4,3,0);c.false(4,'next_'+str(k));c.jump('have')
        c.label('append_'+str(k));c.store(1,2,0);c.jump('have')
        c.label('next_'+str(k))
    c.jump('end')
    c.label('have')
    c.get(4,'gFormData');c.index(8,4,0);c.false(8,'end')
    c.get(5,PENDING);c.false(5,'no_pending');c.jump('has_pending')
    c.label('no_pending');c.num(5,0)
    c.label('has_pending');c.num(6,2);c.binary(0x0a,5,5,6);c.put(5,PENDING)
    c.boolean(6,False);c.put(6,READY)
    c.get(1,0xf3d407b1);c.method(1,'getcurrentmission',[1],2)
    c.get(5,'CosmicAlienLateLoaded')
    c.get(9,0x0bfbfd2d);c.field(10,8,'characterFile')
    c.method(2,0xbc35779c,[2,9,10,5])
    c.get(9,0x79c61e79);c.field(10,8,0x7fb535f8)
    c.method(2,0x1a7328ab,[2,9,10,5])
    c.label('end');save('CosmicAlienReload',1,c)

    c=Code();c.get(1,PENDING);c.false(1,'end');c.num(2,0);c.binary(0x13,3,1,2);c.false(3,'end')
    c.num(2,1);c.binary(0x0b,1,1,2);c.put(1,PENDING);c.num(2,0);c.binary(0x10,3,1,2);c.false(3,'end')
    c.boolean(1,True);c.put(1,READY)
    c.label('end');save('CosmicAlienLateLoaded',1,c)

    c=Code();c.native('cosmic_all_aliens_page',0)
    c.num(1,0);c.binary(0x12,2,0,1);c.false(2,'enabled')
    # No paging input: while the player's own four are showing, keep the saved four equal to them; only a page that
    # is currently showing extras is put back.
    c.get(3,ACTIVE);c.false(3,'end');c.get(3,PAGE);c.num(4,0);c.binary(0x13,5,3,4);c.false(5,'follow')
    c.get(1,BASE);c.false(1,'end');c.call('CosmicAlienRestore');c.jump('end')
    c.label('follow');c.call('CosmicAlienFollow');c.jump('end')
    c.label('enabled');c.get(1,ACTIVE);c.false(1,'load');c.jump('ready')
    c.label('load')
    if not preload_resources:c.call('CosmicAlienLoad')
    c.jump('end')
    c.label('ready');c.get(1,READY);c.false(1,'end');c.get(1,PAGE)
    c.binary(0x11,2,0,1);c.false(2,'same_page');c.put(0,PAGE)
    c.num(1,0);c.binary(0x10,2,0,1);c.false(2,'extras')
    c.call('CosmicAlienRestore');c.jump('sound')
    # The extras on offer are the loaded ones that are not among the player's current four (BASE), so a form moved
    # into the four with the R3 screen leaves the pages. A form moved out comes back with the next mission load,
    # because its data is not loaded until then.
    c.label('extras');c.get(9,EXTRA);c.get(10,BASE);c.table(1);c.num(11,1)
    for idx in range(1,max_extra+1):
        keep='keep_extra_'+str(idx);skip='skip_extra_'+str(idx)
        c.num(12,idx);c.index(13,9,12);c.false(13,skip)
        for j in range(1,5):
            c.num(14,j);c.index(15,10,14);c.binary(0x10,16,13,15);c.false(16,keep+'_'+str(j));c.jump(skip)
            c.label(keep+'_'+str(j))
        c.store(1,11,13);c.num(12,1);c.binary(0x0a,11,11,12)
        c.label(skip)
    c.get(2,'gFormHotKey')
    c.num(3,1);c.binary(0x0b,4,0,3);c.num(3,4);c.binary(0x0c,4,4,3)
    for i in range(1,5):
        c.num(3,i);c.binary(0x0a,5,4,3);c.index(6,1,5)
        if matrix_upgrades:
            c.call('CosmicMatrixAllows',[6],result=8)
            c.false(8,'locked_slot_'+str(i));c.jump('slot_ready_'+str(i))
            c.label('locked_slot_'+str(i));c.nil(6)
            c.label('slot_ready_'+str(i))
        c.index(7,2,3);c.fieldput(7,'formID',6)
    c.label('sound');c.get(1,0x2712f51f);c.emit(2<<8|5,0xf4b7b9fd)
    c.method(1,0x5e89deba,[1,2]);c.native('cosmic_all_aliens_trace')
    c.jump('end')
    c.label('same_page');c.num(1,0);c.binary(0x10,2,0,1);c.false(2,'end');c.call('CosmicAlienFollow')
    c.label('end');save('CosmicAlienUpdate',0,c)
    return result

def decode(code):
    words=list(struct.unpack('>'+str(len(code)//4)+'I',code));result=[];i=0
    while i<len(words):
        kind=words[i]&255;size=2 if kind in (3,5,7,8,0x17,0x19,0x20) else 1
        if kind==4:
            end=code.index(b'\0',i*4+4)+1;size=((end-i*4+3)//4)
        elif not 1<=kind<=0x22:raise ValueError(f'Unexpected opcode {kind:x} at {i}')
        if i+size>len(words):raise ValueError('Truncated VM token')
        result.append((i,kind));i+=size
    return words,result

def relocate(code,insertions):
    words,decoded=decode(code);boundaries={i for i,k in decoded}|{len(words)}
    if not set(insertions)<=boundaries:raise ValueError('Insertion inside VM token')
    def mapped(i):return i+sum(len(v) for k,v in insertions.items() if k<i)
    out=[]
    for i,kind in decoded:
        out.extend(insertions.get(i,[]));size=next((n-i for n,k in decoded if n>i),len(words)-i)
        value=words[i]
        if kind in (0x1d,0x1e,0x1f):
            shift=8 if kind==0x1d else 16;target=value>>shift
            if target not in boundaries:raise ValueError('Invalid original VM branch')
            value=(value&((1<<shift)-1))|(mapped(target)<<shift)
        out.extend([value,*words[i+1:i+size]])
    out.extend(insertions.get(len(words),[]))
    return struct.pack('>'+str(len(out))+'I',*out)

def encode(rows):
    out=bytearray(struct.pack('>II',0x1badbabe,len(rows)))
    for h,a,c in rows:out.extend(struct.pack('>III',h,a,len(c)//4));out.extend(c)
    records(out);return bytes(out)

def hook(name):return [0x00001b07,crc(name),0x00281b20,3]

def transform_globals(blob,preload_resources=False):
    rows=[]
    for h,a,c in records(blob):
        if h==crc('switch_form_update'):c=relocate(c,{34:hook('CosmicAlienUpdate')})
        if h==crc('destroy_form_switching'):c=relocate(c,{0:hook('CosmicAlienUnload')})
        if h==0xa67003d2:c=relocate(c,{0:hook('CosmicAlienRestore')})
        if preload_resources and h==0xaac6a726:c=relocate(c,{87:hook('CosmicAlienLoad')})
        rows.append((h,a,c))
    return encode(rows+authored(preload_resources=preload_resources))

def main():
    source=ROOT/'originals/global/scripts';out=ROOT/'build/diagnostics/all-aliens-script-20261023'
    out.mkdir(parents=True,exist_ok=True)
    original=(source/'globals.ds').read_bytes();candidate=transform_globals(original)
    (out/'globals.ds').write_bytes(candidate)
    report={'original_sha256':hashlib.sha256(original).hexdigest(),
            'candidate_sha256':hashlib.sha256(candidate).hexdigest(),
            'authored_functions':len(authored()),'gameplay_validated':False,
            'installed':False,'release_eligible':False,
            'remaining':['Blank fourth slot HUD/input guards','Gameplay menu toggle','Resource lifetime gameplay test','Audible sound verification']}
    (out/'prepared.json').write_text(json.dumps(report,indent=2))
    # Only our authored functions are embedded; original game instructions are
    # transformed from the user's verified scripts at installation time.
    (ROOT/'launcher/AllAliensProgram.bin').write_bytes(encode(authored()))
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--program-only',action='store_true',help='Build only authored bytecode; no game files are read')
    arguments=parser.parse_args()
    if arguments.program_only:
        (ROOT/'launcher/AllAliensProgram.bin').write_bytes(encode(authored()))
        print('Authored All Aliens program generated without reading game data.')
    else:main()
