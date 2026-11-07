# Discord Rich Presence

The local integration uses desktop Discord RPC over its documented named-pipe
IPC transport. The application ID is public: 1568421826894500000. No bot token,
client secret, OAuth credential or player Developer Portal setup is required.

## Player-facing activity

- Large image: game_cover.
- Small image: the current level's original preview, with its English title.
- Details: Playing followed by the current level, or Menus / Loading.
- Session timer: the game process start time, retained across level changes.

DiscordPresence.cs runs in the bridge on a background worker. It polls a small
session-specific status file every two seconds, sends activity on state changes
and refreshes every 15 seconds. It handles ping/pong, response deadlines,
acknowledgements and reconnects. Closing the bridge closes its IPC connection.
Absent/disconnected Discord does not block the game process or its rendering.

DiscordPresencePatch.cs adds a hash-verified hook at each mission entry. A
native callback writes the level code only at mission lifecycle boundaries;
the global unload hook returns the state to Menus / Loading. The hook preserves
unrelated script records, including an original duplicate ID in l_rush.

## Original preview image mappings

| Game folder | Original English title | Small image asset key |
| --- | --- | --- |
| l_romd | The Catacombs | catacombs |
| l_pari | Eiffel Tower | eiffel_tower |
| l_rush | Devil's Tower | devils_tower |
| l_chin | The Great Wall | great_wall |
| l_tokn | Tokyo Nights | tokyo_nights |
| l_mili | The Amazon | amazon |
| l_romn | The Colosseum | colosseum |
| l_tokd | The Final Battle | final_battle |

These mappings were verified from globals.ds init_level_switching, exact English
strings in xbx_us.txt, mission IDs/folders in missions.ddf, and the preview field
used by the Level Select code in misscr.ds. They are not inferred from filenames
or concept-art images. The preview textures are in global/gtex_s.xbx.

With locally owned extracted input and Pillow available, maintainers can run:

```powershell
python tools/extract_discord_level_images.py --game originals --output build/discord-art/levels
```

The exporter decodes Xbox 360 tiled BC3/DXT5 into native 256x256 RGBA PNGs under
originals/ within that output folder. Upload-ready 1024x1024 PNGs, a contact sheet,
source/PNG hashes, the mappings and upload instructions are also produced.
Enlarging the upload copies adds no new image detail. Transparency is preserved.
The outputs are local game assets and must not be committed or bundled into the
source archive.

The application maintainer uploads the eight prepared PNGs to Rich Presence
Art Assets, using the filename without .png as each key, plus the game cover
under game_cover. App Icon and Rich Presence Invite Image are separate portal
fields and do not replace these named assets. Players use the published app's
assets automatically; they do not repeat this maintainer setup.

## Build and validation

Build the native consumer with the new discord_presence.h callback integration,
then build the bridge with --hero-time --gpu-diagnostics --performance-alpha5
--ultimate-voices --discord-presence. Stage these matching outputs together.
No new SDK revision, SDK layout change or separate Discord DLL is introduced.
System.Web.Extensions is part of the existing Windows .NET Framework dependency.

Local checks passed for the private-pipe handshake/client ID, fragmented frames,
ping/pong, acknowledged updates, level/image mapping, persistent timer and absent
Discord shutdown. All eight mission hooks match the independent relocator and
preserve unrelated functions. Image files, native dimensions and upload copies
were checked against a manifest extracted independently from game data.

Live local screenshots/logs confirmed connection, session timing and changing
level text; the player subsequently reported successful results. This does not
establish a visual test of every level's Discord thumbnail on every Discord
client. In-client appearance and cached assets remain Discord-controlled.

References: https://discord.com/developers/docs/topics/rpc and
https://github.com/discord/discord-api-docs/blob/main/developers/discord-social-sdk/development-guides/setting-rich-presence.mdx
