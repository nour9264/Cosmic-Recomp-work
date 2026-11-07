#pragma once
#include <Windows.h>
#include <filesystem>
#include <fstream>

namespace ben10_presence {
// Called only at mission lifecycle boundaries, never from the frame loop.
inline void Publish(const char* level) noexcept {
  try {
    wchar_t path[32768]{};
    const DWORD n=GetEnvironmentVariableW(L"BEN10_DISCORD_STATUS_FILE",path,32768);
    if(!n || n>=32768)return;
    const std::filesystem::path target(path),temporary=target.wstring()+L".new";
    {std::ofstream file(temporary,std::ios::binary|std::ios::trunc);
      if(!file)return;file<<level<<'\n';file.flush();if(!file)return;}
    MoveFileExW(temporary.c_str(),target.c_str(),MOVEFILE_REPLACE_EXISTING);
  } catch(...) {} // Presence must never prevent gameplay.
}
}
