#include "rct/validation.h"

#include <math.h>

static bool rct_tolerances_are_valid(
    float abs_tolerance,
    float rel_tolerance
) {
    return abs_tolerance >= 0.0f && rel_tolerance >= 0.0f;
}

bool rct_f32_nearly_equal(
    float actual,
    float expected,
    float abs_tolerance,
    float rel_tolerance
) {
    double absolute_error;
    double scale;

    if (!rct_tolerances_are_valid(abs_tolerance, rel_tolerance)) {
        return false;
    }
    if (actual == expected) {
        return true;
    }
    if (!isfinite(actual) || !isfinite(expected)) {
        return false;
    }

    absolute_error = fabs((double)actual - (double)expected);
    if (absolute_error <= (double)abs_tolerance) {
        return true;
    }

    scale = fmax(fabs((double)actual), fabs((double)expected));
    return absolute_error <= (double)rel_tolerance * scale;
}

bool rct_validate_f32(
    const float *actual,
    const float *expected,
    size_t length,
    float abs_tolerance,
    float rel_tolerance
) {
    if (!rct_tolerances_are_valid(abs_tolerance, rel_tolerance)) {
        return false;
    }

    for (size_t index = 0; index < length; ++index) {
        if (!rct_f32_nearly_equal(
                actual[index],
                expected[index],
                abs_tolerance,
                rel_tolerance
            )) {
            return false;
        }
    }

    return true;
}
