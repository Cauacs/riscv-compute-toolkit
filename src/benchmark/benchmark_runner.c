#include "rct/benchmark.h"

#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define RCT_NANOSECONDS_PER_SECOND UINT64_C(1000000000)

static bool rct_multiply_size(size_t left, size_t right, size_t *product) {
    if (left != 0U && right > SIZE_MAX / left) {
        return false;
    }

    *product = left * right;
    return true;
}

static bool rct_has_text(const char *text) {
    return text != NULL && text[0] != '\0';
}

static int rct_compare_u64(const void *left, const void *right) {
    const uint64_t left_value = *(const uint64_t *)left;
    const uint64_t right_value = *(const uint64_t *)right;

    return (left_value > right_value) - (left_value < right_value);
}

static bool rct_monotonic_now(struct timespec *timestamp) {
    return clock_gettime(CLOCK_MONOTONIC, timestamp) == 0;
}

static bool rct_elapsed_ns(
    const struct timespec *start,
    const struct timespec *end,
    uint64_t *elapsed_ns
) {
    uint64_t seconds;
    uint64_t nanoseconds;

    if (start->tv_nsec < 0L || start->tv_nsec >= (long)RCT_NANOSECONDS_PER_SECOND ||
        end->tv_nsec < 0L || end->tv_nsec >= (long)RCT_NANOSECONDS_PER_SECOND ||
        end->tv_sec < start->tv_sec ||
        (end->tv_sec == start->tv_sec && end->tv_nsec < start->tv_nsec)) {
        return false;
    }

    seconds = (uint64_t)(end->tv_sec - start->tv_sec);
    if (end->tv_nsec >= start->tv_nsec) {
        nanoseconds = (uint64_t)(end->tv_nsec - start->tv_nsec);
    } else {
        if (seconds == 0U) {
            return false;
        }
        --seconds;
        nanoseconds = RCT_NANOSECONDS_PER_SECOND +
                      (uint64_t)(end->tv_nsec - start->tv_nsec);
    }

    if (seconds > (UINT64_MAX - nanoseconds) / RCT_NANOSECONDS_PER_SECOND) {
        return false;
    }

    *elapsed_ns = seconds * RCT_NANOSECONDS_PER_SECOND + nanoseconds;
    return true;
}

static bool rct_definition_is_valid(const rct_benchmark_definition *definition) {
    const rct_benchmark_workload *workload;

    if (definition == NULL || !rct_has_text(definition->name) ||
        definition->implementations == NULL ||
        definition->implementation_count == 0U) {
        return false;
    }

    workload = &definition->workload;
    return workload->setup != NULL && workload->prepare != NULL &&
           workload->validate != NULL && workload->observe != NULL &&
           workload->destroy != NULL;
}

static bool rct_implementations_are_valid(
    const rct_benchmark_implementation *implementations,
    size_t implementation_count
) {
    for (size_t index = 0; index < implementation_count; ++index) {
        if (!rct_has_text(implementations[index].name) ||
            !rct_has_text(implementations[index].source_path) ||
            implementations[index].invoke == NULL) {
            return false;
        }

        for (size_t previous = 0; previous < index; ++previous) {
            if (strcmp(implementations[previous].name, implementations[index].name) ==
                0) {
                return false;
            }
        }
    }

    return true;
}

bool rct_benchmark_summarize_samples(
    const uint64_t *samples_ns,
    size_t sample_count,
    rct_benchmark_sample_summary *summary
) {
    uint64_t *sorted_samples;
    rct_benchmark_sample_summary calculated_summary;
    size_t bytes;
    double total = 0.0;

    if (samples_ns == NULL || summary == NULL || sample_count == 0U ||
        !rct_multiply_size(sample_count, sizeof(*sorted_samples), &bytes)) {
        return false;
    }

    sorted_samples = malloc(bytes);
    if (sorted_samples == NULL) {
        return false;
    }

    memcpy(sorted_samples, samples_ns, bytes);
    qsort(sorted_samples, sample_count, sizeof(*sorted_samples), rct_compare_u64);

    for (size_t index = 0; index < sample_count; ++index) {
        total += (double)samples_ns[index];
    }

    calculated_summary.min_ns = sorted_samples[0];
    if (sample_count % 2U == 0U) {
        const size_t upper_index = sample_count / 2U;

        calculated_summary.median_ns =
            ((double)sorted_samples[upper_index - 1U] +
             (double)sorted_samples[upper_index]) /
            2.0;
    } else {
        calculated_summary.median_ns =
            (double)sorted_samples[sample_count / 2U];
    }
    calculated_summary.mean_ns = total / (double)sample_count;

    free(sorted_samples);
    *summary = calculated_summary;
    return true;
}

void rct_benchmark_run_result_destroy(rct_benchmark_run_result *run_result) {
    if (run_result == NULL) {
        return;
    }

    for (size_t index = 0; index < run_result->implementation_count; ++index) {
        free(run_result->implementations[index].samples_ns);
    }
    free(run_result->implementations);
    *run_result = (rct_benchmark_run_result){0};
}

