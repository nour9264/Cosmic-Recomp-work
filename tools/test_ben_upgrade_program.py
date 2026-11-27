"""Run the Ben upgrade bytecode in the same VM model as the roster tests."""
import math

from prepare_all_aliens_candidate import crc, decode, records
from prepare_ben_upgrades import (
    AVAILABLE_POINTS, HUD_SETUP, PLAYER_SETUP, SPENT_POINTS, UPGRADES,
    ORIGINAL_SELECT_TICK, UPGRADE_SELECT_TICK, authored, transform_circular_display,
    transform_globals,
)
from prepare_hero_time_candidate import transform_globals as hero_globals
from test_all_aliens_script import VM, scripts


def main():
    vm = VM([1, 2, 3, 4])
    vm.functions.update({key: (arguments, code) for key, arguments, code in authored()})
    vm.globals.update({key: key for key in vm.functions})

    def run(name, *args):
        return vm.run(name, args)

    assert run('CosmicGetBenHealthTier') == 0
    assert not run('CosmicBuyBenHealth', 0)
    balance = {AVAILABLE_POINTS: 150000, SPENT_POINTS: 0}
    vm.globals[UPGRADES] = balance
    assert run('CosmicBuyBenHealth', 0)
    assert not run('CosmicBuyBenHealth', 0)
    assert run('CosmicBuyBenHealth', 1)
    assert run('CosmicBuyBenEnergy', 0)
    assert run('CosmicGetBenHealthTier') == 2
    assert run('CosmicGetBenEnergyTier') == 1
    assert balance[AVAILABLE_POINTS] == 90000 and balance[SPENT_POINTS] == 60000
    assert run('CosmicBenHealthArc', 53) == 69
    assert run('CosmicBenEnergyArc', 53) == 61
    assert run('CosmicBuyBenHealth', 2)
    assert not run('CosmicBuyBenHealth', 3)
    assert run('CosmicBuyBenEnergy', 1)
    assert not run('CosmicBuyBenEnergy', 2)
    assert balance[AVAILABLE_POINTS] == 15000 and balance[SPENT_POINTS] == 135000

    stats = {'health': [1.5, .75], 'energy': [100, 25]}
    actor = {}
    for name, values in stats.items():
        actor[crc('get' + name)] = lambda _, bar=values: bar[1]
        actor[crc('getmax' + name)] = lambda _, bar=values: bar[0]
        actor[crc('set' + name)] = lambda _, value, bar=values: bar.__setitem__(1, value)
    actor[crc('addmaxhealth')] = lambda _, delta: stats['health'].__setitem__(0, stats['health'][0] + delta)
    actor[crc('setmaxenergy')] = lambda _, value: stats['energy'].__setitem__(0, value)
    for _ in range(3):
        run('CosmicApplyBenHealth', actor, 1.5)
        run('CosmicApplyBenEnergy', actor, 100)
    for stat, expected in {'health': (2.4, 1.2), 'energy': (140, 35)}.items():
        assert all(math.isclose(a, b, rel_tol=1e-6) for a, b in zip(stats[stat], expected))

    stock_values = {'health': (1.5, .75), 'energy': (100, 25)}
    for stat, values in stock_values.items():
        stats[stat][:] = values
    vm.globals[crc('player')] = {crc('person'): lambda _: actor}
    run('CosmicBenCaptureStockVitals')
    first_apply = {stat: values.copy() for stat, values in stats.items()}
    run('CosmicBenCaptureStockVitals')
    run('CosmicBenRefreshVitals')
    assert stats == first_apply
    run('CosmicBenClearStockVitals')
    for stat, values in stock_values.items():
        stats[stat][:] = values
    run('CosmicBenCaptureStockVitals')
    assert stats == first_apply

    # Same actor reused by a different form: capacity applies exactly once.
    vm.globals[crc('gCurrentCharacter')] = 1
    stats['health'][:] = [2, 2]
    stats['energy'][:] = [200, 200]
    balance[crc('CosmicBenEnergyTier')] = 3
    run('CosmicBenCaptureStockVitals')
    assert math.isclose(stats['energy'][0], 320, rel_tol=1e-6)
    # Returning to a cached form with already upgraded maxima must not compound.
    vm.globals[crc('gCurrentCharacter')] = 17
    stats['health'][:] = first_apply['health']
    stats['energy'][:] = first_apply['energy']
    run('CosmicBenCaptureStockVitals')
    assert math.isclose(stats['energy'][0], 160, rel_tol=1e-6)
    vm.globals[crc('gCurrentCharacter')] = 1
    stats['health'][:] = [3.2, 3.2]
    stats['energy'][:] = [320, 320]
    for _ in range(5): run('CosmicBenCaptureStockVitals')
    assert math.isclose(stats['energy'][0], 320, rel_tol=1e-6)
    # A fixed 20-unit special now consumes 6.25% instead of 10% of this form.
    assert math.isclose(20/stats['energy'][0], .0625, rel_tol=1e-6)

    # Progression uses the same purchase table as vitals, including old saves
    # with no matrix field, stale confirms, exact funds and the maximum tier.
    progression = {AVAILABLE_POINTS: 270000, SPENT_POINTS: 0}
    vm.globals[UPGRADES] = progression
    groups = ((11,), (19,), (20, 21, 22, 23), (12, 13, 14, 15, 16, 24, 25))
    assert run('CosmicGetBenMatrixTier') == 0
    master_control=[]
    vm.globals[crc('overlay')][crc('cosmic_master_control_sync')]=lambda _,tier,purchased: master_control.append((tier,purchased))
    for tier in range(7):
        for required, forms in enumerate(groups, 1):
            for form in forms:
                assert run('CosmicMatrixAllows', form) == (tier >= required)
        assert run('CosmicMatrixAllows', 1)
        # Real form IDs: 11 Rath, 19 Four Arms, 20 to 23 the Alien Force aliens; stock forms always pass.
        for form, required in ((1, 0), (10, 0), (11, 1), (19, 2), (20, 3), (21, 3), (22, 3), (23, 3)):
            assert run('CosmicRosterAllows', form) == (tier >= required), (tier, form)
        if tier < 6:
            assert run('CosmicBuyBenMatrix', tier)
            assert not run('CosmicBuyBenMatrix', tier)
    assert progression[AVAILABLE_POINTS] == 0 and progression[SPENT_POINTS] == 270000
    assert master_control==[(1,0),(2,0),(3,0),(4,0),(5,1),(6,0)]
    assert progression[crc('CosmicBenMatrixTier')]==106
    assert not run('CosmicBuyBenMatrix', 6)
    assert run('CosmicGetBenHealthTier') == 0
    vm.globals[UPGRADES] = {AVAILABLE_POINTS: 14999, SPENT_POINTS: 0}
    assert not run('CosmicBuyBenMatrix', 0)
    # Old tier 5 was cooldown, NOT paid Master Control. Preserve earlier
    # unlocks, refuse bypass/stale requests, then purchase both new tiers.
    vm.globals[UPGRADES]={AVAILABLE_POINTS:160000,SPENT_POINTS:0,crc('CosmicBenMatrixTier'):5}
    assert run('CosmicGetBenMatrixTier')==4
    assert not run('CosmicBuyBenMatrix',5)
    assert run('CosmicBuyBenMatrix',4)
    assert run('CosmicGetBenMatrixTier')==5
    assert vm.globals[UPGRADES][crc('CosmicBenMatrixTier')]==105
    assert run('CosmicBuyBenMatrix',5)
    assert run('CosmicGetBenMatrixTier')==6
    assert vm.globals[UPGRADES][AVAILABLE_POINTS]==0
    # Cosmetics start unowned in a new save, cost the listed points, and are bought once.
    vm.globals[UPGRADES]={AVAILABLE_POINTS:100000,SPENT_POINTS:0}
    assert run('CosmicGetBenCosmetics')==0
    assert run('CosmicBuyBenCosmetic',0) and run('CosmicGetBenCosmetics')==1
    assert vm.globals[UPGRADES][AVAILABLE_POINTS]==30000 and vm.globals[UPGRADES][SPENT_POINTS]==70000
    assert not run('CosmicBuyBenCosmetic',0), 'bought once'
    assert run('CosmicBuyBenCosmetic',1) and run('CosmicGetBenCosmetics')==3
    assert not run('CosmicBuyBenCosmetic',3), '5000 points left, costs 30000'
    assert run('CosmicGetBenCosmetics')==3 and vm.globals[UPGRADES][AVAILABLE_POINTS]==5000
    vm.globals[UPGRADES]={AVAILABLE_POINTS:0,SPENT_POINTS:0}
    assert run('CosmicGetBenCosmetics')==0 and not run('CosmicBuyBenCosmetic',2)
    # Exact campaign economy, including all six vital purchases.
    vm.globals[UPGRADES]={AVAILABLE_POINTS:450000,SPENT_POINTS:0}
    for stat,count in (('Health',3),('Energy',3),('Matrix',6)):
        for tier in range(count):
            assert run('CosmicBuyBen'+stat,tier)
    assert vm.globals[UPGRADES][AVAILABLE_POINTS]==0
    assert vm.globals[UPGRADES][SPENT_POINTS]==450000
    # Master Control must not grant the cooldown bonus. The same Hero Time
    # bytecode applies the existing 20% reduction only after tier 6.
    from prepare_hero_time_candidate import authored as hero_authored, PHASE, TARGET, REMAINING, COOLDOWN
    hero_rows=hero_authored(matrix_upgrades=True)
    vm.functions.update({k:(args,code) for k,args,code in hero_rows})
    vm.globals.update({k:k for k,_,_ in hero_rows})
    vm.globals[crc('overlay')][crc('cosmic_hero_return')]=lambda *_:None
    vm.globals[0xf02a2526]=lambda *_:None
    for stored, expected in ((4,10),(5,10),(105,10),(106,8)):
        vm.globals[UPGRADES][crc('CosmicBenMatrixTier')]=stored
        vm.globals[crc(PHASE)]=2; vm.globals[crc(TARGET)]=14
        vm.globals[crc('gCurrentCharacter')]=14; vm.globals[crc(REMAINING)]=30
        run('CosmicHeroReturn')
        assert math.isclose(vm.globals[crc(COOLDOWN)],expected,rel_tol=1e-6)

    raw = (scripts / 'globals.ds').read_bytes()
    original = {key: code for key, _, code in records(raw)}
    patched = {key: code for key, _, code in records(transform_globals(raw))}
    assert {key for key in original if original[key] != patched[key]} == {
        HUD_SETUP, PLAYER_SETUP, crc('global_mission_unload'), 0xe4fc423d, 0x15bcad9a, 0xf902c8bf,
    }
    for _, _, code in records(hero_globals(transform_globals(raw))):
        words, tokens = decode(code)
        boundaries = {at for at, _ in tokens} | {len(words)}
        for at, opcode in tokens:
            if opcode in (0x1d, 0x1e, 0x1f):
                assert words[at] >> (8 if opcode == 0x1d else 16) in boundaries

    circdisp = (scripts / 'circdisp.ds').read_bytes()
    original_tick = next((args, code) for key, args, code in records(circdisp)
                         if key == UPGRADE_SELECT_TICK)
    wrapped = {key: (args, code) for key, args, code in records(transform_circular_display(circdisp))}
    assert wrapped[crc(ORIGINAL_SELECT_TICK)] == original_tick
    vm.functions[UPGRADE_SELECT_TICK] = wrapped[UPGRADE_SELECT_TICK]
    observed = []
    action = [0]
    vm.globals[crc(ORIGINAL_SELECT_TICK)] = lambda *args: observed.append(args)
    vm.globals[crc('overlay')][crc('cosmic_ben_upgrade_menu_tick')] = lambda *_: action[0]
    vm.globals[UPGRADES] = {AVAILABLE_POINTS: 90000, SPENT_POINTS: 0}
    run(UPGRADE_SELECT_TICK, 9, 7)
    assert observed == [(9, 7)]
    sounds = []
    vm.globals[0x2712f51f] = {0x5e89deba: lambda _, sound: sounds.append(sound)}
    for command in (1, 2, 2, 6, 3):
        action[0] = command
        run(UPGRADE_SELECT_TICK, 9, 7)
    assert observed == [(9, 7)] and vm.globals[UPGRADES][AVAILABLE_POINTS] == 30000
    assert run('CosmicGetBenHealthTier') == 2 and run('CosmicGetBenEnergyTier') == 1
    assert sounds == [0xe0ea18b8, 0x97b1b6c7, 0xe0ea18b8, 0xe0ea18b8]
    vm.globals[UPGRADES] = {AVAILABLE_POINTS: 270000, SPENT_POINTS: 0}
    for tier in range(6):
        action[0] = 32 + tier
        run(UPGRADE_SELECT_TICK, 9, 7)
        assert run('CosmicGetBenMatrixTier') == tier + 1
    back = []
    vm.globals[0x0f34e94a] = lambda: back.append(True)
    action[0] = 64
    run(UPGRADE_SELECT_TICK, 9, 7)
    assert back == [True]
    print('Ben upgrade purchases, bar capacity, and HUD script branches passed.')


if __name__ == '__main__':
    main()
