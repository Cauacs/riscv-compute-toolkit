#include "vector_add_benchmark.h"

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const rct_vector_add_f32_benchmark_implementation IMPLEMENTATIONS[] = {
    {"reference", rct_vector_add_f32_reference},
    {"scalar", rct_vector_add_f32_scalar},
    {"auto", rct_vector_add_f32_auto},
};

static const rct_vector_add_f32_benchmark_config DEFAULT_CONFIG = {
    .length = 1024U * 1024U,
    .warmup_iterations = 5U,
    .measured_iterations = 30U,
    .seed = UINT64_C(0x6a09e667f3bcc909),
};

#define RCT_ARRAY_LENGTH(array) (sizeof(array) / sizeof((array)[0]))

static void rct_print_usage(const char *program) {
    printf(
        "Usage: %s [--length N] [--warmup N] [--iterations N] [--seed N] "
        "[--result-protocol]\n",
        program
    );
}

static bool rct_parse_u64(const char *text, uint64_t *value) {
    char *end;
    uintmax_t parsed;

    if (text[0] == '-' || text[0] == '\0') {
        return false;
    }

    errno = 0;
    parsed = strtoumax(text, &end, 0);
    if (errno == ERANGE || *end != '\0' || parsed > UINT64_MAX) {
        return false;
    }

    *value = (uint64_t)parsed;
    return true;
}

static bool rct_parse_size(const char *text, size_t *value) {
    uint64_t parsed;

    if (!rct_parse_u64(text, &parsed) || parsed > SIZE_MAX) {
        return false;
    }

    *value = (size_t)parsed;
    return true;
}

static bool rct_parse_arguments(
    int argc,
    char **argv,
    rct_vector_add_f32_benchmark_config *config,
    bool *result_protocol_output
) {
    for (int index = 1; index < argc; ++index) {
        const char *option = argv[index];
        const char *value;

        if (strcmp(option, "--help") == 0 || strcmp(option, "-h") == 0) {
            rct_print_usage(argv[0]);
            exit(EXIT_SUCCESS);
        }
        if (strcmp(option, "--result-protocol") == 0) {
            *result_protocol_output = true;
            continue;
        }
        if (index + 1 >= argc) {
            fprintf(stderr, "missing value for %s\n", option);
            return false;
        }

        value = argv[++index];
        if (strcmp(option, "--length") == 0) {
            if (!rct_parse_size(value, &config->length) || config->length == 0U) {
                fprintf(stderr, "--length must be a positive integer\n");
                return false;
            }
        } else if (strcmp(option, "--warmup") == 0) {
            if (!rct_parse_size(value, &config->warmup_iterations)) {
                fprintf(stderr, "--warmup must be a nonnegative integer\n");
                return false;
            }
        } else if (strcmp(option, "--iterations") == 0) {
            if (!rct_parse_size(value, &config->measured_iterations) ||
                config->measured_iterations == 0U) {
                fprintf(stderr, "--iterations must be a positive integer\n");
                return false;
            }
        } else if (strcmp(option, "--seed") == 0) {
            if (!rct_parse_u64(value, &config->seed)) {
                fprintf(stderr, "--seed must be an unsigned integer\n");
                return false;
            }
        } else {
            fprintf(stderr, "unknown option: %s\n", option);
            return false;
        }
    }

    return true;
}

static void rct_print_results(
    const rct_vector_add_f32_benchmark_config *config,
    const rct_vector_add_f32_benchmark_result *results,
    size_t result_count
) {
    printf("RCT vector_add_f32\n\n");
    printf("length:      %zu\n", config->length);
    printf("warmup:      %zu\n", config->warmup_iterations);
    printf("iterations:  %zu\n", config->measured_iterations);
    printf("seed:        0x%016" PRIx64 "\n\n", config->seed);
    printf(
        "%-16s %-7s %-12s %-12s %-12s %-8s\n",
        "implementation",
        "valid",
        "median ns",
        "mean ns",
        "min ns",
        "samples"
    );

    for (size_t index = 0; index < result_count; ++index) {
        printf(
            "%-16s %-7s %-12.1f %-12.1f %-12" PRIu64 " %zu\n",
            results[index].implementation_name,
            results[index].valid ? "yes" : "no",
            results[index].summary.median_ns,
            results[index].summary.mean_ns,
            results[index].summary.minimum_ns,
            results[index].sample_count
        );
    }
}

static void rct_print_result_protocol(
    const rct_vector_add_f32_benchmark_config *config,
    const rct_vector_add_f32_benchmark_result *results,
    size_t result_count
) {
    puts("rct-benchmark-result-v1");
    printf(
        "benchmark\tvector_add_f32\t%zu\t%zu\t%zu\t0x%016" PRIx64 "\n",
        config->length,
        config->warmup_iterations,
        config->measured_iterations,
        config->seed
    );

    for (size_t index = 0; index < result_count; ++index) {
        printf(
            "implementation\t%s\t%s\t%" PRIu64 "\t%.17g\t%.17g\t%zu\n",
            results[index].implementation_name,
            results[index].valid ? "true" : "false",
            results[index].summary.minimum_ns,
            results[index].summary.median_ns,
            results[index].summary.mean_ns,
            results[index].sample_count
        );
    }
}

int main(int argc, char **argv) {
    rct_vector_add_f32_benchmark_config config = DEFAULT_CONFIG;
    rct_vector_add_f32_benchmark_result results[RCT_ARRAY_LENGTH(IMPLEMENTATIONS)] = {
        {0},
    };
    const char *failed_implementation = NULL;
    rct_vector_add_f32_benchmark_status status;
    bool result_protocol_output = false;

    if (!rct_parse_arguments(argc, argv, &config, &result_protocol_output)) {
        rct_print_usage(argv[0]);
        return EXIT_FAILURE;
    }

    status = rct_run_vector_add_f32_benchmark(
        &config,
        IMPLEMENTATIONS,
        RCT_ARRAY_LENGTH(IMPLEMENTATIONS),
        results,
        &failed_implementation
    );
    if (status != RCT_VECTOR_ADD_BENCHMARK_OK) {
        fprintf(stderr, "benchmark failed: %s", rct_vector_add_f32_benchmark_status_string(status));
        if (failed_implementation != NULL) {
            fprintf(stderr, " (%s)", failed_implementation);
        }
        fputc('\n', stderr);
        return EXIT_FAILURE;
    }

    if (result_protocol_output) {
        rct_print_result_protocol(&config, results, RCT_ARRAY_LENGTH(results));
    } else {
        rct_print_results(&config, results, RCT_ARRAY_LENGTH(results));
    }
    rct_vector_add_f32_benchmark_results_destroy(
        results,
        RCT_ARRAY_LENGTH(results)
    );
    return EXIT_SUCCESS;
}
