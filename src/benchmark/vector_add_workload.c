#include "vector_add_workload.h"

#include "input.h"
#include "rct/kernels.h"
#include "rct/validation.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>

typedef struct {
    size_t length;
    float *lhs;
    float *rhs;
    float *reference;
    float *output;
} rct_vector_add_f32_fixture;

typedef struct {
    rct_vector_add_f32_fn kernel;
} rct_vector_add_f32_kernel_context;

static volatile float rct_vector_add_f32_observer;

static bool rct_vector_add_f32_size_multiply(
    size_t left,
    size_t right,
    size_t *product
) {
    if (right != 0U && left > SIZE_MAX / right) {
        return false;
    }

    *product = left * right;
    return true;
}

static bool rct_vector_add_f32_setup(
    const void *workload_config,
    void **fixture
) {
    const rct_vector_add_f32_config *config = workload_config;
    rct_vector_add_f32_fixture *vector_fixture;
    size_t vector_bytes;

    if (config == NULL || fixture == NULL || config->length == 0U ||
        !rct_vector_add_f32_size_multiply(
            config->length,
            sizeof(*vector_fixture->lhs),
            &vector_bytes
        )) {
        return false;
    }

    *fixture = NULL;
    vector_fixture = malloc(sizeof(*vector_fixture));
    if (vector_fixture == NULL) {
        return false;
    }

    vector_fixture->length = config->length;
    vector_fixture->lhs = malloc(vector_bytes);
    vector_fixture->rhs = malloc(vector_bytes);
    vector_fixture->reference = malloc(vector_bytes);
    vector_fixture->output = malloc(vector_bytes);
    if (vector_fixture->lhs == NULL || vector_fixture->rhs == NULL ||
        vector_fixture->reference == NULL || vector_fixture->output == NULL) {
        free(vector_fixture->output);
        free(vector_fixture->reference);
        free(vector_fixture->rhs);
        free(vector_fixture->lhs);
        free(vector_fixture);
        return false;
    }

    rct_fill_vector_add_f32_inputs(
        vector_fixture->lhs,
        vector_fixture->rhs,
        vector_fixture->length,
        config->seed
    );
    rct_vector_add_f32_reference(
        vector_fixture->lhs,
        vector_fixture->rhs,
        vector_fixture->reference,
        vector_fixture->length
    );

    *fixture = vector_fixture;
    return true;
}

static void rct_vector_add_f32_prepare(void *fixture) {
    (void)fixture;
}

static bool rct_vector_add_f32_validate(void *fixture) {
    const rct_vector_add_f32_fixture *vector_fixture = fixture;

    if (vector_fixture == NULL) {
        return false;
    }

    return rct_validate_f32(
        vector_fixture->output,
        vector_fixture->reference,
        vector_fixture->length,
        RCT_F32_DEFAULT_ABS_TOLERANCE,
        RCT_F32_DEFAULT_REL_TOLERANCE
    );
}

static void rct_vector_add_f32_observe(void *fixture, size_t iteration) {
    const rct_vector_add_f32_fixture *vector_fixture = fixture;

    if (vector_fixture != NULL && vector_fixture->length != 0U) {
        rct_vector_add_f32_observer =
            vector_fixture->output[iteration % vector_fixture->length];
    }
}

static void rct_vector_add_f32_destroy(void *fixture) {
    rct_vector_add_f32_fixture *vector_fixture = fixture;

    if (vector_fixture == NULL) {
        return;
    }

    free(vector_fixture->output);
    free(vector_fixture->reference);
    free(vector_fixture->rhs);
    free(vector_fixture->lhs);
    free(vector_fixture);
}

static void rct_vector_add_f32_invoke(const void *context, void *fixture) {
    const rct_vector_add_f32_kernel_context *kernel_context = context;
    rct_vector_add_f32_fixture *vector_fixture = fixture;

    kernel_context->kernel(
        vector_fixture->lhs,
        vector_fixture->rhs,
        vector_fixture->output,
        vector_fixture->length
    );
}

static const rct_vector_add_f32_kernel_context RCT_VECTOR_ADD_F32_REFERENCE = {
    .kernel = rct_vector_add_f32_reference,
};

static const rct_vector_add_f32_kernel_context RCT_VECTOR_ADD_F32_SCALAR = {
    .kernel = rct_vector_add_f32_scalar,
};

static const rct_vector_add_f32_kernel_context RCT_VECTOR_ADD_F32_AUTO = {
    .kernel = rct_vector_add_f32_auto,
};

static const rct_benchmark_implementation RCT_VECTOR_ADD_F32_IMPLEMENTATIONS[] = {
    {
        .name = "reference",
        .source_path = "src/kernels/vector_add_reference.c",
        .invoke = rct_vector_add_f32_invoke,
        .context = &RCT_VECTOR_ADD_F32_REFERENCE,
    },
    {
        .name = "scalar",
        .source_path = "src/kernels/vector_add_scalar.c",
        .invoke = rct_vector_add_f32_invoke,
        .context = &RCT_VECTOR_ADD_F32_SCALAR,
    },
    {
        .name = "auto",
        .source_path = "src/kernels/vector_add_auto.c",
        .invoke = rct_vector_add_f32_invoke,
        .context = &RCT_VECTOR_ADD_F32_AUTO,
    },
};

const rct_benchmark_definition rct_vector_add_f32_benchmark = {
    .name = "vector_add_f32",
    .workload = {
        .setup = rct_vector_add_f32_setup,
        .prepare = rct_vector_add_f32_prepare,
        .validate = rct_vector_add_f32_validate,
        .observe = rct_vector_add_f32_observe,
        .destroy = rct_vector_add_f32_destroy,
    },
    .implementations = RCT_VECTOR_ADD_F32_IMPLEMENTATIONS,
    .implementation_count =
        sizeof(RCT_VECTOR_ADD_F32_IMPLEMENTATIONS) /
        sizeof(RCT_VECTOR_ADD_F32_IMPLEMENTATIONS[0]),
};
