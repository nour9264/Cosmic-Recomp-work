"""Author the Ben upgrade transactions for the game's DScript VM."""
import struct

from prepare_all_aliens_candidate import Code, crc, decode, encode, hook, records, relocate


# InitUpgradeTable and the stock purchase handler in circdisp.ds.
UPGRADES = 0xe6db5005
AVAILABLE_POINTS = 0x0f42ad2d
SPENT_POINTS = 0x0ec4a5b4

STATS = ('Health', 'Energy')
COSTS = (15000, 30000, 45000)
CAPACITY_PER_TIER = 0.20
MATRIX_COSTS = (15000, 15000, 30000, 50000, 100000, 60000)
assert sum(MATRIX_COSTS) + 2 * sum(COSTS) == 450000
ARC_DEGREES_PER_TIER = 8
# Albedo, Transformation Animation, Realistic Ultimatrix, Potis Altiare: bought from the same points and kept in the saved
# upgrade table (CosmicBenCosmetic0..3), so a new game starts with none of them.
COSMETIC_COSTS = (70000, 25000, 40000, 30000)
HUD_SETUP = 0x50a41381
PLAYER_SETUP = 0x4f573077
STOCK_ACTOR = 'CosmicBenStockActor'
UPGRADE_SELECT_TICK = 0x53573a0e
ORIGINAL_SELECT_TICK = 'CosmicOriginalUpgradeSelectTick'


def stock_maximum(stat):
    return f'CosmicBenStock{stat}'


