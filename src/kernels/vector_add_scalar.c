#include "rct/kernels.h"

void rct_vector_add_f32_scalar(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
) {
    const size_t unrolled_length = length - (length % 4U);
    size_t index = 0;

    for (; index < unrolled_length; index += 4U) {
        output[index] = lhs[index] + rhs[index];
        output[index + 1U] = lhs[index + 1U] + rhs[index + 1U];
        output[index + 2U] = lhs[index + 2U] + rhs[index + 2U];
        output[index + 3U] = lhs[index + 3U] + rhs[index + 3U];
    }

    for (; index < length; ++index) {
        output[index] = lhs[index] + rhs[index];
    }
}
