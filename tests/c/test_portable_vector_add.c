#include "input.h"
#include "vector_add_benchmark_runner.h"
#include "rct/kernels.h"
#include "rct/validation.h"

#include <float.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define RCT_ARRAY_LENGTH(array) (sizeof(array) / sizeof((array)[0]))

#define RCT_CHECK(condition)                                                   \
    do {                                                                       \
        if (!(condition)) {                                                    \
            fprintf(                                                           \
                stderr,                                                        \
                "%s:%d: check failed: %s\n",                                 \
                __FILE__,                                                      \
                __LINE__,                                                      \
                #condition                                                     \
            );                                                                 \
            return false;                                                      \
        }                                                                      \
    } while (0)

static const rct_vector_add_f32_fn PORTABLE_KERNELS[] = {
    rct_vector_add_f32_reference,
    rct_vector_add_f32_scalar,
    rct_vector_add_f32_auto,
};

static void rct_invalid_vector_add(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
) {
    (void)lhs;
    (void)rhs;

    for (size_t index = 0; index < length; ++index) {
        output[index] = NAN;
    }
}

static bool test_zero_length(void) {
    for (size_t index = 0; index < RCT_ARRAY_LENGTH(PORTABLE_KERNELS); ++index) {
        PORTABLE_KERNELS[index](NULL, NULL, NULL, 0U);
    }

    RCT_CHECK(rct_validate_f32(
        NULL,
        NULL,
        0U,
        RCT_F32_DEFAULT_ABS_TOLERANCE,
        RCT_F32_DEFAULT_REL_TOLERANCE
    ));
    return true;
}

static bool test_one_element(void) {
    const float lhs[] = {1.25f};
    const float rhs[] = {-0.5f};
    float output[] = {NAN};

    for (size_t index = 0; index < RCT_ARRAY_LENGTH(PORTABLE_KERNELS); ++index) {
        PORTABLE_KERNELS[index](lhs, rhs, output, 1U);
        RCT_CHECK(output[0] == 0.75f);
        output[0] = NAN;
    }

    return true;
}

static bool test_deterministic_inputs(void) {
    enum { LENGTH = 257 };
    float lhs_first[LENGTH];
    float rhs_first[LENGTH];
    float lhs_second[LENGTH];
    float rhs_second[LENGTH];
    float golden_lhs[3];
    float golden_rhs[3];
    const uint64_t seed = UINT64_C(0x0123456789abcdef);

    rct_fill_vector_add_f32_inputs(lhs_first, rhs_first, LENGTH, seed);
    rct_fill_vector_add_f32_inputs(lhs_second, rhs_second, LENGTH, seed);

    RCT_CHECK(memcmp(lhs_first, lhs_second, sizeof(lhs_first)) == 0);
    RCT_CHECK(memcmp(rhs_first, rhs_second, sizeof(rhs_first)) == 0);

    rct_fill_vector_add_f32_inputs(golden_lhs, golden_rhs, 3U, seed);
    RCT_CHECK(golden_lhs[0] == ((float)UINT32_C(0x157a38) * 0x1p-23f) - 1.0f);
    RCT_CHECK(golden_rhs[0] == ((float)UINT32_C(0xd57352) * 0x1p-23f) - 1.0f);
    RCT_CHECK(golden_lhs[1] == ((float)UINT32_C(0x2f90b7) * 0x1p-23f) - 1.0f);
    RCT_CHECK(golden_rhs[1] == ((float)UINT32_C(0xa2d419) * 0x1p-23f) - 1.0f);
    RCT_CHECK(golden_lhs[2] == ((float)UINT32_C(0x01404c) * 0x1p-23f) - 1.0f);
    RCT_CHECK(golden_rhs[2] == ((float)UINT32_C(0x14bc57) * 0x1p-23f) - 1.0f);

    return true;
}

static bool kernels_match_at_length(size_t length) {
    float *lhs = malloc(length * sizeof(*lhs));
    float *rhs = malloc(length * sizeof(*rhs));
    float *reference = malloc(length * sizeof(*reference));
    float *scalar = malloc(length * sizeof(*scalar));
    float *automatic = malloc(length * sizeof(*automatic));
    bool passed = false;

    if (lhs == NULL || rhs == NULL || reference == NULL || scalar == NULL ||
        automatic == NULL) {
        fprintf(stderr, "allocation failed for length %zu\n", length);
        goto cleanup;
    }

    rct_fill_vector_add_f32_inputs(
        lhs,
        rhs,
        length,
        UINT64_C(0x6a09e667f3bcc909)
    );
    rct_vector_add_f32_reference(lhs, rhs, reference, length);
    rct_vector_add_f32_scalar(lhs, rhs, scalar, length);
    rct_vector_add_f32_auto(lhs, rhs, automatic, length);

    if (!rct_validate_f32(
            scalar,
            reference,
            length,
            RCT_F32_DEFAULT_ABS_TOLERANCE,
            RCT_F32_DEFAULT_REL_TOLERANCE
        )) {
        fprintf(stderr, "scalar mismatch at length %zu\n", length);
        goto cleanup;
    }
    if (!rct_validate_f32(
            automatic,
            reference,
            length,
            RCT_F32_DEFAULT_ABS_TOLERANCE,
            RCT_F32_DEFAULT_REL_TOLERANCE
        )) {
        fprintf(stderr, "auto-vectorized mismatch at length %zu\n", length);
        goto cleanup;
    }

    passed = true;

cleanup:
    free(automatic);
    free(scalar);
    free(reference);
    free(rhs);
    free(lhs);
    return passed;
}

