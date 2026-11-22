#include "../src/cache_sim/cache_sim.hpp"

#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>

using namespace tilescope;

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    try {
        // Four sets, direct-mapped, 16-byte lines. Blocks 0, 1 and 4 map to sets 0, 1 and 0.
        Config direct{64, 16, 1, Policy::Lru};
        Cache c(direct);
        for (auto [address, op] : {std::pair<std::uint64_t, Operation>{0, Operation::Load}, {16, Operation::Load},
                                   {0, Operation::Load}, {64, Operation::Store}, {64, Operation::Load},
                                   {0, Operation::Load}}) c.access(address, op);
        const auto& s = c.stats();
        require(s.accesses == 6 && s.hits == 2 && s.misses == 4, "hand-computed direct-mapped counts");
        require(s.evictions == 2 && s.write_backs == 1, "dirty eviction/write-back counts");

        // A four-line fully-associative cache retains a three-line working set after warm-up.
        Config fitting{64, 16, 4, Policy::Lru};
        Cache fit(fitting);
        for (int repeat = 0; repeat < 10; ++repeat)
            for (int block = 0; block < 3; ++block) fit.access(static_cast<std::uint64_t>(block) * 16, Operation::Load);
        require(fit.stats().misses == 3, "fitting working set should miss only during warm-up");

        // A sequential 80-float scan crosses five 64-byte lines: 5/80 misses = 1/16.
        Config scan_config{256, 64, 1, Policy::Lru};
        Cache scan(scan_config);
        for (int element = 0; element < 80; ++element)
            scan.access(static_cast<std::uint64_t>(element) * sizeof(float), Operation::Load);
        require(scan.stats().misses == 5 && scan.stats().hits == 75, "sequential scan should miss once per line");

        // Five lines in a four-line fully associative LRU cache: cyclic reuse misses every time.
        Cache thrash(fitting);
        for (int repeat = 0; repeat < 8; ++repeat)
            for (int block = 0; block < 5; ++block) thrash.access(static_cast<std::uint64_t>(block) * 16, Operation::Load);
        require(thrash.stats().misses == 40, "cyclic over-capacity LRU stream should miss on every access");

        std::ofstream validation("results/validation_results.csv");
        validation << "case,accesses,hits,misses,evictions,write_backs,expected\n";
        validation << "hand_direct_mapped," << s.accesses << ',' << s.hits << ',' << s.misses << ',' << s.evictions << ',' << s.write_backs << ",\"4 sets; 0,16,0,64-store,64,0 gives 2 hits / 4 misses\"\n";
        validation << "fitting_working_set," << fit.stats().accesses << ',' << fit.stats().hits << ',' << fit.stats().misses << ',' << fit.stats().evictions << ',' << fit.stats().write_backs << ",3 compulsory misses then 27 hits\n";
        validation << "sequential_scan," << scan.stats().accesses << ',' << scan.stats().hits << ',' << scan.stats().misses << ',' << scan.stats().evictions << ',' << scan.stats().write_backs << ",80 float32 values; 64-byte lines hold 16 values; miss rate 1/16\n";
        validation << "cyclic_over_capacity," << thrash.stats().accesses << ',' << thrash.stats().hits << ',' << thrash.stats().misses << ',' << thrash.stats().evictions << ',' << thrash.stats().write_backs << ",5 lines cycle through 4 fully associative LRU lines\n";
        if (!validation) throw std::runtime_error("could not write results/validation_results.csv");

        bool rejected = false;
        try { Cache invalid(Config{300, 16, 1, Policy::Lru}); }
        catch (const std::invalid_argument&) { rejected = true; }
        require(rejected, "non-power-of-two cache size must be rejected");
        std::cout << "cache unit tests passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "test_cache: " << error.what() << '\n';
        return 1;
    }
}
