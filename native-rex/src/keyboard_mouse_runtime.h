#pragma once

#include "keyboard_mouse_controls.h"
#include <rex/cvar.h>
#include <rex/input/mnk/mnk_input_driver.h>
#include <rex/logging.h>
#include <atomic>
#include <memory>

namespace ben10::controls {
inline std::vector<std::pair<std::string,std::string>> legacy_flags;
inline std::atomic<std::shared_ptr<const Settings>> active_custom;
inline std::string PromptBinding(const char* action) {
  const auto settings=active_custom.load();
  if(!settings)return {};
  for(size_t i=0;i<std::size(actions);++i)if(std::string_view(actions[i].key)==action) {
    const auto& pair=settings->bindings[i];
    return pair[0].empty()?pair[1]:pair[0];
  }
  return {};
}
// First key bound to an action right now (the live cvar is "primary,alternate").
inline std::string FirstBinding(const char* action) {
  if(!action)return {};
  auto binding=rex::cvar::GetFlagByName(action);
  binding=binding.substr(0,binding.find(','));
  while(!binding.empty() && binding.front()==' ')binding.erase(0,1);
  while(!binding.empty() && binding.back()==' ')binding.pop_back();
  return binding;
}
// Keycap images in the ImGui atlas (keyboard_prompt_icons.bin), for host pages.
inline std::vector<std::pair<std::string,ImFontAtlasRectId>> key_icons;
inline ImFontAtlasRectId KeyIconForToken(const std::string& token) {
  for(const auto& icon:key_icons)if(icon.first==token)return icon.second;
  return ImFontAtlasRectId_Invalid;
}
inline ImFontAtlasRectId KeyIcon(const char* action) { return KeyIconForToken(FirstBinding(action)); }
inline bool Apply(const Settings& settings) {
  if(legacy_flags.empty()) {
    for(const auto& action:actions)
      legacy_flags.emplace_back(action.key,rex::cvar::GetFlagByName(action.key));
    for(const char* key:{"mnk_mouse","mnk_sensitivity","mnk_invert_x","mnk_invert_y","mnk_custom_modifiers"})
      legacy_flags.emplace_back(key,rex::cvar::GetFlagByName(key));
  }
  auto values=legacy_flags;
  if(settings.custom) {
    for(size_t i=0;i<std::size(actions);++i) {
      auto binding=settings.bindings[i][0];
      if(!settings.bindings[i][1].empty()) {
        if(!binding.empty())binding+=",";
        binding+=settings.bindings[i][1];
      }
      values[i].second=binding;
    }
    const size_t offset=std::size(actions);
    values[offset].second=settings.mouse?"true":"false";
    values[offset+1].second=std::to_string(settings.sensitivity);
    values[offset+2].second=settings.invert_x?"true":"false";
    values[offset+3].second=settings.invert_y?"true":"false";
    values[offset+4].second="true";
  }
  bool success=true;
  for(const auto& value:values)
    success=rex::cvar::SetFlagByName(value.first,value.second) && success;
  if(success)active_custom.store(settings.custom?std::make_shared<const Settings>(settings):nullptr);
  // Mouse camera turns by the distance moved (Ben10MouseCamera), not as a stick.
  rex::input::mnk::SetDirectMouseLook(settings.mouse);
  REXLOG_INFO("Keyboard and mouse profile: {} applied={}",settings.custom?"custom":"current",success);
  return success;
}
}