def authored():
    rows = []

    def add(name, args, code):
        rows.append((crc(name), args, code.finish()))

    for stat in (*STATS, 'Matrix'):
        costs = MATRIX_COSTS if stat == 'Matrix' else COSTS
        field = f'CosmicBen{stat}Tier'
        level = f'CosmicGetBen{stat}Tier'
        c = Code()
        c.get(1, UPGRADES)
        c.false(1, 'zero')
        c.field(2, 1, field)
        # Read old saves with no field and accept only a purchased tier.
        # The old fifth tier was Fast Recharge, not Master Control.
        # Store new tiers 5/6 as 105/106 in the existing saved field. Old
        # saves retain tiers 1..4 and cannot get Master Control for free.
        stored = [(t, t) for t in range(1, len(costs) + 1)]
        if stat == 'Matrix':
            stored = [(t, t) for t in range(1, 5)] + [(5, 4), (105, 5), (106, 6)]
        for encoded, tier in stored:
            c.num(3, encoded)
            c.binary(0x10, 4, 2, 3)
            c.false(4, f'next_{encoded}')
            if encoded != tier:
                c.num(3, tier)
            c.emit(0x322)
            c.label(f'next_{encoded}')
        c.label('zero')
        c.num(3, 0)
        c.emit(0x322)
        add(level, 0, c)

        # The caller passes the tier displayed on the purchase button so a
        # repeated confirm on a stale screen cannot buy a second level.
        c = Code()
        c.call(level, result=1)
        c.binary(0x10, 2, 0, 1)
        c.false(2, 'refuse')
        c.get(3, UPGRADES)
        c.false(3, 'refuse')
        c.field(4, 3, AVAILABLE_POINTS)
        c.false(4, 'refuse')
        c.field(5, 3, SPENT_POINTS)
        c.false(5, 'refuse')
        for tier, cost in enumerate(costs):
            c.num(6, tier)
            c.binary(0x10, 7, 1, 6)
            c.false(7, f'next_{tier}')
            c.num(8, cost)
            c.binary(0x12, 9, 4, 8)
            c.false(9, 'purchase')
            c.jump('refuse')
            c.label(f'next_{tier}')
        c.jump('refuse')
        c.label('purchase')
        c.num(6, 1)
        c.binary(0x0a, 7, 1, 6)
        c.binary(0x0b, 4, 4, 8)
        c.binary(0x0a, 5, 5, 8)
        c.fieldput(3, AVAILABLE_POINTS, 4)
        c.fieldput(3, SPENT_POINTS, 5)
        if stat == 'Matrix':
            c.num(6,4); c.binary(0x13,10,7,6)
            c.false(10,'store_matrix')
            c.num(6,100); c.binary(0x0a,7,7,6)
            c.label('store_matrix')
        c.fieldput(3, field, 7)
        if stat == 'Matrix':
            c.num(6,4); c.binary(0x10,10,1,6)
            c.false(10,'matrix_sync')
            c.call('CosmicMasterControlPurchased'); c.jump('matrix_synced')
            c.label('matrix_sync'); c.call('CosmicMasterControlSync')
            c.label('matrix_synced')
        c.boolean(9, True)
        c.emit(0x922)
        c.label('refuse')
        c.boolean(9, False)
        c.emit(0x922)
        add(f'CosmicBuyBen{stat}', 1, c)

        if stat == 'Matrix':
            continue

        # Scale an original form capacity supplied by its setup callback,
        # so reloads and switches cannot scale an already upgraded maximum.
        for suffix, increment in (('Capacity', CAPACITY_PER_TIER),
                                  ('Arc', ARC_DEGREES_PER_TIER)):
            c = Code()
            c.call(level, result=1)
            c.num(2, increment)
            c.binary(0x0c, 1, 1, 2)
            if suffix == 'Capacity':
                c.binary(0x0c, 1, 1, 0)
            c.binary(0x0a, 2, 0, 1)
            c.emit(0x222)
            add(f'CosmicBen{stat}{suffix}', 1, c)

        # The gameplay entry point supplies a person and the stock maximum.
        # Preserve the current fill ratio and do nothing on a repeated apply.
        method = stat.lower()
        c = Code()
        c.false(0, 'end')
        c.method(0, f'getmax{method}', [0], result=2)
        c.false(2, 'end')
        c.num(3, 0)
        c.binary(0x13, 4, 2, 3)
        c.false(4, 'end')
        c.binary(0x13, 4, 1, 3)
        c.false(4, 'end')
        c.call(f'CosmicBen{stat}Capacity', [1], result=5)
        c.binary(0x11, 4, 5, 2)
        c.false(4, 'end')
        c.method(0, f'get{method}', [0], result=6)
        c.false(6, 'end')
        c.binary(0x0d, 6, 6, 2)
        if stat == 'Health':
            c.binary(0x0b, 7, 5, 2)
            c.method(0, 'addmaxhealth', [0, 7])
        else:
            c.method(0, 'setmaxenergy', [0, 5])
        c.binary(0x0c, 6, 6, 5)
        c.method(0, f'set{method}', [0, 6])
        c.label('end')
        c.done()
        add(f'CosmicApplyBen{stat}', 2, c)

    # Cache each form's ORIGINAL capacities for this mission. Actor pointers
    # can be reused across transformations, so compare both actor and form.
    c = Code()
    for flag in (0x597a958a, 0xc16ef1c4):
        c.get(15, flag)
        c.false(15, f'stable_{flag}')
        c.jump('end')
        c.label(f'stable_{flag}')
    c.get(1, 'player')
    c.false(1, 'end')
    c.method(1, 'person', [1], result=2)
    c.false(2, 'end')
    c.get(10, 'gCurrentCharacter')
    c.false(10, 'ben')
    c.jump('form_ready')
    c.label('ben')
    c.num(10, 17)
    c.label('form_ready')
    c.get(3, STOCK_ACTOR)
    c.binary(0x10, 4, 2, 3)
    c.false(4, 'capture')
    c.get(3, 'CosmicBenStockForm')
    c.binary(0x10, 4, 10, 3)
    c.false(4, 'capture')
    c.jump('end')
    c.label('capture')
    for register, stat in enumerate(STATS, 8):
        cache = f'CosmicBenBase{stat}ByForm'
        c.get(11, cache)
        c.false(11, f'create_{stat}')
        c.jump(f'cache_{stat}')
        c.label(f'create_{stat}')
        c.table(11)
        c.put(11, cache)
        c.label(f'cache_{stat}')
        c.index(register, 11, 10)
        c.false(register, f'read_{stat}')
        c.jump(f'known_{stat}')
        c.label(f'read_{stat}')
        c.method(2, f'getmax{stat.lower()}', [2], result=register)
        c.false(register, 'end')
        c.num(6, 0)
        c.binary(0x13, 7, register, 6)
        c.false(7, 'end')
        c.store(11, 10, register)
        c.label(f'known_{stat}')
    for register, stat in enumerate(STATS, 8):
        c.put(register, stock_maximum(stat))
    c.put(2, STOCK_ACTOR)
    c.put(10, 'CosmicBenStockForm')
    c.call('CosmicBenRefreshVitals')
    c.call('CosmicBenSyncHud')
    # Player setup runs after saved progress is available; refresh even if
    # the earlier mission preload saw an uninitialized upgrade table.
    c.call('CosmicMasterControlSync')
    c.label('end')
    c.done()
    add('CosmicBenCaptureStockVitals', 0, c)

    c = Code()
    c.get(1, 'player')
    c.false(1, 'end')
    c.method(1, 'person', [1], result=2)
    c.false(2, 'end')
    c.get(3, STOCK_ACTOR)
    c.binary(0x10, 4, 2, 3)
    c.false(4, 'end')
    for stat in STATS:
        c.get(5, stock_maximum(stat))
        c.call(f'CosmicApplyBen{stat}', [2, 5])
    c.label('end')
    c.done()
    add('CosmicBenRefreshVitals', 0, c)

    c = Code()
    c.nil(1)
    c.put(1, STOCK_ACTOR)
    c.put(1, 'CosmicBenStockForm')
    for stat in STATS:
        c.put(1, f'CosmicBenBase{stat}ByForm')
        c.put(1, stock_maximum(stat))
    c.call('CosmicNormalTransformCancel')
    c.done()
    add('CosmicBenClearStockVitals', 0, c)
    # Use real actor values after initial setup, damage, recovery and pickups.
    # Both gauges retain maxvalue=1 and receive one clamped normalized fraction.
    for stat in STATS:
        c = Code()
        c.get(1, 0x391c324a)
        c.false(1, 'end')
        c.field(2, 1, stat.lower())
        c.false(2, 'end')
        c.get(3, 'player')
        c.false(3, 'end')
        c.method(3, 'person', [3], result=4)
        c.false(4, 'end')
        c.method(4, 'getmax' + stat.lower(), [4], result=5)
        c.false(5, 'end')
        c.num(6, 0)
        c.binary(0x13, 7, 5, 6)
        c.false(7, 'end')
        c.method(4, 'get' + stat.lower(), [4], result=8)
        c.false(8, 'end')
        c.binary(0x0d, 9, 8, 5)
        c.binary(0x12, 7, 9, 6)
        c.false(7, 'nonnegative')
        c.move(9, 6)
        c.label('nonnegative')
        c.num(10, 1)
        c.binary(0x13, 7, 9, 10)
        c.false(7, 'bounded')
        c.move(9, 10)
        c.label('bounded')
        c.method(2, 'getmaxvalue', [2], result=11)
        c.binary(0x11, 7, 11, 10)
        c.false(7, 'fill')
        c.method(2, 'setmaxvalue', [2, 10])
        c.label('fill')
        c.method(2, 'setcurrentvalue', [2, 9])
        c.label('end')
        c.done()
        add('CosmicBenSync' + stat + 'Hud', 0, c)
    c = Code()
    for stat in STATS:
        c.call('CosmicBenSync' + stat + 'Hud')
    c.done()
    add('CosmicBenSyncHud', 0, c)

    # Existing circular elements are retained; update their strip only when
    # the HUD is created or a purchase succeeds, never on the per-frame path.
    c = Code()
    c.get(1, 0x391c324a)
    c.false(1, 'end')
    c.get(3, 'overlay')
    c.field(4, 3, 'cosmic_ben_resize_hud_arc')
    c.false(4, 'end')
    c.num(7, 0)
    for index, stat in enumerate(STATS):
        c.field(2, 1, stat.lower())
        c.false(2, f'next_hud_{stat}')
        c.call(f'CosmicGetBen{stat}Tier', result=5)
        c.num(6, index)
        c.method(3, 'cosmic_ben_resize_hud_arc', [2, 5, 6], result=7)
        c.label(f'next_hud_{stat}')
    c.num(8, 1)
    c.binary(0x10, 9, 7, 8)
    c.false(9, 'end')
    c.field(2, 1, 0x630d1c2a)  # Original silver frame, a CounterElement.
    c.false(2, 'end')
    c.field(4, 2, 'setalpha')
    c.false(4, 'end')
    c.num(6, 0)
    c.method(2, 'setalpha', [2, 6])
    c.method(3, 'cosmic_ben_hud_frame_ready', [3])
    c.label('end')
    c.done()
    add('CosmicBenRefreshHud', 0, c)

    # Shared by roster selection and the All Aliens wheel. Resource loading
    # remains unchanged; a locked slot is blank until its tier is purchased.
    c = Code()
    c.call('CosmicGetBenMatrixTier', result=1)
    for form, required in ((11, 1), (19, 2), (20, 3), (21, 3), (22, 3), (23, 3),
                           (12, 4), (13, 4), (14, 4), (15, 4), (16, 4), (24, 4), (25, 4)):
        c.num(2, form); c.binary(0x10, 3, 0, 2)
        c.false(3, f'next_form_{form}')
        c.num(2, required); c.binary(0x12, 3, 1, 2)
        c.false(3, 'allowed'); c.boolean(4, False); c.emit(0x422)
        c.label(f'next_form_{form}')
    c.label('allowed'); c.boolean(4, True); c.emit(0x422)
    add('CosmicMatrixAllows', 1, c)
    # Cosmetics: owned flags live in the saved upgrade table; the native menu gets them as a bit mask.
    c = Code()
    c.num(5, 0)
    c.get(1, UPGRADES); c.false(1, 'done')
    for i in range(len(COSMETIC_COSTS)):
        c.field(2, 1, f'CosmicBenCosmetic{i}'); c.false(2, f'cosmetic_next_{i}')
        c.num(3, 1 << i); c.binary(0x0a, 5, 5, 3)
        c.label(f'cosmetic_next_{i}')
    c.label('done')
    c.emit(5 << 8 | 0x22)
    add('CosmicGetBenCosmetics', 0, c)

    c = Code()
    c.get(3, UPGRADES); c.false(3, 'refuse')
    c.field(4, 3, AVAILABLE_POINTS); c.false(4, 'refuse')
    c.field(5, 3, SPENT_POINTS); c.false(5, 'refuse')
    for i, cost in enumerate(COSMETIC_COSTS):
        c.num(6, i); c.binary(0x10, 7, 0, 6); c.false(7, f'not_cosmetic_{i}')
        c.field(8, 3, f'CosmicBenCosmetic{i}'); c.false(8, f'can_buy_{i}'); c.jump('refuse')
        c.label(f'can_buy_{i}')
        c.num(9, cost); c.binary(0x12, 10, 4, 9); c.false(10, f'pay_{i}'); c.jump('refuse')
        c.label(f'pay_{i}')
        c.binary(0x0b, 4, 4, 9); c.binary(0x0a, 5, 5, 9)
        c.fieldput(3, AVAILABLE_POINTS, 4); c.fieldput(3, SPENT_POINTS, 5)
        c.boolean(11, True); c.fieldput(3, f'CosmicBenCosmetic{i}', 11)
        c.jump('bought')
        c.label(f'not_cosmetic_{i}')
    c.jump('refuse')
    c.label('bought')
    c.boolean(9, True); c.emit(0x922)
    c.label('refuse')
    c.boolean(9, False); c.emit(0x922)
    add('CosmicBuyBenCosmetic', 1, c)

    c = Code()
    c.call('CosmicGetBenCosmetics', result=1)
    c.get(2, 'overlay'); c.false(2, 'end')
    c.field(3, 2, 'cosmic_cosmetics_sync'); c.false(3, 'end')
    c.method(2, 'cosmic_cosmetics_sync', [2, 1])
    c.label('end'); c.done()
    add('CosmicCosmeticsSync', 0, c)
    # The form ring and the Upgrade Forms screen ask with the real form ID (11 Rath, 19 Four Arms, 20 to 23 the Alien Force
    # aliens); this is the tier table plus a log line.
    c = Code()
    c.move(1, 0)
    # Diagnostic: report each check (form ID, level, answer) to the runtime log.
    c.call('CosmicGetBenMatrixTier', result=5)
    c.call('CosmicMatrixAllows', [0], result=4)
    c.num(9, 0); c.false(4, 'result_ready'); c.num(9, 1); c.label('result_ready')
    c.get(6, 'overlay'); c.false(6, 'traced')
    c.field(7, 6, 'cosmic_roster_trace'); c.false(7, 'traced')
    c.method(6, 'cosmic_roster_trace', [6, 1, 0, 5, 9], result=8)
    c.label('traced')
    c.emit(0x422)
    add('CosmicRosterAllows', 1, c)
    # The native input filter and Settings toggle both use this entitlement
    # from the loaded save, never from the INI preference alone.
    for name, purchased in (('CosmicMasterControlSync', 0), ('CosmicMasterControlPurchased', 1)):
        c = Code()
        c.call('CosmicCosmeticsSync')
        c.call('CosmicGetBenMatrixTier', result=1)
        c.get(2,'overlay'); c.false(2,'end')
        c.field(3,2,'cosmic_master_control_sync'); c.false(3,'end')
        c.num(4,purchased)
        c.method(2,'cosmic_master_control_sync',[2,1,4])
        c.label('end'); c.done()
        add(name,0,c)
    from prepare_transformation_animation import authored as transform_authored
    rows.extend(transform_authored())
    return rows


