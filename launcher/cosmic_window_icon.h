#pragma once

#include <windows.h>

inline void SetCosmicWindowIcon(HWND window) {
    if (!window) return;
    const HINSTANCE module = GetModuleHandleW(nullptr);
    const auto setIcon = [&](WPARAM kind, int width, int height) {
        const auto icon = LoadImageW(module, MAKEINTRESOURCEW(101), IMAGE_ICON,
                                     GetSystemMetrics(width), GetSystemMetrics(height), LR_SHARED);
        if (icon) SendMessageW(window, WM_SETICON, kind, reinterpret_cast<LPARAM>(icon));
    };
    setIcon(ICON_SMALL, SM_CXSMICON, SM_CYSMICON);
    setIcon(ICON_BIG, SM_CXICON, SM_CYICON);
}
