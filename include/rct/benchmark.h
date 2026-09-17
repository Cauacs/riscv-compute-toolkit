#ifndef RCT_BENCHMARK_H
#define RCT_BENCHMARK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Configuration shared by all benchmark workloads. */
typedef struct {
    size_t warmup_iterations;
    size_t measured_iterations;
} rct_benchmark_run_config;

/**
 * Workload lifecycle callbacks. The runner calls setup once, then uses the
 * fixture for every implementation. It calls prepare before and observe after
 * every invocation, with both operations outside the timed interval.
 */
typedef struct {
    bool (*setup)(const void *workload_config, void **fixture);
    void (*prepare)(void *fixture);
    bool (*validate)(void *fixture);
    void (*observe)(void *fixture, size_t iteration);
    void (*destroy)(void *fixture);
} rct_benchmark_workload;

/** A benchmarkable implementation and its workload-specific context. */
typedef struct {
    const char *name;
    const char *source_path;
    void (*invoke)(const void *context, void *fixture);
    const void *context;
} rct_benchmark_implementation;

/** A workload and the implementations measured against it. */
typedef struct {
    const char *name;
    rct_benchmark_workload workload;
    const rct_benchmark_implementation *implementations;
    size_t implementation_count;
} rct_benchmark_definition;

typedef struct {
    uint64_t min_ns;
    double median_ns;
    double mean_ns;
} rct_benchmark_sample_summary;

typedef struct {
    const char *name;
    const char *source_path;
    bool valid;
    uint64_t *samples_ns;
    size_t sample_count;
    rct_benchmark_sample_summary summary;
} rct_benchmark_implementation_result;

/**
 * Caller-owned result storage. Destroy this object with
 * rct_benchmark_run_result_destroy when it is no longer needed.
 */
typedef struct {
    rct_benchmark_implementation_result *implementations;
    size_t implementation_count;
} rct_benchmark_run_result;

typedef enum {
    RCT_BENCHMARK_OK,
    RCT_BENCHMARK_INVALID_CONFIGURATION,
    RCT_BENCHMARK_ALLOCATION_FAILURE,
    RCT_BENCHMARK_CLOCK_FAILURE,
    RCT_BENCHMARK_SETUP_FAILURE,
    RCT_BENCHMARK_VALIDATION_FAILURE,
} rct_benchmark_status;

/**
 * Summarize raw elapsed-time samples without changing their original order.
 * At least one sample is required. The median of an even sample count is the
 * mean of its two central sorted samples.
 */
bool rct_benchmark_summarize_samples(
    const uint64_t *samples_ns,
    size_t sample_count,
    rct_benchmark_sample_summary *summary
);

/**
 * Run every implementation in definition against its workload configuration.
 * The returned result is empty on failure. failed_implementation, when
 * supplied, identifies the implementation whose validation failed.
 */
rct_benchmark_status rct_run_benchmark(
    const rct_benchmark_definition *definition,
    const void *workload_config,
    const rct_benchmark_run_config *run_config,
    rct_benchmark_run_result *run_result,
    const char **failed_implementation
);

/** Release all allocations owned by a benchmark run result. */
void rct_benchmark_run_result_destroy(rct_benchmark_run_result *run_result);

/** Return a stable, human-readable description of status. */
const char *rct_benchmark_status_string(rct_benchmark_status status);

#ifdef __cplusplus
}
#endif

#endif
