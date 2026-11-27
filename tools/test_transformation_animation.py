"""Exercise the actual authored Ben transformation state machine."""
from prepare_all_aliens_candidate import crc
from prepare_transformation_animation import authored,CLIP,TARGET,ACTOR,REMAINING,NORMAL_SWITCH
from test_all_aliens_script import VM

vm=VM([1,2,3,4])
vm.functions.update({k:(a,c) for k,a,c in authored()})
vm.globals.update({k:k for k,_,_ in authored()})
enabled=[0];dt=[0.1];dead=[False];events=[]
overlay=vm.globals[crc('overlay')]
overlay.update({
    crc('cosmic_ben_transform_enabled'):lambda *_:enabled[0],
    crc('cosmic_ben_transform_delta'):lambda *_:dt[0],
    crc('cosmic_ben_transform_pending'):lambda _,v:events.append(('pending',v))})
actor={crc('isdead'):lambda _:dead[0],
    crc('playanim'):lambda _,clip,speed:events.append(('play',clip,speed))}
vm.globals[crc('player')]={crc('person'):lambda _:actor}
vm.globals[crc('gCurrentCharacter')]=17
vm.globals[NORMAL_SWITCH]=lambda target:events.append(('switch',target))
run=lambda name,*args:vm.run(name,args)
run('CosmicNormalTransformRequest',3)
assert events==[('switch',3)] and not run('CosmicNormalTransformUpdate')
events.clear();enabled[0]=1
run('CosmicNormalTransformRequest',4)
assert events==[('pending',1)]
run('CosmicNormalTransformRequest',5)
assert len(events)==1
dt[0]=0
assert run('CosmicNormalTransformUpdate') and len(events)==1
dt[0]=.1
assert run('CosmicNormalTransformUpdate') and len(events)==1
assert run('CosmicNormalTransformUpdate') and events==[('pending',1),('play',CLIP,1)]
for _ in range(13):assert run('CosmicNormalTransformUpdate') and len(events)==2
assert run('CosmicNormalTransformUpdate')
assert events==[('pending',1),('play',CLIP,1),('pending',0),('switch',4)]
assert not run('CosmicNormalTransformUpdate')
events.clear()
# Alien-to-alien remains instantaneous.
vm.globals[crc('gCurrentCharacter')]=3
run('CosmicNormalTransformRequest',5)
assert events==[('switch',5)]
events.clear();vm.globals[crc('gCurrentCharacter')]=17
run('CosmicNormalTransformRequest',1);dead[0]=True
assert run('CosmicNormalTransformUpdate')
assert events[-1]==('pending',0) and not any(e[0]=='switch' for e in events)
assert vm.globals[crc(TARGET)] is None
dead[0]=False;events.clear()
run('CosmicNormalTransformRequest',2);run('CosmicNormalTransformCancel')
assert vm.globals[crc(TARGET)] is None and vm.globals[crc(ACTOR)] is None
assert not run('CosmicNormalTransformUpdate')
assert not any(e[0]=='switch' for e in events)
print('Ben transformation VM: OFF, ON, duplicate prevention, pause, actor/death cancellation, unload passed.')
