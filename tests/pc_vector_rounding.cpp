// Exercise the exact SIMDe operation emitted for vrfin128, without game data.
#include <simde/x86/sse4.1.h>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>

#if !defined(SIMDE_X86_SSE4_1_NATIVE)
#error This check requires the native SSE4.1 path used by the consumer.
#endif

__declspec(noinline) void Round(const float* input, float* output) {
  simde_mm_storeu_ps(output, simde_mm_round_ps(simde_mm_loadu_ps(input),
      SIMDE_MM_FROUND_TO_NEAREST_INT | SIMDE_MM_FROUND_NO_EXC));
}

int main() {
  const auto infinity=std::numeric_limits<float>::infinity();
  const auto nan=std::numeric_limits<float>::quiet_NaN();
  const std::array<std::array<float,4>,3> inputs{{
      {{0.5f,-0.5f,1.5f,-1.5f}}, {{2.5f,-2.5f,3.5f,-3.5f}},
      {{infinity,-infinity,nan,8388608.0f}}}};
  const std::array<std::array<float,4>,3> expected{{
      {{0.0f,-0.0f,2.0f,-2.0f}}, {{2.0f,-2.0f,4.0f,-4.0f}},
      {{infinity,-infinity,nan,8388608.0f}}}};
  const unsigned saved=_mm_getcsr();
  unsigned cases=0;
  for(unsigned mode:{_MM_ROUND_NEAREST,_MM_ROUND_DOWN,_MM_ROUND_UP,_MM_ROUND_TOWARD_ZERO}) {
    _mm_setcsr((saved & ~_MM_ROUND_MASK) | mode);
    for(size_t row=0;row<inputs.size();++row) {
      std::array<float,4> output{};Round(inputs[row].data(),output.data());
      for(size_t lane=0;lane<4;++lane) {
        if(std::isnan(expected[row][lane]) ? !std::isnan(output[lane]) :
            std::bit_cast<uint32_t>(output[lane])!=std::bit_cast<uint32_t>(expected[row][lane])) {
          _mm_setcsr(saved);return 1;
        }
        ++cases;
      }
    }
  }
  _mm_setcsr(saved);
  std::printf("Native nearest-even rounding: %u lane cases passed.\n",cases);
}
