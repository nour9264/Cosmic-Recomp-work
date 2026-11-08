[English](#english) | [Português (Brasil)](#portugues)

<a id="english"></a>
# Cosmic Recomp

## Alpha 7.1 - Button Icons, Albedo Fix & Game Icon

**Community Alpha 7.1:** [Download the Windows installer and read the release notes](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.7.1).

- **Albedo and Four Arms:** The launcher prepares Albedo's textures locally and includes the Four Arms recolor when the optional form is installed.
- **Button Icons:** Choose Xbox, PlayStation, or Keyboard in **Options → Video → Button Icons**. The setting covers supported menu, HUD, and tutorial prompts. PlayStation icons are built in.
- **Game icon:** Added to the Windows game, launcher, and installer.

## Alpha 7 - Four Arms, Albedo Mode & Launcher Improvements

**Community Alpha 7:** [Download the Windows installer and read the release notes](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.7).

- **Four Arms:** a separate playable form alongside Rath. The local build adds him to All Aliens, the R3 selection wheel and the Upgrades wheel. Enter `classic` to unlock him.
- **Optional PS3 import:** Alpha 7 targets the extracted European PS3 `PS3_GAME` folder (`BLES01110`) for Four Arms. The Xbox 360 ISO is still the base game input. Use **Import Four Arms** in the launcher's Setup tab.
- **Play as Albedo:** an Extras toggle with an alternate character look, red Omnitrix details, menu and HUD accents, and a red-and-white transformation flash.
- **Launcher and startup:** redesigned launcher and settings screens, an optional Skip Intro setting, and a fixed Quit to Launcher action in the pause menu.
- **Ultimate Omnitrix:** restored the red and yellow HUD accents during Ultimate transformations.
- **Performance:** carries forward the Alpha 5 frame pacing fix, tested locally at 30 and 60 FPS.

## Alpha 6 - Ultimate Voices & Discord Rich Presence

**Community Alpha 6:** [Download the installer and read the release notes](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.6).
The previous [Alpha 5 release](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.5) remains available.

- **Ultimate transformation voice lines:** repaired Hero Time name callouts for
  all five supported Ultimates using their original recordings. The integration
  aligns voice-bank indices and event resolvers, adds a missing callout after
  confirmed activation, and avoids duplicating existing playvo requests.
- **Discord Rich Presence:** game cover, a small original Level Select preview,
  current level name and elapsed session time. Mission changes update the level
  without resetting the timer; Discord being unavailable does not block play.

Local player testing reported successful results. Original sound preservation,
voice-event mapping, duplicate suppression, Discord IPC and all eight level-image
mappings passed focused checks. Full campaign and clean-machine validation remain
open. The tested Alpha 5 performance configuration is retained.

[Alpha 6 update notes](docs/ALPHA6_UPDATE.md) ·
[Voice repair details](docs/ULTIMATE_VOICE_DIAGNOSTICS.md) ·
[Discord integration and original preview mappings](docs/DISCORD_RICH_PRESENCE.md)

For this combined configuration, build the matching current native game and use:

```powershell
python tools/build_release_bridge.py --hero-time --gpu-diagnostics --performance-alpha5 --ultimate-voices --discord-presence
```

The feature flags are explicit; ordinary unqualified bridge builds retain their
previous defaults. Rebuilding only the bridge cannot add Discord's new native
mission callbacks. Players do not need a Discord Developer Portal application.
Original recordings and extracted preview PNGs remain outside Git.


**Community work — Alpha 5:** see the
[local performance investigation and reproduction steps](docs/PERFORMANCE_ALPHA5.md).
The community Alpha 5 bridge automatically selects the tested performance path.
See the [Alpha 5 release notes](docs/ALPHA5_RELEASE.md). The upstream Alpha 4 reference below is preserved.

[Community Releases](https://github.com/nour9264/Cosmic-Recomp-work/releases) ·
[Performance report](docs/PERFORMANCE_ALPHA5.md)

## Community performance update — Alpha 5

Local testing identified a major CPU-side upload-reuse bottleneck on an
NVIDIA GeForce RTX 4060 Laptop GPU. The affected area previously ran at about
15 game FPS. `UploadAudit::Observe`, which compares uploaded data against a
shadow cache, consumed approximately 49–54 ms per frame in the slow capture.

The tested candidate uses the existing full-upload path without that comparison.
The user confirmed recovery to 30 FPS and smooth operation after selecting
60 FPS. The latest six telemetry windows recorded **59.97–60.03 game FPS**, with
the 60 FPS cap confirmed by cadence logs. Graphics-worker CPU wall time was
approximately 3–5.4 ms per frame in those samples.

This is a result from the affected area, not a campaign-wide guarantee or a
controlled percentage benchmark. The player also reports that the previous screen
shaking disappeared in the test. A separate flicker-specific fix, other hardware
and comprehensive visual correctness remain unverified. See the performance report for
the measurements, source changes and validation limits.

Alpha 5 selects `measure-no-reuse` automatically, including when an old diagnostic
profile file exists. Build it with `--hero-time --gpu-diagnostics --performance-alpha5`.
The ordinary bridge without this Alpha 5 flag retains its previous defaults.

## Community EXE release

**Cosmic Recomp — Alpha 5** is a community release distributed as one installer:

```text
CosmicRecomp-Alpha5-win64.exe
```

The player flow is:

1. Download and run the EXE from this repository's Releases page.
2. Choose an installation folder. The installer unpacks its bundled runtime
   into `app/<package-hash>/` and opens the launcher. The chosen folder also
   receives `game-data/`, `logs/` and `temp/`; these are created locally during
   setup and use, not copied from the maintainer's personal installation.
3. In the launcher, choose **Select ISO** and select your own supported Xbox 360
   copy. Wait for validation, then choose **Prepare game**.
4. Select **Play**. Later launches use the installed launcher or its shortcut;
   the same prepared installation does not require importing the ISO again.

The EXE contains the launcher, bridge, precompiled native game runtime,
dependencies and license notices. It does not contain an ISO, original game
assets, personal saves, logs, caches or personal installation paths. Prepare
imports the player's assets; it does not compile C++ on the player's computer.

### Manual publication while Actions is unavailable

Maintainers build locally and use the existing allowlisted
`tools/build_portable_distribution.py` packager. Publication requires a coherent
release stage, the tested performance setting, matching runtime hashes,
source/license information, and an installer test in a separate folder.
Do not package the working test installation or upload the bare launcher alone.

After those checks, the repository owner can open **Releases → Draft a new
release**, choose the tested source commit and a version tag, enter the English
release notes, and attach the verified installer EXE and its SHA-256 checksum.
Mark the initial community Alpha as a pre-release and identify its upstream base.
The repository's automatic source ZIP is source code, not the playable installer.

Release artifacts and validation details are listed on the
[Alpha 5 release page](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.5).
See the attached validation file for packaging checks and gameplay limits.

## Upstream Alpha 4 reference

Experimental Windows 10/11 x64 native port of **Ben 10 Ultimate Alien: Cosmic Destruction** (Xbox 360), using ReXGlue v0.10.0 and Direct3D 12.

**Alpha software. Camera/scenery flicker above 30 FPS is still present and is the next priority.**

**Bring your own supported copy.** No ISO, XEX, original assets, generated game source or personal saves are distributed.

[Upstream Alpha 4 download](https://github.com/ExtremestoneGG/Cosmic-Recompi/releases/tag/v0.4.0-alpha.4) · [User guide](USER_GUIDE.md) · [Build guide](BUILD.md) · [Contributor / coding-agent runbook](docs/CONTRIBUTOR_BUILD_RUNBOOK.md) · [Validation](VALIDATION.json) · [Sources](SOURCES.md)

Latest update: [animation and lever crash fixes](RELEASE_NOTES.md), including a manual phase-1 lever test. Rath upgrades with All Aliens disabled remain under investigation.

Latest update: **boss-transition stability, proportional Hero Time and accumulated native-quality optimizations**. [Details](RELEASE_NOTES.md).

**Contributors and coding agents:** start with the [current-source handoff](docs/AI_HANDOFF.md)
and [build runbook](docs/CONTRIBUTOR_BUILD_RUNBOOK.md). All Aliens and Hero Time
are authored source features in this repository. After the patched SDK setup,
`tools/build_development.ps1` builds and stages the current development app;
it does not download an older release runtime. Full clean-machine reproduction
remains unverified.

## Alpha v0.4.0-alpha.4 — stability and performance

- One portable EXE: select your ISO, wait for acceptance, then **Prepare game**. Import uses a precompiled native runtime; it does not compile C++ on the player's PC.
- Separate launcher with **Play, Settings, Quit**. Play closes the frontend before gameplay. There is no automatic-start checkbox.
- Original in-game **Options → Video** menus: output resolution, 30/60/Unlimited frame limits, display mode and **Show FPS → On/Off**. Show FPS controls both the counter and frame-time graph. Launcher Settings edits the same values.
- Live output size in windowed mode and supported exclusive fullscreen modes; borderless uses the desktop's size. These are presentation settings, not a claim of increased internal rendering resolution. Native 1280×720 remains the minimum.
- Quit to launcher, early startup diagnostics, save-folder information, desktop shortcut creation, and user-supplied text-translation import.
- Repaired missing animation-stream resources for All Aliens. Eleven ordinary forms, including Rath, transformed in the recorded Paris scene. This is scene-level validation, not full campaign coverage.
- **Gameplay → Wipe Data** asks for confirmation, closes the game, archives this title's profile data, and returns to the launcher. Native video settings remain intact. Backups are in `game-data/save-backups`.

All Aliens starts **OFF**. Hold LT and tap RT to change pages; RT abilities are suppressed while LT is held. Normal Rath progression and the original cheat are preserved. All Aliens makes Rath available without changing the profile unlock. Four Arms is not included.

Hero Time starts **OFF**. Enable it under **Options → Gameplay → Extras**. Use a compatible normal alien, then **L3 / F** for its corresponding Ultimate. It lasts up to 60 seconds, followed by proportional recharge as Ben (time used / 3, maximum 20 seconds). See [Hero Time details](RELEASE_NOTES.md) for tested scope and known issues.

## Keyboard and controllers

Controllers are supported natively through the SDK SDL backend, including XInput-compatible controllers. Prompts retain Xbox button names. Contextual actions follow the original game.

| Keyboard | Xbox input / purpose |
| --- | --- |
| WASD | Left stick: movement |
| Arrows | Right stick: camera |
| Space or semicolon | A: confirm / jump |
| Backspace or apostrophe | B: back / original B action |
| L / P | X / Y |
| Q or I | LT: alien wheel |
| E or O | RT: abilities; next wheel page while LT held with All Aliens ON |
| 1 / 3 | LB / RB |
| F / K | Left / right stick click |
| Shift + arrows | D-pad |
| Enter or X | Start / pause |
| Tab or Z | Back / Select |

With All Aliens ON, hold Q and tap E to cycle pages. Mouse camera is opt-in and disabled by default. Mappings checked against the SDK keyboard driver and launcher configuration; not every contextual keyboard action has been playtested.

## Getting started

1. Run the installer and choose your installation folder on any writable drive. To update, select the existing CosmicRecomp folder.
2. In Settings, choose **Select ISO**, wait for validation, then **Prepare game**.
3. Click **Play**. The default is native 720p with a 30 FPS limit. Higher limits remain experimental.
4. Preserve `CosmicRecomp/game-data/user` when updating. Setup logs are in `CosmicRecomp/logs`; game/startup logs are in `CosmicRecomp/game-data/logs`.

Save/Continue was manually confirmed in an earlier test. No saves are supplied. Use a separate folder for a new test release and preserve your existing user folder before migration.

## Known limits

Stable 60 FPS and camera/scenery flicker above 30 FPS remain open. Full campaign compatibility, extended combat/abilities and the earlier first-boss death regression remain unverified. Returning from the main menu to Press Start with B is pending. Retained performance changes and the limits of the fixed-scene measurement are documented in [release notes](RELEASE_NOTES.md). Unsupported exclusive resolutions are rejected and logged.

ReXGlue supplies the kernel, GPU translation and audio. This project does not replace them with a new renderer or kernel. [SOURCES.md](SOURCES.md), [THIRD_PARTY.md](THIRD_PARTY.md), [PROVENANCE.json](PROVENANCE.json) and `LICENSES/` record sources, revisions, changes and licenses. Complete corresponding SDK sources accompany the release. A full clean-machine rebuild remains unverified.

---
<a id="portugues"></a>
# Português (Brasil)

## Alpha 7 - Four Arms, modo Albedo e melhorias no launcher

**Alpha 7 da comunidade:** [Baixe o instalador para Windows e veja as notas da versão](https://github.com/nour9264/Cosmic-Recomp-work/releases/tag/v0.4.0-alpha.7).

- **Four Arms:** forma jogável separada de Rath, com espaço no All Aliens, na roda de seleção do R3 e na roda de melhorias da versão local. Use o código `classic` para desbloqueá-lo.
- **Importação opcional do PS3:** a Alpha 7 usa a pasta extraída `PS3_GAME` da edição europeia (`BLES01110`) para o Four Arms. A ISO do Xbox 360 continua sendo a base do jogo. Use **Import Four Arms** na aba Setup do launcher.
- **Modo Albedo:** opção em Extras que altera o visual do personagem, os detalhes do Omnitrix, os elementos da interface e o clarão da transformação, que fica branco e vermelho.
- **Launcher e inicialização:** interface e tela de configurações redesenhadas, opção de pular a introdução e correção do comando Quit to Launcher no menu de pausa.
- **Omnitrix Supremo:** restaura os detalhes vermelhos e amarelos da interface durante as transformações Supremas.
- **Desempenho:** mantém a correção de cadência da Alpha 5, testada localmente a 30 e 60 FPS.

Port nativo experimental para Windows 10/11 x64 de **Ben 10 Ultimate Alien: Cosmic Destruction**, baseado no ReXGlue v0.10.0 e Direct3D 12. **Você precisa fornecer sua própria cópia compatível.** Nenhum dado original, código gerado do jogo ou save pessoal é distribuído.

Esta versão corrige recursos de animação ausentes no All Aliens e acrescenta opções nos menus do próprio jogo: resolução de saída, 30/60/Unlimited, modo de tela e **Show FPS**, que mostra ou esconde juntos o contador e o gráfico de frametime. O launcher controla os mesmos valores. A resolução de saída muda sem reiniciar em janela e nos modos exclusivos compatíveis; borderless acompanha o desktop. Isso não significa aumento da resolução interna.

O All Aliens começa desligado. Segure LT e toque RT para trocar páginas; habilidades por RT ficam bloqueadas enquanto LT estiver segurado. As onze formas comuns, incluindo Rath, foram verificadas na cena de Paris. O progresso normal e o cheat do Rath são preservados. O Four Arms faz parte da versão local da Alpha 7 descrita acima.

Wipe Data pede confirmação, fecha o jogo, guarda os dados deste título em `game-data/save-backups` e retorna ao launcher. As configurações nativas de vídeo são preservadas. Mantenha `game-data/user` ao atualizar. Logs ficam em `game-data/logs`.

A meta de 60 FPS estáveis e a tremedeira acima de 30 FPS continuam pendentes. A campanha completa e o crash antigo ao morrer no primeiro chefe ainda precisam de verificação. B para voltar ao Press Start também está pendente. As otimizações acumuladas e os limites da medição estão nas notas desta Alpha. Consulte as [notas](RELEASE_NOTES.md), [testes](TESTING.md) e [origens](SOURCES.md).

Hero Time agora inclui brilho verde e recarga proporcional ao uso, limitada a 20 segundos. A correção da transição dos Vreedle e as otimizações acumuladas estão nas [notas da Alpha 4](RELEASE_NOTES.md).

## Teclado e controle

Controles são aceitos nativamente via SDL, incluindo modelos compatíveis com XInput.
Os avisos do jogo continuam mostrando os botões do Xbox.

| Tecla | Ação / botão Xbox |
| --- | --- |
| WASD | Movimento |
| Setas | Câmera |
| Espaço ou ponto e vírgula | A: confirmar / pular |
| Backspace ou apóstrofo | B: voltar / ação original |
| L / P | X / Y |
| Q ou I | LT: seleção de aliens |
| E ou O | RT: habilidades / próxima página com LT segurado e All Aliens ligado |
| 1 / 3 | LB / RB |
| F / K | Clique do analógico esquerdo / direito |
| Shift + setas | Direcional |
| Enter ou X | Start / pausa |
| Tab ou Z | Back / Select |

Com All Aliens ligado, segure Q e toque E para trocar páginas. Mouse desativado
por padrão. Mapeamento conferido no código e configuração; nem toda ação
contextual foi testada em gameplay.