def menu_tick():
    """Route input inside Upgrade Forms, keeping the stock wheel underneath."""
    c = Code()
    c.get(2, UPGRADES)
    c.false(2, 'original')
    c.field(3, 2, AVAILABLE_POINTS)
    c.false(3, 'original')
    c.get(4, 'overlay')
    c.field(5, 4, 'cosmic_ben_upgrade_menu_tick')
    c.false(5, 'original')
    for reg, stat in enumerate(STATS, 6):
        c.call(f'CosmicGetBen{stat}Tier', result=reg)
    c.call('CosmicGetBenMatrixTier', result=12)
    c.call('CosmicMasterControlSync')
    c.call('CosmicGetBenCosmetics', result=15)
    c.method(4, 'cosmic_ben_upgrade_menu_tick', [4, 3, 6, 7, 12, 15], result=8)
    c.num(9, 0)
    c.binary(0x10, 10, 8, 9)
    c.false(10, 'modal')
    c.label('original')
    c.call(ORIGINAL_SELECT_TICK, [0, 1])
    c.done()
    c.label('modal')
    c.num(9, 64)
    c.binary(0x10, 10, 8, 9)
    c.false(10, 'purchases')
    c.call(0x0f34e94a)  # Original CharacterUpgradeSelectScreen_BackMenu.
    c.jump('end')
    c.label('purchases')
    c.num(9, 65)
    c.binary(0x10, 10, 8, 9)
    c.false(10, 'matrix_purchases')
    c.jump('rejected')
    c.label('matrix_purchases')
    for tier in range(len(MATRIX_COSTS)):
        c.num(9, 32 + tier)
        c.binary(0x10, 10, 8, 9)
        c.false(10, f'next_matrix_{tier}')
        c.num(9, tier)
        c.call('CosmicBuyBenMatrix', [9], result=11)
        c.false(11, 'rejected')
        c.jump('success')
        c.label(f'next_matrix_{tier}')
    for index in range(len(COSMETIC_COSTS)):
        c.num(9, 48 + index)
        c.binary(0x10, 10, 8, 9)
        c.false(10, f'next_cosmetic_{index}')
        c.num(9, index)
        c.call('CosmicBuyBenCosmetic', [9], result=11)
        c.false(11, 'rejected')
        c.call('CosmicCosmeticsSync')
        c.jump('success')
        c.label(f'next_cosmetic_{index}')
    for stat_index, stat in enumerate(STATS):
        for tier in range(len(COSTS)):
            c.num(9, 2 + stat_index + tier * 4)
            c.binary(0x10, 10, 8, 9)
            c.false(10, f'next_{stat}_{tier}')
            c.num(9, tier)
            c.call(f'CosmicBuyBen{stat}', [9], result=11)
            c.false(11, 'rejected')
            c.call('CosmicBenRefreshVitals')
            c.call('CosmicBenRefreshHud')
            c.call('CosmicBenSyncHud')
            c.jump('success')
            c.label(f'next_{stat}_{tier}')
    c.jump('end')
    c.label('success')
    c.get(13, 0x2712f51f)
    c.emit(14<<8|5, 0xe0ea18b8)
    c.method(13, 0x5e89deba, [13, 14])
    c.jump('end')
    c.label('rejected')
    c.get(13, 0x2712f51f)
    c.emit(14<<8|5, 0x97b1b6c7)
    c.method(13, 0x5e89deba, [13, 14])
    c.label('end')
    c.done()
    return c.finish()


