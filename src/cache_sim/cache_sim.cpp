#include "cache_sim.hpp"

#include <algorithm>
#include <cctype>
#include <stdexcept>

namespace tilescope {

bool is_power_of_two(std::uint64_t value) {
    return value != 0 && (value & (value - 1)) == 0;
}

std::string policy_name(Policy policy) {
    return policy == Policy::Lru ? "lru" : "fifo";
}

namespace {
unsigned log2_power_of_two(std::uint64_t value) {
    unsigned result = 0;
    while (value > 1) {
        value >>= 1;
        ++result;
    }
    return result;
}

std::uint64_t align_up(std::uint64_t value, std::uint64_t alignment) {
    return (value + alignment - 1) & ~(alignment - 1);
}
}  // namespace

Cache::Cache(const Config& config, bool classify_misses) : config_(config), classify_(classify_misses) {
    if (!is_power_of_two(config_.capacity_bytes))
        throw std::invalid_argument("cache size must be a power of two (bytes)");
    if (!is_power_of_two(config_.line_bytes))
        throw std::invalid_argument("line size must be a power of two (bytes)");
    if (!is_power_of_two(config_.ways))
        throw std::invalid_argument("associativity must be a power of two (1, 2, 4, 8, ...)");
    if (config_.line_bytes > config_.capacity_bytes || config_.capacity_bytes % config_.line_bytes != 0)
        throw std::invalid_argument("cache size must be a multiple of the line size");
    line_count_ = config_.capacity_bytes / config_.line_bytes;
    if (config_.ways > line_count_ || line_count_ % config_.ways != 0)
        throw std::invalid_argument("associativity must divide the number of cache lines");
    set_count_ = line_count_ / config_.ways;
    if (!is_power_of_two(set_count_))
        throw std::invalid_argument("number of sets must be a power of two");
    offset_bits_ = log2_power_of_two(config_.line_bytes);
    index_bits_ = log2_power_of_two(set_count_);
    if (offset_bits_ + index_bits_ >= 64)
        throw std::invalid_argument("cache configuration leaves no address bits for the tag");

    lines_.resize(static_cast<std::size_t>(line_count_));
    if (classify_) {
        shadow_.reserve(static_cast<std::size_t>(line_count_ * 2));
        seen_blocks_.reserve(1 << 20);
    }
}

void Cache::update_shadow(std::uint64_t block) {
    auto hit = shadow_.find(block);
    if (hit != shadow_.end()) {
        hit->second.stamp = ++clock_;
        return;
    }
    if (shadow_.size() == line_count_) {
        auto victim = shadow_.begin();
        for (auto it = shadow_.begin(); it != shadow_.end(); ++it)
            if (it->second.stamp < victim->second.stamp) victim = it;
        shadow_.erase(victim);
    }
    shadow_.emplace(block, ShadowLine{++clock_});
}

void Cache::access(std::uint64_t address, Operation operation) {
    ++stats_.accesses;
    const std::uint64_t block = address >> offset_bits_;
    const std::uint64_t set = (address >> offset_bits_) & (set_count_ - 1);
    const std::uint64_t tag = address >> (offset_bits_ + index_bits_);
    const std::size_t first = static_cast<std::size_t>(set * config_.ways);
    std::size_t invalid = first;
    bool has_invalid = false;
    std::size_t oldest = first;
    for (std::size_t way = 0; way < config_.ways; ++way) {
        Line& line = lines_[first + way];
        if (line.valid && line.tag == tag) {
            ++stats_.hits;
            if (config_.policy == Policy::Lru) line.stamp = ++clock_;
            if (operation == Operation::Store) line.dirty = true;
            if (classify_) update_shadow(block);
            return;
        }
        if (!line.valid && !has_invalid) {
            invalid = first + way;
            has_invalid = true;
        }
        if (line.valid && lines_[oldest].stamp > line.stamp) oldest = first + way;
    }

    ++stats_.misses;
    if (classify_) {
        if (seen_blocks_.insert(block).second) {
            ++stats_.compulsory;
        } else if (shadow_.find(block) == shadow_.end()) {
            ++stats_.capacity;
        } else {
            ++stats_.conflict;
        }
        update_shadow(block);
    }

    const std::size_t victim = has_invalid ? invalid : oldest;
    Line& line = lines_[victim];
    if (line.valid) {
        ++stats_.evictions;
        if (line.dirty) ++stats_.write_backs;
    }
    line.tag = tag;
    line.valid = true;
    line.dirty = operation == Operation::Store;
    line.stamp = ++clock_;
}

void run_matrix_pattern(Cache& cache, int n, const std::string& pattern, int tile) {
    if (n <= 0) throw std::invalid_argument("N must be positive");
    if (tile <= 0) throw std::invalid_argument("tile size must be positive");
    const std::uint64_t matrix_bytes = static_cast<std::uint64_t>(n) * n * sizeof(float);
    const std::uint64_t a_base = 0;
    const std::uint64_t b_base = align_up(matrix_bytes, 4096);
    const std::uint64_t c_base = b_base + align_up(matrix_bytes, 4096);
    const std::uint64_t row_bytes = static_cast<std::uint64_t>(n) * sizeof(float);
    const auto addr = [row_bytes](std::uint64_t base, int row, int col) {
        return base + static_cast<std::uint64_t>(row) * row_bytes + static_cast<std::uint64_t>(col) * sizeof(float);
    };
    const auto mac = [&](int i, int j, int k) {
        cache.access(addr(a_base, i, k), Operation::Load);
        cache.access(addr(b_base, k, j), Operation::Load);
        cache.access(addr(c_base, i, j), Operation::Load);
        cache.access(addr(c_base, i, j), Operation::Store);
    };

    if (pattern == "naive") {
        for (int i = 0; i < n; ++i)
            for (int j = 0; j < n; ++j)
                for (int k = 0; k < n; ++k) mac(i, j, k);
    } else if (pattern == "ikj") {
        for (int i = 0; i < n; ++i)
            for (int k = 0; k < n; ++k)
                for (int j = 0; j < n; ++j) mac(i, j, k);
    } else if (pattern == "tiled") {
        // ii, kk, jj, then i, k, j: A[i,k] is reused across a contiguous j tile.
        for (int ii = 0; ii < n; ii += tile)
            for (int kk = 0; kk < n; kk += tile)
                for (int jj = 0; jj < n; jj += tile)
                    for (int i = ii; i < std::min(ii + tile, n); ++i)
                        for (int k = kk; k < std::min(kk + tile, n); ++k)
                            for (int j = jj; j < std::min(jj + tile, n); ++j) mac(i, j, k);
    } else {
        throw std::invalid_argument("pattern must be one of: naive, ikj, tiled");
    }
}

}  // namespace tilescope
