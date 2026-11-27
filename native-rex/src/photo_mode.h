#pragma once
// Photo Mode: a free camera with the game frozen.
//  * The gameplay camera object (found with the camera probe) keeps the eye at +010 (copies +0B0 +174 +180), the target
//    at +004 (copy +150), and a basis in the matrix at +080. OnCamera runs every time the game builds the projection.
//  * Freezing: the game's mode word 0x826EB784 is 7 in play and 0xA when paused; forcing 0xA every frame stops the
//    world without showing the pause menu, and giving the original value back resumes it.
//  * Input: keyboard (keys the game leaves alone as far as possible) and a controller read through XInput.
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <algorithm>
#include <string>
#include <filesystem>
#include <rex/logging.h>
#include <intrin.h>
#include <windows.h>
#include "fov_runtime.h"
#include "time_freeze.h"
#include <rex/cvar.h>

namespace ben10::photo {

// ---- state shared with the overlay (UI thread)
inline std::atomic<bool> active{false}, frozen{false}, panel{true}, grid{false}, details{true};
inline std::atomic<bool> shot_requested{false};
inline std::atomic<int> speed_step{2}, zoom{0};
inline std::atomic<bool> toggle_request{false};
inline std::atomic<bool> hide_hud{false};   // the game's 2D layer (health, energy, dial, prompts) is not submitted while true

// The four words that differ between play and pause (found by comparing memory snapshots). All four are needed.
struct FreezeWord { uint32_t address; uint32_t paused; };
constexpr FreezeWord kFreeze[2] = {{0x826EB784u, 0xAu}, {0x826F0D40u, 0u}};
inline std::atomic<bool> reading{false};
inline std::atomic<int64_t> last_tick{0};
inline int64_t NowMs() { return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
constexpr float kSpeeds[] = {0.5f, 1.0f, 2.5f, 5.0f, 10.0f, 20.0f};

inline float Get(const uint8_t* base, uint32_t a) { uint32_t v; std::memcpy(&v, base + a, 4); v = _byteswap_ulong(v); float f; std::memcpy(&f, &v, 4); return f; }
inline void Put(uint8_t* base, uint32_t a, float f) { uint32_t v; std::memcpy(&v, &f, 4); v = _byteswap_ulong(v); std::memcpy(base + a, &v, 4); }
inline uint32_t GetU(const uint8_t* base, uint32_t a) { uint32_t v; std::memcpy(&v, base + a, 4); return _byteswap_ulong(v); }
inline void PutU(uint8_t* base, uint32_t a, uint32_t v) { v = _byteswap_ulong(v); std::memcpy(base + a, &v, 4); }

// ---- input
inline bool GameFocused() {
  const HWND foreground = GetForegroundWindow();
  DWORD process = 0;
  GetWindowThreadProcessId(foreground, &process);
  return foreground && process == GetCurrentProcessId();
}
inline bool Key(int code) { return GameFocused() && (GetAsyncKeyState(code) & 0x8000) != 0; }

struct Pad { float lx = 0, ly = 0, rx = 0, ry = 0, lt = 0, rt = 0; uint16_t buttons = 0; bool ok = false; };
inline bool (*pad_provider)(Pad&) = nullptr;   // set by the app: reads the game's own input system
inline std::filesystem::path pictures_dir;
inline std::atomic<bool> show_hud{true};   // Options > Gameplay > Show HUD (pc-gameplay.ini: show_hud)
inline bool (*gameplay_provider)() = nullptr;                       // true while a level is being played (not paused, no menu)
inline void (*invert_provider)(bool& pitch, bool& yaw) = nullptr;   // the game's Invert Up/Down and Invert Left/Right options
// The game's UI layers are skipped while Photo Mode hides the HUD, or while Show HUD is off during play (never in menus).
inline bool HudHidden() {
  return hide_hud.load(std::memory_order_relaxed) || (!show_hud.load(std::memory_order_relaxed) && gameplay_provider && gameplay_provider());
}
inline std::atomic<bool> hide_effects{false};   // T: skips the layer-16 light item, see ItemIsEffect
// UI layers: 16 = scene effects (its other item must keep drawing or the scene darkens), 17 = the HUD (dial, arcs, prompts, silver plating).
inline bool HudLayerHidden(uint32_t layer) { return layer == 17 && HudHidden(); }

// The layer loop (generated sub_821B6DC0) records which UI layer it is drawing; the item loop (sub_8221BA60) asks NoteItem
// whether an item must be skipped. Only the particle item of layer 16 is ever skipped (T in Photo Mode).
inline uint32_t current_layer = 0xFFFFu;   // render thread only
inline bool ReadWordSafe(const uint8_t* base, uint32_t address, uint32_t& out) {
  __try { uint32_t v; std::memcpy(&v, base + address, 4); out = _byteswap_ulong(v); return true; }
  __except (EXCEPTION_EXECUTE_HANDLER) { return false; }
}
// The callback 82209348 is submitted about 38 times a frame by layer 16 and draws the scene lights (found by logging every
// item of every layer). Hiding it is what T does; the ice and fire particles are not in these layers.
inline bool ItemIsEffect(uint32_t layer, uint32_t kind, uint32_t key) { return layer == 16 && kind == 1 && key == 0x82209348u; }
// Called for each item in a UI layer; returns true when the item must not be drawn.
inline bool NoteItem(uint32_t item, const uint8_t* base) {
  if (!hide_effects.load(std::memory_order_relaxed) || current_layer != 16) return false;
  uint32_t callback = 0;
  return base[item] == 1 && ReadWordSafe(base, item + 8, callback) && ItemIsEffect(current_layer, 1, callback);
}
inline int (*style_provider)() = nullptr;                          // 0 = Xbox buttons, 1 = PlayStation buttons
inline void ApplyMute(bool mute) {
  static bool have = false, previous = false;
  if (mute && !have) { previous = rex::cvar::GetFlagByName("audio_mute") == "true"; have = true; }
  rex::cvar::SetFlagByName("audio_mute", mute || (have && previous) ? "true" : "false");
  if (!mute) have = false;
}
inline Pad ReadPad() {
  if (pad_provider) { Pad provided; if (pad_provider(provided)) { provided.ok = true; return provided; } }
  struct State { DWORD packet; WORD buttons; BYTE lt, rt; SHORT lx, ly, rx, ry; };
  using Fn = DWORD(WINAPI*)(DWORD, State*);
  static Fn get = [] {
    HMODULE module = LoadLibraryW(L"xinput1_4.dll");
    if (!module) module = LoadLibraryW(L"xinput9_1_0.dll");
    return module ? reinterpret_cast<Fn>(GetProcAddress(module, "XInputGetState")) : nullptr;
  }();
  Pad pad;
  State state{};
  if (!get || !GameFocused()) return pad;
  for (DWORD index = 0; index < 4; ++index)
    if (get(index, &state) == 0) {
      auto stick = [](SHORT v) { const float f = v / 32767.0f; return std::fabs(f) < 0.18f ? 0.0f : f; };
      pad.lx = stick(state.lx); pad.ly = stick(state.ly); pad.rx = stick(state.rx); pad.ry = stick(state.ry);
      pad.lt = state.lt / 255.0f; pad.rt = state.rt / 255.0f; pad.buttons = state.buttons; pad.ok = true;
      return pad;
    }
  return pad;
}
constexpr uint16_t kDUp = 1, kDDown = 2, kStart = 0x10, kL3 = 0x40, kR3 = 0x80, kLB = 0x100, kRB = 0x200, kA = 0x1000, kB = 0x2000, kX = 0x4000, kY = 0x8000;

struct Edge {
  bool was = false;
  bool Press(bool now) { const bool hit = now && !was; was = now; return hit; }
};

inline void Toggle() { toggle_request.store(true); }
// The pause menu's Photo Mode row: the script resumes the game first, so the request waits for play to be live again.
inline std::atomic<int64_t> pause_entry_at{0};
inline void RequestFromPauseMenu() { pause_entry_at.store(NowMs()); }
inline bool BlockGameInput() {
  const bool block = active.load() && !reading.load() && NowMs() - last_tick.load() < 500;
  static std::atomic<int> logged{0};
  if (block && logged.fetch_add(1) < 3) REXLOG_INFO("Photo mode: the game's input is being blocked");
  return block;
}

// Every place that reads the pad straight from the input system for a game feature (Hero Time on L3, the alien pages on
// the triggers, Way Big on L3) goes through this, so Photo Mode keeps all of them out of the game.
template <class Input, class State>
inline int ReadGameState(Input* input, State& state) {
  const int result = input->GetState(0, &state);
  if (result == 0 && BlockGameInput()) std::memset(&state.gamepad, 0, sizeof(state.gamepad));
  return result;
}

// ---- the camera
struct Saved { uint32_t offset; float v[3]; };
inline void OnCamera(uint32_t camera, uint8_t* base) {
  using Clock = std::chrono::steady_clock;
  static Clock::time_point last_time{};
  static bool in_photo = false;
  static uint32_t bound = 0, original_words[2] = {7, 1};
  auto hold = [&] { for (const auto& w : kFreeze) PutU(base, w.address, w.paused); };
  auto release = [&] { for (int i = 0; i < 2; ++i) PutU(base, kFreeze[i].address, original_words[i]); };
  static float eye[3], dir[3], dist = 5.0f, yaw = 0, pitch = 0;
  static float start_eye[3], start_yaw = 0, start_pitch = 0;
  static int base_fov = 0;
  static Saved saved[16];
  static int saved_count = 0;
  static float original_rows[12];
  static Edge e_toggle, e_freeze, e_panel, e_grid, e_shot, e_reset, e_details, e_speed_up, e_speed_down, e_pad_freeze, e_pad_panel, e_pad_grid,
      e_pad_shot, e_pad_exit, e_pad_reset, e_pad_details, e_pad_up, e_pad_down;
  // Only heap objects whose eye matches its matrix copy and whose basis is a real rotation are gameplay cameras.
  auto plausible = [&](uint32_t c) {
    if (c < 0xB0000000u || c >= 0xC0000000u) return false;
    for (int i = 0; i < 3; ++i) if (std::fabs(Get(base, c + 0x10 + 4 * i) - Get(base, c + 0xB0 + 4 * i)) > 0.01f) return false;
    const float fx = Get(base, c + 0xA0), fy = Get(base, c + 0xA4), fz = Get(base, c + 0xA8);
    const float len = std::sqrt(fx * fx + fy * fy + fz * fz);
    return len > 0.95f && len < 1.05f;
  };
  static bool armed = false;
  static uint32_t seen[8] = {}; static int seen_count[8] = {}; static int armed_calls = 0;
  if (camera < 0x10000u || camera >= 0xE0000000u) return;
  const auto now = Clock::now();
  const float dt = std::min(0.1f, std::chrono::duration<float>(now - last_time).count());
  last_time = now;
  const Pad pad = ReadPad();

  static Edge e_pad_open;
  const bool shortcut = e_pad_open.Press(!in_photo && (pad.buttons & kDDown) && gameplay_provider && gameplay_provider());
  bool from_menu = false;
  if (const int64_t asked = pause_entry_at.load()) {
    if (in_photo || NowMs() - asked > 6000) pause_entry_at.store(0);
    else if (gameplay_provider && gameplay_provider()) { pause_entry_at.store(0); from_menu = true; }
  }
  const bool want_toggle = e_toggle.Press(Key(VK_F9)) || toggle_request.exchange(false) || shortcut || from_menu;
  const bool pad_exit = e_pad_exit.Press(in_photo && (pad.buttons & kB));
  bool enter_now = false;
  // The game puts itself in this paused state for its own full-screen menus (the R3 form screens); the log shows 0xA
  // before Photo Mode writes anything. Photo Mode then starts only from live gameplay.
  const bool game_screen_open = !in_photo && !armed && GetU(base, kFreeze[0].address) == kFreeze[0].paused;
  if (!in_photo && want_toggle && game_screen_open) REXLOG_INFO("Photo mode: not started, a game screen is open");
  if (!in_photo && want_toggle && !game_screen_open) { armed = true; armed_calls = 0; std::memset(seen, 0, sizeof(seen)); std::memset(seen_count, 0, sizeof(seen_count)); }
  if (armed && !in_photo) {
    if (plausible(camera)) {
      int slot = -1;
      for (int i = 0; i < 8; ++i) if (seen[i] == camera) { slot = i; break; }
      if (slot < 0) for (int i = 0; i < 8; ++i) if (!seen[i]) { seen[i] = camera; slot = i; break; }
      if (slot >= 0) ++seen_count[slot];
    }
    if (++armed_calls < 40) return;
    armed = false;
    int best = -1;
    for (int i = 0; i < 8; ++i) if (seen[i] && (best < 0 || seen_count[i] > seen_count[best])) best = i;
    if (best < 0) { REXLOG_INFO("Photo mode: no gameplay camera found"); return; }
    REXLOG_INFO("Photo mode: camera {:08X} chosen ({} calls of {} candidates)", seen[best], seen_count[best], std::count_if(seen, seen + 8, [](uint32_t v) { return v != 0; }));
    camera = seen[best];
    enter_now = true;
  }
  if (!in_photo && enter_now) {
    in_photo = true; bound = camera;
    for (int i = 0; i < 3; ++i) { eye[i] = Get(base, camera + 0x10 + 4 * i); dir[i] = Get(base, camera + 0x04 + 4 * i) - eye[i]; }
    dist = std::sqrt(dir[0] * dir[0] + dir[1] * dir[1] + dir[2] * dir[2]);
    if (dist < 0.5f) dist = 5.0f;
    for (float& d : dir) d /= std::max(dist, 0.001f);
    yaw = std::atan2(dir[0], dir[2]); pitch = std::asin(std::clamp(dir[1], -0.999f, 0.999f));
    start_yaw = yaw; start_pitch = pitch; std::memcpy(start_eye, eye, sizeof(eye));
    saved_count = 0;
    for (uint32_t off : {0x04u, 0x10u, 0x1Cu, 0xB0u, 0x150u, 0x174u, 0x180u}) {
      saved[saved_count++] = {off, {Get(base, camera + off), Get(base, camera + off + 4), Get(base, camera + off + 8)}};
    }
    for (int r = 0; r < 3; ++r) for (int i = 0; i < 4; ++i) original_rows[r * 4 + i] = Get(base, camera + 0x80 + 0x10 * r + 4 * i);
    for (int i = 0; i < 2; ++i) original_words[i] = GetU(base, kFreeze[i].address);
    if (original_words[0] == kFreeze[0].paused) { original_words[0] = 7; original_words[1] = 1; }
    base_fov = ben10::fov::offset.load();
    zoom.store(0);
    active.store(true); frozen.store(true);
    REXLOG_INFO("Photo mode: ON (camera {:08X}, eye {:.2f} {:.2f} {:.2f}, game mode was {:X})", camera, eye[0], eye[1], eye[2], original_words[0]);
  } else if (in_photo && (want_toggle || pad_exit)) {
    in_photo = false;
    for (int i = 0; i < saved_count; ++i) for (int k = 0; k < 3; ++k) Put(base, bound + saved[i].offset + 4 * k, saved[i].v[k]);
    for (int r = 0; r < 3; ++r) for (int i = 0; i < 4; ++i) Put(base, bound + 0x80 + 0x10 * r + 4 * i, original_rows[r * 4 + i]);
    release();
    ben10::fov::offset.store(base_fov);
    active.store(false); frozen.store(false); hide_hud.store(false); hide_effects.store(false);
    REXLOG_INFO("Photo mode: OFF");
    return;
  }
  if (in_photo) {
    last_tick.store(NowMs());
    static int64_t last_report = 0;
    if (NowMs() - last_report > 2000) {
      last_report = NowMs();
      REXLOG_INFO("Photo mode: state frozen={} block={} words before write {:X} {:X}", frozen.load(), BlockGameInput(), GetU(base, kFreeze[0].address), GetU(base, kFreeze[1].address));
    }
  }
  ben10::time_freeze::frozen.store(in_photo && frozen.load());
  { static bool muted = false; const bool want = in_photo && frozen.load(); if (want != muted) { ApplyMute(want); muted = want; } }
  if (!in_photo || camera != bound) return;

  // ---- controls (keyboard / controller)
  if (e_freeze.Press(Key('Y')) || e_pad_freeze.Press(pad.buttons & kL3)) {
    frozen.store(!frozen.load());
    if (!frozen.load()) release();
    REXLOG_INFO("Photo mode: game {}", frozen.load() ? "frozen" : "running");
  }
  if (e_panel.Press(Key('H')) || e_pad_panel.Press(pad.buttons & kY)) panel.store(!panel.load());
  if (e_grid.Press(Key('G')) || e_pad_grid.Press(pad.buttons & kX)) grid.store(!grid.load());
  if (e_details.Press(false) || e_pad_details.Press(pad.buttons & kStart)) details.store(!details.load());
  if (e_shot.Press(Key('P')) || e_pad_shot.Press(pad.buttons & kA)) shot_requested.store(true);
  if (e_speed_up.Press(Key(VK_OEM_PLUS)) || e_pad_up.Press(pad.buttons & kDUp)) speed_step.store(std::min(5, speed_step.load() + 1));
  if (e_speed_down.Press(Key(VK_OEM_MINUS)) || e_pad_down.Press(pad.buttons & kDDown)) speed_step.store(std::max(0, speed_step.load() - 1));
  static Edge e_hud_key, e_hud_pad, e_fx_key, e_fx_pad;
  if (e_hud_key.Press(Key('N')) || e_hud_pad.Press(pad.buttons & 4)) { hide_hud.store(!hide_hud.load()); }
  if (e_fx_key.Press(Key('T')) || e_fx_pad.Press(pad.buttons & 8)) hide_effects.store(!hide_effects.load());

  if (e_reset.Press(Key('R')) || e_pad_reset.Press(pad.buttons & kR3)) {
    std::memcpy(eye, start_eye, sizeof(eye)); yaw = start_yaw; pitch = start_pitch; zoom.store(0);
  }
  const float speed = kSpeeds[speed_step.load()] * (Key(VK_SHIFT) ? 3.0f : 1.0f);
  float forward = (Key('I') ? 1.f : 0.f) - (Key('K') ? 1.f : 0.f) + pad.ly;
  float side = (Key('L') ? 1.f : 0.f) - (Key('J') ? 1.f : 0.f) + pad.lx;
  float rise = (Key('U') ? 1.f : 0.f) - (Key('O') ? 1.f : 0.f) + pad.rt - pad.lt;
  const float turn = 1.8f * dt;
  bool invert_pitch = false, invert_yaw = false;
  if (invert_provider) invert_provider(invert_pitch, invert_yaw);
  yaw += turn * ((Key(VK_LEFT) ? -1.f : 0.f) + (Key(VK_RIGHT) ? 1.f : 0.f) + pad.rx) * (invert_yaw ? 1.f : -1.f);
  pitch += turn * ((Key(VK_UP) ? 1.f : 0.f) + (Key(VK_DOWN) ? -1.f : 0.f) + pad.ry) * (invert_pitch ? -1.f : 1.f);
  pitch = std::clamp(pitch, -1.45f, 1.45f);
  if (Key(VK_OEM_6) || (pad.buttons & kRB)) zoom.store(std::clamp(zoom.load() - (dt > 0 ? 1 : 0), -40, 45));  // ] zoom in
  if (Key(VK_OEM_4) || (pad.buttons & kLB)) zoom.store(std::clamp(zoom.load() + (dt > 0 ? 1 : 0), -40, 45));  // [ zoom out
  ben10::fov::offset.store(std::clamp(base_fov + zoom.load() / 2, -40, 45));

  dir[0] = std::cos(pitch) * std::sin(yaw); dir[1] = std::sin(pitch); dir[2] = std::cos(pitch) * std::cos(yaw);
  const float right[3] = {dir[2], 0.0f, -dir[0]};   // up x forward, flattened (left-handed, Y up)
  const float rl = std::max(0.0001f, std::sqrt(right[0] * right[0] + right[2] * right[2]));
  const float r[3] = {right[0] / rl, 0.0f, right[2] / rl};
  for (int i = 0; i < 3; ++i) eye[i] += speed * dt * (forward * dir[i] - side * r[i] + (i == 1 ? rise : 0.0f));

  const float target[3] = {eye[0] + dir[0] * dist, eye[1] + dir[1] * dist, eye[2] + dir[2] * dist};
  for (int i = 0; i < saved_count; ++i) {
    const uint32_t off = saved[i].offset;
    const bool is_target = off == 0x04u || off == 0x150u;
    const bool is_eye = off == 0x10u || off == 0xB0u || off == 0x174u || off == 0x180u;
    if (is_target) for (int k = 0; k < 3; ++k) Put(base, camera + off + 4 * k, target[k]);
    if (is_eye) for (int k = 0; k < 3; ++k) Put(base, camera + off + 4 * k, eye[k]);
  }
  // basis rows: (-right, up, -forward) as the game stores them
  const float up[3] = {dir[1] * r[2], dir[2] * r[0] - dir[0] * r[2], -dir[1] * r[0]};
  for (int i = 0; i < 3; ++i) {
    Put(base, camera + 0x80 + 4 * i, -r[i]);
    Put(base, camera + 0x90 + 4 * i, up[i]);
    Put(base, camera + 0xA0 + 4 * i, -dir[i]);
  }
}
}  // namespace ben10::photo
