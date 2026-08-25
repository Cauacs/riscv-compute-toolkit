#include "input.h"

#include <stdint.h>

static uint64_t rct_splitmix64_next(uint64_t *state) {
    uint64_t value;

    *state += UINT64_C(0x9e3779b97f4a7c15);
    value = *state;
    value = (value ^ (value >> 30U)) * UINT64_C(0xbf58476d1ce4e5b9);
    value = (value ^ (value >> 27U)) * UINT64_C(0x94d049bb133111eb);
    return value ^ (value >> 31U);
}

static float rct_sample_f32(uint64_t *state) {
    const uint32_t sample = (uint32_t)(rct_splitmix64_next(state) >> 40U);
    return ((float)sample * 0x1p-23f) - 1.0f;
}

void rct_fill_vector_add_f32_inputs(
    float *lhs,
    float *rhs,
    size_t length,
    uint64_t seed
) {
    uint64_t state = seed;

    for (size_t index = 0; index < length; ++index) {
        lhs[index] = rct_sample_f32(&state);
        rhs[index] = rct_sample_f32(&state);
    }
}
