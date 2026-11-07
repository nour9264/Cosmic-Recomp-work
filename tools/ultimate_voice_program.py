"""Authored additions only; game instructions/audio are never embedded."""
from prepare_all_aliens_candidate import Code, crc

# Verified against the original mission-specific VO resolver functions.
EVENTS={12:0xa0f9f55e,13:0xb4ca7f6e,14:0x4e411e8d,15:0xba4be767,16:0x3fc58ea9}
SOUNDS={12:'ult_swampfire_name_callout_01',13:'ult_humongousaur_name_callout_01',
        14:'ult_echoecho_name_callout_01',15:'ult_spidermonkey_name_callout_01',16:'ult_bigchill_name_callout_01'}
OBSERVED='cosmic_hero_voice_observed'

def resolver():
    c=Code();c.move(10,0);c.move(11,1)
    for form,event in EVENTS.items():
        c.emit(1<<8|5,event);c.binary(0x10,2,0,1);c.false(2,'next'+str(form))
        c.emit(3<<8|5,crc(SOUNDS[form]));c.emit(3<<8|0x22);c.label('next'+str(form))
    c.call('CosmicOriginalUltimateVoiceResolver',[10,11],20);c.emit(20<<8|0x22);c.done()
    return [(0xe8c0396d,2,c.finish())]

def hero_functions():
    c=Code();c.get(0,'cosmic_hero_phase');c.num(1,1);c.binary(0x10,2,0,1);c.false(2,'end')
    c.boolean(0,True);c.put(0,OBSERVED);c.label('end');c.done()
    result=[(crc('CosmicHeroObserveVoice'),0,c.finish())]
    c=Code();c.get(0,OBSERVED);c.false(0,'missing');c.jump('end');c.label('missing')
    c.get(0,'player');c.false(0,'end');c.get(1,'cosmic_hero_target')
    for form,event in EVENTS.items():
        c.num(2,form);c.binary(0x10,3,1,2);c.false(3,'next'+str(form))
        c.emit(4<<8|5,event);c.get(5,0x2a9e34cc);c.boolean(6,False)
        c.boolean(7,True);c.put(7,OBSERVED)
        c.method(0,'playvo',[0,4,5,6]);c.jump('end');c.label('next'+str(form))
    c.label('end');c.done();result.append((crc('CosmicHeroCallout'),0,c.finish()))
    return result
