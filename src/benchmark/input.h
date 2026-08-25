#ifndef RCT_BENCHMARK_INPUT_H
#define RCT_BENCHMARK_INPUT_H

#include <stddef.h>
#include <stdint.h>

/**
 * Fill both input buffers deterministically from seed using SplitMix64.
 *
 * Generated values are exactly representable floats in the interval [-1, 1).
 * For length greater than zero, lhs and rhs must each address at least length
 * non-overlapping floats. For length zero, either pointer may be null.
 */
void rct_fill_vector_add_f32_inputs(
    float *lhs,
    float *rhs,
    size_t length,
    uint64_t seed
);

#endif
