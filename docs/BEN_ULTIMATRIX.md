# Ben's new Ultimatrix (model swap)

Ben's wrist device can be drawn as one of two models, switched at draw time, with an optional extra piece:

| Setting (`user/pc-cosmetics.ini`) | Draws |
| --- | --- |
| `realistic=off`, `bolts=off` (default) | the new green Ultimatrix |
| `realistic=on` | the realistic Ultimatrix |
| `bolts=on` | adds the Bolts Tears piece (the Potis Altiare design) to whichever device is shown |

Edit the file by hand for now. The Upgrades menu page that buys and switches these, and the rule that Play as Albedo recolours the device, belong to the upgrade-system step (S7). `owned_*` and `spent` in the same file are stored but unused until then.

## How it works

- Ben's mesh (10089-vertex skin) carries both wrist devices in one index buffer: `[green][piece][realistic][piece]`. One model, one draw call; the hook only changes which index range that call draws.
- `native-rex/src/way_big_draw_swap.h`: `DrawModel` sends any draw whose model has 10089 vertices to `BenDeviceRange`, which rewrites the draw's start/count to the selected device (constants `kGreenStart`, `kGreenCount`, `kGreenPieceCount`, `kRealStart`, `kRealCount`, `kRealPieceCount`). A draw that is not one of those four known ranges is left alone, so stock models are never touched.
- `native-rex/src/cosmetics_state.h`: reads and writes `pc-cosmetics.ini`; `pc_menu_bridge.h` loads it at startup.
- `native-rex/src/albedo_textures.cpp`: replacement textures up to 2048x2048 (was 1024). The new device texture is a 2048 atlas.

## Building the assets (local, owner's own game files)

Nothing here is generated at build time and no game or model data is committed.

1. `blender -b -P tools/ben_ultimatrix/build_ben_ultimatrix_assets.py -- green --export-dir <blender exports> --banks <pristine game folder> --output <out>`
   - exports needed: `device_v4.png`, `real_color.png`, `real_color_albedo.png`, `bolts_piece_tex.png`, `ben_device_export.json`, `ben_realistic_export.json`, `bolts_piece_wrist.json`
   - writes, for every level bank, replacement `l_*.xbx` (skin), `l_*_d.xbx` (mesh) and `l_*_t.xbx` (texture), plus `texture_green.bin` and `manifest.json`. Records are replaced in place: the engine registry only finds keys the game already knows.
   - run it again with `albedo` for `texture_albedo.bin`.
2. `python tools/ben_ultimatrix/make_albedo_pack_entries.py --staged <out> --pack <user/albedo-textures.bin> --out <new pack>` adds the Albedo recolour to a copy of the pack. It never writes the installed pack.

Do not point `--banks` at an install that was already patched; use a pristine copy.

## Verified and not verified

- Verified here: the clone compiles and links with the hook (native build check), `tools/test_ben_ultimatrix.py` passes (range constants agree with each other and with the builder's layout, hook wiring, `pc-cosmetics.ini` keys, 2048 px limit, Albedo pack entry add/replace/limit on a synthetic pack). Pass `--staged <out>` to also compare the constants against a real builder `manifest.json`.
- Played by the repository owner on the working build: green and realistic devices, Bolts Tears piece. Not played from an executable built out of this checkout.
- Not part of this step: the transformation animation and its sound, the cosmetics pictures, page and ownership rules (now in `docs/UPGRADES.md`), and installing the staged banks from the launcher (an asset-delivery decision for the end of the sync).

## Asset provenance

| Asset | Origin |
| --- | --- |
| Ben body and cuff | the game's own mesh (cuff modified) |
| New green Ultimatrix, realistic Ultimatrix | authored in Blender by the repository owner |
| Bolts Tears piece (Potis Altiare design) | derived from the owner's reference images; to be confirmed at S9 |
| Cosmetics pictures | made from reference images supplied by the owner |

Whether any of these may ship with a release is the repository owner's decision (see AGENTS.md); until then the builder reads the owner's local exports.
