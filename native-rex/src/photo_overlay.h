#pragma once
// Photo Mode panel, grid and screenshot (UI thread). The state lives in photo_mode.h.
#include <rex/ui/imgui_dialog.h>
#include <imgui.h>
#include <windows.h>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <rex/logging.h>
#include "photo_mode.h"
#include "albedo_hud.h"

namespace ben10::photo {

inline uint32_t Crc32(const uint8_t* data, size_t size, uint32_t crc = 0) {
  static uint32_t table[256];
  static bool ready = false;
  if (!ready) {
    for (uint32_t i = 0; i < 256; ++i) { uint32_t c = i; for (int k = 0; k < 8; ++k) c = c & 1 ? 0xEDB88320u ^ (c >> 1) : c >> 1; table[i] = c; }
    ready = true;
  }
  crc = ~crc;
  for (size_t i = 0; i < size; ++i) crc = table[(crc ^ data[i]) & 255] ^ (crc >> 8);
  return ~crc;
}

// Uncompressed PNG (stored deflate blocks): simple and dependable.
inline bool WritePng(const std::filesystem::path& path, const std::vector<uint8_t>& rgb, int width, int height) {
  std::vector<uint8_t> raw;
  raw.reserve(size_t(width) * height * 3 + height);
  for (int y = 0; y < height; ++y) { raw.push_back(0); raw.insert(raw.end(), rgb.begin() + size_t(y) * width * 3, rgb.begin() + size_t(y + 1) * width * 3); }
  std::vector<uint8_t> z{0x78, 0x01};
  for (size_t pos = 0; pos < raw.size();) {
    const size_t n = std::min<size_t>(65535, raw.size() - pos);
    z.push_back(pos + n >= raw.size() ? 1 : 0);
    z.push_back(n & 255); z.push_back(n >> 8); z.push_back(~n & 255); z.push_back((~n >> 8) & 255);
    z.insert(z.end(), raw.begin() + pos, raw.begin() + pos + n);
    pos += n;
  }
  uint32_t a = 1, b = 0;
  for (uint8_t v : raw) { a = (a + v) % 65521; b = (b + a) % 65521; }
  const uint32_t adler = (b << 16) | a;
  for (int s = 24; s >= 0; s -= 8) z.push_back((adler >> s) & 255);
  std::ofstream file(path, std::ios::binary);
  if (!file) return false;
  auto be = [&](uint32_t v) { const uint8_t o[4] = {uint8_t(v >> 24), uint8_t(v >> 16), uint8_t(v >> 8), uint8_t(v)}; file.write(reinterpret_cast<const char*>(o), 4); };
  auto chunk = [&](const char* type, const std::vector<uint8_t>& data) {
    be(uint32_t(data.size()));
    std::vector<uint8_t> body(type, type + 4); body.insert(body.end(), data.begin(), data.end());
    file.write(reinterpret_cast<const char*>(body.data()), std::streamsize(body.size()));
    be(Crc32(body.data(), body.size()));
  };
  const uint8_t signature[8] = {0x89, 'P', 'N', 'G', 13, 10, 26, 10};
  file.write(reinterpret_cast<const char*>(signature), 8);
  std::vector<uint8_t> header(13);
  header[0] = uint8_t(width >> 24); header[1] = uint8_t(width >> 16); header[2] = uint8_t(width >> 8); header[3] = uint8_t(width);
  header[4] = uint8_t(height >> 24); header[5] = uint8_t(height >> 16); header[6] = uint8_t(height >> 8); header[7] = uint8_t(height);
  header[8] = 8; header[9] = 2;
  chunk("IHDR", header); chunk("IDAT", z); chunk("IEND", {});
  return bool(file);
}

// The game window's picture as it is on screen (taken after the panel has been hidden).
inline bool CaptureWindow(std::vector<uint8_t>& rgb, int& width, int& height) {
  const HWND window = GetForegroundWindow();
  DWORD process = 0;
  GetWindowThreadProcessId(window, &process);
  if (!window || process != GetCurrentProcessId()) return false;
  RECT client{};
  GetClientRect(window, &client);
  POINT origin{0, 0};
  ClientToScreen(window, &origin);
  width = client.right - client.left; height = client.bottom - client.top;
  if (width <= 0 || height <= 0) return false;
  HDC screen = GetDC(nullptr);
  HDC memory = CreateCompatibleDC(screen);
  BITMAPINFO info{};
  info.bmiHeader.biSize = sizeof(info.bmiHeader); info.bmiHeader.biWidth = width; info.bmiHeader.biHeight = -height;
  info.bmiHeader.biPlanes = 1; info.bmiHeader.biBitCount = 32; info.bmiHeader.biCompression = BI_RGB;
  void* pixels = nullptr;
  HBITMAP bitmap = CreateDIBSection(screen, &info, DIB_RGB_COLORS, &pixels, nullptr, 0);
  bool ok = false;
  if (bitmap && pixels) {
    HGDIOBJ previous = SelectObject(memory, bitmap);
    ok = BitBlt(memory, 0, 0, width, height, screen, origin.x, origin.y, SRCCOPY | CAPTUREBLT) != 0;
    SelectObject(memory, previous);
    if (ok) {
      rgb.resize(size_t(width) * height * 3);
      const uint8_t* src = static_cast<const uint8_t*>(pixels);
      for (size_t i = 0; i < size_t(width) * height; ++i) { rgb[i * 3] = src[i * 4 + 2]; rgb[i * 3 + 1] = src[i * 4 + 1]; rgb[i * 3 + 2] = src[i * 4]; }
    }
  }
  if (bitmap) DeleteObject(bitmap);
  DeleteDC(memory);
  ReleaseDC(nullptr, screen);
  return ok;
}

class Overlay final : public rex::ui::ImGuiDialog {
 public:
  Overlay(rex::ui::ImGuiDrawer* drawer, std::filesystem::path pictures) : ImGuiDialog(drawer), pictures_(std::move(pictures)) {}
  bool NeedsContinuousRepaint() override { return false; }

