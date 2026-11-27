#pragma once
#include <cfloat>
#include "menu_text.h"
#include "keyboard_mouse_runtime.h"
namespace ben10::upgrade_ui {
inline std::string Logical(const std::string& key) {
  const int language=ben10::language::current.load();
  if(language==0)return key;
  // Prefer the upgrade dictionary when a shared Options label also exists.
  static const std::vector<ben10::menu_text::Row> rows={
#include "upgrade_text_table.inc"
  };
  for(const auto& row:rows)if(key==row[0])return row[language];
  return key;
}
inline std::string Format(const char* key,std::initializer_list<std::string> args) {
  std::string line=Logical(key);int index=0;
  for(const auto& arg:args){const auto token="{"+std::to_string(index++)+"}";size_t at=0;
    while((at=line.find(token,at))!=std::string::npos){line.replace(at,token.size(),arg);at+=arg.size();}}
  return line;
}
inline void Text(ImDrawList* draw,ImFont* font,const std::string& logical,ImVec2 pos,
                 float height,ImU32 ink,float width=0,bool centered=false) {
  if(!font)return;
  auto value=Logical(logical);
  if(ben10::language::current.load()==1)value=arabic::Visual(value);
  const float baked=font->LegacySize;
  const auto extent=font->CalcTextSizeA(baked,FLT_MAX,0,value.c_str());
  float stretch=height/baked;
  if(width>0 && extent.x*stretch>width)stretch=width/extent.x;
  const int first=draw->VtxBuffer.Size;
  draw->AddText(font,baked,pos,ink,value.c_str());
  const float left=pos.x-(centered?extent.x*stretch*.5f:0);
  for(int i=first;i<draw->VtxBuffer.Size;++i){auto& v=draw->VtxBuffer[i];
    v.pos.x=left+(v.pos.x-pos.x)*stretch;v.pos.y=pos.y+(v.pos.y-pos.y)*stretch;}
}
inline void Prompt(ImDrawList* draw,ImGuiIO& io,ImFont* font,int code,ImVec2 pos,
                   float height,const char* label,ImU32 ink,float width) {
  using Icons=ben10::albedo_textures::ButtonIcons;
  const auto style=ben10::albedo_textures::CurrentButtonIcons();
  const float radius=height*.48f, cx=pos.x+radius, cy=pos.y+height*.5f;
  const float thick=std::max(1.f,height*.065f);
  const char* action=code==1?"keybind_a":code==4?"keybind_b":code==3?"keybind_y":code==26?"keybind_left_shoulder":"keybind_right_shoulder";
  float icon_width=height;
  if(style==Icons::Keyboard) {
    const auto id=ben10::controls::KeyIcon(action);ImFontAtlasRect rect;
    if(id!=ImFontAtlasRectId_Invalid && io.Fonts->GetCustomRect(id,&rect))
      draw->AddImage(io.Fonts->TexRef,pos,ImVec2(pos.x+height,pos.y+height),rect.uv0,rect.uv1);
    else {
      std::string binding=ben10::controls::FirstBinding(action);
      if(binding.empty())binding=code==26?"Q":code==27?"E":code==1?"ENT":code==4?"ESC":"Y";
      icon_width=std::max(height,float(binding.size())*height*.48f);
      draw->AddRect(pos,ImVec2(pos.x+icon_width,pos.y+height),ink,3,0,thick);
      Text(draw,font,binding,ImVec2(pos.x+icon_width*.5f,pos.y+height*.18f),height*.6f,ink,icon_width-4,true);
    }
  } else if(code==26 || code==27) {
    icon_width=height*1.7f;
    draw->AddRect(pos,ImVec2(pos.x+icon_width,pos.y+height),ink,4,0,thick);
    const char* name=style==Icons::PlayStation?(code==26?"L1":"R1"):(code==26?"LB":"RB");
    Text(draw,font,name,ImVec2(pos.x+icon_width*.5f,pos.y+height*.15f),height*.68f,ink,icon_width-4,true);
  } else {
    ImU32 color=code==1?IM_COL32(115,190,255,255):code==4?IM_COL32(255,100,120,255):IM_COL32(90,225,145,255);
    if(style==Icons::Xbox)color=code==1?IM_COL32(100,220,100,255):code==3?IM_COL32(245,210,65,255):IM_COL32(255,100,100,255);
    draw->AddCircle(ImVec2(cx,cy),radius,color,32,thick);
    const float r=radius*.52f;
    if(style==Icons::PlayStation) {
      if(code==1){draw->AddLine(ImVec2(cx-r,cy-r),ImVec2(cx+r,cy+r),color,thick);draw->AddLine(ImVec2(cx-r,cy+r),ImVec2(cx+r,cy-r),color,thick);}
      else if(code==4)draw->AddCircle(ImVec2(cx,cy),r,color,24,thick);
      else draw->AddTriangle(ImVec2(cx,cy-r*1.1f),ImVec2(cx-r*1.1f,cy+r*.8f),ImVec2(cx+r*1.1f,cy+r*.8f),color,thick);
    } else {
      const char* name=code==1?"A":code==4?"B":"Y";
      Text(draw,font,name,ImVec2(cx,cy-height*.34f),height*.68f,color,height,true);
    }
  }
  if(label && *label)Text(draw,font,label,ImVec2(pos.x+icon_width+height*.3f,pos.y+height*.1f),height*.8f,ink,std::max(1.f,width-icon_width-height*.3f));
}
}
