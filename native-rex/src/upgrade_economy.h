#pragma once
#include <array>
#include <string>

namespace ben10::upgrade_economy {
inline constexpr std::array<unsigned,3> stat_costs{15000,30000,45000};
inline constexpr std::array<unsigned,6> matrix_costs{15000,15000,30000,50000,100000,60000};
inline constexpr unsigned master_control_tier=5;
inline constexpr unsigned matrix_max=static_cast<unsigned>(matrix_costs.size());
static_assert(2*(stat_costs[0]+stat_costs[1]+stat_costs[2])+
    matrix_costs[0]+matrix_costs[1]+matrix_costs[2]+matrix_costs[3]+matrix_costs[4]+matrix_costs[5]==450000);
inline std::string Points(unsigned value) {
    auto result=std::to_string(value);
    for(int at=int(result.size())-3;at>0;at-=3)result.insert(size_t(at),1,',');
    return result;
}
}
