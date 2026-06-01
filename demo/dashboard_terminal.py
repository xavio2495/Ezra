"""Terminal dashboard (Rich) for the F1 demo.

Renders a finished ``DemoResult``: the six beats as panels (dynamic agent count,
permission denial, contradiction events with the winning strategy, the custom-
resolver escalation, the branch diff) plus the scaling curve as a table. This is
pure presentation over the structured result the orchestration returns — no
platform logic lives here.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def render_demo(result, *, console: Console | None = None) -> None:
    console = console or Console()
    console.rule("[bold]Ezra — F1 Race Weekend (Monaco GP)")
    console.print(f"Peak active agents: [bold cyan]{result.peak_agents}[/]\n")

    for i, beat in enumerate(result.beats, start=1):
        console.print(
            Panel(
                beat.summary,
                title=f"Beat {i}: {beat.name.replace('_', ' ')}",
                border_style="cyan",
                expand=True,
            )
        )

    if result.scaling is not None and result.scaling.points:
        table = Table(title="Scaling — per-agent router overhead", expand=False)
        table.add_column("agents", justify="right")
        table.add_column("p50 (ms)", justify="right")
        table.add_column("p99 (ms)", justify="right")
        table.add_column("samples", justify="right")
        for point in result.scaling.points:
            table.add_row(
                str(point.agent_count),
                f"{point.p50_ms:.2f}",
                f"{point.p99_ms:.2f}",
                str(point.samples),
            )
        console.print(table)
        verdict = "FLAT ✓" if result.scaling.flat else "NOT FLAT ✗"
        console.print(f"Curve: [bold]{verdict}[/]")
