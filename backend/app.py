import uuid
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich import print as rprint

from agents.research_agent import create_research_agent
from agents.team_orchestrator import create_financial_sentinel, db

console = Console()

# =====================================================================
#  Corp8AI Financial Sentinel — Entry Point
#  All orchestration is handled by the Agno Team leader.
# =====================================================================


def _print_banner():
    banner = Table.grid(padding=1)
    banner.add_column(justify="center")
    banner.add_row(
        Panel(
            Text.assemble(
                ("⚡ Corp8AI Financial Sentinel\n", "bold bright_cyan"),
                ("Auditable Multi-Agent Intelligence for Finance\n\n", "dim white"),
                ("  • Market Data Agent    ", "yellow"), ("— real-time stock prices\n", "dim"),
                ("  • News Agent           ", "yellow"), ("— latest financial headlines\n", "dim"),
                ("  • Sentiment Analyst    ", "yellow"), ("— bullish / bearish scoring\n", "dim"),
                ("  • Research Analyst     ", "yellow"), ("— deep RAG on SEC filings\n", "dim"),
                ("  • Signal Validator     ", "yellow"), ("— contradiction detection", "dim"),
            ),
            border_style="bright_cyan",
            padding=(1, 4),
        )
    )
    console.print(banner)
    console.print(
        "[dim]Type [bold]exit[/bold] or [bold]quit[/bold] to stop. "
        "During confirmation prompts, type [bold]n[/bold] to reject a ticker.[/dim]\n"
    )


def _handle_hitl(run_response, team, session_id: str, user_id: str):
    """
    Loops until the team run is completed, handling any HITL requirements.
    Implements ticker-level auto-confirmation: if the user confirms a ticker
    for one tool, it will be automatically confirmed for subsequent tools
    for that same ticker in the current run turn.
    """
    current_response = run_response
    confirmed_tickers = set()  # Cache for tickers approved in this specific turn
    
    while hasattr(current_response, "is_paused") and current_response.is_paused:
        requirements = current_response.active_requirements if hasattr(current_response, "active_requirements") else []
        
        if not requirements:
            break

        # ── Process each pending requirement ──────────────────────────────
        for req in requirements:
            if not (hasattr(req, "needs_confirmation") and req.needs_confirmation):
                continue

            tool_execution = req.tool_execution
            tool_name = tool_execution.tool_name if tool_execution else "unknown_tool"
            tool_args = tool_execution.tool_args if tool_execution else {}

            # Parse ticker from args
            ticker = (
                tool_args.get("ticker")
                or tool_args.get("symbol")
                or tool_args.get("stock")
                or "UNKNOWN"
            ).upper()

            # ── Auto-Confirmation Check ────────────────────────────────────
            if ticker in confirmed_tickers:
                req.confirm()
                console.print(f"[dim]  • Auto-confirmed [yellow]{ticker}[/yellow] for [cyan]{tool_name}[/cyan][/dim]")
                continue

            # ── HITL Confirmation UI ────────────────────────────────────────
            console.print()
            console.print(Rule("[bold yellow]🔍 Ticker Confirmation Required[/bold yellow]", style="yellow"))
            console.print()

            info_table = Table(show_header=False, box=None, padding=(0, 2))
            info_table.add_column(style="dim", width=20)
            info_table.add_column(style="bold white")
            info_table.add_row("Tool", f"[cyan]{tool_name}[/cyan]")
            info_table.add_row("Detected Ticker", f"[bright_yellow]{ticker}[/bright_yellow]")
            info_table.add_row("Full Args", str(tool_args))
            console.print(
                Panel(
                    info_table,
                    title="[bold]Agent wants to fetch data for[/bold]",
                    border_style="yellow",
                    padding=(1, 2),
                )
            )
            console.print()

            choice = (
                Prompt.ask(
                    f"  [bold]Is [bright_yellow]{ticker}[/bright_yellow] the correct ticker?[/bold]  "
                    "(y = yes, n = provide a different one)",
                    choices=["y", "n"],
                    default="y",
                    console=console,
                )
                .strip()
                .lower()
            )

            if choice == "y":
                req.confirm()
                confirmed_tickers.add(ticker)  # Remember this ticker for subsequent tools
                console.print(
                    f"\n  [bold bright_green]✔  Confirmed![/bold bright_green]  "
                    f"Proceeding with [bright_yellow]{ticker}[/bright_yellow].\n"
                )
            else:
                # Ask for the correct ticker
                correct_ticker = (
                    Prompt.ask(
                        "  [bold]Enter the correct ticker symbol[/bold]",
                        console=console,
                    )
                    .strip()
                    .upper()
                )
                if correct_ticker:
                    req.reject(
                        note=(
                            f"The user says '{ticker}' is wrong. "
                            f"Use '{correct_ticker}' instead for ALL subsequent tool calls."
                        )
                    )
                    console.print(
                        f"\n  [bold bright_red]✖  Rejected.[/bold bright_red]  "
                        f"Restarting with ticker [bright_yellow]{correct_ticker}[/bright_yellow].\n"
                    )
                else:
                    # No replacement given — just reject
                    req.reject(note=f"User says '{ticker}' is wrong but provided no replacement.")
                    console.print("\n  [bold bright_red]✖  Rejected[/bold bright_red] without a replacement ticker.\n")

            console.print(Rule(style="dim"))

        # ── Resume the run ─────────────────────────────────────────────────
        console.print("\n[dim]▶  Resuming analysis…[/dim]\n")
        current_response = team.continue_run(
            run_response=current_response,
            requirements=current_response.requirements,
            stream=False,
            user_id=user_id,
            session_id=session_id,
        )

    # Final result printing
    from agno.utils.pprint import pprint_run_response
    pprint_run_response(current_response, markdown=True)


def main():
    _print_banner()

    session_id = str(uuid.uuid4())
    user_id = "user_123"

    # Build a session-scoped team (research agent gets its own LanceDB table)
    research_agent = create_research_agent(session_id)
    financial_sentinel = create_financial_sentinel(research_agent)

    while True:
        console.print()
        query = console.input("[bold bright_cyan]📊 Ask a question:[/bold bright_cyan] ").strip()

        if query.lower() in ["exit", "quit"]:
            console.print("\n[bold]Goodbye! 👋[/bold]\n")
            try:
                db.delete_session(session_id=session_id)
                db.clear_memories()
                console.print("[dim]Internal memory cleared.[/dim]")
            except Exception:
                pass
            break

        if not query:
            continue

        console.print()
        console.print(Rule("[dim]Processing your query…[/dim]", style="dim"))
        console.print()

        try:
            # Run without streaming so we can inspect requirements first
            run_response = financial_sentinel.run(
                query,
                stream=False,
                user_id=user_id,
                session_id=session_id,
            )

            if hasattr(run_response, "is_paused") and run_response.is_paused:
                # HITL path — handle confirmations then continue
                _handle_hitl(run_response, financial_sentinel, session_id, user_id)
            else:
                # No pause — print the response directly
                from agno.utils.pprint import pprint_run_response
                pprint_run_response(run_response, markdown=True)

        except Exception as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}\n")


if __name__ == "__main__":
    main()