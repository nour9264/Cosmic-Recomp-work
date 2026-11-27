#pragma once
#include <array>
#include <atomic>
#include <filesystem>
#include <fstream>
#include <string>

// Cosmetics category of the Upgrades menu: what was bought and what is switched on.
// Purchases spend from the same point balance as the other upgrades (balance shown =
// game points - spent here). State lives in pc-cosmetics.ini beside the other settings.
// Play as Albedo and Transformation Animation keep their own switches (albedo_hud::enabled,
// transformation_animation_enabled); only the gate (owned) is stored here.
namespace ben10::cosmetics {
enum Item { Albedo = 0, Transform = 1, Realistic = 2, Bolts = 3, Count = 4 };
inline constexpr std::array<unsigned, Count> costs{70000, 25000, 40000, 30000};
inline std::array<std::atomic<bool>, Count> owned{};
inline std::atomic<bool> realistic_on{false}, bolts_on{false};
inline std::atomic<unsigned> spent{0};

inline void Load(const std::filesystem::path& root) {
    std::ifstream file(root / "pc-cosmetics.ini");
    for (std::string line; std::getline(file, line);) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        const auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        const auto key = line.substr(0, eq), value = line.substr(eq + 1);
        // Ownership and the points spent live in the game save now (CosmicBenCosmetic0..3), so an old file's
        // owned_* and spent lines are ignored; only the ON/OFF choices are kept here.
        if (key == "realistic") realistic_on = value == "on";
        else if (key == "bolts") bolts_on = value == "on";
    }
}

inline bool Save(const std::filesystem::path& root) {
    std::error_code error;
    std::filesystem::create_directories(root, error);
    auto path = root / "pc-cosmetics.ini";
    auto temporary = path;
    temporary += L".tmp";
    {
        std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
        file << "realistic=" << (realistic_on ? "on" : "off") << "\nbolts=" << (bolts_on ? "on" : "off") << "\n";
        file.close();
        if (!file) return false;
    }
    std::filesystem::rename(temporary, path, error);
    if (error) {
        std::filesystem::remove(path, error);
        std::filesystem::rename(temporary, path, error);
    }
    return !error;
}
}  // namespace ben10::cosmetics
