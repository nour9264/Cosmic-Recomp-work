# Cosmic Recomp — Alpha 5

Community pre-release based on ExtremestoneGG's Alpha 4 sources, upstream
revision `a99e9ea`.

## Performance and frame stability

This release addresses the severe FPS slowdown reported in Alpha 4. On the
tested RTX 4060 Laptop system, the player confirmed stable gameplay at both
**30 FPS and 60 FPS**, with the previously observed screen shaking and frame
instability no longer appearing during the test. The latest six telemetry
windows recorded **59.97–60.03 game FPS**.

Diagnostics identified expensive CPU-side upload-reuse comparisons in
`UploadAudit::Observe`, consuming approximately **49–54 ms per frame** in the
slow capture. The tested configuration bypasses those comparisons and uses
the existing full-upload path. Graphics-worker CPU wall time subsequently
measured approximately **3–5.4 ms per frame**.

Alpha 5 automatically selects this configuration; no diagnostic profile file
needs to be edited. All Aliens, Hero Time, original menus and save handling
remain included. Performance collectors remain enabled for further diagnosis.

These results cover the tested system and gameplay area. Disappearance of
screen shaking is player-reported; a separate flicker-specific fix or causal
explanation has not been established. Full campaign coverage, equivalent
results on other hardware and all above-30-FPS visual issues remain unverified.

## Download and play

1. Download **CosmicRecomp-Alpha5-win64.exe** below.
2. Run it and choose a writable installation folder. A separate folder is
   recommended for this community pre-release.
3. In the launcher, choose **Select ISO**, wait for validation, then choose
   **Prepare game**.
4. Select **Play**. Subsequent launches can use the installed launcher or its
   shortcut without preparing the same game again.

The installer creates `app/<package-hash>/`, `game-data/`, `logs/` and `temp/`.
Only the runtime, launcher, bridge, dependencies and notices are bundled.
No ISO, original game assets, personal saves or development logs are included.
Game preparation imports your own assets; it does not compile C++ on your PC.

## Release files and verification

- `CosmicRecomp-Alpha5-win64.exe`: the playable installer.
- `CosmicRecomp-Alpha5-SHA256SUMS.txt`: download checksums.
- `CosmicRecomp-Alpha5-VALIDATION.json`: checks performed and remaining limits.
- `CosmicRecomp-Alpha5-corresponding-source.zip`: consumer, patched SDK,
  dependency sources and a source-relocation helper, without game inputs.

Release binaries use source-path mappings to exclude the builder's personal
directories. They were rebuilt for packaging after the successful gameplay
test; the validation file distinguishes packaging checks from gameplay results.
GitHub's automatic source archives alone do not contain the SDK dependencies.

## Credits

Original port by **ExtremestoneGG**, based on **ReXGlue SDK**. This community
release continues that work. Included dependencies retain their original
licenses and credits.
