"""The deterministic verifier: each tool's checks, and the task's, on contract instances."""

from contract import Task, Tool

from . import division

# tool -> (verify_input(value), verify_output(input_value, output_value, workspace))
TOOLS = {
    Tool.GET_STANDINGS: (
        division.verify_division_input,
        lambda given, made, workspace: division.verify_standings_output(given, made),
    ),
    Tool.SUBSET_BOUND: (
        division.verify_bound_input,
        lambda given, made, workspace: division.verify_bound_output(given, made),
    ),
    Tool.PIN_ELIMINATIONS: (
        division.verify_division_input,
        lambda given, made, workspace: division.verify_pin_output(given, made),
    ),
}
# task -> its output's check, verify_task(arguments, output, reference, workspace)
TASKS = {Task.FIND_ELIMINATED: division.verify_task}


def verify_input(tool, value):
    return TOOLS[Tool(tool)][0](value)


def verify_output(tool, input_value, output_value, workspace):
    return TOOLS[Tool(tool)][1](input_value, output_value, workspace)


def verify_task(task, arguments, output, reference, workspace):
    return TASKS[Task(task)](arguments, output, reference, workspace)
