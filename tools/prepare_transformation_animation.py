"""Opt-in manual Ben-to-alien animation, preserving the original switch."""
from prepare_all_aliens_candidate import Code,crc

TARGET='CosmicBenTransformTarget'
ACTOR='CosmicBenTransformActor'
REMAINING='CosmicBenTransformRemaining'
SETTLE='CosmicBenTransformSettle'
CLIP=0x7eefec3a
NORMAL_SWITCH=0x577e126c
SECONDS=6400/4800

def authored():
    rows=[]
    def add(name,args,c):rows.append((crc(name),args,c.finish()))

    c=Code()
    c.nil(1)
    for field in (TARGET,ACTOR,REMAINING,SETTLE):c.put(1,field)
    c.get(2,'overlay');c.false(2,'end')
    c.field(3,2,'cosmic_ben_transform_pending');c.false(3,'end')
    c.num(4,0);c.method(2,'cosmic_ben_transform_pending',[2,4])
    c.label('end');c.done()
    add('CosmicNormalTransformCancel',0,c)

    # Only the four ordinary wheel input branches call this wrapper.
    # Story-driven transformations, reverts and Hero Time retain their
    # original immediate code path.
    c=Code()
    c.get(1,TARGET);c.false(1,'new');c.done()
    c.label('new')
    c.native('cosmic_ben_transform_enabled',1)
    c.num(2,1);c.binary(0x10,3,1,2);c.false(3,'normal')
    c.get(1,'gCurrentCharacter');c.num(2,17)
    c.binary(0x10,3,1,2);c.false(3,'normal')
    c.get(1,'player');c.false(1,'normal')
    c.method(1,'person',[1],result=2);c.false(2,'normal')
    c.method(2,'isdead',[2],result=3);c.false(3,'alive');c.jump('normal')
    c.label('alive')
    c.field(3,2,'playanim');c.false(3,'normal')
    c.put(0,TARGET);c.put(2,ACTOR)
    c.num(4,SECONDS);c.put(4,REMAINING)
    c.get(5,'overlay');c.num(6,1)
    c.method(5,'cosmic_ben_transform_pending',[5,6])
    # Cosmic Destruction itself uses this three-argument Person.playanim
    # ABI. Do not import the newer Vilgax Attacks five-argument callback.
    # Neutralise the controller before invoking Person.playanim: the previous
    # locomotion update can otherwise overwrite a pose in the request frame.
    c.num(7,.12);c.put(7,SETTLE)
    c.done()
    c.label('normal')
    c.call(NORMAL_SWITCH,[0]);c.done()
    add('CosmicNormalTransformRequest',1,c)

    # Called at the existing post-pause/post-loading form update boundary.
    # Its return value consumes ordinary wheel input until completion.
    c=Code()
    c.get(0,TARGET);c.false(0,'idle')
    c.get(1,'gCurrentCharacter');c.num(2,17)
    c.binary(0x10,3,1,2);c.false(3,'cancel')
    c.get(1,'player');c.false(1,'cancel')
    c.method(1,'person',[1],result=2);c.false(2,'cancel')
    c.get(3,ACTOR);c.binary(0x10,4,2,3);c.false(4,'cancel')
    c.method(2,'isdead',[2],result=3);c.false(3,'alive');c.jump('cancel')
    c.label('alive')
    c.native('cosmic_ben_transform_enabled',1)
    c.num(2,1);c.binary(0x10,3,1,2);c.false(3,'commit')
    c.native('cosmic_ben_transform_delta',1)
    c.num(2,0);c.binary(0x13,3,1,2);c.false(3,'consumed')
    c.get(5,SETTLE);c.false(5,'playing')
    c.binary(0x0b,5,5,1);c.binary(0x13,3,5,2);c.false(3,'start_clip');c.put(5,SETTLE);c.jump('consumed')
    c.label('start_clip');c.nil(5);c.put(5,SETTLE);c.get(6,ACTOR);c.emit(7<<8|5,CLIP);c.num(8,1);c.method(6,'playanim',[6,7,8]);c.jump('consumed')
    c.label('playing')
    c.get(4,REMAINING);c.binary(0x0b,4,4,1);c.put(4,REMAINING)
    c.binary(0x13,3,4,2);c.false(3,'commit');c.jump('consumed')
    c.label('commit')
    c.call('CosmicNormalTransformCancel');c.call(NORMAL_SWITCH,[0]);c.jump('consumed')
    c.label('cancel')
    c.call('CosmicNormalTransformCancel')
    c.label('consumed')
    c.boolean(3,True);c.emit(0x322)
    c.label('idle')
    c.boolean(3,False);c.emit(0x322)
    add('CosmicNormalTransformUpdate',0,c)
    return rows
