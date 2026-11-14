#pragma once
// Applies the Field of View preference to the gameplay camera. sub_821A5898
// builds the camera's projection from its vertical FOV in degrees; the hook
// (Ben10FovDegrees, frame_metrics.cpp) offsets that value as it is loaded, so
// the camera object and every other copy of the matrix stay the game's own.
#include "fov_setting.h"
#include <atomic>

namespace ben10::fov {
inline std::atomic<int> offset{0};  // Degrees added to the game's vertical FOV.
}
