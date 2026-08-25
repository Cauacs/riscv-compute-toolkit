#include "rct/kernels.h"

void rct_vector_add_f32_reference(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
) {
    for (size_t index = 0; index < length; ++index) {
        output[index] = lhs[index] + rhs[index];
    }
}
