#include "vector_add_benchmark_runner.h"

#include "input.h"
#include "rct/validation.h"

#include <stdlib.h>
#include <string.h>
#include <time.h>

#define RCT_NANOSECONDS_PER_SECOND UINT64_C(1000000000)

/*
 * The observer consumes one result after each call outside the timed interval.
 * This makes every kernel invocation observably produce output without adding
 * checksum work to the measurement itself.
 */
static volatile float rct_benchmark_observer;

static bool rct_multiply_size(size_t left, size_t right, size_t *product) {
    if (left != 0U && right > SIZE_MAX / left) {
        return false;
    }

    *product = left * right;
    return true;
}

static int rct_compare_u64(const void *left, const void *right) {
    const uint64_t left_value = *(const uint64_t *)left;
    const uint64_t right_value = *(const uint64_t *)right;

    return (left_value > right_value) - (left_value < right_value);
}

static bool rct_monotonic_now(struct timespec *timestamp) {
    return clock_gettime(CLOCK_MONOTONIC, timestamp) == 0;
}

static uint64_t rct_elapsed_ns(
    const struct timespec *start,
    const struct timespec *end
) {
    const time_t seconds = end->tv_sec - start->tv_sec;
    const long nanoseconds = end->tv_nsec - start->tv_nsec;

    if (nanoseconds >= 0L) {
        return (uint64_t)seconds * RCT_NANOSECONDS_PER_SECOND +
               (uint64_t)nanoseconds;
    }

    return (uint64_t)(seconds - 1) * RCT_NANOSECONDS_PER_SECOND +
           (uint64_t)(nanoseconds + (long)RCT_NANOSECONDS_PER_SECOND);
}

static void rct_observe_output(
    const float *output,
    size_t length,
    size_t iteration
) {
    rct_benchmark_observer = output[iteration % length];
}

static void rct_zero_results(
    rct_vector_add_f32_benchmark_result *results,
    size_t result_count
) {
    for (size_t index = 0; index < result_count; ++index) {
        results[index] = (rct_vector_add_f32_benchmark_result){0};
    }
}

bool rct_vector_add_f32_benchmark_summarize_samples(
    const uint64_t *samples_ns,
    size_t sample_count,
    rct_vector_add_f32_benchmark_summary *summary
) {
    uint64_t *sorted_samples;
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

    summary->minimum_ns = sorted_samples[0];
    if (sample_count % 2U == 0U) {
        const size_t upper_index = sample_count / 2U;

        summary->median_ns = ((double)sorted_samples[upper_index - 1U] +
                              (double)sorted_samples[upper_index]) /
                             2.0;
    } else {
        summary->median_ns = (double)sorted_samples[sample_count / 2U];
    }
    summary->mean_ns = total / (double)sample_count;

    free(sorted_samples);
    return true;
}

void rct_vector_add_f32_benchmark_results_destroy(
    rct_vector_add_f32_benchmark_result *results,
    size_t result_count
) {
    if (results == NULL) {
        return;
    }

    for (size_t index = 0; index < result_count; ++index) {
        free(results[index].samples_ns);
        results[index] = (rct_vector_add_f32_benchmark_result){0};
    }
}

const char *rct_vector_add_f32_benchmark_status_string(
    rct_vector_add_f32_benchmark_status status
) {
    switch (status) {
        case RCT_VECTOR_ADD_BENCHMARK_OK:
            return "success";
        case RCT_VECTOR_ADD_BENCHMARK_INVALID_CONFIGURATION:
            return "invalid benchmark configuration";
        case RCT_VECTOR_ADD_BENCHMARK_ALLOCATION_FAILURE:
            return "memory allocation failed";
        case RCT_VECTOR_ADD_BENCHMARK_CLOCK_FAILURE:
            return "monotonic clock read failed";
        case RCT_VECTOR_ADD_BENCHMARK_VALIDATION_FAILURE:
            return "implementation failed validation";
    }

    return "unknown benchmark status";
}