static bool test_unaligned_lengths(void) {
    static const size_t LENGTHS[] = {3U, 7U, 15U, 17U, 31U, 33U};

    for (size_t index = 0; index < RCT_ARRAY_LENGTH(LENGTHS); ++index) {
        RCT_CHECK(kernels_match_at_length(LENGTHS[index]));
    }

    return true;
}

static bool test_medium_length(void) {
    return kernels_match_at_length(4099U);
}

static bool test_benchmark_summary(void) {
    const uint64_t original_samples[] = {9U, 1U, 7U, 3U};
    uint64_t samples[RCT_ARRAY_LENGTH(original_samples)];
    rct_vector_add_f32_benchmark_summary summary;

    memcpy(samples, original_samples, sizeof(samples));
    RCT_CHECK(rct_vector_add_f32_benchmark_summarize_samples(
        samples,
        RCT_ARRAY_LENGTH(samples),
        &summary
    ));
    RCT_CHECK(memcmp(samples, original_samples, sizeof(samples)) == 0);
    RCT_CHECK(summary.minimum_ns == 1U);
    RCT_CHECK(summary.median_ns == 5.0);
    RCT_CHECK(summary.mean_ns == 5.0);
    RCT_CHECK(!rct_vector_add_f32_benchmark_summarize_samples(
        NULL,
        0U,
        &summary
    ));

    return true;
}

static bool test_benchmark_rejects_invalid_kernel(void) {
    const rct_vector_add_f32_benchmark_config config = {
        .length = 8U,
        .warmup_iterations = 0U,
        .measured_iterations = 1U,
        .seed = UINT64_C(1),
    };
    const rct_vector_add_f32_benchmark_implementation implementations[] = {
        {"reference", rct_vector_add_f32_reference},
        {"invalid", rct_invalid_vector_add},
    };
    rct_vector_add_f32_benchmark_result results[
        RCT_ARRAY_LENGTH(implementations)
    ] = {{0}};
    const char *failed_implementation = NULL;

    RCT_CHECK(rct_run_vector_add_f32_benchmark(
        &config,
        implementations,
        RCT_ARRAY_LENGTH(implementations),
        results,
        &failed_implementation
    ) == RCT_VECTOR_ADD_BENCHMARK_VALIDATION_FAILURE);
    RCT_CHECK(failed_implementation != NULL);
    RCT_CHECK(strcmp(failed_implementation, "invalid") == 0);
    RCT_CHECK(results[0].samples_ns == NULL);
    RCT_CHECK(results[1].samples_ns == NULL);

    return true;
}

static bool test_validation_policy(void) {
    const float expected[] = {1.0f, 2.0f, 3.0f};
    const float close[] = {1.0f, 2.0000005f, 3.0f};
    const float far[] = {1.0f, 2.01f, 3.0f};

    RCT_CHECK(rct_f32_nearly_equal(INFINITY, INFINITY, 0.0f, 0.0f));
    RCT_CHECK(!rct_f32_nearly_equal(INFINITY, -INFINITY, 1.0f, 1.0f));
    RCT_CHECK(!rct_f32_nearly_equal(NAN, NAN, 1.0f, 1.0f));
    RCT_CHECK(rct_f32_nearly_equal(1.0000005f, 1.0f, 1.0e-6f, 0.0f));
    RCT_CHECK(rct_f32_nearly_equal(1000000.5f, 1000000.0f, 0.0f, 1.0e-6f));
    RCT_CHECK(!rct_f32_nearly_equal(FLT_MAX, -FLT_MAX, 0.0f, 1.1f));
    RCT_CHECK(rct_f32_nearly_equal(FLT_MAX, -FLT_MAX, 0.0f, 2.0f));
    RCT_CHECK(!rct_f32_nearly_equal(1.01f, 1.0f, 1.0e-6f, 1.0e-6f));
    RCT_CHECK(!rct_f32_nearly_equal(1.0f, 1.0f, -1.0f, 0.0f));
    RCT_CHECK(rct_validate_f32(close, expected, 3U, 1.0e-6f, 1.0e-6f));
    RCT_CHECK(!rct_validate_f32(far, expected, 3U, 1.0e-6f, 1.0e-6f));

    return true;
}

int main(void) {
    bool passed = true;

    passed = test_zero_length() && passed;
    passed = test_one_element() && passed;
    passed = test_deterministic_inputs() && passed;
    passed = test_unaligned_lengths() && passed;
    passed = test_medium_length() && passed;
    passed = test_validation_policy() && passed;
    passed = test_benchmark_summary() && passed;
    passed = test_benchmark_rejects_invalid_kernel() && passed;

    if (!passed) {
        return EXIT_FAILURE;
    }

    puts("portable vector-add tests passed");
    return EXIT_SUCCESS;
}
