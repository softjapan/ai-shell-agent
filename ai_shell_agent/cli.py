"""Command-line interface for AI Shell Command Agent."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from ai_shell_agent import __version__
from ai_shell_agent.config import load_environment
from ai_shell_agent.executor import ExecutionError, ExecutionTimeout, execute_command, resolve_shell
from ai_shell_agent.formatting import Palette, should_use_color
from ai_shell_agent.generator import (
    API_KEY_ENV_VARS,
    DEFAULT_MODELS,
    DEFAULT_PROVIDER,
    PROVIDER_ENV_VAR,
    SUPPORTED_PROVIDERS,
    CommandGenerator,
    GenerationError,
    create_generator,
)
from ai_shell_agent.models import ExecutionResult, RiskAssessment, RiskLevel
from ai_shell_agent.policy import assess_command

OutputFn = Callable[[str], None]
InputFn = Callable[[str], str]
GeneratorFactory = Callable[..., CommandGenerator]
ExecutorFn = Callable[..., ExecutionResult]

EXIT_USAGE_ERROR = 2
EXIT_BLOCKED = 3
EXIT_EXECUTION_ERROR = 4
EXIT_TIMEOUT = 124


def positive_float(value: str) -> float:
    """Parse a strictly positive floating-point CLI option."""
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def resolve_provider(cli_provider: str | None, env: Mapping[str, str]) -> str:
    """Resolve the provider: explicit CLI flag, then environment, then default."""
    if cli_provider is not None:
        return cli_provider
    env_provider = env.get(PROVIDER_ENV_VAR, "").strip().lower()
    if not env_provider:
        return DEFAULT_PROVIDER
    if env_provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(SUPPORTED_PROVIDERS)
        raise GenerationError(f"unsupported {PROVIDER_ENV_VAR}; expected one of: {supported}")
    return env_provider


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="ai-shell-agent",
        description="Generate, inspect, and optionally execute one shell command.",
    )
    parser.add_argument("prompt", nargs="+", help="natural-language command request")
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDERS,
        default=None,
        help=(
            f"AI provider (default: {DEFAULT_PROVIDER}; "
            f"override the default with {PROVIDER_ENV_VAR})"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="inspect only; generate and assess the command without executing it",
    )
    parser.add_argument(
        "--timeout",
        type=positive_float,
        default=30.0,
        help="command timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--api-timeout",
        type=positive_float,
        default=30.0,
        help="AI provider API timeout in seconds (default: 30)",
    )
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="command working directory")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="optional .env file used only for keys absent from the environment (default: .env)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model name (default: provider-specific)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="show provider, model, risk, working directory, shell, and exit status",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="disable ANSI color output (also honored via NO_COLOR)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _print_plan(
    command: str,
    explanation: str,
    assessment: RiskAssessment,
    *,
    provider: str,
    model_name: str,
    cwd: Path,
    shell: str,
    palette: Palette,
    output: OutputFn,
    verbose: bool,
) -> None:
    if not verbose:
        output(f"[AI Answer]: {command}")
        return

    def label(name: str) -> str:
        return palette.style(f"{name:<9}", "bold", "cyan")

    output(f"{label('Command')} {palette.style(command, 'bold')}")
    output(f"{label('Details')} {explanation}")
    output(f"{label('Provider')} {provider}  ({model_name})")
    output(f"{label('Risk')} {palette.risk(assessment.level)}")
    for reason in assessment.reasons:
        output(f"          {palette.style('↳', 'dim')} {palette.style(reason, 'dim')}")
    output(f"{label('Workdir')} {cwd}")
    output(f"{label('Shell')} {shell}")


def confirm_execution(
    command: str,
    assessment: RiskAssessment,
    *,
    input_fn: InputFn,
    output: OutputFn,
    palette: Palette,
) -> bool:
    """Confirm execution, warning only for high-risk commands."""
    if assessment.level is RiskLevel.HIGH:
        output(
            palette.style(
                "⚠ High-risk command: it may delete data, change permissions, "
                "or otherwise be hard to undo.",
                "red",
                "bold",
            )
        )
        for reason in assessment.reasons:
            output(palette.style(f"  - {reason}", "red"))
    return input_fn("Execute? Y/N: ").strip().lower() in {"y", "yes", "\uff59"}


def _process_exit_code(returncode: int) -> int:
    if returncode < 0:
        return min(128 + abs(returncode), 255)
    if returncode > 255:
        return 1
    return returncode


def run_cli(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    input_fn: InputFn = input,
    output: OutputFn = print,
    generator_factory: GeneratorFactory = create_generator,
    executor: ExecutorFn = execute_command,
) -> int:
    """Run the CLI with injectable boundaries for deterministic tests."""
    args = build_parser().parse_args(argv)
    env = load_environment(environ, env_file=args.env_file)
    request = " ".join(args.prompt).strip()
    cwd = args.cwd.expanduser().resolve()
    palette = Palette(
        should_use_color(
            stream=sys.stdout,
            no_color_flag=args.no_color,
            env=env,
        )
    )

    try:
        provider = resolve_provider(args.provider, env)
        model_name = args.model or DEFAULT_MODELS[provider]
        api_key_name = API_KEY_ENV_VARS[provider]
        shell = resolve_shell(env.get("SHELL"))
        generator = generator_factory(
            provider,
            env.get(api_key_name, ""),
            model_name=model_name,
            timeout=args.api_timeout,
        )
        plan = generator.generate(request, cwd=cwd, shell=shell)
    except (GenerationError, ExecutionError) as exc:
        output(f"Error: {exc}")
        return EXIT_USAGE_ERROR
    except KeyboardInterrupt:
        output("Cancelled.")
        return 130
    except Exception:
        output("Error: unexpected command generation failure")
        return EXIT_USAGE_ERROR

    if not plan.success:
        output(f"Generation failed: {plan.failure}")
        return EXIT_USAGE_ERROR

    assert plan.command is not None
    assessment = assess_command(plan.command)
    _print_plan(
        plan.command,
        plan.explanation,
        assessment,
        provider=provider,
        model_name=model_name,
        cwd=cwd,
        shell=shell,
        palette=palette,
        output=output,
        verbose=args.verbose,
    )

    if assessment.blocked:
        output(
            palette.style(
                "Blocked by local safety policy; this command cannot be executed.",
                "red_bg",
                "bold",
            )
        )
        return EXIT_BLOCKED
    if args.dry_run:
        output("Dry run only. Re-run without --dry-run to allow confirmation and execution.")
        return 0
    try:
        if not confirm_execution(
            plan.command,
            assessment,
            input_fn=input_fn,
            output=output,
            palette=palette,
        ):
            output("Execution cancelled.")
            return 0
        if args.verbose:
            output(palette.style("--- output ---", "dim"))
        result = executor(
            plan.command,
            cwd=cwd,
            timeout=args.timeout,
            shell=shell,
        )
    except ExecutionTimeout as exc:
        output(f"Error: {exc}")
        return EXIT_TIMEOUT
    except ExecutionError as exc:
        output(f"Error: {exc}")
        return EXIT_EXECUTION_ERROR
    except KeyboardInterrupt:
        output("Execution interrupted.")
        return 130

    exit_code = _process_exit_code(result.returncode)
    if args.verbose:
        if result.returncode == 0:
            output(palette.style(f"✓ exit {result.returncode}", "green"))
        else:
            output(palette.style(f"✗ exit {result.returncode}", "red", "bold"))
    elif result.returncode != 0:
        output(f"Command exited with status {result.returncode}.")
    return exit_code


def entrypoint() -> None:
    """Console-script entry point."""
    raise SystemExit(run_cli())


if __name__ == "__main__":
    entrypoint()