rct_vector_add_f32_benchmark_status rct_run_vector_add_f32_benchmark(
    const rct_vector_add_f32_benchmark_config *config,
    const rct_vector_add_f32_benchmark_implementation *implementations,
    size_t implementation_count,
    rct_vector_add_f32_benchmark_result *results,
    const char **failed_implementation
) {
    float *lhs = NULL;
    float *rhs = NULL;
    float *reference = NULL;
    float *output = NULL;
    size_t vector_bytes;
    size_t sample_bytes;
    rct_vector_add_f32_benchmark_status status = RCT_VECTOR_ADD_BENCHMARK_OK;

    if (failed_implementation != NULL) {
        *failed_implementation = NULL;
    }
    if (config == NULL || implementations == NULL || results == NULL ||
        implementation_count == 0U || config->length == 0U ||
        config->measured_iterations == 0U ||
        !rct_multiply_size(config->length, sizeof(*lhs), &vector_bytes) ||
        !rct_multiply_size(
            config->measured_iterations,
            sizeof(*results[0].samples_ns),
            &sample_bytes
        )) {
        return RCT_VECTOR_ADD_BENCHMARK_INVALID_CONFIGURATION;
    }

    rct_zero_results(results, implementation_count);
    for (size_t index = 0; index < implementation_count; ++index) {
        if (implementations[index].name == NULL ||
            implementations[index].kernel == NULL) {
            return RCT_VECTOR_ADD_BENCHMARK_INVALID_CONFIGURATION;
        }
        results[index].implementation_name = implementations[index].name;
    }

    lhs = malloc(vector_bytes);
    rhs = malloc(vector_bytes);
    reference = malloc(vector_bytes);
    output = malloc(vector_bytes);
    if (lhs == NULL || rhs == NULL || reference == NULL || output == NULL) {
        status = RCT_VECTOR_ADD_BENCHMARK_ALLOCATION_FAILURE;
        goto cleanup;
    }

    rct_fill_vector_add_f32_inputs(lhs, rhs, config->length, config->seed);
    rct_vector_add_f32_reference(lhs, rhs, reference, config->length);

    for (size_t index = 0; index < implementation_count; ++index) {
        implementations[index].kernel(lhs, rhs, output, config->length);
        if (!rct_validate_f32(
                output,
                reference,
                config->length,
                RCT_F32_DEFAULT_ABS_TOLERANCE,
                RCT_F32_DEFAULT_REL_TOLERANCE
            )) {
            if (failed_implementation != NULL) {
                *failed_implementation = implementations[index].name;
            }
            status = RCT_VECTOR_ADD_BENCHMARK_VALIDATION_FAILURE;
            goto cleanup;
        }
        results[index].valid = true;
    }

    for (size_t index = 0; index < implementation_count; ++index) {
        struct timespec start;
        struct timespec end;

        results[index].samples_ns = malloc(sample_bytes);
        if (results[index].samples_ns == NULL) {
            status = RCT_VECTOR_ADD_BENCHMARK_ALLOCATION_FAILURE;
            goto cleanup;
        }

        for (size_t iteration = 0; iteration < config->warmup_iterations;
             ++iteration) {
            implementations[index].kernel(lhs, rhs, output, config->length);
            rct_observe_output(output, config->length, iteration);
        }

        for (size_t iteration = 0; iteration < config->measured_iterations;
             ++iteration) {
            if (!rct_monotonic_now(&start)) {
                status = RCT_VECTOR_ADD_BENCHMARK_CLOCK_FAILURE;
                goto cleanup;
            }
            implementations[index].kernel(lhs, rhs, output, config->length);
            if (!rct_monotonic_now(&end)) {
                status = RCT_VECTOR_ADD_BENCHMARK_CLOCK_FAILURE;
                goto cleanup;
            }
            rct_observe_output(output, config->length, iteration);
            results[index].samples_ns[iteration] = rct_elapsed_ns(&start, &end);
        }

        if (!rct_validate_f32(
                output,
                reference,
                config->length,
                RCT_F32_DEFAULT_ABS_TOLERANCE,
                RCT_F32_DEFAULT_REL_TOLERANCE
            )) {
            if (failed_implementation != NULL) {
                *failed_implementation = implementations[index].name;
            }
            status = RCT_VECTOR_ADD_BENCHMARK_VALIDATION_FAILURE;
            goto cleanup;
        }

        results[index].sample_count = config->measured_iterations;
        if (!rct_vector_add_f32_benchmark_summarize_samples(
                results[index].samples_ns,
                results[index].sample_count,
                &results[index].summary
            )) {
            status = RCT_VECTOR_ADD_BENCHMARK_ALLOCATION_FAILURE;
            goto cleanup;
        }
    }

cleanup:
    free(output);
    free(reference);
    free(rhs);
    free(lhs);

    if (status != RCT_VECTOR_ADD_BENCHMARK_OK) {
        rct_vector_add_f32_benchmark_results_destroy(results, implementation_count);
    }
    return status;
}
