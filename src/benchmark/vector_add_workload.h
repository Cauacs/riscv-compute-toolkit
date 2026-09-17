#ifndef RCT_VECTOR_ADD_WORKLOAD_H
#define RCT_VECTOR_ADD_WORKLOAD_H

#include "rct/benchmark.h"

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    size_t length;
    uint64_t seed;
} rct_vector_add_f32_config;

extern const rct_benchmark_definition rct_vector_add_f32_benchmark;

#ifdef __cplusplus
}
#endif

#endif
