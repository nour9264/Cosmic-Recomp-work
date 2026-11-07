[English](#english) | [PortuguÃªs (Brasil)](#portugues)

<a id="english"></a>

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

---

<a id="portugues"></a>

# Componentes de terceiros

O frontend reutiliza Dear ImGui e o carregador GIF do fork recomp-ui do Full Emerald, commit `047bc82d8679e96d1dec19ce2cd8ab677003465f`. As licenÃ§as MIT do projeto e ImGui, os termos do stb e a licenÃ§a zlib do SDL devem acompanhar a distribuiÃ§Ã£o. NÃ£o sÃ£o incluÃ­dos recursos do jogo Full Emerald nem o arquivo da fonte Segoe UI do Windows.

O runtime Ã© baseado no [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk), commit `c94f5ebdcb3c9d1a460ca48e04f9758448f8d518`, com patches locais. O SDK mantÃ©m crÃ©ditos ao projeto Xenia e usa BSD-3-Clause para seu cÃ³digo principal. O diff local acompanha o cÃ³digo deste projeto.

As dependÃªncias do SDK mantÃªm suas prÃ³prias licenÃ§as: entre elas SDL, ImGui, fmt, spdlog, xxHash, toml++, SPIR-V e bibliotecas de processamento/compressÃ£o. FFmpeg e o descompressor LZX de libmspack incluem componentes LGPL. As cÃ³pias das licenÃ§as fornecidas junto ao pacote nÃ£o devem ser removidas.

Este software usa cÃ³digo de [FFmpeg](https://ffmpeg.org), licenciado sob [LGPLv2.1 ou posterior](https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html). Seu cÃ³digo-fonte correspondente estÃ¡ no arquivo `CosmicRecomp-test-0.2.1-sdk-corresponding-source.zip` anexado Ã  mesma release. O SDK compila o subconjunto de Ã¡udio descrito em `thirdparty/CMakeLists.txt`, com as listas de codecs/parser/bitstream-filter em `thirdparty/ffmpeg-overlay`; nÃ£o Ã© uma distribuiÃ§Ã£o do executÃ¡vel `ffmpeg`.

Os arquivos Microsoft Visual C++ Runtime, quando incluÃ­dos, mantÃªm os termos de redistribuiÃ§Ã£o da Microsoft. O .NET Framework e componentes do Windows sÃ£o requisitos do sistema e nÃ£o sÃ£o distribuÃ­dos como parte do launcher.

O arquivo de fontes inclui o SDK, dependÃªncias, diff atual e cabeÃ§alhos atuais do consumidor. Este hotfix altera apenas o diagnÃ³stico de falhas no runtime; essa alteraÃ§Ã£o acompanha as fontes. O cÃ³digo atual do aplicativo/launcher tambÃ©m estÃ¡ na tag correspondente do repositÃ³rio.

Para recompilar, use o pacote completo corrigido `CosmicRecomp-test-0.2.1-sdk-source-fix1.zip`, com seu SHA256SUMS separado. O pacote anterior omitia um header de shader prÃ³prio do projeto e mantinha um include privado. A correÃ§Ã£o inclui os mesmos bytes do shader e um auxiliar para ajustar os includes aos headers fornecidos. Os binÃ¡rios do jogo nÃ£o mudaram. Consulte BUILD.md e SOURCE_CORRECTION.md dentro do arquivo; os arquivos jÃ¡ publicados sÃ£o preservados para rastreabilidade.

ReferÃªncia oficial: [Redistribute Visual C++ Files](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files). A licenÃ§a BSD do projeto nÃ£o se aplica aos DLLs da Microsoft. NÃ£o distribuÃ­mos o compilador, headers ou bibliotecas de desenvolvimento do Windows/MSVC.

As marcas e os recursos de Ben 10 pertencem a seus respectivos titulares. Nenhuma licenÃ§a deste repositÃ³rio concede direitos sobre esses recursos. Eles devem ser obtidos da cÃ³pia do prÃ³prio usuÃ¡rio.

O arquivo de fontes correspondentes do SDK, quando anexado Ã  release, contÃ©m o SDK utilizado e seus submÃ³dulos, sem arquivos do jogo. Para modificar/recompilar o runtime, preserve os termos das dependÃªncias e consulte a documentaÃ§Ã£o de build do SDK. Nenhuma restriÃ§Ã£o adicional Ã© imposta Ã  modificaÃ§Ã£o das bibliotecas LGPL ou Ã  engenharia reversa necessÃ¡ria para depurÃ¡-las.
