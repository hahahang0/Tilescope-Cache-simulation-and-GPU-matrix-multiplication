#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Matrix = std::vector<float>;
using Clock = std::chrono::steady_clock;

void multiply(const Matrix& a, const Matrix& b, Matrix& c, int n, int tile, const std::string& algorithm) {
    if (algorithm == "naive") {
        for (int i = 0; i < n; ++i)
            for (int j = 0; j < n; ++j) {
                float sum = 0.0f;
                for (int k = 0; k < n; ++k) sum += a[static_cast<std::size_t>(i) * n + k] * b[static_cast<std::size_t>(k) * n + j];
                c[static_cast<std::size_t>(i) * n + j] = sum;
            }
    } else if (algorithm == "ikj") {
        for (int i = 0; i < n; ++i)
            for (int k = 0; k < n; ++k) {
                const float aik = a[static_cast<std::size_t>(i) * n + k];
                for (int j = 0; j < n; ++j) c[static_cast<std::size_t>(i) * n + j] += aik * b[static_cast<std::size_t>(k) * n + j];
            }
    } else {
        for (int ii = 0; ii < n; ii += tile)
            for (int kk = 0; kk < n; kk += tile)
                for (int jj = 0; jj < n; jj += tile)
                    for (int i = ii; i < std::min(ii + tile, n); ++i)
                        for (int k = kk; k < std::min(kk + tile, n); ++k) {
                            const float aik = a[static_cast<std::size_t>(i) * n + k];
                            for (int j = jj; j < std::min(jj + tile, n); ++j)
                                c[static_cast<std::size_t>(i) * n + j] += aik * b[static_cast<std::size_t>(k) * n + j];
                        }
    }
}

std::vector<int> parse_list(const std::string& value) {
    std::vector<int> values;
    std::size_t begin = 0;
    while (begin < value.size()) {
        const auto comma = value.find(',', begin);
        values.push_back(std::stoi(value.substr(begin, comma == std::string::npos ? comma : comma - begin)));
        if (comma == std::string::npos) break;
        begin = comma + 1;
    }
    return values;
}

std::string csv_quote(const std::string& value) {
    std::string out = "\"";
    for (char ch : value) { if (ch == '"') out += '"'; out += ch; }
    return out + '"';
}

double median(std::vector<double> values) {
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}
}  // namespace

int main(int argc, char** argv) {
    try {
        std::string sizes_arg = "128,256,512,1024";
        std::string tiles_arg = "8,16,32,64";
        std::string output_path = "results/cpu_results.csv";
        std::string cpu_name = "unspecified";
        int repeats = 5;
        for (int i = 1; i < argc; ++i) {
            const std::string key = argv[i];
            if (i + 1 == argc) throw std::invalid_argument("missing value after " + key);
            const std::string value = argv[++i];
            if (key == "--sizes") sizes_arg = value;
            else if (key == "--tile-sizes") tiles_arg = value;
            else if (key == "--repeats") repeats = std::stoi(value);
            else if (key == "--output") output_path = value;
            else if (key == "--cpu-name") cpu_name = value;
            else throw std::invalid_argument("unknown option: " + key);
        }
        if (repeats < 1) throw std::invalid_argument("repeats must be at least 1");
        std::ofstream output(output_path);
        if (!output) throw std::runtime_error("cannot create output file: " + output_path);
        output << "n,algorithm,tile,seconds,gflops,repeats,cpu_name\n" << std::setprecision(9);
        for (int n : parse_list(sizes_arg)) {
            if (n < 1) throw std::invalid_argument("matrix sizes must be positive");
            const std::size_t count = static_cast<std::size_t>(n) * n;
            Matrix a(count), b(count), c(count), reference(count);
            for (std::size_t i = 0; i < count; ++i) {
                a[i] = static_cast<float>((i * 17 + 3) % 101) / 101.0f;
                b[i] = static_cast<float>((i * 29 + 5) % 97) / 97.0f;
            }
            std::fill(reference.begin(), reference.end(), 0.0f);
            multiply(a, b, reference, n, 16, "naive");
            for (const std::string algorithm : {"naive", "ikj", "tiled"}) {
                const std::vector<int> selected_tiles = algorithm == "tiled" ? parse_list(tiles_arg) : std::vector<int>{0};
                for (int tile : selected_tiles) {
                    std::fill(c.begin(), c.end(), 0.0f);
                    multiply(a, b, c, n, tile == 0 ? 16 : tile, algorithm);
                    for (std::size_t p = 0; p < count; ++p)
                        if (std::fabs(c[p] - reference[p]) > 1.0e-3f * std::max(1.0f, std::fabs(reference[p])))
                            throw std::runtime_error("correctness check failed for " + algorithm + " at N=" + std::to_string(n));
                    (void)"warm-up";
                    std::vector<double> times;
                    times.reserve(static_cast<std::size_t>(repeats));
                    for (int rep = 0; rep < repeats + 1; ++rep) {
                        std::fill(c.begin(), c.end(), 0.0f);
                        const auto start = Clock::now();
                        multiply(a, b, c, n, tile == 0 ? 16 : tile, algorithm);
                        const auto stop = Clock::now();
                        if (rep != 0) times.push_back(std::chrono::duration<double>(stop - start).count());
                    }
                    const double seconds = median(times);
                    const double gflops = (2.0 * n * n * n) / seconds / 1.0e9;
                    output << n << ',' << algorithm << ',' << tile << ',' << seconds << ',' << gflops << ',' << repeats << ',' << csv_quote(cpu_name) << '\n';
                }
            }
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "cpu_bench: " << error.what() << '\n';
        return 2;
    }
}