 protected:
  void OnDraw(ImGuiIO& io) override {
    if (!active.load()) { hide_frames_ = 0; return; }
    const auto now = std::chrono::steady_clock::now();
    // Screenshot: hide everything for a few frames, then grab the window.
    if (shot_requested.exchange(false) && hide_frames_ == 0) hide_frames_ = 6;
    if (hide_frames_ > 0) {
      if (--hide_frames_ == 0) {
        std::vector<uint8_t> rgb; int w = 0, h = 0;
        std::error_code error;
        const std::filesystem::path folder = pictures_dir.empty() ? pictures_ : pictures_dir;
        std::filesystem::create_directories(folder, error);
        const std::time_t t = std::time(nullptr);
        std::tm local{}; localtime_s(&local, &t);
        char stamp[64]; std::strftime(stamp, sizeof(stamp), "photo_%Y%m%d_%H%M%S.png", &local);
        const auto path = folder / stamp;
        const bool ok = CaptureWindow(rgb, w, h) && WritePng(path, rgb, w, h);
        message_ = ok ? std::string("Saved: ") + path.string() : std::string("Could not save the screenshot");
        message_until_ = now + std::chrono::seconds(4);
        REXLOG_INFO("Photo mode: screenshot {} ({})", ok ? "saved" : "failed", path.string());
      }
      return;
    }
    auto* draw = ImGui::GetForegroundDrawList();
    if (grid.load()) {
      const ImU32 line = IM_COL32(255, 255, 255, 120);
      for (int i = 1; i < 3; ++i) {
        draw->AddLine(ImVec2(io.DisplaySize.x * i / 3.0f, 0), ImVec2(io.DisplaySize.x * i / 3.0f, io.DisplaySize.y), line, 1.0f);
        draw->AddLine(ImVec2(0, io.DisplaySize.y * i / 3.0f), ImVec2(io.DisplaySize.x, io.DisplaySize.y * i / 3.0f), line, 1.0f);
      }
    }
    if (now < message_until_) {
      ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x * .5f, 24), ImGuiCond_Always, ImVec2(.5f, 0));
      ImGui::SetNextWindowBgAlpha(.8f);
      if (ImGui::Begin("photo_message", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings))
        ImGui::TextUnformatted(message_.c_str());
      ImGui::End();
    }
    if (!panel.load()) return;
    DrawPanel(io);
  }

  void DrawPanel(ImGuiIO& io) {
    const bool red = ben10::albedo_hud::enabled.load();
    const ImU32 accent = red ? IM_COL32(255, 84, 70, 255) : IM_COL32(150, 240, 50, 255);
    const ImU32 chip_fill = IM_COL32(255, 255, 255, 30), chip_edge = IM_COL32(255, 255, 255, 70), ink = IM_COL32(240, 244, 238, 255), dim = IM_COL32(170, 178, 168, 255);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 18.0f);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(18, 14));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowBorderSize, 1.0f);
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(0.04f, 0.06f, 0.05f, 0.82f));
    ImGui::PushStyleColor(ImGuiCol_Border, ImVec4(1, 1, 1, 0.12f));
    ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x - 18, io.DisplaySize.y - 18), ImGuiCond_Always, ImVec2(1, 1));
    if (ImGui::Begin("photo_panel", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoInputs | ImGuiWindowFlags_AlwaysAutoResize | ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoNav)) {
      ImDrawList* draw = ImGui::GetWindowDrawList();
      auto pill = [&](const char* text, ImU32 fill, ImU32 text_color) {
        const ImVec2 size = ImGui::CalcTextSize(text);
        const ImVec2 at = ImGui::GetCursorScreenPos();
        draw->AddRectFilled(at, ImVec2(at.x + size.x + 18, at.y + size.y + 6), fill, 12.0f);
        draw->AddText(ImVec2(at.x + 9, at.y + 3), text_color, text);
        ImGui::Dummy(ImVec2(size.x + 18, size.y + 6));
      };
      auto chip = [&](const char* text) {
        const ImVec2 size = ImGui::CalcTextSize(text);
        const ImVec2 at = ImGui::GetCursorScreenPos();
        draw->AddRectFilled(at, ImVec2(at.x + size.x + 14, at.y + size.y + 4), chip_fill, 6.0f);
        draw->AddRect(at, ImVec2(at.x + size.x + 14, at.y + size.y + 4), chip_edge, 6.0f);
        draw->AddText(ImVec2(at.x + 7, at.y + 2), ink, text);
        ImGui::Dummy(ImVec2(size.x + 14, size.y + 4));
      };
      auto row = [&](const char* keys, const char* what) {
        ImGui::AlignTextToFramePadding();
        chip(keys); ImGui::SameLine(0, 10);
        ImGui::PushStyleColor(ImGuiCol_Text, dim); ImGui::TextUnformatted(what); ImGui::PopStyleColor();
      };
      // Controller buttons drawn in the style of the controller in use (Xbox or PlayStation).
      const bool playstation = style_provider && style_provider() == 1;
      auto glyph = [&](const std::string& kind) {
        const ImVec2 at = ImGui::GetCursorScreenPos();
        const float r = 10.0f; const ImVec2 c(at.x + r + 1, at.y + r + 1);
        float width = 2 * r + 2;
        auto text_at = [&](const char* s, ImU32 color) { const ImVec2 sz = ImGui::CalcTextSize(s); draw->AddText(ImVec2(c.x - sz.x * .5f, c.y - sz.y * .5f), color, s); };
        auto face = [&](ImU32 fill, const char* letter, int symbol, ImU32 symbol_color) {
          draw->AddCircleFilled(c, r, playstation ? IM_COL32(20, 24, 30, 255) : fill);
          draw->AddCircle(c, r, playstation ? IM_COL32(150, 160, 175, 255) : IM_COL32(0, 0, 0, 90), 24, 1.5f);
          if (!playstation) { text_at(letter, IM_COL32(255, 255, 255, 255)); return; }
          if (symbol == 0) { draw->AddLine(ImVec2(c.x - 4.5f, c.y - 4.5f), ImVec2(c.x + 4.5f, c.y + 4.5f), symbol_color, 2.0f); draw->AddLine(ImVec2(c.x - 4.5f, c.y + 4.5f), ImVec2(c.x + 4.5f, c.y - 4.5f), symbol_color, 2.0f); }
          if (symbol == 1) draw->AddCircle(c, 4.8f, symbol_color, 20, 2.0f);
          if (symbol == 2) draw->AddRect(ImVec2(c.x - 4.5f, c.y - 4.5f), ImVec2(c.x + 4.5f, c.y + 4.5f), symbol_color, 0, 0, 2.0f);
          if (symbol == 3) draw->AddTriangle(ImVec2(c.x, c.y - 5.5f), ImVec2(c.x + 5.2f, c.y + 4.2f), ImVec2(c.x - 5.2f, c.y + 4.2f), symbol_color, 2.0f);
        };
        auto pill_glyph = [&](const char* label) {
          const ImVec2 sz = ImGui::CalcTextSize(label); width = sz.x + 14;
          draw->AddRectFilled(ImVec2(at.x, at.y + 1), ImVec2(at.x + width, at.y + 2 * r + 1), IM_COL32(28, 32, 38, 255), 7.0f);
          draw->AddRect(ImVec2(at.x, at.y + 1), ImVec2(at.x + width, at.y + 2 * r + 1), IM_COL32(150, 160, 175, 255), 7.0f);
          draw->AddText(ImVec2(at.x + 7, c.y - sz.y * .5f), IM_COL32(240, 244, 238, 255), label);
        };
        auto stick = [&](const char* side, bool press) {
          draw->AddCircleFilled(c, r, IM_COL32(28, 32, 38, 255)); draw->AddCircle(c, r, IM_COL32(150, 160, 175, 255), 24, 1.5f);
          draw->AddCircleFilled(c, 4.0f, press ? accent : IM_COL32(190, 198, 208, 255));
          const ImVec2 sz = ImGui::CalcTextSize(side); draw->AddText(ImVec2(c.x - sz.x * .5f, at.y + 2 * r + 2), dim, side);
        };
        if (kind == "A") face(IM_COL32(60, 170, 60, 255), "A", 0, IM_COL32(120, 170, 255, 255));
        else if (kind == "B") face(IM_COL32(205, 60, 55, 255), "B", 1, IM_COL32(255, 105, 105, 255));
        else if (kind == "X") face(IM_COL32(60, 110, 215, 255), "X", 2, IM_COL32(255, 150, 215, 255));
        else if (kind == "Y") face(IM_COL32(215, 175, 40, 255), "Y", 3, IM_COL32(110, 230, 150, 255));
        else if (kind == "LS") stick("L", false);
        else if (kind == "RS") stick("R", false);
        else if (kind == "L3") stick("L3", true);
        else if (kind == "R3") stick("R3", true);
        else if (kind == "LT") pill_glyph(playstation ? "L2" : "LT");
        else if (kind == "RT") pill_glyph(playstation ? "R2" : "RT");
        else if (kind == "LB") pill_glyph(playstation ? "L1" : "LB");
        else if (kind == "RB") pill_glyph(playstation ? "R1" : "RB");
        else if (kind == "MENU") pill_glyph(playstation ? "OPTIONS" : "MENU");
        else if (kind == "DPAD") {
          draw->AddRectFilled(ImVec2(c.x - 3.5f, c.y - r), ImVec2(c.x + 3.5f, c.y + r), IM_COL32(190, 198, 208, 255), 2.0f);
          draw->AddRectFilled(ImVec2(c.x - r, c.y - 3.5f), ImVec2(c.x + r, c.y + 3.5f), IM_COL32(190, 198, 208, 255), 2.0f);
        }
        ImGui::Dummy(ImVec2(width, 2 * r + 2));
      };
      auto crow = [&](std::initializer_list<const char*> kinds, const char* what) {
        bool first = true;
        for (const char* kind : kinds) { if (!first) ImGui::SameLine(0, 5); glyph(kind); first = false; ImGui::SameLine(0, 5); }
        ImGui::SameLine(0, 5);
        ImGui::AlignTextToFramePadding();
        ImGui::PushStyleColor(ImGuiCol_Text, dim); ImGui::TextUnformatted(what); ImGui::PopStyleColor();
      };      // header
      const ImVec2 dot = ImGui::GetCursorScreenPos();
      draw->AddCircleFilled(ImVec2(dot.x + 6, dot.y + 11), 5.0f, accent);
      ImGui::Dummy(ImVec2(16, 20)); ImGui::SameLine();
      ImGui::PushStyleColor(ImGuiCol_Text, ink); ImGui::TextUnformatted("PHOTO MODE"); ImGui::PopStyleColor();
      ImGui::SameLine(0, 14);
      if (frozen.load()) pill("FROZEN", IM_COL32(70, 140, 255, 190), IM_COL32(255, 255, 255, 255));
      else pill("LIVE", IM_COL32(255, 176, 60, 200), IM_COL32(30, 20, 5, 255));
      static const char* speeds[] = {"0.5x", "1x", "2.5x", "5x", "10x", "20x"};
      char info[96];
      std::snprintf(info, sizeof(info), "Speed %s    Zoom %+d    Grid %s", speeds[speed_step.load()], zoom.load() / 2, grid.load() ? "on" : "off");
      ImGui::PushStyleColor(ImGuiCol_Text, dim); ImGui::TextUnformatted(info); ImGui::PopStyleColor();
      if (details.load()) {
        ImGui::Dummy(ImVec2(0, 6));
        ImGui::PushStyleColor(ImGuiCol_Text, accent); ImGui::TextUnformatted("KEYBOARD"); ImGui::PopStyleColor();
        row("I K J L", "move"); row("U  O", "up / down"); row("Arrows", "look"); row("[  ]", "zoom out / in");
        row("-  =", "speed (Shift = faster)"); row("Y", "freeze / run"); row("G", "grid"); row("R", "reset camera");
        row("P", "screenshot"); row("H", "hide panel"); row("N", "hide / show HUD"); row("T", "hide / show effects"); row("F9", "exit");
        ImGui::Dummy(ImVec2(0, 6));
        ImGui::PushStyleColor(ImGuiCol_Text, accent); ImGui::TextUnformatted("CONTROLLER"); ImGui::PopStyleColor();
        crow({"LS"}, "move"); crow({"RS"}, "look"); crow({"RT", "LT"}, "up / down"); crow({"RB", "LB"}, "zoom in / out");
        crow({"DPAD"}, "up / down speed, left HUD, right effects"); crow({"L3"}, "freeze / run"); crow({"R3"}, "reset camera"); crow({"Y"}, "hide panel");
        crow({"X"}, "grid"); crow({"A"}, "screenshot"); crow({"B"}, "exit"); crow({"MENU"}, "hide this list");
      } else {
        ImGui::Dummy(ImVec2(0, 4));
        crow({"MENU"}, "show controls");
      }
    }
    ImGui::End();
    ImGui::PopStyleColor(2);
    ImGui::PopStyleVar(3);
  }
 private:
  std::filesystem::path pictures_;
  int hide_frames_ = 0;
  std::string message_;
  std::chrono::steady_clock::time_point message_until_{};
};
}  // namespace ben10::photo





