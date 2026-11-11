#pragma once
#include <cstdint>
#include <array>
#include <cstddef>
// Counts the original game's VdSwap calls without altering its PPC state.
extern "C" void Ben10FrameSubmitted();
extern "C" void Ben10FilterGameInput(uint32_t status,uint32_t guest_state,uint8_t* base);
// Input poll sub_821A8FC8: this frame's direct mouse look as right-stick
// deflection (1 = full, up positive). Returns 0 when the mouse did not move.
extern "C" int Ben10MouseCameraStick(double* x,double* y);
// sub_82166B08, around each shader constant upload: the FOV preference is
// applied to the source for the upload, then the original is restored.
extern "C" void Ben10FovBegin(uint8_t* base,uint32_t source,uint32_t vectors);
extern "C" void Ben10FovEnd();
uint64_t Ben10SubmittedFrames();
struct Ben10FrameStats {
  std::array<float,240> frame_times_ms{};
  size_t count=0;
  double fps=0,latest_ms=0,p95_ms=0;
  uint64_t submitted_frames=0;
};
Ben10FrameStats Ben10ReadFrameStats();
