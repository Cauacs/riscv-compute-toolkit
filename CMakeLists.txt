cmake_minimum_required(VERSION 3.20)

project(riscv_compute_toolkit VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

include(CTest)

set(RCT_REFERENCE_SOURCE src/kernels/vector_add_reference.c)
set(RCT_SCALAR_SOURCE src/kernels/vector_add_scalar.c)
set(RCT_AUTO_SOURCE src/kernels/vector_add_auto.c)

option(
    RCT_SOURCE_DEBUG
    "Build source-friendly binaries instead of applying experiment optimizations"
    OFF
)

option(
    RCT_ENABLE_RVV
    "Compile scalar and auto kernels for an explicitly selected RISC-V V ISA"
    OFF
)
set(
    RCT_RISCV_ARCH
    ""
    CACHE STRING
    "Explicit RISC-V ISA passed as -march when RCT_ENABLE_RVV is enabled"
)
set(
    RCT_RISCV_ABI
    ""
    CACHE STRING
    "Optional RISC-V ABI passed as -mabi when RCT_ENABLE_RVV is enabled"
)

if(RCT_ENABLE_RVV)
    if(NOT CMAKE_C_COMPILER_ID STREQUAL "GNU")
        message(FATAL_ERROR "RCT_ENABLE_RVV requires a GNU C compiler.")
    endif()
    if(NOT CMAKE_SYSTEM_PROCESSOR MATCHES "^[Rr][Ii][Ss][Cc][Vv]")
        message(
            FATAL_ERROR
            "RCT_ENABLE_RVV requires a RISC-V target system; "
            "CMAKE_SYSTEM_PROCESSOR is '${CMAKE_SYSTEM_PROCESSOR}'."
        )
    endif()
    if(RCT_SOURCE_DEBUG)
        message(FATAL_ERROR "RCT_ENABLE_RVV requires RCT_SOURCE_DEBUG=OFF.")
    endif()
    if(RCT_RISCV_ARCH STREQUAL "")
        message(
            FATAL_ERROR
            "RCT_ENABLE_RVV requires RCT_RISCV_ARCH, for example "
            "-DRCT_RISCV_ARCH=<explicit-rvv-capable-isa>."
        )
    endif()
    # This only guards the experiment's full-V invariant; GCC validates ISA syntax.
    if(NOT RCT_RISCV_ARCH MATCHES "^rv(32|64)[a-z]*v([a-z0-9_].*)?$")
        message(
            FATAL_ERROR
            "RCT_RISCV_ARCH must name a lowercase rv32/rv64 ISA containing "
            "the ratified V extension; got '${RCT_RISCV_ARCH}'."
        )
    endif()

    set(RCT_RISCV_ARCH_FLAG "-march=${RCT_RISCV_ARCH}")
    set_property(
        SOURCE ${RCT_SCALAR_SOURCE} ${RCT_AUTO_SOURCE}
        APPEND PROPERTY COMPILE_OPTIONS "${RCT_RISCV_ARCH_FLAG}"
    )
    if(NOT RCT_RISCV_ABI STREQUAL "")
        add_compile_options("-mabi=${RCT_RISCV_ABI}")
    endif()
    message(STATUS "RCT RVV target: ${RCT_RISCV_ARCH_FLAG}")
endif()

if(RCT_SOURCE_DEBUG)
    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        add_compile_options(-Og -g3 -fno-omit-frame-pointer)
    else()
        message(
            WARNING
            "RCT_SOURCE_DEBUG has no compiler-specific flags for "
            "${CMAKE_C_COMPILER_ID}"
        )
    endif()
endif()

add_library(
    rct_core
    STATIC
    ${RCT_REFERENCE_SOURCE}
    ${RCT_SCALAR_SOURCE}
    ${RCT_AUTO_SOURCE}
    src/benchmark/input.c
    src/benchmark/validation.c
    src/benchmark/vector_add_benchmark.c
)
target_include_directories(
    rct_core
    PUBLIC include
    PRIVATE src/benchmark
)

if(NOT RCT_SOURCE_DEBUG)
    if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
        set_property(
            SOURCE ${RCT_REFERENCE_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O1 -fno-tree-vectorize
        )
        set_property(
            SOURCE ${RCT_SCALAR_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O3 -fno-tree-vectorize
        )
        set_property(
            SOURCE ${RCT_AUTO_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O3 -ftree-vectorize
        )
    elseif(CMAKE_C_COMPILER_ID MATCHES "Clang")
        set_property(
            SOURCE ${RCT_REFERENCE_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O1 -fno-vectorize -fno-slp-vectorize
        )
        set_property(
            SOURCE ${RCT_SCALAR_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O3 -fno-vectorize -fno-slp-vectorize
        )
        set_property(
            SOURCE ${RCT_AUTO_SOURCE}
            APPEND PROPERTY COMPILE_OPTIONS -O3
        )
    else()
        message(
            WARNING
            "Compiler ${CMAKE_C_COMPILER_ID} is unsupported for explicit "
            "scalar/auto-vectorization separation"
        )
    endif()
endif()

if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
    set(RCT_AUTO_VECTORIZATION_REPORT "${CMAKE_BINARY_DIR}/rct-vectorization/auto.opt")
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/rct-vectorization")
    set_property(
        SOURCE ${RCT_AUTO_SOURCE}
        APPEND PROPERTY COMPILE_OPTIONS
        "-fopt-info-vec-all=${RCT_AUTO_VECTORIZATION_REPORT}"
    )
endif()

if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(rct_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(NOT WIN32)
    target_link_libraries(rct_core PRIVATE m)
endif()

add_executable(
    rct_vector_add_bench
    src/benchmark/vector_add_bench.c
)
target_include_directories(
    rct_vector_add_bench
    PRIVATE src/benchmark
)
target_link_libraries(rct_vector_add_bench PRIVATE rct_core)
target_compile_definitions(rct_core PRIVATE _POSIX_C_SOURCE=200809L)

if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(
        rct_vector_add_bench
        PRIVATE -Wall -Wextra -Wpedantic
    )
endif()

if(BUILD_TESTING)
    add_executable(
        rct_portable_tests
        tests/c/test_portable_vector_add.c
    )
    target_include_directories(
        rct_portable_tests
        PRIVATE src/benchmark
    )
    target_link_libraries(rct_portable_tests PRIVATE rct_core)

    if(CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(
            rct_portable_tests
            PRIVATE -Wall -Wextra -Wpedantic
        )
    endif()

    add_test(NAME portable_vector_add COMMAND rct_portable_tests)
endif()
