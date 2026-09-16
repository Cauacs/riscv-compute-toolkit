#ifndef RCT_VECTOR_ADD_BENCHMARK_H
#define RCT_VECTOR_ADD_BENCHMARK_H

#include "rct/kernels.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct {
    size_t length;
    size_t warmup_iterations;
    size_t measured_iterations;
    uint64_t seed;
} rct_vector_add_f32_benchmark_config;

typedef struct {
    const char *name;
    rct_vector_add_f32_fn kernel;
} rct_vector_add_f32_benchmark_implementation;

typedef struct {
    uint64_t minimum_ns;
    double median_ns;
    double mean_ns;
} rct_vector_add_f32_benchmark_summary;

typedef struct {
    const char *implementation_name;
    bool valid;
    uint64_t *samples_ns;
    size_t sample_count;
    rct_vector_add_f32_benchmark_summary summary;
} rct_vector_add_f32_benchmark_result;

typedef enum {
    RCT_VECTOR_ADD_BENCHMARK_OK,
    RCT_VECTOR_ADD_BENCHMARK_INVALID_CONFIGURATION,
    RCT_VECTOR_ADD_BENCHMARK_ALLOCATION_FAILURE,
    RCT_VECTOR_ADD_BENCHMARK_CLOCK_FAILURE,
    RCT_VECTOR_ADD_BENCHMARK_VALIDATION_FAILURE,
} rct_vector_add_f32_benchmark_status;

/**
 * Summarize raw elapsed-time samples without changing their original order.
 *
 * At least one sample is required. The summary median is the mean of the two
 * central samples when sample_count is even.
 */
bool rct_vector_add_f32_benchmark_summarize_samples(
    const uint64_t *samples_ns,
    size_t sample_count,
    rct_vector_add_f32_benchmark_summary *summary
);

/**
 * Validate and benchmark each portable vector-add implementation.
 *
 * Inputs and reference output are generated before timing. Every implementation
 * is validated before warmups or samples are recorded. On failure,
 * failed_implementation identifies the invalid implementation when applicable,
 * and no successful benchmark result is returned. The caller owns the returned
 * sample arrays and must release them with rct_vector_add_f32_benchmark_results_destroy.
 */
rct_vector_add_f32_benchmark_status rct_run_vector_add_f32_benchmark(
    const rct_vector_add_f32_benchmark_config *config,
    const rct_vector_add_f32_benchmark_implementation *implementations,
    size_t implementation_count,
    rct_vector_add_f32_benchmark_result *results,
    const char **failed_implementation
);

void rct_vector_add_f32_benchmark_results_destroy(
    rct_vector_add_f32_benchmark_result *results,
    size_t result_count
);

const char *rct_vector_add_f32_benchmark_status_string(
    rct_vector_add_f32_benchmark_status status
);

#endif
