# Ultimate transformation voice lines

## Result and scope

Hero Time transformation name callouts were repaired in the local build. The
player reported successful results after testing the second integration.
This covers the five supported Ultimates: Big Chill, Echo Echo, Humungousaur,
Swampfire and Spider Monkey. Full campaign audio compatibility and every
possible transformation/cutscene interaction have not been exhaustively tested.

## Cause and implementation

The original English name recordings exist in mission-specific FSB4 voice
banks. Making those samples available alone was insufficient: sounds.ddf uses
numeric subsound indices, and mission-specific vo_*.ds resolvers translate
transformation event IDs to sound descriptors. The original transformation
callbacks also differ: two omit a direct playvo call and another is conditional.

The --ultimate-voices bridge option enables the following authored integration:

- UltimateVoicePatch.cs preserves every original sample index, header and
  compressed audio payload. It puts the five original name callouts at common
  slots 216-220 in the global and eight gameplay voice banks. Valid donor-based
  padding samples fill unused slots where necessary. The title bank is untouched.
- UltimateVoiceLinks.cs updates only the five name-callout descriptor indices.
  Each mission resolver keeps its original body under a private function name;
  a wrapper handles the five transformation events and delegates every other
  event and its original arguments to that body.
- ultimate_voice_program.py and prepare_hero_time_candidate.py observe existing
  playvo requests while Hero Time owns a transition. After the normal form and
  loading guards confirm the requested Ultimate is active, a missing callout is
  requested once. An existing original request suppresses the additional call.
  Rejected/pending requests and returning to Ben do not trigger the added call.

No synthesized or replacement voice is used. Original dialogue and combat
sounds retain their existing definitions. Audio and original instructions are
read from the player's supported local game input, never embedded in Git.

## Build and verification

Build with --hero-time --gpu-diagnostics --performance-alpha5 --ultimate-voices.
Add --discord-presence for the combined Alpha 6 source configuration. The
performance-alpha5 name is retained for compatibility with the tested upload
configuration; it does not label this source update as a new Alpha 5 installer.

The native game and matching SDK must already be built and staged. Rebuilding
this bridge is sufficient for the voice-only change. Discord's mission callbacks
also require the matching updated native game executable.

Passed local checks:

- Independent parsing of all nine output banks: original sample order, headers
  and bytes preserved; donor callouts exact; fixed slots and idempotence checked.
- Five-descriptor isolation and eight unchanged original resolver bodies.
- VM completion gating, duplicate suppression and fallback argument preservation.
- Original Hero Time lifecycle regression and local migration/repeated preparation.
- Player-reported successful audible gameplay test.

Original banks, voice scripts and sounds.ddf receive adjacent
.cosmic-voice-original backups; base gameplay scripts retain .cosmic-original
backups. Exact previous local outputs are recognized for migration, while
unknown changes are rejected. Restore prepared files consistently with the
corresponding bridge for rollback; saves are outside these patch targets.
