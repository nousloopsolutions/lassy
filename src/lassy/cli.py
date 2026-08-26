import os
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed LASSY version."""
    from lassy import __version__

    typer.echo(__version__)


def _build_runner(
    control_url: str, runner_id: str, workspace_config: Path, data_dir: Path
):
    from lassy.runner import Runner

    secret = os.environ.get("LASSY_RUNNER_SECRET")
    if secret is None:
        raise typer.BadParameter("LASSY_RUNNER_SECRET is not set")
    return Runner(
        control_url=control_url,
        runner_id=runner_id,
        secret=secret,
        workspace_config=workspace_config,
        data_dir=data_dir,
    )


@app.command("runner-once")
def runner_once(
    control_url: str = typer.Option(..., envvar="LASSY_CONTROL_URL"),
    runner_id: str = typer.Option(..., envvar="LASSY_RUNNER_ID"),
    workspace_config: Path = typer.Option(..., exists=True, dir_okay=False),
    data_dir: Path = typer.Option(..., file_okay=False),
) -> None:
    """Poll once for one signed allowlisted job, then return."""
    worked = _build_runner(control_url, runner_id, workspace_config, data_dir).run_once()
    typer.echo("job processed" if worked else "no job available")


@app.command("runner")
def runner_loop(
    control_url: str = typer.Option(..., envvar="LASSY_CONTROL_URL"),
    runner_id: str = typer.Option(..., envvar="LASSY_RUNNER_ID"),
    workspace_config: Path = typer.Option(..., exists=True, dir_okay=False),
    data_dir: Path = typer.Option(..., file_okay=False),
    poll_seconds: float = typer.Option(5.0, min=1.0, max=60.0),
) -> None:
    """Continuously poll the control plane using outbound HTTPS only."""
    _build_runner(control_url, runner_id, workspace_config, data_dir).run_forever(
        poll_seconds
    )
