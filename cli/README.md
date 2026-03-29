# Gitpoli CLI

CLI para inicializar y gestionar proyectos gitpoli.

## Comandos principales
- `gitpoli init`: Inicializa la carpeta .repol y archivos de configuración.

## Instalación local

1. Instala las dependencias:
   ```bash
   pip install typer rich pyyaml
   ```
2. Ejecuta el CLI:
   ```bash
   python -m gitpoli_cli.main init
   ```

O bien, instala como paquete editable:
   ```bash
   pip install -e .
   gitpoli init
   ```
