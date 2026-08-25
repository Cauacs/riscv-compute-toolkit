#ifndef RCT_KERNELS_H
#define RCT_KERNELS_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Function contract for single-precision vector addition.
 *
 * For length greater than zero, lhs, rhs, and output must each point to at
 * least length floats. Their memory ranges must not overlap. For length zero,
 * the pointers may be null and no memory is accessed.
 */
typedef void (*rct_vector_add_f32_fn)(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
);

void rct_vector_add_f32_reference(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
);

void rct_vector_add_f32_scalar(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
);

void rct_vector_add_f32_auto(
    const float *lhs,
    const float *rhs,
    float *output,
    size_t length
);

#ifdef __cplusplus
}
#endif

#endif
