import typer

app = typer.Typer(no_args_is_help=True)


@app.command()
def version() -> None:
    """Print the installed LASSY version."""
    from lassy import __version__

    typer.echo(__version__)
