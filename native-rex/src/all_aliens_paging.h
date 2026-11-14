#pragma once
#include <cstdint>
#include <cstdlib>

namespace ben10 {
// Only advances on an RT rising edge while LT is already held. Releasing LT
// restores the player's original four slots, rather than rewriting the preset.
class AlienPages {
 public:
  int Poll(bool enabled, bool connected, uint8_t lt, uint8_t rt) {
    const bool left=lt>30, right=rt>30;
    if (!enabled || !connected || !left) {
      page_=0;
      // RT pressed before opening the wheel must not also turn a page.
      right_down_=right;
      left_down_=false;
      return enabled ? 0 : -1;
    }
    if (left_down_ && right && !right_down_) page_=(page_+1)%Pages();
    left_down_=true;right_down_=right;
    return page_;
  }
 private:
  // The player's four slots plus two pages of extras; the launcher raises
  // this when it installs aliens imported from Vilgax Attacks.
  static int Pages() {
    static const int pages=[] {
      const char* value=std::getenv("BEN10_ALIEN_PAGES");
      const int count=value?std::atoi(value):3;
      return count>=3 && count<=8?count:3;
    }();
    return pages;
  }
  int page_=0;
  bool left_down_=false,right_down_=false;
};
}
