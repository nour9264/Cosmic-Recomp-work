# Cosmic Recomp - Alpha 6: Ultimate Voices & Discord Rich Presence

Community source update building on Alpha 5. The Alpha 6 installer has not yet
been packaged or published; the current downloadable release remains Alpha 5.

## Fixed: Ultimate transformation voice lines

Hero Time now requests the correct original name callout for Ultimate Big Chill,
Echo Echo, Humungousaur, Swampfire and Spider Monkey when a missing callout is
needed after a successful transformation.

The repair makes the original recordings available across missions, aligns the
five voice-bank indices, and extends mission-specific event resolvers while
preserving their existing dialogue behavior. Existing playvo requests are
observed so the added callout does not duplicate them. Original audio samples,
normal transformations and other sound definitions are preserved.

## Added: Discord Rich Presence

Display the game cover as the large image and the current level's original
Level Select preview as the small image, together with the level name and
elapsed session time. The timer stays consistent when changing levels.

The eight level titles and image mappings were verified against the original
game data. Integration uses local desktop IPC and mission lifecycle updates;
no account credentials or player-side developer setup are needed. The game
continues normally when Discord is unavailable.

## Validation and availability

Local player testing reported successful Ultimate callouts and Rich Presence.
Automated checks cover original audio preservation, callout gating and duplicate
suppression, resolver fallback, mission-hook preservation, Discord IPC, and all
eight extracted image mappings. Full campaign coverage, every Discord client
layout and a fresh-machine rebuild remain unverified.

This source update retains Alpha 5's tested performance configuration. It does
not claim a new FPS improvement or a universal fix for above-30-FPS visual issues.
Original game assets, personal saves, logs and generated title C++ are excluded
from the repository. Original port by ExtremestoneGG, based on ReXGlue SDK.

Technical details: [Ultimate voices](ULTIMATE_VOICE_DIAGNOSTICS.md) and
[Discord integration](DISCORD_RICH_PRESENCE.md).
