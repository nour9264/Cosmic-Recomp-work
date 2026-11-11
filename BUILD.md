
# Building Cosmic Recomp

Start with the detailed [contributor and coding-agent runbook](docs/CONTRIBUTOR_BUILD_RUNBOOK.md). It separates ISO import, native compilation and coherent runtime staging, with stop rules for build failures. A clean-machine full rebuild remains unverified.

## Source layout and SDK identity

`launcher/native/` contains the standalone Dear ImGui/SDL3/OpenGL frontend. `launcher/NativeBridge.cs`, `InstalledGame.cs`, `IsoImage.cs` and `GameMenuPatch.cs` implement its process bridge, importer and local menu transformation. Legacy Windows Forms sources are retained for reference, not used by the new frontend. `native-rex/src/` contains title integration, frame pacing, diagnostics and original-game video menu callbacks. Generated game C++ belongs only in ignored `native-rex/generated/default`.

The SDK is pinned to commit `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518` in the 0.10.0 series. A window title such as `v0.10.0-dev.unknown` is not a precise source revision; use the commit and patch.

## Required tools

Use a Windows x64 developer terminal with Git, CMake, Ninja, LLVM/Clang targeting the MSVC ABI, and the Microsoft C++/Windows SDK headers and libraries. Obtain these tools from their upstream providers listed in SOURCES.md; they are not bundled with the launcher.

## Reference native-build sequence

The commands below describe the SDK workflow. A complete clean-machine native build has **not** been verified for this test release. Local development used an existing portable toolchain; do not treat its private benchmark scripts as a universal SDK installer.

```powershell
$root = (Get-Location).Path
git clone https://github.com/rexglue/rexglue-sdk.git third_party/rexglue-sdk
git -C third_party/rexglue-sdk checkout c94f5ebdcb3c9d1a460ca48e04f9758448f8d518
git -C third_party/rexglue-sdk submodule update --init --recursive
./tools/apply_sdk_patch.ps1

Push-Location third_party/rexglue-sdk
cmake --preset win-amd64 "-DCMAKE_INSTALL_PREFIX=$root/toolchain/rexglue-sdk"
cmake --build --preset win-amd64-release --parallel 2
cmake --install out/build/win-amd64 --config Release
Pop-Location

# Place assets from your own supported copy in originals/ first.
& "$root/toolchain/rexglue-sdk/bin/rexglue.exe" codegen native-rex/ben10_manifest.toml
python tools/apply_game_integration.py --generated native-rex/generated/default
cmake -S native-rex -B build/native -G Ninja -DCMAKE_BUILD_TYPE=Release `
  -DCMAKE_CXX_COMPILER=clang-cl "-DCMAKE_PREFIX_PATH=$root/toolchain/rexglue-sdk"
cmake --build build/native --parallel 2
./tools/build_launcher.ps1
```

The patch helper runs `git apply --check` and relocates diagnostic include paths to your checkout. Do not apply the patch to a different SDK revision without reviewing conflicts. SDK build details are in `CMakePresets.json` and `thirdparty/CMakeLists.txt`, also preserved in the corresponding-source archive.

## Building from the complete SDK source archive

Use `CosmicRecomp-v0.4.0-alpha.4-corresponding-source.zip` when rebuilding the published SDK. It supersedes the earlier 0.2.1 SDK source archive, which omitted the project-owned direct-resolve bytecode header and retained an include into a private research directory. Alpha 4 includes the retained resolve/texture changes, CPU integration recipes and synchronous RAM/GPU metrics. Use its corresponding SDK sources and consumer together.

After extracting the archive, run this from its root:

```powershell
python prepare_sdk_source.py --sdk rexglue-sdk --consumer consumer
```

The helper validates and relocates the SDK's diagnostic includes to the consumer headers bundled in that archive. The SDK patch is **already applied** in the archive; do not apply it again. For a pristine Git checkout, use the normal patch sequence above instead. Include closure and relocation were checked; a complete clean-machine build remains unverified.

## Native frontend and bridge

Check out the UI dependency before configuring the frontend:

```powershell
git clone https://github.com/ExtremestoneGG/recomp-ui.git third_party/full-emerald-ui
git -C third_party/full-emerald-ui checkout 047bc82d8679e96d1dec19ce2cd8ab677003465f
cmake -S launcher/native -B build/frontend -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build/frontend --parallel 2
python tools/build_release_bridge.py --hero-time
# Matching bridge: build/hero-time-release/CosmicBridge.exe
```

Use an x64 MSVC developer environment. CMake builds a separate SDL3 copy with OpenGL enabled; the game SDK's SDL configuration is not changed. Keep the dependency's MIT/ImGui/stb notices and SDL license with redistributions. A GIF background is optional and not provided.

The bridge requires the matching native executable and `runtime/pc-menu-api.txt` containing `7`, plus the runtime hash manifest. Do not mix this frontend with the first test release's older native executable.

## Launcher and importer tests

`tools/build_launcher.ps1` configures the native frontend with CMake and builds the C# bridge with the Windows .NET Framework compiler, writing to `build/launcher`. It requires the pinned UI and SDL checkouts and an x64 C++ developer environment. It creates a project-local temporary directory and does not install tools. The native frontend and bridge were built locally; a clean-machine full-project build remains unverified.

```powershell
$root = (Get-Location).Path
$csc = "$env:WINDIR/Microsoft.NET/Framework64/v4.0.30319/csc.exe"
New-Item -ItemType Directory -Force build/launcher | Out-Null
& $csc /nologo /target:exe /platform:x64 "/out:$root\build\launcher\IsoReaderTests.exe" `
  "$root\launcher\IsoImage.cs" "$root\tests\IsoReaderTests.cs"
./build/launcher/IsoReaderTests.exe "$root/build/launcher/parser-fixtures"
```

