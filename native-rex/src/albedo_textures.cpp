#include "albedo_textures.h"

#include "albedo_hud.h"
#include "frame_metrics.h"
#include <rex/system/xmemory.h>
#include <rex/logging.h>
#include <algorithm>
#include <bit>
#include <cmath>
#include <array>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string_view>
#include <vector>
#include <windows.h>

namespace ben10::albedo_textures {
std::atomic<rex::memory::Memory*> memory{nullptr};
std::filesystem::path pack_path;
std::filesystem::path button_icon_preview_path;
std::filesystem::path keyboard_icon_path;
std::filesystem::path prompt_sprite_path;
std::atomic<ButtonIcons> button_icons{ButtonIcons::Xbox};

namespace {
constexpr uint32_t kSpritePage = 16384;
constexpr uint32_t kPageMask = 0x1ffff000;
thread_local int prompt_sprite = -1;
thread_local bool prompt_sprite_bound = false;
struct Sprite {
  uint32_t virtual_address = 0;
  uint32_t physical_address = 0;
};
std::array<Sprite, 16> sprites;
int WorldPromptFace(rex::memory::Memory& mem, uint32_t base, uint32_t blocks);

const std::vector<uint8_t>& SpritePixels() {
  static const auto pixels = [] {
    constexpr std::string_view magic("PSIC\3\0\0\0", 8);
    constexpr size_t size = kSpritePage * sprites.size();
    if (std::ifstream file(prompt_sprite_path, std::ios::binary); file) {
      char header[magic.size()]{};
      std::vector<uint8_t> data(size);
      if (file.read(header, sizeof(header)) && std::string_view(header, sizeof(header)) == magic &&
          file.read(reinterpret_cast<char*>(data.data()), data.size()) &&
          file.peek() == std::char_traits<char>::eof()) return data;
    }
    const auto module = GetModuleHandleW(nullptr);
    const auto resource = FindResourceW(module, MAKEINTRESOURCEW(102), MAKEINTRESOURCEW(10));
    if (!resource || SizeofResource(module, resource) != magic.size() + size)
      return std::vector<uint8_t>{};
    const auto data = LoadResource(module, resource);
    const auto* bytes = data ? static_cast<const uint8_t*>(LockResource(data)) : nullptr;
    if (!bytes || std::memcmp(bytes, magic.data(), magic.size()) != 0)
      return std::vector<uint8_t>{};
    return std::vector<uint8_t>(bytes + magic.size(), bytes + magic.size() + size);
  }();
  return pixels;
}
}

bool HasPromptSprites() {
  return !SpritePixels().empty();
}

PromptSpriteBind::PromptSpriteBind(uint8_t code)
    : previous_(prompt_sprite), previous_bound_(prompt_sprite_bound) {
  prompt_sprite = -1;
  prompt_sprite_bound = false;
  const auto mode = button_icons.load(std::memory_order_relaxed);
  if ((mode != ButtonIcons::PlayStation && mode != ButtonIcons::Keyboard) || !HasPromptSprites())
    return;
  const bool keyboard = mode == ButtonIcons::Keyboard;
  if (code >= 1 && code <= 4) {
    constexpr int keyboard_faces[] = {12, 14, 15, 13};
    prompt_sprite = keyboard ? keyboard_faces[code - 1] : code - 1;
    return;
  }
  switch (code) {
    case 0x19: prompt_sprite = keyboard ? 11 : 10; break;  // Right stick click.
    case 0x1a: prompt_sprite = keyboard ? 5 : 4; break;    // Left bumper.
    case 0x1b: prompt_sprite = keyboard ? 7 : 6; break;    // Left trigger.
    case 0x1d: prompt_sprite = keyboard ? 9 : 8; break;    // Right trigger.
  }
}

PromptSpriteBind::~PromptSpriteBind() {
  prompt_sprite = previous_;
  prompt_sprite_bound = previous_bound_;
}

bool BindPromptSprite(uint32_t& flags, uint32_t& size, uint32_t& base_word, uint32_t& mip_word) {
  if ((flags & 3) != 2 || ((mip_word >> 9) & 3) != 1) return false;
  auto* mem = memory.load(std::memory_order_acquire);
  if (!mem) return false;
  int index = prompt_sprite;
  if (index < 0) {
    constexpr uint32_t size_mask = (1u << 26) - 1;
    constexpr uint32_t size_64 = (63u << 13) | 63u;
    constexpr uint32_t size_128 = (127u << 13) | 127u;
    const auto dimensions = size & size_mask;
    if ((base_word & 63) != 20 || (dimensions != size_64 && dimensions != size_128)) return false;
    const auto mode = button_icons.load(std::memory_order_relaxed);
    if (mode != ButtonIcons::PlayStation && mode != ButtonIcons::Keyboard) return false;
    const int face = WorldPromptFace(*mem, base_word & kPageMask, dimensions == size_64 ? 16 : 32);
    if (face < 0 || !HasPromptSprites()) return false;
    constexpr int playstation_faces[] = {0, 3, 1, 2};
    index = mode == ButtonIcons::Keyboard ? 12 + face : playstation_faces[face];
  }
  auto& sprite = sprites[index];
  if (!sprite.virtual_address) {
    auto* heap = mem->LookupHeapByType(true, 4096);
    uint32_t address = 0;
    if (!heap || !heap->Alloc(kSpritePage + 4096, 4096,
          rex::memory::kMemoryAllocationReserve | rex::memory::kMemoryAllocationCommit,
          rex::memory::kMemoryProtectRead | rex::memory::kMemoryProtectWrite, true, &address))
      return false;
    const auto physical = mem->GetPhysicalAddress(address);
    if (!physical || physical != (physical & kPageMask)) {
      heap->Release(address);
      return false;
    }
    std::memcpy(mem->TranslateVirtual(address),
                SpritePixels().data() + index * kSpritePage, kSpritePage);
    sprite = {address, physical};
    REXLOG_INFO("Button Icons: prompt sprite {} ready", index);
  }
  flags = (flags & 0x003fffff) | 0x81000000;
  size = (127u << 13) | 127u;
  base_word = sprite.physical_address | 0x54;
  mip_word &= 0x7ff;
  if (prompt_sprite >= 0) prompt_sprite_bound = true;
  return true;
}

uint32_t PromptSpriteBind::Coordinates(uint32_t original) const {
  if (!prompt_sprite_bound || !original) return original;
  auto* mem = memory.load(std::memory_order_acquire);
  if (!mem) return original;
  const auto* source = mem->TranslateVirtual<const uint8_t*>(original);
  std::array<float, 12> uv{};
  for (size_t i = 0; i < uv.size(); ++i) {
    const auto* word = source + i * 4;
    const auto bits = uint32_t(word[0]) << 24 | uint32_t(word[1]) << 16 |
                      uint32_t(word[2]) << 8 | word[3];
    uv[i] = std::bit_cast<float>(bits);
    if (!std::isfinite(uv[i])) return original;
  }
  const auto address = sprites[prompt_sprite].virtual_address + kSpritePage;
  auto* result = mem->TranslateVirtual<uint8_t*>(address);
  for (size_t axis = 0; axis < 2; ++axis) {
    float low = uv[axis], high = uv[axis];
    for (size_t i = axis + 2; i < uv.size(); i += 2) {
      low = std::min(low, uv[i]);
      high = std::max(high, uv[i]);
    }
    if (low == high) return original;
    for (size_t i = axis; i < uv.size(); i += 2) {
      const auto value = std::bit_cast<uint32_t>((uv[i] - low) / (high - low));
      for (size_t byte = 0; byte < 4; ++byte)
        result[i * 4 + byte] = static_cast<uint8_t>(value >> (24 - byte * 8));
    }
  }
  return address;
}

void TracePromptRenderer(uint32_t symbol, uint32_t alias, uint32_t callback) {
  constexpr uint32_t text_method = 0x5da0fc05;
  if (symbol == text_method || alias == text_method)
    REXLOG_INFO("Button Icons: original text renderer callback {:08X}", callback);
}

PromptDraw::PromptDraw(uint8_t* text) {
  const auto mode = button_icons.load(std::memory_order_relaxed);
  if ((mode != ButtonIcons::Keyboard && mode != ButtonIcons::PlayStation) || text[1] != ' ')
    return;
  if (mode == ButtonIcons::PlayStation && HasPromptSprites()) return;
  if (mode == ButtonIcons::Keyboard && text[0] == 26 && HasPromptSprites()) return;
  const bool keyboard = mode == ButtonIcons::Keyboard;
  const char* keycap = nullptr;
  switch (text[0]) {
    case 1: keycap = keyboard ? "[SPACE]" : "[CROSS]"; break;
    case 2: keycap = keyboard ? "[L]" : "[SQUARE]"; break;
    case 3: keycap = keyboard ? "[P]" : "[TRIANGLE]"; break;
    case 4: keycap = keyboard ? "[BKSP]" : "[CIRCLE]"; break;
    case 26: keycap = keyboard ? "[1]" : "[L1]"; break;
  }
  if (!keycap) return;
  const auto size = std::strlen(keycap);
  const auto* end = static_cast<const uint8_t*>(std::memchr(text, 0, original_.size() - size));
  if (!end || end <= text + 1) return;
  const auto length = static_cast<size_t>(end - text);
  text_ = text;
  saved_size_ = length + size;
  std::memcpy(original_.data(), text, saved_size_);
  std::memmove(text + size, text + 1, length);
  std::memcpy(text, keycap, size);
}

PromptDraw::~PromptDraw() {
  if (text_) std::memcpy(text_, original_.data(), saved_size_);
}

static ButtonIcons ConnectedControllerIcons() {
  static thread_local ULONGLONG next_check = 0;
  static thread_local auto detected = ButtonIcons::Keyboard;
  const auto now = GetTickCount64();
  if (now < next_check) return detected;
  next_check = now + 1000;
  UINT count = 0;
  if (GetRawInputDeviceList(nullptr, &count, sizeof(RAWINPUTDEVICELIST)) != 0)
    return detected;
  std::vector<RAWINPUTDEVICELIST> devices(count);
  if (count && GetRawInputDeviceList(devices.data(), &count, sizeof(RAWINPUTDEVICELIST)) == UINT(-1))
    return detected;
  detected = ButtonIcons::Keyboard;
  for (const auto& device : devices) {
    if (device.dwType != RIM_TYPEHID) continue;
    RID_DEVICE_INFO info{};
    info.cbSize = sizeof(info);
    UINT size = sizeof(info);
    if (GetRawInputDeviceInfoW(device.hDevice, RIDI_DEVICEINFO, &info, &size) == UINT(-1))
      continue;
    if (info.hid.usUsagePage != 1 || (info.hid.usUsage != 4 && info.hid.usUsage != 5))
      continue;
    if (info.hid.dwVendorId == 0x054c) return detected = ButtonIcons::PlayStation;
    detected = ButtonIcons::Xbox;
  }
  return detected;
}

struct Texture {
  uint32_t key, width, height, format, base_size, mip_size;
  uint64_t prefix_hash, base_hash, mip_hash;
  std::vector<uint8_t> replacement;
  uint32_t replacement_base = 0;
  uint32_t verified_base = 0, verified_mip = 0;
};

inline std::vector<Texture> ReadPack(const std::filesystem::path& path) {
  std::ifstream file(path, std::ios::binary);
  char magic[8]{};
  uint32_t count = 0;
  file.read(magic, sizeof(magic));
  file.read(reinterpret_cast<char*>(&count), sizeof(count));
  const std::string_view version(magic, sizeof(magic));
  if (!file || (version != std::string_view("ALBD\2\0\0\0", 8) &&
                version != std::string_view("ALBD\3\0\0\0", 8)) ||
      !count || count > 32) return {};
  std::vector<Texture> textures;
  for (uint32_t i = 0; i < count; ++i) {
    Texture item{};
    const auto read = [&](auto& value) {
      file.read(reinterpret_cast<char*>(&value), sizeof(value));
    };
    read(item.key); read(item.width); read(item.height); read(item.format);
    read(item.base_size); read(item.mip_size);
    read(item.prefix_hash); read(item.base_hash); read(item.mip_hash);
    if (!file || !item.width || item.width > 1024 || !item.height || item.height > 1024 ||
        (item.format != 18 && item.format != 20) ||
        item.base_size < 4096 || item.base_size > 2 * 1024 * 1024 || (item.base_size & 4095) ||
        item.mip_size > 2 * 1024 * 1024 || (item.mip_size & 4095)) return {};
    item.replacement.resize(item.base_size + item.mip_size);
    if (!file.read(reinterpret_cast<char*>(item.replacement.data()), item.replacement.size())) return {};
    textures.push_back(std::move(item));
  }
  return file.peek() == std::char_traits<char>::eof() ? std::move(textures) : std::vector<Texture>{};
}

inline uint64_t Fingerprint(const uint8_t* bytes, uint32_t size, uint64_t hash = 14695981039346656037ull) {
  for (uint32_t i = 0; i < size; ++i) hash = (hash ^ bytes[i]) * 1099511628211ull;
  return hash;
}

static uint32_t IconBlockOffset(uint32_t x, uint32_t y) {
  const uint32_t micro = ((x & 7) + ((y & 14) << 2)) << 4;
  const uint32_t offset = ((micro & ~15u) << 1) + (micro & 15) + ((y & 1) << 4);
  return ((offset & ~511u) << 3) + ((y & 16) << 7) + ((offset & 448) << 2) +
         (((((y & 8) >> 2) + (x >> 3)) & 3) << 6) + (offset & 63);
}

void PrepareButtonIconArchive(const std::filesystem::path& game, const std::filesystem::path& user,
                              ButtonIcons mode) {
  const auto playstation = ReadPack(user / "playstation-button-icons.bin");
  const auto keyboard = ReadPack(user / "keyboard-button-icons.bin");
  if (playstation.empty() || keyboard.empty()) return;
  const auto archive = game / "global/gtex_s.xbx";
  auto backup = archive; backup += L".cosmic-icon-original";
  const auto read = [](const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("Could not read button icon archive");
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(input), {});
  };
  const auto current = read(archive);
  const bool has_backup = std::filesystem::is_regular_file(backup);
  const auto original = has_backup ? read(backup) : current;
  const auto make = [&](const std::vector<Texture>& icons) {
    auto bytes = original;
    const auto word = [&](size_t offset) {
      if (offset > bytes.size() || bytes.size() - offset < 4)
        throw std::runtime_error("Truncated button icon archive");
      return uint32_t(bytes[offset]) << 24 | uint32_t(bytes[offset + 1]) << 16 |
             uint32_t(bytes[offset + 2]) << 8 | bytes[offset + 3];
    };
    if (word(0) != 0x76617073 || word(4) != 0x00010003 || word(48) != 12)
      throw std::runtime_error("Unsupported button icon archive");
    const size_t base = word(28), directory = size_t(32) + word(44), count = word(8);
    if (directory > bytes.size() || count > (bytes.size() - directory) / 12 || base > bytes.size())
      throw std::runtime_error("Invalid button icon archive directory");
    for (const auto& icon : icons) {
      size_t index = 0;
      while (index < count && word(directory + index * 12) != icon.key) ++index;
      if (index == count) throw std::runtime_error("Original button icon not found");
      const size_t entry = directory + index * 12;
      const size_t offset = base + word(entry + 8);
      const size_t size = word(entry + 4) & 0xffffff;
      if (size != 128 + icon.replacement.size() || offset > bytes.size() || size > bytes.size() - offset)
        throw std::runtime_error("Unexpected button icon texture length");
      auto* pixels = bytes.data() + offset + 128;
      uint64_t active = 14695981039346656037ull;
      const uint32_t blocks = icon.width / 4;
      for (uint32_t y = 0; y < blocks; ++y)
        for (uint32_t x = 0; x < blocks; ++x)
          active = Fingerprint(pixels + IconBlockOffset(x, y), 16, active);
      if (active != icon.base_hash) throw std::runtime_error("Original button icon signature mismatch");
      std::copy(icon.replacement.begin(), icon.replacement.end(), pixels);
    }
    return bytes;
  };
  const auto desired = mode == ButtonIcons::PlayStation ? make(playstation) :
                       mode == ButtonIcons::Keyboard ? make(keyboard) : original;
  if (current == desired) return;
  if (current != original && current != make(playstation) && current != make(keyboard))
    throw std::runtime_error("The button icon archive was modified by another tool");
  if (!has_backup) std::filesystem::copy_file(archive, backup);
  auto temporary = archive; temporary += L".icons-new";
  {
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    output.write(reinterpret_cast<const char*>(desired.data()), desired.size());
    output.close();
    if (!output) throw std::runtime_error("Could not write the button icon archive");
  }
  if (!MoveFileExW(temporary.c_str(), archive.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
    throw std::runtime_error("Could not install the button icon archive");
  REXLOG_INFO("Button Icons: prepared original UI archive for mode {}", static_cast<int>(mode));
}

inline bool Readable(rex::memory::Memory& mem, uint32_t address, uint32_t size) {
  return !size || mem.GetPhysicalHeap()->QueryRangeAccess(address, address + size - 1) !=
      rex::memory::PageAccess::kNoAccess;
}

namespace {
int WorldPromptFace(rex::memory::Memory& mem, uint32_t base, uint32_t blocks) {
  // Active BC3 blocks from the world prompts and circular QTE icons in gtex_s.xbx.
  // Ignore padding and require a full active-image match when there is no key.
  struct Signature { uint32_t key; uint64_t prefix, image; int face; uint32_t blocks = 16; };
  static constexpr Signature prompts[] = {
    {0xd82646fd, 0x825ba350b2cbbbd8ull, 0x1044ae59ed081fbcull, 0},
    {0x5556421e, 0x1ab37128ff9d88b3ull, 0x4a3b9c3ea7aa832full, 0},
    {0xd155d06f, 0x54e7a8f33b31b4bdull, 0xf91cc1bb963520dbull, 0},
    {0x5e1525cf, 0x497e22050ca471b0ull, 0xa4ff047b01dcde67ull, 0},
    {0x96f5aabf, 0x1ab37128ff9d88b3ull, 0xae058eee050cb6bfull, 0},
    {0xec35f9df, 0x030e4c379b5a881bull, 0x280b201deb355a00ull, 0},
    {0x56a9411e, 0xef4f9341e8d16a47ull, 0xa7f54baf9f23e57eull, 1},
    {0x5fdad78c, 0x96e17f60f58293d9ull, 0xb1d6b3abd0504b8dull, 1},
    {0xdbd945fd, 0xc425ac798e8ec4f4ull, 0x484f92d7dc1259a6ull, 1},
    {0x187aad5c, 0xc425ac798e8ec4f4ull, 0x34f0dee9d66ff768ull, 1},
    {0xd09a222c, 0x96e17f60f58293d9ull, 0x0cf891f8170fe481ull, 1},
    {0xbbd26cfd, 0x3669db383338d74full, 0xae8d3f542be7b219ull, 2},
    {0xf50180bf, 0xef7435499daf556dull, 0xf5ea8105e4499fa0ull, 2},
    {0x36a2681e, 0xef7435499daf556dull, 0x152cc69f347e94b3ull, 2},
    {0x8fc1d3df, 0x38ec5ce97c94d3a2ull, 0xf21641294e1573fcull, 2},
    {0x3de10fcf, 0xdec7ee196a705e03ull, 0xc3fdc1ebe43aa838ull, 2},
    {0xb2a1fa6f, 0xdec7ee196a705e03ull, 0xaafbc13881ea437full, 2},
    {0xfa086880, 0x523b1564a4e6478bull, 0xdace4efabb049923ull, 3},
    {0x39ab8021, 0x523b1564a4e6478bull, 0x0a59030d94ad4a90ull, 3},
    {0xf14b0f51, 0xd80caf0ef8ade809ull, 0x65a668a7dabca745ull, 3},
    {0x7e0bfaf1, 0xa55a00a92285c6f1ull, 0x94aec737ced00fbaull, 3},
    {0x62bafe3c, 0x77b616248c473d3cull, 0x66480c1be61f470dull, 3},
    {0x436bd341, 0xa4fe78a6b48f424dull, 0xa0963489595711fbull, 3},
    {0x77786c63, 0xde19b722ad1c462eull, 0x03ece4d3030ebb07ull, 3},
    {0x10fbcff1, 0xdf4e1319c0e84456ull, 0x5ca95f710e03f31dull, 0, 32},
    {0x9fbb3a51, 0xcd830a98b913b6c8ull, 0xf01e5da225d1b317ull, 1, 32},
    {0x2d9be641, 0x8bbfa746a837b172ull, 0x00ee56e2552b0859ull, 2, 32},
    {0x575bb521, 0x4796f14638699ebfull, 0x13f1a08ae3646e4full, 3, 32},
  };
  const auto key = albedo_hud::texture_key;
  for (const auto& prompt : prompts)
    if (prompt.blocks == blocks && prompt.key == key) return prompt.face;
  if (!base || base > 0x20000000 - kSpritePage || !Readable(mem, base, kSpritePage)) return -1;
  const auto* source = mem.TranslatePhysical(base);
  const auto center = blocks / 2;
  const auto prefix = Fingerprint(source + IconBlockOffset(center, center - 2), 16,
                                  Fingerprint(source + IconBlockOffset(center, center), 16));
  if (std::none_of(std::begin(prompts), std::end(prompts),
                   [prefix, blocks](const Signature& prompt) {
                     return prompt.blocks == blocks && prompt.prefix == prefix;
                   })) return -1;
  uint64_t image = 14695981039346656037ull;
  for (uint32_t y = 0; y < blocks; ++y)
    for (uint32_t x = 0; x < blocks; ++x)
      image = Fingerprint(source + IconBlockOffset(x, y), 16, image);
  for (const auto& prompt : prompts)
    if (prompt.blocks == blocks && prompt.prefix == prefix && prompt.image == image) return prompt.face;
  return -1;
}
}

template<int Pack>
void ApplyPack(rex::memory::Memory* mem, uint32_t flags, uint32_t size,
               uint32_t& base_word, uint32_t& mip_word) {
  const uint32_t format = base_word & 63;
  const auto key = albedo_hud::texture_key;
  const uint32_t width = (size & 8191) + 1, height = ((size >> 13) & 8191) + 1;
  if constexpr (Pack != 0) {

    const bool known = key == 0x10fbcff1 || key == 0x9fbb3a51 ||
                       key == 0x2d9be641 || key == 0x575bb521;
    static thread_local std::array<uint32_t, 48> audited{};
    const bool candidate = known || (width == height && (width == 64 || width == 128) && format == 20);
    const uint32_t page = base_word & 0x1ffff000;
    if (candidate && page && std::find(audited.begin(), audited.end(), page) == audited.end()) {
      const auto slot = std::find(audited.begin(), audited.end(), 0u);
      if (slot != audited.end()) {
        *slot = page;
        REXLOG_INFO("Button Icons trace: key={:08X}, {}x{}, format={}, flags={:08X}, base={:08X}, mip={:08X}",
                    key, width, height, format, flags, base_word, mip_word);
      }
    }
  }
  if (!(flags & 0x80000000) || (format != 18 && format != 20) || ((mip_word >> 9) & 3) != 1)
    return;
  constexpr uint32_t page_mask = 0x1ffff000;
  const uint32_t base = base_word & page_mask, mip = mip_word & page_mask;
  if (!base) return;
  if constexpr (Pack != 0) {
    if ((width != 64 && width != 128) || height != width || format != 20) return;
  }
  if (width < 32 || height < 32 || width > 1024 || height > 1024 ||
      (width & (width - 1)) || (height & (height - 1))) return;

  // Many draws bind the same pages. Cache both matches and misses for the
  // current submitted frame, then recheck the signature if pages are reused.
  struct CachedBind {
    uint64_t frame = UINT64_MAX;
    uint32_t size = 0, base = 0, mip = 0, format = 0, key = 0;
    uint32_t replacement_base = 0, replacement_mip = 0;
  };
  static thread_local std::array<CachedBind, 512> cache{};
  const auto frame = Ben10SubmittedFrames();
  auto& cached = cache[((base >> 12) * 31u + (mip >> 12)) % cache.size()];
  if (cached.frame == frame && cached.size == size && cached.base == base && cached.mip == mip &&
      cached.format == format && cached.key == key) {
    if (cached.replacement_base) {
      base_word = (base_word & ~page_mask) | cached.replacement_base;
      mip_word = (mip_word & ~page_mask) | cached.replacement_mip;
    }
    return;
  }
  cached = {frame, size, base, mip, format, key};
  static std::mutex lock;
  std::lock_guard guard(lock);
  static auto textures = [] {
    auto pack = ReadPack(Pack == 0 ? pack_path : Pack == 1 ? button_icon_preview_path : keyboard_icon_path);
    if constexpr (Pack != 0)
      REXLOG_INFO("Button Icons trace: mode={} loaded {} textures", Pack, pack.size());
    return pack;
  }();
  if (textures.empty()) return;
  const auto* source = mem->TranslatePhysical(base);
  const uint32_t base_size = ((width + 127) / 128) * ((height + 127) / 128) *
      (format == 20 ? 16384 : 8192);
  if (base_size > 0x20000000 - base) return;
  const uint32_t first = base_size / 4, second = base_size / 2;
  if (!Readable(*mem, base + first, 64) || !Readable(*mem, base + second, 64)) return;
  const uint32_t blocks = width / 4;
  uint64_t prefix;
  if constexpr (Pack != 0) {
    if (!Readable(*mem, base, base_size)) return;
    prefix = Fingerprint(source + IconBlockOffset(blocks / 2, blocks / 2 - 2), 16,
                        Fingerprint(source + IconBlockOffset(blocks / 2, blocks / 2), 16));
  } else {
    prefix = Fingerprint(source + second, 64, Fingerprint(source + first, 64));
  }
  for (auto& item : textures) {
    // Stock UI sprites have stable archive IDs. Their runtime padding or
    // mip upload can differ from the original archive, so use that identity
    // together with the exact fetch dimensions and format.
    const bool menu_trim = item.key == 0xa57fdd41 || item.key == 0x8f250b9a;
    const bool matching_key = (Pack != 0 || menu_trim) && key == item.key;
    // The stock menu also binds these textures without their mip pages.
    const bool bezel = item.key == 0xc8c35802;
    const bool base_only = !mip && (Pack != 0 || menu_trim || bezel || item.key == 0xe9c69775);
    if (item.width != width || item.height != height || item.format != format ||
        item.base_size != base_size || (!matching_key && item.prefix_hash != prefix) ||
        (!base_only && (item.mip_size != 0) != (mip != 0))) continue;
    if (!matching_key && (item.verified_base != base || item.verified_mip != mip)) {
      if constexpr (Pack != 0) {
        uint64_t active = 14695981039346656037ull;
        for (uint32_t y = 0; y < blocks; ++y)
          for (uint32_t x = 0; x < blocks; ++x)
            active = Fingerprint(source + IconBlockOffset(x, y), 16, active);
        if (active != item.base_hash) continue;
      } else {
        const auto* mip_source = mem->TranslatePhysical(mip);
        if (!Readable(*mem, base, item.base_size) ||
            Fingerprint(source, item.base_size) != item.base_hash ||
            (!base_only && (item.mip_size > 0x20000000 - mip ||
             !Readable(*mem, mip, item.mip_size) ||
             Fingerprint(mip_source, item.mip_size) != item.mip_hash))) continue;
      }
      item.verified_base = base;
      item.verified_mip = mip;
    }
    if (!item.replacement_base) {
      auto* heap = mem->LookupHeapByType(true, 4096);
      uint32_t address = 0;
      if (!heap || !heap->Alloc(static_cast<uint32_t>(item.replacement.size()), 4096,
            rex::memory::kMemoryAllocationReserve | rex::memory::kMemoryAllocationCommit,
            rex::memory::kMemoryProtectRead | rex::memory::kMemoryProtectWrite, true, &address)) return;
      const uint32_t physical = mem->GetPhysicalAddress(address);
      if (!physical || physical != (physical & page_mask) ||
          item.replacement.size() > 0x20000000 - physical) {
        heap->Release(address);
        return;
      }
      std::memcpy(mem->TranslateVirtual(address), item.replacement.data(), item.replacement.size());
      item.replacement_base = physical;
      REXLOG_INFO("Cosmic {}: replacement texture {:08X} ready",
                  Pack ? "Button Icons" : "Albedo", item.key);
    }
    cached.replacement_base = item.replacement_base;
    cached.replacement_mip = mip ? item.replacement_base + item.base_size : 0;
    base_word = (base_word & ~page_mask) | cached.replacement_base;
    mip_word = (mip_word & ~page_mask) | cached.replacement_mip;
    return;
  }
}

void Apply(uint32_t flags, uint32_t size, uint32_t& base_word, uint32_t& mip_word) {
  auto* mem = memory.load(std::memory_order_acquire);
  if (!mem) return;
  if (albedo_hud::enabled.load(std::memory_order_relaxed))
    ApplyPack<0>(mem, flags, size, base_word, mip_word);
  if (button_icon_preview_path.empty() && keyboard_icon_path.empty()) return;
  auto mode = button_icons.load(std::memory_order_relaxed);
  if (mode == ButtonIcons::Auto) mode = ConnectedControllerIcons();
  if (mode == ButtonIcons::PlayStation && !button_icon_preview_path.empty())
    ApplyPack<1>(mem, flags, size, base_word, mip_word);
  if (mode == ButtonIcons::Keyboard && !keyboard_icon_path.empty())
    ApplyPack<2>(mem, flags, size, base_word, mip_word);
}
}
