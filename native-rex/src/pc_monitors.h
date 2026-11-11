#pragma once

#include <windows.h>
#include <algorithm>
#include <string>
#include <vector>

namespace ben10::monitors {
struct Monitor {
  std::string id;
  std::string label;
  RECT bounds{};
};
inline std::string Utf8(const wchar_t* value) {
  const int size = WideCharToMultiByte(CP_UTF8, 0, value, -1, nullptr, 0, nullptr, nullptr);
  if (size <= 1) return {};
  std::string result(size, '\0');
  if (!WideCharToMultiByte(CP_UTF8, 0, value, -1, result.data(), size, nullptr, nullptr))
    return {};
  result.pop_back();
  return result;
}
inline std::string MonitorProductName(const wchar_t* device_path) {
  const std::wstring path(device_path);
  const auto first = path.find(L'#');
  if (first == std::wstring::npos) return {};
  const auto second = path.find(L'#', first + 1);
  if (second == std::wstring::npos) return {};
  const auto third = path.find(L'#', second + 1);
  if (third == std::wstring::npos) return {};
  const auto model = path.substr(first + 1, second - first - 1);
  const auto key = L"SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\" + model + L"\\" +
      path.substr(second + 1, third - second - 1) + L"\\Device Parameters";
  BYTE edid[256]{};
  DWORD size = sizeof(edid);
  if (RegGetValueW(HKEY_LOCAL_MACHINE, key.c_str(), L"EDID", RRF_RT_REG_BINARY,
      nullptr, edid, &size) == ERROR_SUCCESS && size >= 128) {
    for (int offset = 54; offset + 18 <= 126; offset += 18) {
      if (edid[offset] || edid[offset + 1] || edid[offset + 2] || edid[offset + 3] != 0xfc)
        continue;
      std::string name;
      for (int i = offset + 5; i < offset + 18 && edid[i] >= 32 && edid[i] < 127; ++i)
        name += static_cast<char>(edid[i]);
      while (!name.empty() && name.back() == ' ') name.pop_back();
      if (!name.empty()) return name;
    }
  }
  return Utf8(model.c_str());
}
inline std::string DisplayName(const char* device) {
  // Match the active Windows display source to its physical monitor target.
  // The target name comes from the monitor's reported product information.
  for (int attempt = 0; attempt < 3; ++attempt) {
    UINT32 path_count = 0, mode_count = 0;
    if (GetDisplayConfigBufferSizes(QDC_ONLY_ACTIVE_PATHS, &path_count, &mode_count) != ERROR_SUCCESS)
      break;
    std::vector<DISPLAYCONFIG_PATH_INFO> paths(path_count);
    std::vector<DISPLAYCONFIG_MODE_INFO> modes(mode_count);
    const auto status = QueryDisplayConfig(QDC_ONLY_ACTIVE_PATHS, &path_count, paths.data(),
        &mode_count, modes.data(), nullptr);
    if (status == ERROR_INSUFFICIENT_BUFFER) continue;
    if (status != ERROR_SUCCESS) break;
    paths.resize(path_count);
    for (const auto& path : paths) {
      DISPLAYCONFIG_SOURCE_DEVICE_NAME source{};
      source.header = {DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME, sizeof(source),
          path.sourceInfo.adapterId, path.sourceInfo.id};
      if (DisplayConfigGetDeviceInfo(&source.header) != ERROR_SUCCESS ||
          Utf8(source.viewGdiDeviceName) != device) continue;
      DISPLAYCONFIG_TARGET_DEVICE_NAME target{};
      target.header = {DISPLAYCONFIG_DEVICE_INFO_GET_TARGET_NAME, sizeof(target),
          path.targetInfo.adapterId, path.targetInfo.id};
      if (DisplayConfigGetDeviceInfo(&target.header) == ERROR_SUCCESS) {
        if (target.monitorFriendlyDeviceName[0])
          return Utf8(target.monitorFriendlyDeviceName);
        const auto name = MonitorProductName(target.monitorDevicePath);
        if (!name.empty()) return name;
      }
    }
    break;
  }
  return {};
}
inline std::vector<Monitor> Enumerate() {
  std::vector<Monitor> monitors{{"primary", "Primary monitor", {}}};
  EnumDisplayMonitors(nullptr, nullptr, [](HMONITOR handle, HDC, LPRECT, LPARAM data) -> BOOL {
    auto& result = *reinterpret_cast<std::vector<Monitor>*>(data);
    MONITORINFOEXA info{};
    info.cbSize = sizeof(info);
    if (GetMonitorInfoA(handle, &info)) {
      const auto& rect = info.rcMonitor;
      auto name = DisplayName(info.szDevice);
      if (name.empty()) name = "Monitor " + std::to_string(result.size());
      result.push_back({info.szDevice, name + " (" +
          std::to_string(rect.right - rect.left) + " x " +
          std::to_string(rect.bottom - rect.top) + ")", rect});
      if (info.dwFlags & MONITORINFOF_PRIMARY)
        result[0].label = "Primary - " + name;
    }
    return TRUE;
  }, reinterpret_cast<LPARAM>(&monitors));
  return monitors;
}
inline int Find(const std::vector<Monitor>& monitors, const std::string& id) {
  for (size_t i = 0; i < monitors.size(); ++i)
    if (monitors[i].id == id) return static_cast<int>(i);
  return 0;
}
inline bool Move(HWND window, const std::string& id) {
  auto monitors = Enumerate();
  const int index = Find(monitors, id);
  RECT target = monitors[index].bounds;
  if (!index) {
    MONITORINFO info{};
    info.cbSize = sizeof(info);
    if (!GetMonitorInfoA(MonitorFromPoint(POINT{0, 0}, MONITOR_DEFAULTTOPRIMARY), &info))
      return false;
    target = info.rcMonitor;
  }
  RECT rect{};
  if (!GetWindowRect(window, &rect)) return false;
  const int x = target.left + std::max(0L, (target.right - target.left - (rect.right - rect.left)) / 2);
  const int y = target.top + std::max(0L, (target.bottom - target.top - (rect.bottom - rect.top)) / 2);
  return SetWindowPos(window, nullptr, x, y, 0, 0,
      SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE) != FALSE;
}
}
