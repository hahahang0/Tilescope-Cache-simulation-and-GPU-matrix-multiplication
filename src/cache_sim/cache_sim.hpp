#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace tilescope {

enum class Policy { Lru, Fifo };
enum class Operation { Load, Store };

struct Config {
    std::uint64_t capacity_bytes = 32 * 1024;
    std::uint64_t line_bytes = 64;
    std::uint64_t ways = 8;
    Policy policy = Policy::Lru;
};

struct Stats {
    std::uint64_t accesses = 0;
    std::uint64_t hits = 0;
    std::uint64_t misses = 0;
    std::uint64_t evictions = 0;
    std::uint64_t write_backs = 0;
    std::uint64_t compulsory = 0;
    std::uint64_t capacity = 0;
    std::uint64_t conflict = 0;
};

class Cache {
public:
    explicit Cache(const Config& config, bool classify_misses = false);
    void access(std::uint64_t address, Operation operation);
    const Stats& stats() const { return stats_; }
    std::uint64_t set_count() const { return set_count_; }
    std::uint64_t line_count() const { return line_count_; }

private:
    struct Line {
        std::uint64_t tag = 0;
        std::uint64_t stamp = 0;
        bool valid = false;
        bool dirty = false;
    };

    struct ShadowLine {
        std::uint64_t stamp = 0;
    };

    Config config_;
    std::uint64_t set_count_ = 0;
    std::uint64_t line_count_ = 0;
    unsigned offset_bits_ = 0;
    unsigned index_bits_ = 0;
    std::uint64_t clock_ = 0;
    std::vector<Line> lines_;
    Stats stats_;
    bool classify_ = false;
    std::unordered_map<std::uint64_t, ShadowLine> shadow_;
    std::unordered_set<std::uint64_t> seen_blocks_;

    void update_shadow(std::uint64_t block);
};

void run_matrix_pattern(Cache& cache, int n, const std::string& pattern, int tile);
bool is_power_of_two(std::uint64_t value);
std::string policy_name(Policy policy);

}  // namespace tilescope
