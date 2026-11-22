#include <cuda_runtime.h>
#include <cublas_v2.h>

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

#define CUDA_CHECK(call) do { \
    const cudaError_t error__ = (call); \
    if (error__ != cudaSuccess) { \
        std::cerr << "CUDA error at " << __FILE__ << ':' << __LINE__ << ": " << cudaGetErrorString(error__) << '\n'; \
        std::exit(EXIT_FAILURE); \
    } \
} while (0)
#define CUBLAS_CHECK(call) do { \
    const cublasStatus_t status__ = (call); \
    if (status__ != CUBLAS_STATUS_SUCCESS) { \
        std::cerr << "cuBLAS error at " << __FILE__ << ':' << __LINE__ << ": status " << static_cast<int>(status__) << '\n'; \
        std::exit(EXIT_FAILURE); \
    } \
} while (0)

__global__ void naive_kernel(const float* a, const float* b, float* c, int n) {
    const int col = blockIdx.x * blockDim.x + threadIdx.x;
    const int row = blockIdx.y * blockDim.y + threadIdx.y;
    if (row >= n || col >= n) return;
    float sum = 0.0f;
    for (int k = 0; k < n; ++k) sum += a[static_cast<std::size_t>(row) * n + k] * b[static_cast<std::size_t>(k) * n + col];
    c[static_cast<std::size_t>(row) * n + col] = sum;
}

template <int TILE>
__global__ void tiled_kernel(const float* a, const float* b, float* c, int n) {
    __shared__ float tile_a[TILE][TILE];
    __shared__ float tile_b[TILE][TILE];
    const int tx = threadIdx.x;
    const int ty = threadIdx.y;
    const int row = blockIdx.y * TILE + ty;
    const int col = blockIdx.x * TILE + tx;
    float sum = 0.0f;
    const int tiles = (n + TILE - 1) / TILE;
    for (int m = 0; m < tiles; ++m) {
        const int a_col = m * TILE + tx;
        const int b_row = m * TILE + ty;
        tile_a[ty][tx] = (row < n && a_col < n) ? a[static_cast<std::size_t>(row) * n + a_col] : 0.0f;
        tile_b[ty][tx] = (b_row < n && col < n) ? b[static_cast<std::size_t>(b_row) * n + col] : 0.0f;
        __syncthreads();
        #pragma unroll
        for (int k = 0; k < TILE; ++k) sum += tile_a[ty][k] * tile_b[k][tx];
        __syncthreads();  // No thread overwrites a tile while another still consumes it.
    }
    if (row < n && col < n) c[static_cast<std::size_t>(row) * n + col] = sum;
}

namespace {
std::vector<int> parse_list(const std::string& text) {
    std::vector<int> result;
    std::size_t begin = 0;
    while (begin < text.size()) {
        const auto comma = text.find(',', begin);
        result.push_back(std::stoi(text.substr(begin, comma == std::string::npos ? comma : comma - begin)));
        if (comma == std::string::npos) break;
        begin = comma + 1;
    }
    return result;
}

template <typename Function>
double median_ms(Function launch, int repeats) {
    for (int i = 0; i < 2; ++i) launch();
    std::vector<float> values;
    values.reserve(static_cast<std::size_t>(repeats));
    cudaEvent_t start{}, stop{};
    CUDA_CHECK(cudaEventCreate(&start));
    CUDA_CHECK(cudaEventCreate(&stop));
    for (int i = 0; i < repeats; ++i) {
        CUDA_CHECK(cudaEventRecord(start));
        launch();
        CUDA_CHECK(cudaEventRecord(stop));
        CUDA_CHECK(cudaEventSynchronize(stop));
        float elapsed = 0.0f;
        CUDA_CHECK(cudaEventElapsedTime(&elapsed, start, stop));
        values.push_back(elapsed);
    }
    CUDA_CHECK(cudaEventDestroy(start));
    CUDA_CHECK(cudaEventDestroy(stop));
    std::sort(values.begin(), values.end());
    return values[values.size() / 2];
}

template <typename Launch>
void check_against(const std::vector<float>& reference, std::vector<float>& output, Launch launch,
                   float* device_c, int n, const char* name) {
    launch();
    CUDA_CHECK(cudaGetLastError());
    CUDA_CHECK(cudaDeviceSynchronize());
    CUDA_CHECK(cudaMemcpy(output.data(), device_c, output.size() * sizeof(float), cudaMemcpyDeviceToHost));
    constexpr float atol = 1.0e-2f;
    constexpr float rtol = 1.0e-3f;
    for (std::size_t i = 0; i < output.size(); ++i)
        if (std::fabs(output[i] - reference[i]) > atol + rtol * std::fabs(reference[i]))
            throw std::runtime_error(std::string(name) + " correctness mismatch at linear index " + std::to_string(i) +
                                     " (N=" + std::to_string(n) + ")");
}

void csv_row(std::ofstream& csv, const char* gpu, int runtime, int driver, int n, const char* algorithm,
             int tile, double ms, int repeats) {
    const double seconds = ms / 1000.0;
    const double gflops = 2.0 * n * n * n / seconds / 1.0e9;
    csv << '"' << gpu << "\"," << runtime << ',' << driver << ',' << n << ',' << algorithm << ',' << tile << ','
        << std::setprecision(9) << seconds << ',' << gflops << ',' << repeats << ",0.01,0.001\n";
}
}  // namespace

