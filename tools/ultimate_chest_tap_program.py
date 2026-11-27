"""Approved chest tap entry and delay for the existing Hero Time transaction."""
from prepare_all_aliens_candidate import Code,crc
SOURCE='cosmic_ultimate_tap_source'; ACTOR='cosmic_ultimate_tap_actor'; TIMER='cosmic_ultimate_tap_timer'
WAY_TIMER='cosmic_way_big_tap_timer'; WAY_ACTOR='cosmic_way_big_tap_actor'
SETTLE='cosmic_ultimate_tap_settle'; TAP_CLIP='cosmic_ultimate_tap_clip'; WAY_SETTLE='cosmic_way_big_tap_settle'
CLIPS={1:0xca7b0c29,2:0x634dc7b3,3:0x315b94f9,4:0x5da9d5a1,5:0x7e1a023e,23:0x100603e9}
SECONDS=.8

def pending(c,value):
    c.get(10,'overlay');c.num(11,value);c.method(10,'cosmic_ben_transform_pending',[10,11])

def clear(c,fields):
    c.nil(9)
    for field in fields:c.put(9,field)
    pending(c,0)

def ret(c,r,value):c.boolean(r,value);c.emit(r<<8|0x22)

def authored():
    rows=[]
    def add(name,args,c):rows.append((crc(name),args,c.finish()))
    c=Code();c.get(1,TIMER);c.false(1,'way');clear(c,(SOURCE,ACTOR,TIMER,SETTLE,TAP_CLIP));c.label('way');c.get(1,WAY_TIMER);c.false(1,'end');clear(c,(WAY_TIMER,WAY_ACTOR,WAY_SETTLE));c.label('end');c.done();add('CosmicUltimateTapCancel',0,c)

    c=Code();c.native('cosmic_ben_transform_enabled',0);c.num(1,1);c.binary(0x10,2,0,1);c.false(2,'no')
    c.get(1,'gCurrentCharacter');c.get(2,'player');c.false(2,'no');c.method(2,'person',[2],result=3);c.false(3,'no');c.field(4,3,'playanim');c.false(4,'no')
    for normal,key in CLIPS.items():
        c.num(4,normal);c.binary(0x10,5,1,4);c.false(5,'next'+str(normal));c.emit(6<<8|5,key);c.jump('start');c.label('next'+str(normal))
    c.jump('no');c.label('start');c.put(1,SOURCE);c.put(3,ACTOR);c.put(6,TAP_CLIP);c.num(4,SECONDS);c.put(4,TIMER);c.num(4,.12);c.put(4,SETTLE);c.num(4,5);c.put(4,'cosmic_hero_phase');pending(c,1);ret(c,1,True)
    c.label('no');ret(c,1,False);add('CosmicUltimateTapBegin',0,c)

    c=Code();c.get(0,TIMER);c.false(0,'cancel');c.get(1,'gCurrentCharacter');c.get(2,SOURCE);c.binary(0x10,3,1,2);c.false(3,'cancel')
    c.get(1,'player');c.false(1,'cancel');c.method(1,'person',[1],result=2);c.false(2,'cancel');c.get(3,ACTOR);c.binary(0x10,4,2,3);c.false(4,'cancel');c.method(2,'isdead',[2],result=3);c.false(3,'alive');c.jump('cancel')
    c.label('alive');c.native('cosmic_hero_delta',4);c.num(1,0);c.binary(0x13,3,4,1);c.false(3,'wait');c.get(5,SETTLE);c.false(5,'playing');c.binary(0x0b,5,5,4);c.binary(0x13,3,5,1);c.false(3,'start_clip');c.put(5,SETTLE);c.done()
    c.label('start_clip');c.nil(5);c.put(5,SETTLE);c.get(6,TAP_CLIP);c.num(7,1);c.method(2,'playanim',[2,6,7]);c.done()
    c.label('playing');c.get(0,TIMER);c.binary(0x0b,0,0,4);c.binary(0x13,2,0,1);c.false(2,'commit');c.put(0,TIMER);c.label('wait');c.done()
    c.label('commit');clear(c,(SOURCE,ACTOR,TIMER,SETTLE,TAP_CLIP));c.num(1,1);c.put(1,'cosmic_hero_phase');c.call('switch_to_ultimate');c.call('CosmicHeroFlash');c.done()
    c.label('cancel');clear(c,(SOURCE,ACTOR,TIMER,SETTLE,TAP_CLIP));c.num(1,0);c.put(1,'cosmic_hero_phase');c.nil(1);c.put(1,'cosmic_hero_target');c.done();add('CosmicUltimateTapAdvance',0,c)

    # Way Big uses the separate Final Battle transaction. Its existing
    # callback is re-queued only while this short gesture is pending.
    c=Code();c.get(1,WAY_TIMER);c.false(1,'new');c.get(2,WAY_ACTOR);c.binary(0x10,3,2,0);c.false(3,'cancel')
    c.native('cosmic_ben_transform_delta',2);c.num(3,0);c.binary(0x13,4,2,3);c.false(4,'wait');c.get(5,WAY_SETTLE);c.false(5,'playing');c.binary(0x0b,5,5,2);c.binary(0x13,4,5,3);c.false(4,'start_clip');c.put(5,WAY_SETTLE);ret(c,1,False)
    c.label('start_clip');c.nil(5);c.put(5,WAY_SETTLE);c.emit(2<<8|5,0xd710a7bc);c.num(3,1);c.method(0,'playanim',[0,2,3]);ret(c,1,False)
    c.label('playing');c.get(1,WAY_TIMER);c.binary(0x0b,1,1,2);c.binary(0x13,4,1,3);c.false(4,'commit');c.put(1,WAY_TIMER);c.label('wait');ret(c,1,False)
    c.label('commit');clear(c,(WAY_TIMER,WAY_ACTOR,WAY_SETTLE));ret(c,1,True)
    c.label('cancel');clear(c,(WAY_TIMER,WAY_ACTOR,WAY_SETTLE));ret(c,1,False)
    c.label('new');c.native('cosmic_ben_transform_enabled',1);c.num(2,1);c.binary(0x10,3,1,2);c.false(3,'immediate');c.field(1,0,'playanim');c.false(1,'immediate');c.put(0,WAY_ACTOR);c.num(1,SECONDS);c.put(1,WAY_TIMER);c.num(1,.12);c.put(1,WAY_SETTLE);pending(c,1);ret(c,1,False)
    c.label('immediate');ret(c,1,True);add('CosmicWayBigTapGate',1,c)
    return rows
