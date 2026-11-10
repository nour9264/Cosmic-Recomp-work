#pragma once

#include <atomic>
#include <array>
#include <cstdint>
#include <filesystem>

namespace rex::memory { class Memory; }

namespace ben10::albedo_textures {
extern std::atomic<rex::memory::Memory*> memory;
extern std::filesystem::path pack_path;
extern std::filesystem::path button_icon_preview_path;
enum class ButtonIcons { Auto, Xbox, PlayStation, Keyboard };
extern std::atomic<ButtonIcons> button_icons;
extern std::filesystem::path keyboard_icon_path;
extern std::filesystem::path prompt_sprite_path;
extern std::atomic<bool> final_battle_trace_enabled;
extern std::atomic<bool> final_battle_active;
extern std::atomic<unsigned> final_battle_trace_epoch;
extern std::atomic<bool> way_big_launch_albedo;
extern std::atomic<bool> way_big_beam_trace_enabled;
void SetWayBigBeamAppearance(bool player, bool swapped);
bool SwapWayBigBeamTint(uint32_t texture, const std::array<uint32_t, 4>& colors);
void ArmWayBigBeamTrace();
void TraceWayBigBeamCommand(bool player);
void TraceWayBigDrawSwap(uint32_t source, uint32_t target);
void TraceWayBigResource(uint32_t id, uint32_t caller, bool template_lookup);
void TraceWayBigLoad(uint32_t id, uint32_t caller, uint32_t stack, const uint8_t* base);
void TraceWayBigDraw(uint32_t id, uint32_t caller, uint32_t stack, const uint8_t* base);
void TraceWayBigBeamEffect(uint32_t id, uint32_t caller, uint32_t stack, const uint8_t* base);
bool HasPromptSprites();
class PromptSpriteBind {
 public:
  explicit PromptSpriteBind(uint8_t code);
  ~PromptSpriteBind();
  uint32_t Coordinates(uint32_t original) const;
  PromptSpriteBind(const PromptSpriteBind&) = delete;
  PromptSpriteBind& operator=(const PromptSpriteBind&) = delete;

 private:
  int previous_;
  bool previous_bound_;
};
bool BindPromptSprite(uint32_t& flags, uint32_t& size, uint32_t& base_word, uint32_t& mip_word);
void TracePromptRenderer(uint32_t symbol, uint32_t alias, uint32_t callback);
class PromptDraw {
 public:
  explicit PromptDraw(uint8_t* text);
  ~PromptDraw();
  PromptDraw(const PromptDraw&) = delete;
  PromptDraw& operator=(const PromptDraw&) = delete;

 private:
  uint8_t* text_ = nullptr;
  size_t saved_size_ = 0;
  std::array<uint8_t, 128> original_{};
};
void PrepareButtonIconArchive(const std::filesystem::path& game, const std::filesystem::path& user,
                              ButtonIcons mode);
void Apply(uint32_t flags, uint32_t size, uint32_t& base_word, uint32_t& mip_word);
}
