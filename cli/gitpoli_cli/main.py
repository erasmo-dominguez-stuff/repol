import os
from pathlib import Path
import typer
import rich
from rich.console import Console
import yaml

app = typer.Typer()
console = Console()

@app.command()
def init():
    """
    Inicializa un proyecto gitpoli creando la carpeta .repol y archivos de configuración.
    """
    repol_dir = Path('.repol')
    if repol_dir.exists():
        console.print('[yellow].repol ya existe. Abortando.[/yellow]')
        raise typer.Exit(code=1)
    repol_dir.mkdir()
    # project.yaml de ejemplo
    project = {
        'metadata': {'name': 'my-repo', 'owner': 'your-org'},
        'classification': {'tier': 1, 'data_sensitivity': 'high'},
        'compliance': {'frameworks': ['soc2']}
    }
    # pullrequest.yaml de ejemplo
    pullrequest = {
        'rules': [
            {'name': 'require-2-approvers', 'description': 'Tier 1 repos require 2 approvals'}
        ]
    }
    with open(repol_dir / 'project.yaml', 'w') as f:
        yaml.dump(project, f)
    with open(repol_dir / 'pullrequest.yaml', 'w') as f:
        yaml.dump(pullrequest, f)
    console.print('[green]Proyecto gitpoli inicializado correctamente en .repol/[/green]')

if __name__ == "__main__":
    app()