def transform_circular_display(blob):
    rows = records(blob)
    original = next(((args, code) for key, args, code in rows if key == UPGRADE_SELECT_TICK), None)
    if original is None or original[0] != 2:
        raise ValueError('Upgrade Forms input handler missing')
    renamed = crc(ORIGINAL_SELECT_TICK)
    if any(key == renamed for key, _, _ in rows):
        raise ValueError('Ben Upgrade Forms entry is already installed')
    return encode([(renamed if key == UPGRADE_SELECT_TICK else key, args, code)
                   for key, args, code in rows] + [(UPGRADE_SELECT_TICK, 2, menu_tick())])


def extend_hud(code):
    """Widen the stock bar endpoints independently at HUD creation."""
    words, _ = decode(code)
    # The stock dial builds two 106-degree arcs centered at 180 and 0.
    sites = ((334, 24, 233.0, 'Health', 1),
             (336, 25, 127.0, 'Health', -1),
             (417, 24, -53.0, 'Energy', -1),
             (419, 25, 53.0, 'Energy', 1))
    insertions = {}
    for at, reg, original, stat, direction in sites:
        if (words[at] != reg << 8 | 3 or
                words[at+1] != struct.unpack('>I', struct.pack('>f', original))[0]):
            raise ValueError(f'Unexpected stock {stat} arc at word {at}')
        c = Code()
        c.num(31, original * direction)
        c.call(f'CosmicBen{stat}Arc', [31], result=31)
        c.num(32, direction)
        c.binary(0x0c, reg, 31, 32)
        insertions[at+2] = c.words
    insertions[len(words)-1] = hook('CosmicBenRefreshHud') + hook('CosmicBenSyncHud')
    return relocate(code, insertions)