These tests use small synthetic images. `tools/build_iso_import_core.ps1` builds `InspectIso.exe`: pass an ISO path to inspect its supported edition; add `--extract <new-folder>` for full extraction without the GUI. Never select an existing folder or your saves as an extraction destination.

## Runtime integrity and modification

The launcher expects `runtime/ben10.exe`, `rexruntime.dll`, `rexgpu-xenos.dll`, and dependencies listed in `runtime/SHA256SUMS.txt`. This manifest detects incomplete or changed copies; it is not a digital signature. Developers replacing SDK DLLs may recalculate its hashes using the same filenames and `sha256`, two spaces, filename format.

`BEN10_PORTABLE_ROOT` separates original assets, user saves, cache, metadata, and logs from the development checkout. Never commit assets, generated game sources, saves, or caches. Build release ZIPs from an explicit allowlist, never recursively from an installed test directory.

## Alpha 4 bridge and integration profile

The Alpha 4 bridge uses `COSMIC_NATIVE_SETTINGS;COSMIC_ALIEN_STREAMS;COSMIC_HERO_TIME;COSMIC_PRELOAD_ALIENS`. Run `python tools/build_release_bridge.py --hero-time` to produce `build/hero-time-release/CosmicBridge.exe`; `tools/build_launcher.ps1` copies this matching profile beside the frontend. It embeds only authored VM programs, not original game scripts. `--rath-disabled` reproduces an older exclusion profile and is not the Alpha default. `--gpu-diagnostics` is reserved for the experimental GPU test build.

Use the pinned SDK plus the single `sdk-patches/rex-sdk-local.diff`, including `Ben10ConfigurePresentation` in the SDK SDL window translation unit. In the corresponding-source archive the diff is already applied; do not apply it again. Run `python prepare_sdk_source.py --sdk rexglue-sdk --consumer consumer` to resolve the consumer include placeholders. The presentation addition uses the runtime's SDL instance, adds no data members or virtual methods, and makes no GPU algorithm change. SDK/kernel/GPU source origins and revisions remain in PROVENANCE.json and SOURCES.md.

After local game codegen, `python tools/apply_game_integration.py --generated native-rex/generated/default` applies the 96 MiB DB File Heap request, expanded callback/storage integration, input filter and retained CPU polling changes. These are idempotent title-specific transformations of locally generated code. Generated files must not enter Git or source archives.

The packaged runtime requires `runtime/pc-menu-api.txt` containing `7` and a `runtime/SHA256SUMS.txt` manifest covering every runtime file. Build the game and the SDK together before staging them; never change only the API marker on an older runtime. Build and runtime validation remain separate requirements. A complete clean-machine rebuild has not been verified.

Run `tools/test_all_aliens_patch.py --native-settings`, the importer/menu suites, and the animation-stream parity and save-reset fixtures against disposable copies. Native gameplay, fullscreen and checkpoint tests have a separate scope recorded in VALIDATION.json. Do not publish private input recordings, screenshots containing user data, original assets, generated functions, caches or saves.

## Hero Time Alpha

Build the bridge with `python tools/build_release_bridge.py --hero-time`. This embeds only authored VM extensions and enables the Hero Time API. The gameplay option remains OFF by default. See docs/HERO_TIME.md for validation limits.

## Alpha 4 source correspondence

See docs/ALPHA4.md. Run the authored post-codegen recipe before building. Its callback/storage, file-heap and CPU polling changes are part of this release; copying only the frontend does not reproduce them. The corresponding archive has the SDK patch already applied.
