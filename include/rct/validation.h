#ifndef RCT_VALIDATION_H
#define RCT_VALIDATION_H

#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RCT_F32_DEFAULT_ABS_TOLERANCE 1.0e-6f
#define RCT_F32_DEFAULT_REL_TOLERANCE 1.0e-6f

/**
 * Compare two floats using the Phase 1 validation policy.
 *
 * Tolerances must be nonnegative. Exact equality then succeeds, including
 * equal infinities and signed zero. NaNs fail. Finite values succeed when
 * either their absolute error is within abs_tolerance or their error is within
 * rel_tolerance times the larger magnitude.
 */
bool rct_f32_nearly_equal(
    float actual,
    float expected,
    float abs_tolerance,
    float rel_tolerance
);

/**
 * Validate actual against expected element by element.
 *
 * For length greater than zero, both pointers must address at least length
 * floats. For length zero, either pointer may be null.
 */
bool rct_validate_f32(
    const float *actual,
    const float *expected,
    size_t length,
    float abs_tolerance,
    float rel_tolerance
);

#ifdef __cplusplus
}
#endif

#endif