const char *rct_benchmark_status_string(rct_benchmark_status status) {
    switch (status) {
        case RCT_BENCHMARK_OK:
            return "success";
        case RCT_BENCHMARK_INVALID_CONFIGURATION:
            return "invalid benchmark configuration";
        case RCT_BENCHMARK_ALLOCATION_FAILURE:
            return "memory allocation failed";
        case RCT_BENCHMARK_CLOCK_FAILURE:
            return "monotonic clock read failed";
        case RCT_BENCHMARK_SETUP_FAILURE:
            return "workload setup failed";
        case RCT_BENCHMARK_VALIDATION_FAILURE:
            return "implementation failed validation";
    }

    return "unknown benchmark status";
}

rct_benchmark_status rct_run_benchmark(
    const rct_benchmark_definition *definition,
    const void *workload_config,
    const rct_benchmark_run_config *run_config,
    rct_benchmark_run_result *run_result,
    const char **failed_implementation
) {
    const rct_benchmark_workload *workload;
    void *fixture = NULL;
    bool setup_attempted = false;
    size_t implementation_bytes;
    size_t sample_bytes;
    rct_benchmark_status status = RCT_BENCHMARK_OK;

    if (failed_implementation != NULL) {
        *failed_implementation = NULL;
    }
    if (run_result == NULL) {
        return RCT_BENCHMARK_INVALID_CONFIGURATION;
    }
    *run_result = (rct_benchmark_run_result){0};

    if (workload_config == NULL || run_config == NULL ||
        run_config->measured_iterations == 0U ||
        !rct_definition_is_valid(definition) ||
        !rct_implementations_are_valid(
            definition->implementations,
            definition->implementation_count
        ) ||
        !rct_multiply_size(
            definition->implementation_count,
            sizeof(*run_result->implementations),
            &implementation_bytes
        ) ||
        !rct_multiply_size(
            run_config->measured_iterations,
            sizeof(*run_result->implementations->samples_ns),
            &sample_bytes
        )) {
        return RCT_BENCHMARK_INVALID_CONFIGURATION;
    }

    run_result->implementations = calloc(1U, implementation_bytes);
    if (run_result->implementations == NULL) {
        return RCT_BENCHMARK_ALLOCATION_FAILURE;
    }
    run_result->implementation_count = definition->implementation_count;

    for (size_t index = 0; index < definition->implementation_count; ++index) {
        run_result->implementations[index].name = definition->implementations[index].name;
        run_result->implementations[index].source_path =
            definition->implementations[index].source_path;
    }

    workload = &definition->workload;
    setup_attempted = true;
    if (!workload->setup(workload_config, &fixture)) {
        status = RCT_BENCHMARK_SETUP_FAILURE;
        goto cleanup;
    }

    for (size_t index = 0; index < definition->implementation_count; ++index) {
        const rct_benchmark_implementation *implementation =
            &definition->implementations[index];

        workload->prepare(fixture);
        implementation->invoke(implementation->context, fixture);
        workload->observe(fixture, 0U);
        if (!workload->validate(fixture)) {
            if (failed_implementation != NULL) {
                *failed_implementation = implementation->name;
            }
            status = RCT_BENCHMARK_VALIDATION_FAILURE;
            goto cleanup;
        }
    }

    for (size_t index = 0; index < definition->implementation_count; ++index) {
        const rct_benchmark_implementation *implementation =
            &definition->implementations[index];
        rct_benchmark_implementation_result *implementation_result =
            &run_result->implementations[index];

        implementation_result->samples_ns = malloc(sample_bytes);
        if (implementation_result->samples_ns == NULL) {
            status = RCT_BENCHMARK_ALLOCATION_FAILURE;
            goto cleanup;
        }
        implementation_result->sample_count = run_config->measured_iterations;

        for (size_t iteration = 0; iteration < run_config->warmup_iterations;
             ++iteration) {
            workload->prepare(fixture);
            implementation->invoke(implementation->context, fixture);
            workload->observe(fixture, iteration);
        }

        for (size_t iteration = 0; iteration < run_config->measured_iterations;
             ++iteration) {
            struct timespec start;
            struct timespec end;
            uint64_t elapsed_ns;

            workload->prepare(fixture);
            if (!rct_monotonic_now(&start)) {
                status = RCT_BENCHMARK_CLOCK_FAILURE;
                goto cleanup;
            }
            implementation->invoke(implementation->context, fixture);
            if (!rct_monotonic_now(&end)) {
                workload->observe(fixture, iteration);
                status = RCT_BENCHMARK_CLOCK_FAILURE;
                goto cleanup;
            }
            workload->observe(fixture, iteration);
            if (!rct_elapsed_ns(&start, &end, &elapsed_ns)) {
                status = RCT_BENCHMARK_CLOCK_FAILURE;
                goto cleanup;
            }
            implementation_result->samples_ns[iteration] = elapsed_ns;
        }

        if (!workload->validate(fixture)) {
            if (failed_implementation != NULL) {
                *failed_implementation = implementation->name;
            }
            status = RCT_BENCHMARK_VALIDATION_FAILURE;
            goto cleanup;
        }
        if (!rct_benchmark_summarize_samples(
                implementation_result->samples_ns,
                implementation_result->sample_count,
                &implementation_result->summary
            )) {
            status = RCT_BENCHMARK_ALLOCATION_FAILURE;
            goto cleanup;
        }
        implementation_result->valid = true;
    }

cleanup:
    if (setup_attempted && fixture != NULL) {
        workload->destroy(fixture);
    }
    if (status != RCT_BENCHMARK_OK) {
        rct_benchmark_run_result_destroy(run_result);
    }
    return status;
}
