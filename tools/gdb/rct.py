"""Small RCT-specific commands for GDB's embedded Python runtime."""

import gdb


_PIPELINE_BREAKPOINTS = (
    ("benchmark entry", "main"),
    ("benchmark orchestration", "rct_run_vector_add_f32_benchmark"),
    ("deterministic input generation", "rct_fill_vector_add_f32_inputs"),
    ("scalar vector-add kernel", "rct_vector_add_f32_scalar"),
    ("numerical validation", "rct_validate_f32"),
)


def _write_line(text=""):
    gdb.write(f"{text}\n")


class RctHelp(gdb.Command):
    """Display the RCT-specific GDB commands loaded from this script."""

    def __init__(self):
        super().__init__("rct-help", gdb.COMMAND_SUPPORT)

    def invoke(self, argument, from_tty):
        del argument, from_tty
        _write_line("RCT GDB commands:")
        _write_line("  rct-help             Show this help.")
        _write_line("  rct-break-pipeline   Break on the current vector-add pipeline.")
        _write_line(
            "  rct-show-config      Show configuration in rct_run_vector_add_f32_benchmark."
        )


class RctBreakPipeline(gdb.Command):
    """Set breakpoints for the stable, current vector-add execution path."""

    def __init__(self):
        super().__init__("rct-break-pipeline", gdb.COMMAND_BREAKPOINTS)

    def invoke(self, argument, from_tty):
        del argument, from_tty

        for label, symbol_name in _PIPELINE_BREAKPOINTS:
            if gdb.lookup_global_symbol(symbol_name) is None:
                _write_line(f"RCT: {label}: symbol not found: {symbol_name}")
                continue

            try:
                breakpoint = gdb.Breakpoint(symbol_name)
            except gdb.error as error:
                _write_line(f"RCT: {label}: could not set {symbol_name}: {error}")
                continue

            _write_line(
                f"RCT: breakpoint {breakpoint.number}: {label}: {symbol_name}"
            )


class RctShowConfig(gdb.Command):
    """Show the active benchmark configuration without parsing GDB text output."""

    def __init__(self):
        super().__init__("rct-show-config", gdb.COMMAND_DATA)

    def invoke(self, argument, from_tty):
        del argument, from_tty
        selected_frame = gdb.selected_frame()
        benchmark_frame = selected_frame

        while benchmark_frame is not None:
            if benchmark_frame.name() == "rct_run_vector_add_f32_benchmark":
                break
            benchmark_frame = benchmark_frame.older()

        if benchmark_frame is None:
            _write_line(
                "RCT: no active rct_run_vector_add_f32_benchmark frame; "
                "stop in the benchmark orchestration first."
            )
            return

        benchmark_frame.select()
        try:
            # parse_and_eval evaluates in the selected frame, avoiding fragile
            # parsing of GDB's human-oriented `print` output.
            config = gdb.parse_and_eval("config").dereference()
            length = int(config["length"])
            warmup = int(config["warmup_iterations"])
            iterations = int(config["measured_iterations"])
            seed = int(config["seed"])
        except gdb.error as error:
            _write_line(f"RCT: could not read benchmark configuration: {error}")
            return
        finally:
            selected_frame.select()

        _write_line("RCT benchmark configuration")
        _write_line(f"  length:       {length}")
        _write_line(f"  warmup:       {warmup}")
        _write_line(f"  iterations:   {iterations}")
        _write_line(f"  seed:         0x{seed:016x}")


RctHelp()
RctBreakPipeline()
RctShowConfig()
