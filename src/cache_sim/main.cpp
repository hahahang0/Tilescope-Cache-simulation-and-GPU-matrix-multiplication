#include "cache_sim.hpp"

#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
struct Args {
    tilescope::Config cache;
    int n = 64;
    int tile = 16;
    std::string pattern = "naive";
    std::string format = "human";
    std::string trace;
    bool classify = false;
};

std::uint64_t parse_u64(const std::string& value, const std::string& name) {
    try { return std::stoull(value); }
    catch (...) { throw std::invalid_argument("invalid integer for " + name + ": " + value); }
}

Args parse_args(int argc, char** argv) {
    Args args;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        auto value = [&]() -> std::string {
            if (i + 1 >= argc) throw std::invalid_argument("missing value after " + key);
            return argv[++i];
        };
        if (key == "--help" || key == "-h") {
            std::cout << "cache_sim [--n N] [--pattern naive|ikj|tiled] [--tile T] [--cache-size bytes] "
                         "[--line-size bytes] [--ways N|fully] [--policy lru|fifo] [--classify] "
                         "[--trace text-file] [--format human|json|csv]\n"
                         "Trace lines: R 0xADDRESS or W 0xADDRESS. Matrix mode emits A load, B load, "
                         "C load, C store per multiply-accumulate.\n";
            std::exit(0);
        } else if (key == "--n") args.n = static_cast<int>(parse_u64(value(), key));
        else if (key == "--tile") args.tile = static_cast<int>(parse_u64(value(), key));
        else if (key == "--pattern") args.pattern = value();
        else if (key == "--cache-size") args.cache.capacity_bytes = parse_u64(value(), key);
        else if (key == "--line-size") args.cache.line_bytes = parse_u64(value(), key);
        else if (key == "--ways") {
            const auto w = value();
            args.cache.ways = w == "fully" ? args.cache.capacity_bytes / args.cache.line_bytes : parse_u64(w, key);
        } else if (key == "--policy") {
            const auto p = value();
            if (p == "lru") args.cache.policy = tilescope::Policy::Lru;
            else if (p == "fifo") args.cache.policy = tilescope::Policy::Fifo;
            else throw std::invalid_argument("policy must be lru or fifo");
        } else if (key == "--trace") args.trace = value();
        else if (key == "--format") args.format = value();
        else if (key == "--classify") args.classify = true;
        else throw std::invalid_argument("unknown option: " + key);
    }
    if (args.format != "human" && args.format != "json" && args.format != "csv")
        throw std::invalid_argument("format must be human, json, or csv");
    return args;
}

void emit(const Args& args, const tilescope::Cache& cache) {
    const auto& s = cache.stats();
    const double rate = s.accesses ? static_cast<double>(s.misses) / s.accesses : 0.0;
    if (args.format == "json") {
        std::cout << "{\"pattern\":\"" << (args.trace.empty() ? args.pattern : "trace") << "\",\"n\":" << args.n
                  << ",\"tile\":" << args.tile << ",\"cache_bytes\":" << args.cache.capacity_bytes
                  << ",\"line_bytes\":" << args.cache.line_bytes << ",\"ways\":" << args.cache.ways
                  << ",\"policy\":\"" << tilescope::policy_name(args.cache.policy) << "\",\"accesses\":" << s.accesses
                  << ",\"hits\":" << s.hits << ",\"misses\":" << s.misses << ",\"miss_rate\":" << std::setprecision(9) << rate
                  << ",\"evictions\":" << s.evictions << ",\"write_backs\":" << s.write_backs
                  << ",\"compulsory\":" << s.compulsory << ",\"capacity\":" << s.capacity
                  << ",\"conflict\":" << s.conflict << "}\n";
    } else if (args.format == "csv") {
        std::cout << "pattern,n,tile,cache_bytes,line_bytes,ways,policy,accesses,hits,misses,miss_rate,evictions,write_backs,compulsory,capacity,conflict\n";
        std::cout << (args.trace.empty() ? args.pattern : "trace") << ',' << args.n << ',' << args.tile << ','
                  << args.cache.capacity_bytes << ',' << args.cache.line_bytes << ',' << args.cache.ways << ','
                  << tilescope::policy_name(args.cache.policy) << ',' << s.accesses << ',' << s.hits << ',' << s.misses << ','
                  << std::setprecision(9) << rate << ',' << s.evictions << ',' << s.write_backs << ','
                  << s.compulsory << ',' << s.capacity << ',' << s.conflict << '\n';
    } else {
        std::cout << "Pattern: " << (args.trace.empty() ? args.pattern : "trace") << "\nN: " << args.n << ", tile: " << args.tile
                  << "\nCache: " << args.cache.capacity_bytes << " B, " << args.cache.line_bytes << " B lines, "
                  << args.cache.ways << "-way, " << tilescope::policy_name(args.cache.policy)
                  << "\nAccesses: " << s.accesses << "\nHits: " << s.hits << "\nMisses: " << s.misses
                  << " (" << std::fixed << std::setprecision(4) << rate * 100 << "%)\nEvictions: " << s.evictions
                  << "\nWrite-backs: " << s.write_backs;
        if (args.classify) std::cout << "\nMisses (compulsory/capacity/conflict): " << s.compulsory << '/' << s.capacity << '/' << s.conflict;
        std::cout << '\n';
    }
}
}  // namespace

int main(int argc, char** argv) {
    try {
        const Args args = parse_args(argc, argv);
        tilescope::Cache cache(args.cache, args.classify);
        if (args.trace.empty()) {
            tilescope::run_matrix_pattern(cache, args.n, args.pattern, args.tile);
        } else {
            std::ifstream input(args.trace, std::ios::binary);
            if (!input) throw std::runtime_error("cannot open trace file: " + args.trace);
            char op = 0;
            std::string address;
            while (input >> op >> address) {
                if (op != 'R' && op != 'r' && op != 'W' && op != 'w')
                    throw std::invalid_argument("trace operation must be R or W");
                const auto parsed = std::stoull(address, nullptr, 0);
                cache.access(parsed, (op == 'W' || op == 'w') ? tilescope::Operation::Store : tilescope::Operation::Load);
            }
            if (!input.eof()) throw std::runtime_error("malformed trace; expected '<R|W> <hex-or-decimal-address>' per line");
        }
        emit(args, cache);
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "cache_sim: " << error.what() << '\n';
        return 2;
    }
}
