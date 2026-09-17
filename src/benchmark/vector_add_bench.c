#include "rct/benchmark.h"
#include "vector_add_workload.h"

#include <errno.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const rct_benchmark_definition *const RCT_BENCHMARK_REGISTRY[] = {
    &rct_vector_add_f32_benchmark,
};

static const rct_vector_add_f32_config DEFAULT_VECTOR_ADD_F32_CONFIG = {
    .length = 1024U * 1024U,
    .seed = UINT64_C(0x6a09e667f3bcc909),
};

static const rct_benchmark_run_config DEFAULT_RUN_CONFIG = {
    .warmup_iterations = 5U,
    .measured_iterations = 30U,
};

static void rct_print_usage(FILE *stream, const char *program) {
    fprintf(
        stream,
        "Usage: %s --benchmark NAME [--length N] [--warmup N] [--iterations N] "
        "[--seed N] [--result-protocol]\n",
        program
    );
}

static const rct_benchmark_definition *rct_find_benchmark(const char *name) {
    for (size_t index = 0; index < sizeof(RCT_BENCHMARK_REGISTRY) /
                                        sizeof(RCT_BENCHMARK_REGISTRY[0]);
         ++index) {
        if (strcmp(RCT_BENCHMARK_REGISTRY[index]->name, name) == 0) {
            return RCT_BENCHMARK_REGISTRY[index];
        }
    }

    return NULL;
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
    const rct_benchmark_definition **benchmark,
    rct_vector_add_f32_config *workload_config,
    rct_benchmark_run_config *run_config,
    bool *result_protocol_output
) {
    for (int index = 1; index < argc; ++index) {
        const char *option = argv[index];
        const char *value;

        if (strcmp(option, "--help") == 0 || strcmp(option, "-h") == 0) {
            rct_print_usage(stdout, argv[0]);
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
        if (strcmp(option, "--benchmark") == 0) {
            if (*benchmark != NULL) {
                fprintf(stderr, "--benchmark may only be specified once\n");
                return false;
            }
            *benchmark = rct_find_benchmark(value);
            if (*benchmark == NULL) {
                fprintf(stderr, "unknown benchmark: %s\n", value);
                return false;
            }
        } else if (strcmp(option, "--length") == 0) {
            if (!rct_parse_size(value, &workload_config->length) ||
                workload_config->length == 0U) {
                fprintf(stderr, "--length must be a positive integer\n");
                return false;
            }
        } else if (strcmp(option, "--warmup") == 0) {
            if (!rct_parse_size(value, &run_config->warmup_iterations)) {
                fprintf(stderr, "--warmup must be a nonnegative integer\n");
                return false;
            }
        } else if (strcmp(option, "--iterations") == 0) {
            if (!rct_parse_size(value, &run_config->measured_iterations) ||
                run_config->measured_iterations == 0U) {
                fprintf(stderr, "--iterations must be a positive integer\n");
                return false;
            }
        } else if (strcmp(option, "--seed") == 0) {
            if (!rct_parse_u64(value, &workload_config->seed)) {
                fprintf(stderr, "--seed must be an unsigned integer\n");
                return false;
            }
        } else {
            fprintf(stderr, "unknown option: %s\n", option);
            return false;
        }
    }

    if (*benchmark == NULL) {
        fputs("missing required --benchmark NAME\n", stderr);
        return false;
    }

    return true;
}

static void rct_print_results(
    const rct_benchmark_definition *benchmark,
    const rct_vector_add_f32_config *workload_config,
    const rct_benchmark_run_config *run_config,
    const rct_benchmark_run_result *run_result
) {
    printf("RCT %s\n\n", benchmark->name);
    printf("length:      %zu\n", workload_config->length);
    printf("warmup:      %zu\n", run_config->warmup_iterations);
    printf("iterations:  %zu\n", run_config->measured_iterations);
    printf("seed:        0x%016" PRIx64 "\n\n", workload_config->seed);
    printf(
        "%-16s %-37s %-7s %-12s %-12s %-12s %-8s\n",
        "implementation",
        "source",
        "valid",
        "median ns",
        "mean ns",
        "min ns",
        "samples"
    );

    for (size_t index = 0; index < run_result->implementation_count; ++index) {
        const rct_benchmark_implementation_result *implementation =
            &run_result->implementations[index];

        printf(
            "%-16s %-37s %-7s %-12.1f %-12.1f %-12" PRIu64 " %zu\n",
            implementation->name,
            implementation->source_path,
            implementation->valid ? "yes" : "no",
            implementation->summary.median_ns,
            implementation->summary.mean_ns,
            implementation->summary.min_ns,
            implementation->sample_count
        );
    }
}

static void rct_print_result_protocol(
    const rct_benchmark_definition *benchmark,
    const rct_vector_add_f32_config *workload_config,
    const rct_benchmark_run_config *run_config,
    const rct_benchmark_run_result *run_result
) {
    puts("rct-benchmark-result-v2");
    printf(
        "benchmark\t%s\t%zu\t%zu\t%zu\t0x%016" PRIx64 "\n",
        benchmark->name,
        workload_config->length,
        run_config->warmup_iterations,
        run_config->measured_iterations,
        workload_config->seed
    );

    for (size_t index = 0; index < run_result->implementation_count; ++index) {
        const rct_benchmark_implementation_result *implementation =
            &run_result->implementations[index];

        printf(
            "implementation\t%s\t%s\t%s\t%" PRIu64 "\t%.17g\t%.17g\t%zu\n",
            implementation->name,
            implementation->source_path,
            implementation->valid ? "true" : "false",
            implementation->summary.min_ns,
            implementation->summary.median_ns,
            implementation->summary.mean_ns,
            implementation->sample_count
        );
    }

    for (size_t implementation_index = 0;
         implementation_index < run_result->implementation_count;
         ++implementation_index) {
        const rct_benchmark_implementation_result *implementation =
            &run_result->implementations[implementation_index];

        for (size_t sample_index = 0;
             sample_index < implementation->sample_count;
             ++sample_index) {
            printf(
                "sample\t%s\t%zu\t%" PRIu64 "\n",
                implementation->name,
                sample_index,
                implementation->samples_ns[sample_index]
            );
        }
    }
}

int main(int argc, char **argv) {
    const rct_benchmark_definition *benchmark = NULL;
    rct_vector_add_f32_config workload_config = DEFAULT_VECTOR_ADD_F32_CONFIG;
    rct_benchmark_run_config run_config = DEFAULT_RUN_CONFIG;
    rct_benchmark_run_result run_result = {0};
    const char *failed_implementation = NULL;
    rct_benchmark_status status;
    bool result_protocol_output = false;

    if (!rct_parse_arguments(
            argc,
            argv,
            &benchmark,
            &workload_config,
            &run_config,
            &result_protocol_output
        )) {
        rct_print_usage(stderr, argv[0]);
        return EXIT_FAILURE;
    }

    status = rct_run_benchmark(
        benchmark,
        &workload_config,
        &run_config,
        &run_result,
        &failed_implementation
    );
    if (status != RCT_BENCHMARK_OK) {
        fprintf(stderr, "benchmark failed: %s", rct_benchmark_status_string(status));
        if (failed_implementation != NULL) {
            fprintf(stderr, " (%s)", failed_implementation);
        }
        fputc('\n', stderr);
        rct_benchmark_run_result_destroy(&run_result);
        return EXIT_FAILURE;
    }

    if (result_protocol_output) {
        rct_print_result_protocol(benchmark, &workload_config, &run_config, &run_result);
    } else {
        rct_print_results(benchmark, &workload_config, &run_config, &run_result);
    }
    rct_benchmark_run_result_destroy(&run_result);
    return EXIT_SUCCESS;
}
