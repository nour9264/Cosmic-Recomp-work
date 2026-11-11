# Third-party components and licenses

Alpha 6 community release: the corresponding sources for this build are in
`CosmicRecomp-Alpha6-corresponding-source.zip` attached to the same release.
This supersedes the historical archive names below for rebuilding Alpha 6.
The installer includes dependency notices under `licenses/`.

The standalone frontend reuses Dear ImGui and the GIF loader from [Full Emerald's recomp-ui fork](https://github.com/ExtremestoneGG/recomp-ui), revision `047bc82d8679e96d1dec19ce2cd8ab677003465f`. Preserve its MIT notice (Matthew Stanley), Dear ImGui's MIT notice and stb's MIT/public-domain terms. Its separately compiled SDL3 uses the zlib license. No Full Emerald game assets are included. Windows' installed Segoe UI font is read at runtime and is not redistributed.

The runtime uses [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk), commit `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518`, with local patches. Its principal SDK code uses BSD-3-Clause and preserves Xenia credits. The local diff is supplied with the project sources; the original SDK notice is in `LICENSES/ReXGlue.txt`.

SDK dependencies retain their own terms, including SDL, ImGui, fmt, spdlog, xxHash, toml++, SPIR-V components, compression libraries, and codecs. Preserve their original notices supplied under `licenses` in the binary package and in the complete SDK source archive. Component origins and exact recorded revisions are listed in SOURCES.md and PROVENANCE.json.

This software uses code from [FFmpeg](https://ffmpeg.org), licensed under [LGPLv2.1 or later](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html). Corresponding source is provided in `CosmicRecomp-test-0.2.1-sdk-corresponding-source.zip`, attached to the release. The SDK builds the audio subset described in `thirdparty/CMakeLists.txt` and the codec/parser/filter lists in `thirdparty/ffmpeg-overlay`; this is not a distribution of the ffmpeg command-line application. The LZX decompressor from libmspack also includes LGPL code.

For rebuilding, use the complete corrected snapshot `CosmicRecomp-test-0.2.1-sdk-source-fix1.zip` and its separate SHA256SUMS file. The original 0.2.1 source archive omitted a project-owned direct-resolve shader header and retained a private include path. The corrected archive contains the exact existing bytecode header and a relocation helper for bundled consumer headers; game binaries are unchanged. See BUILD.md and SOURCE_CORRECTION.md inside the archive. Previously published assets remain available for traceability.

The source archive includes the SDK, its dependencies, the current local diff and current consumer integration headers, without game assets. This hotfix changes failure-only runtime diagnostics; the archive includes that source. Application/launcher sources are also in the matching repository tag. No additional restriction is imposed on modifying LGPL libraries or reverse engineering necessary to debug those modifications.

Microsoft Visual C++ Runtime DLLs, when supplied, retain Microsoft's redistribution terms; the project's BSD license does not cover them. See [Microsoft's redistribution documentation](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files). The .NET Framework and Windows system components are prerequisites, not bundled framework/compiler/SDK development packages.

Ben 10 trademarks and original game assets belong to their respective owners. No project license grants rights to those assets; players must supply their own copy.
