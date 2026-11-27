# Photo Mode

A free camera with the game frozen, for taking pictures. It is part of the native frontend; the launcher only adds one row to the pause menu.

## Opening and leaving

- **During play:** press **D-pad Down** on the controller, or **F9** on the keyboard.
- **From the pause menu:** the **PHOTO MODE** row (directly under Upgrade Forms; Arabic, Russian and Japanese labels are drawn by the text overlay). It runs the stock Resume first, then starts Photo Mode once play is live again.
- **Leave:** **F9** or **B / Circle**. The game camera, field of view and game state are restored exactly.

## What it does

- Opens frozen: the world, animation and sound stop, enemies cannot hit, audio is muted. **Y / L3** switches the world back on and off; running the world inside Photo Mode does not crash.
- While it is open, keyboard, mouse and controller input are removed from the game (including Hero Time on L3, the alien wheel, the pause button) and are restored on exit.
- Look direction follows the game's **Invert Up/Down** and **Invert Left/Right** options.
- Screenshots are saved as PNG in `user/screenshots/` (panel hidden for the capture).

## Controls

| Action | Keyboard | Controller |
| --- | --- | --- |
| Move | I K J L | Left stick |
| Up / down | U / O | R2 / L2 |
| Look | Arrow keys | Right stick |
| Zoom in / out | ] / [ | R1 / L1 |
| Speed (Shift = faster) | - / = | D-pad Up / Down |
| Freeze / run world | Y | L3 |
| Reset camera | R | R3 |
| Screenshot | P | Cross / A |
| Grid | G | Square / X |
| Hide / show panel | H | Triangle / Y |
| Hide / show HUD | N | D-pad Left |
| Hide / show scene lights | T | D-pad Right |
| Hide the controls list | | Options / Start |
| Exit | F9 | Circle / B |

The panel at the bottom right lists the controls with Xbox or PlayStation button icons following the game's button-icon setting, and key caps for the keyboard.

## How it works (for contributors)

- `native-rex/src/photo_mode.h`: the camera (`OnCamera`), freeze, input blocking, HUD/effects state. `photo_overlay.h`: panel, grid and screenshot. `time_freeze.h`: freezes the guest tick count.
- `tools/apply_photo_mode.py` (called by `apply_game_integration.py`) adds three hooks to locally generated code: `sub_821A5898` calls `OnCamera` once per projection; `sub_821B6DC0` skips UI layer 17 (the HUD) while hidden and records the layer; `sub_8221BA60` skips the layer-16 light item for **T**.
- The pause-menu row is patched by the bridge (`GameMenuPatch.InsertRowAfter`, `AllAliensPatch.PhotoPauseRow`). Installs made before the row existed are upgraded in place.

## Verification and limits

- Played by the repository owner on a local build: freeze, free camera, controls, panel, screenshots, invert options, the D-pad shortcut and the pause-menu row.
- `tools/test_photo_pause_menu.py` checks the pause-menu patch on local original scripts: row order, upgrade from the previous install, idempotence and rejection of unknown edits.
- **T** hides the scene lights. The ice and fire particles are not in the UI layers and cannot be hidden separately.
- Not part of this document's evidence: other languages beyond Arabic, Russian and Japanese for the row label (they show English), and any level other than those the owner tested.

## Show HUD option

**Options > Gameplay > Show HUD** (and the same checkbox in the launcher's Gameplay tab) hides the HUD while a level is being played; menus and the pause screen are never affected. It applies at once, is saved as `show_hud=on/off` in `user/pc-gameplay.ini` and defaults to on. In-game it is a native-only row: it is never sent to the script VM. Photo Mode's **N** hides the HUD independently and is reset when Photo Mode closes.