int main(int argc, char** argv) {
    try {
        std::string sizes_text = "256,512,1024,2048,4096";
        std::string tiles_text = "8,16,32";
        std::string output_path = "results/gpu_results.csv";
        int repeats = 7;
        for (int i = 1; i < argc; ++i) {
            const std::string key = argv[i];
            if (i + 1 == argc) throw std::invalid_argument("missing value after " + key);
            const auto value = std::string(argv[++i]);
            if (key == "--sizes") sizes_text = value;
            else if (key == "--tile-sizes") tiles_text = value;
            else if (key == "--repeats") repeats = std::stoi(value);
            else if (key == "--output") output_path = value;
            else throw std::invalid_argument("unknown option: " + key);
        }
        int device = 0;
        CUDA_CHECK(cudaGetDevice(&device));
        cudaDeviceProp properties{};
        CUDA_CHECK(cudaGetDeviceProperties(&properties, device));
        int runtime_version = 0, driver_version = 0;
        CUDA_CHECK(cudaRuntimeGetVersion(&runtime_version));
        CUDA_CHECK(cudaDriverGetVersion(&driver_version));
        std::ofstream csv(output_path);
        if (!csv) throw std::runtime_error("cannot create GPU output file: " + output_path);
        csv << "gpu_name,cuda_runtime,cuda_driver,n,algorithm,tile,seconds,gflops,repeats,atol,rtol\n";
        cublasHandle_t handle{};
        CUBLAS_CHECK(cublasCreate(&handle));
        const std::vector<int> tiles = parse_list(tiles_text);
        for (int n : parse_list(sizes_text)) {
            const std::size_t count = static_cast<std::size_t>(n) * n;
            const std::size_t bytes = count * sizeof(float);
            std::size_t free_bytes = 0, total_bytes = 0;
            CUDA_CHECK(cudaMemGetInfo(&free_bytes, &total_bytes));
            if (3 * bytes > free_bytes) {
                std::cerr << "Skipping N=" << n << ": A, B, and C exceed currently free GPU memory.\n";
                continue;
            }
            std::vector<float> a(count), b(count), reference(count), output(count);
            std::mt19937 generator(20261121u + static_cast<unsigned>(n));
            std::uniform_real_distribution<float> distribution(-1.0f, 1.0f);
            for (std::size_t i = 0; i < count; ++i) { a[i] = distribution(generator); b[i] = distribution(generator); }
            float *device_a = nullptr, *device_b = nullptr, *device_c = nullptr;
            CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&device_a), bytes));
            CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&device_b), bytes));
            CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&device_c), bytes));
            CUDA_CHECK(cudaMemcpy(device_a, a.data(), bytes, cudaMemcpyHostToDevice));
            CUDA_CHECK(cudaMemcpy(device_b, b.data(), bytes, cudaMemcpyHostToDevice));
            const float alpha = 1.0f, beta = 0.0f;
            // Row-major C=A*B is column-major C^T=B^T*A^T in the same storage.
            CUBLAS_CHECK(cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, n, n, n, &alpha,
                                     device_b, n, device_a, n, &beta, device_c, n));
            CUDA_CHECK(cudaDeviceSynchronize());
            CUDA_CHECK(cudaMemcpy(reference.data(), device_c, bytes, cudaMemcpyDeviceToHost));
            const double blas_ms = median_ms([&] {
                CUBLAS_CHECK(cublasSgemm(handle, CUBLAS_OP_N, CUBLAS_OP_N, n, n, n, &alpha,
                                         device_b, n, device_a, n, &beta, device_c, n));
            }, repeats);
            csv_row(csv, properties.name, runtime_version, driver_version, n, "cublas", 0, blas_ms, repeats);

            dim3 block(16, 16);
            dim3 grid((n + block.x - 1) / block.x, (n + block.y - 1) / block.y);
            auto naive = [&] { naive_kernel<<<grid, block>>>(device_a, device_b, device_c, n); CUDA_CHECK(cudaGetLastError()); };
            check_against(reference, output, naive, device_c, n, "naive");
            const double naive_ms = median_ms(naive, repeats);
            csv_row(csv, properties.name, runtime_version, driver_version, n, "naive", 0, naive_ms, repeats);

            for (int tile : tiles) {
                if (tile != 8 && tile != 16 && tile != 32) throw std::invalid_argument("tile widths must be 8, 16, or 32");
                const dim3 tiled_block(static_cast<unsigned>(tile), static_cast<unsigned>(tile));
                const dim3 tiled_grid((n + tile - 1) / tile, (n + tile - 1) / tile);
                auto tiled = [&] {
                    if (tile == 8) tiled_kernel<8><<<tiled_grid, tiled_block>>>(device_a, device_b, device_c, n);
                    else if (tile == 16) tiled_kernel<16><<<tiled_grid, tiled_block>>>(device_a, device_b, device_c, n);
                    else tiled_kernel<32><<<tiled_grid, tiled_block>>>(device_a, device_b, device_c, n);
                    CUDA_CHECK(cudaGetLastError());
                };
                check_against(reference, output, tiled, device_c, n, "tiled");
                const double tiled_ms = median_ms(tiled, repeats);
                csv_row(csv, properties.name, runtime_version, driver_version, n, "tiled", tile, tiled_ms, repeats);
            }
            CUDA_CHECK(cudaFree(device_a));
            CUDA_CHECK(cudaFree(device_b));
            CUDA_CHECK(cudaFree(device_c));
        }
        CUBLAS_CHECK(cublasDestroy(handle));
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "gpu_bench: " << error.what() << '\n';
        return 2;
    }
}
