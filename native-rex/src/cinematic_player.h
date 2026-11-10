#pragma once

#include <cstdint>
#include <filesystem>
#include <string>

namespace ben10::cinematic_player {
void Attach(void* window, void* input, void* presenter, const std::filesystem::path& movie);
void Detach(void* presenter);
bool Playing();
uint64_t PlaybackMilliseconds();
uint64_t SubmittedFrames();
void ResetSource();
void CaptureSource(const char* path);
void Begin(uint32_t caller, uint32_t movie);
bool Ready(uint32_t movie, uint32_t& result);
std::string CurrentSubtitle();
bool Update(uint32_t movie);
bool Result(uint32_t movie, uint32_t& result);
void Close(uint32_t movie);
}
