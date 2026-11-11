#pragma once

#include <windows.h>
#include <imgui.h>
#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <functional>
#include <string>
#include <vector>

namespace ben10::controls {
struct Action {
  const char* key;
  const char* label;
  const char* primary;
  const char* alternate;
};
inline constexpr Action actions[] = {
  {"keybind_lstick_up","Move forward","W",""},
  {"keybind_lstick_down","Move backward","S",""},
  {"keybind_lstick_left","Move left","A",""},
  {"keybind_lstick_right","Move right","D",""},
  {"keybind_rstick_up","Camera up","Up",""},
  {"keybind_rstick_down","Camera down","Down",""},
  {"keybind_rstick_left","Camera left","Left",""},
  {"keybind_rstick_right","Camera right","Right",""},
  {"keybind_a","Jump / Confirm (A)","Space","Semicolon"},
  {"keybind_b","Back / Action (B)","Backspace","Quote"},
  {"keybind_x","Attack / Action (X)","LMB","L"},
  {"keybind_y","Attack / Action (Y)","RMB","P"},
  {"keybind_left_trigger","Alien wheel (LT)","Q","I"},
  {"keybind_right_trigger","Ability / Next alien page (RT)","E","O"},
  {"keybind_left_shoulder","Left shoulder (LB)","1",""},
  {"keybind_right_shoulder","Right shoulder (RB)","3",""},
  {"keybind_lstick_press","Hero Time / Left stick click","F",""},
  {"keybind_rstick_press","Right stick click","K",""},
  {"keybind_dpad_up","D-pad up","Shift+Up",""},
  {"keybind_dpad_down","D-pad down","Shift+Down",""},
  {"keybind_dpad_left","D-pad left","Shift+Left",""},
  {"keybind_dpad_right","D-pad right","Shift+Right",""},
  {"keybind_start","Pause (Start)","Escape","Return"},
  {"keybind_back","Back / Select","Tab","Z"},
};
// There is one Keyboard & Mouse profile and mouse camera is always on; older
// files may still say profile=legacy or mouse_camera=off and load as custom.
struct Settings {
  bool custom = true;
  bool mouse = true;
  bool invert_x = false, invert_y = false;
  float sensitivity = 1.0f;
  std::array<std::array<std::string,2>,std::size(actions)> bindings;
  Settings() {
    for (size_t i=0;i<std::size(actions);++i)
      bindings[i]={actions[i].primary,actions[i].alternate};
  }
};
inline std::string KeyToken(ImGuiKey key) {
  if(key>=ImGuiKey_A && key<=ImGuiKey_Z)return std::string(1,char('A'+key-ImGuiKey_A));
  if(key>=ImGuiKey_0 && key<=ImGuiKey_9)return std::string(1,char('0'+key-ImGuiKey_0));
  if(key>=ImGuiKey_F1 && key<=ImGuiKey_F24)return "F"+std::to_string(key-ImGuiKey_F1+1);
  if(key>=ImGuiKey_Keypad0 && key<=ImGuiKey_Keypad9)return "Numpad"+std::to_string(key-ImGuiKey_Keypad0);
  switch(key) {
    case ImGuiKey_Escape:return "Escape";
    case ImGuiKey_Space:return "Space";
    case ImGuiKey_Enter:return "Return";
    case ImGuiKey_Tab:return "Tab";
    case ImGuiKey_Backspace:return "Backspace";
    case ImGuiKey_LeftArrow:return "Left";
    case ImGuiKey_RightArrow:return "Right";
    case ImGuiKey_UpArrow:return "Up";
    case ImGuiKey_DownArrow:return "Down";
    case ImGuiKey_LeftShift:case ImGuiKey_RightShift:return "Shift";
    case ImGuiKey_LeftCtrl:case ImGuiKey_RightCtrl:return "Control";
    case ImGuiKey_LeftAlt:case ImGuiKey_RightAlt:return "Alt";
    case ImGuiKey_Insert:return "Insert";
    case ImGuiKey_Delete:return "Delete";
    case ImGuiKey_Home:return "Home";
    case ImGuiKey_End:return "End";
    case ImGuiKey_PageUp:return "PageUp";
    case ImGuiKey_PageDown:return "PageDown";
    case ImGuiKey_Apostrophe:return "Quote";
    case ImGuiKey_Comma:return "Comma";
    case ImGuiKey_Minus:return "Minus";
    case ImGuiKey_Period:return "Period";
    case ImGuiKey_Slash:return "Slash";
    case ImGuiKey_Semicolon:return "Semicolon";
    case ImGuiKey_Equal:return "Plus";
    case ImGuiKey_LeftBracket:return "LBracket";
    case ImGuiKey_RightBracket:return "RBracket";
    case ImGuiKey_Backslash:return "Backslash";
    case ImGuiKey_GraveAccent:return "Backtick";
    case ImGuiKey_CapsLock:return "CapsLock";
    case ImGuiKey_NumLock:return "NumLock";
    case ImGuiKey_ScrollLock:return "ScrollLock";
    case ImGuiKey_PrintScreen:return "PrintScreen";
    case ImGuiKey_Pause:return "Pause";
    case ImGuiKey_KeypadDecimal:return "Period";
    case ImGuiKey_KeypadDivide:return "NumpadSlash";
    case ImGuiKey_KeypadMultiply:return "NumpadStar";
    case ImGuiKey_KeypadSubtract:return "NumpadMinus";
    case ImGuiKey_KeypadAdd:return "NumpadPlus";
    case ImGuiKey_KeypadEnter:return "NumpadEnter";
    default:return {};
  }
}
inline bool ValidBinding(std::string token) {
  for(const char* modifier:{"Shift+","Ctrl+","Alt+"}) {
    if(token.rfind(modifier,0)==0)token.erase(0,std::string(modifier).size());
  }
  if(token.empty() || token=="LMB" || token=="RMB" || token=="MMB" ||
      token=="Mouse4" || token=="Mouse5")return true;
  for(int i=ImGuiKey_NamedKey_BEGIN;i<ImGuiKey_NamedKey_END;++i)
    if(KeyToken(static_cast<ImGuiKey>(i))==token)return true;
  return false;
}
inline Settings Read(const std::filesystem::path& user) {
  Settings result;
  std::ifstream file(user/"keyboard-mouse.ini");
  for(std::string line;std::getline(file,line);) {
    if(!line.empty() && line.back()=='\r')line.pop_back();
    const auto split=line.find('=');
    if(split==std::string::npos)continue;
    const auto key=line.substr(0,split),value=line.substr(split+1);
    if(key=="invert_x")result.invert_x=value=="on";
    if(key=="invert_y")result.invert_y=value=="on";
    if(key=="sensitivity") {
      try {const float number=std::stof(value);
        if(number>=0.01f && number<=10.0f)result.sensitivity=number;
      }catch(...) {}
    }
    for(size_t i=0;i<std::size(actions);++i)for(int slot=0;slot<2;++slot)
      if(key==std::string(actions[i].key)+(slot?".alternate":".primary") && ValidBinding(value))
        result.bindings[i][slot]=value;
  }
  return result;
}
inline bool Save(const std::filesystem::path& user,const Settings& settings) {
  const auto path=user/"keyboard-mouse.ini";
  auto temporary=path;temporary+=L".tmp";
  std::ofstream file(temporary,std::ios::binary|std::ios::trunc);
  file<<"profile="<<(settings.custom?"custom":"legacy")<<"\nmouse_camera="<<(settings.mouse?"on":"off")
      <<"\ninvert_x="<<(settings.invert_x?"on":"off")<<"\ninvert_y="<<(settings.invert_y?"on":"off")
      <<"\nsensitivity="<<settings.sensitivity<<'\n';
  for(size_t i=0;i<std::size(actions);++i)for(int slot=0;slot<2;++slot)
    file<<actions[i].key<<(slot?".alternate=":".primary=")<<settings.bindings[i][slot]<<'\n';
  file.close();
  if(!file)return false;
  return MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)!=FALSE;
}
class Editor {
 public:
  bool open=false;
  bool Capturing() const {return capture_row_>=0;}
  void Open(const std::filesystem::path& user) {
    settings_=Read(user);capture_row_=-1;message_.clear();open=true;popup_pending_=true;
  }
  void Draw(const std::filesystem::path& user,const std::function<bool(const Settings&)>& apply={}) {
    if(!open)return;
    if(popup_pending_) {
      ImGui::OpenPopup("Customize Keyboard and Mouse Controls");
      popup_pending_=false;
    }
    ImGui::GetIO().ConfigFlags|=ImGuiConfigFlags_NavEnableKeyboard;
    const auto& io=ImGui::GetIO();
    ImGui::SetNextWindowSize(ImVec2(std::min(1000.0f,io.DisplaySize.x-32),
        std::min(680.0f,io.DisplaySize.y-32)),ImGuiCond_Always);
    ImGui::SetNextWindowPos(ImVec2(io.DisplaySize.x*.5f,io.DisplaySize.y*.5f),ImGuiCond_Always,ImVec2(.5f,.5f));
    if(ImGui::BeginPopupModal("Customize Keyboard and Mouse Controls",nullptr,
        ImGuiWindowFlags_NoCollapse|ImGuiWindowFlags_NoSavedSettings|ImGuiWindowFlags_NoResize)) {
      ImGui::TextWrapped("Escape cancels rebinding. Hold modifiers before pressing a key.");
      ImGui::BeginDisabled(Capturing());
      ImGui::Checkbox("Invert mouse X",&settings_.invert_x);
      ImGui::SameLine();ImGui::Checkbox("Invert mouse Y",&settings_.invert_y);
      ImGui::SliderFloat("Mouse sensitivity",&settings_.sensitivity,.01f,10.0f,"%.2f",ImGuiSliderFlags_Logarithmic);
      ImGui::EndDisabled();
      ImGui::BeginChild("Mappings",ImVec2(0,-112),true);
      if(ImGui::BeginTable("Bindings",3,ImGuiTableFlags_RowBg|ImGuiTableFlags_BordersInnerV)) {
        ImGui::TableSetupColumn("Action",ImGuiTableColumnFlags_WidthStretch,1.6f);
        ImGui::TableSetupColumn("Primary",ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("Alternate",ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableHeadersRow();
        for(size_t row=0;row<std::size(actions);++row) {
          ImGui::PushID(int(row));ImGui::TableNextRow();ImGui::TableNextColumn();
          ImGui::TextWrapped("%s",actions[row].label);
          for(int slot=0;slot<2;++slot) {
            ImGui::TableNextColumn();ImGui::PushID(slot);
            const auto& binding=settings_.bindings[row][slot];
            const bool capturing=capture_row_==int(row) && capture_slot_==slot;
            if(ImGui::Button(capturing?"Press key / mouse...":binding.empty()?"Unbound":binding.c_str(),
                ImVec2(-30,0))) {
              capture_row_=int(row);capture_slot_=slot;capture_frame_=ImGui::GetFrameCount();
              modifier_.clear();message_.clear();
            }
            ImGui::SameLine();
            if(ImGui::SmallButton("X")) {settings_.bindings[row][slot].clear();capture_row_=-1;}
            ImGui::PopID();
          }
          ImGui::PopID();
        }
        ImGui::EndTable();
      }
      ImGui::EndChild();
      Capture();
      if(!message_.empty())ImGui::TextWrapped("%s",message_.c_str());
      ImGui::BeginDisabled(Capturing());
      if(ImGui::Button("Save and apply")) {
        if(!Save(user,settings_))message_="Could not save controls. Check folder permissions.";
        else if(apply && !apply(settings_))message_="Saved, but applying failed. Check the game log.";
        else message_="Controls saved.";
      }
      ImGui::SameLine();
      if(ImGui::Button("Restore defaults")) {
        settings_=Settings{};message_="Defaults restored. Select Save and apply.";
      }
      ImGui::SameLine();
      if(ImGui::Button("Back")) {open=false;ImGui::CloseCurrentPopup();}
      ImGui::EndDisabled();
      ImGui::EndPopup();
    }
  }
 private:
  Settings settings_;
  int capture_row_=-1,capture_slot_=0,capture_frame_=0;
  std::string modifier_,message_;
  bool popup_pending_=false;
  void Capture() {
    if(!Capturing() || ImGui::GetFrameCount()<=capture_frame_)return;
    if(ImGui::IsKeyPressed(ImGuiKey_Escape,false)){capture_row_=-1;return;}
    std::string token;
    const char* buttons[]={"LMB","RMB","MMB","Mouse4","Mouse5"};
    for(int i=0;i<5;++i)if(ImGui::IsMouseClicked(i))token=buttons[i];
    for(int i=ImGuiKey_NamedKey_BEGIN;i<ImGuiKey_NamedKey_END;++i) {
      const auto key=static_cast<ImGuiKey>(i);
      if(!ImGui::IsKeyPressed(key,false))continue;
      const auto name=KeyToken(key);
      if(name=="Shift" || name=="Control" || name=="Alt")modifier_=name;
      else if(!name.empty())token=name;
    }
    const auto& io=ImGui::GetIO();
    if(!token.empty()) {
      std::string prefix;
      if(io.KeyShift)prefix+="Shift+";
      if(io.KeyCtrl)prefix+="Ctrl+";
      if(io.KeyAlt)prefix+="Alt+";
      token=prefix+token;
    }else if(!modifier_.empty() && !io.KeyShift && !io.KeyCtrl && !io.KeyAlt)
      token=modifier_;
    if(token.empty())return;
    bool duplicate=false;
    for(size_t row=0;row<std::size(actions);++row)for(int slot=0;slot<2;++slot)
      duplicate|=(row!=size_t(capture_row_) || slot!=capture_slot_) &&
          settings_.bindings[row][slot]==token;
    settings_.bindings[capture_row_][capture_slot_]=token;
    message_=duplicate?"This binding is shared with another action. Change it if that was unintended.":"Binding updated. Select Save and apply.";
    capture_row_=-1;
  }
};
}