def transform_globals(blob):
    """Compose the original player and HUD entries before launcher relocation."""
    rows = []
    extensions = authored()
    callbacks = {0xe4fc423d: 'CosmicBenSyncHealthHud',
                 0x15bcad9a: 'CosmicBenSyncEnergyHud',
                 0xf902c8bf: 'CosmicBenSyncHealthHud'}
    required = {HUD_SETUP, PLAYER_SETUP, crc('global_mission_unload'), *callbacks}
    for key, args, code in records(blob):
        if key == HUD_SETUP:
            code = extend_hud(code)
        elif key in callbacks:
            words, _ = decode(code)
            if args != 1 or words[-1] != 0x21:
                raise ValueError('Unexpected stock HUD update callback')
            code = relocate(code, {len(words)-1: hook(callbacks[key])})
        elif key == PLAYER_SETUP:
            words, _ = decode(code)
            if words[295:299] != [0x00000d07, HUD_SETUP, 0x00100d20, 1]:
                raise ValueError('Unexpected player HUD setup call')
            code = relocate(code, {295: hook('CosmicBenCaptureStockVitals')})
        elif key == crc('global_mission_unload'):
            code = relocate(code, {0: hook('CosmicBenClearStockVitals')})
        required.discard(key)
        rows.append((key, args, code))
    if required or {key for key, _, _ in rows}.intersection(key for key, _, _ in extensions):
        raise ValueError('Invalid globals for Ben upgrade integration')
    return encode(rows + extensions)
