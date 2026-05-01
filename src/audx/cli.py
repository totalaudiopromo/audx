"""audx command-line interface."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from audx import __version__
from audx.config import CONFIG_DIR, DEFAULT_BPM, PROJECTS_DIR, SAMPLES_DIR
from audx.engine import get_engine, init_engine
from audx.pattern import Pattern, get_pattern_engine
from audx.project import Project, list_projects
from audx.sampler import SampleLibrary
from audx.ui.app import DAWApp

app = typer.Typer(help="audx — code your music, own your sound.")
pattern_app = typer.Typer(help="Pattern commands")
samples_app = typer.Typer(help="Sample library commands")
projects_app = typer.Typer(help="Project commands")
plugin_app = typer.Typer(help="Plugin discovery commands")
push2_app = typer.Typer(help="Push 2 mapping commands")
heartmula_app = typer.Typer(help="Heartmula bridge commands")
sadact_app = typer.Typer(help="Sadact bridge commands")
daemon_app = typer.Typer(help="audxd daemon commands")
app.add_typer(pattern_app, name="pattern")
app.add_typer(samples_app, name="samples")
app.add_typer(projects_app, name="projects")
app.add_typer(plugin_app, name="plugins")
app.add_typer(push2_app, name="push2")
app.add_typer(heartmula_app, name="heartmula")
app.add_typer(sadact_app, name="sadact")
app.add_typer(daemon_app, name="daemon")


def _pattern_payload() -> list[dict]:
    return [
        {
            "name": name,
            "dsl": pattern.dsl,
            "length_beats": pattern.length_beats,
            "channel": pattern.channel,
            "swing": pattern.swing,
        }
        for name, pattern in get_pattern_engine().patterns.items()
    ]


def _load_project(path: Path) -> Project:
    if not path.exists():
        typer.echo(f"Project not found: {path}", err=True)
        raise typer.Exit(1)
    project = Project.load(path)
    project.apply_to_engine()
    init_engine().set_bpm(project.bpm)
    return project


@app.command()
def launch(
    project: Path | None = typer.Argument(None, help="Path to .audx project file"),
    samples: Path | None = typer.Option(None, "--samples", "-s", help="Samples directory"),
) -> None:
    """Launch the audx TUI."""
    if samples:
        os.environ["AUDX_SAMPLES_DIR"] = str(samples)
    if project is not None:
        loaded = _load_project(project)
        typer.echo(f"Loaded project: {loaded.name}")
    else:
        last = CONFIG_DIR / "last.audx"
        if last.exists():
            try:
                loaded = _load_project(last)
                typer.echo(f"Auto-loaded last project: {loaded.name}")
            except typer.Exit:
                raise
            except Exception as exc:
                typer.echo(f"Could not auto-load last project: {exc}", err=True)
    DAWApp(project=project, samples_dir=samples).run()


@app.command()
def save(
    path: Path = typer.Argument(..., help="Project file path (.audx)"),
    name: str | None = typer.Option(None, "--name", "-n", help="Project name"),
) -> None:
    """Save current in-process state to a project file.

    Note: command invocations are separate processes, so this saves patterns
    created in the current process only. Use the TUI for persistent sessions.
    """
    project = Project(name=name or path.stem, bpm=get_pattern_engine().bpm, patterns=_pattern_payload())
    project.save(path)
    typer.echo(f"Saved project to {path} ({len(project.patterns)} patterns)")


@app.command()
def load(path: Path = typer.Argument(..., help="Project file path (.audx)")) -> None:
    """Load a project and print its contents."""
    project = _load_project(path)
    typer.echo(f"Loaded '{project.name}'")
    typer.echo(f"BPM: {project.bpm}")
    typer.echo(f"Patterns: {', '.join(p['name'] for p in project.patterns) or 'none'}")


@app.command()
def play() -> None:
    """Start audio playback in this process."""
    engine = init_engine()
    get_pattern_engine().start()
    engine.start()
    typer.echo("Playing. Press Ctrl-C to stop.")
    try:
        while True:
            import time

            time.sleep(0.25)
    except KeyboardInterrupt:
        engine.stop()
        get_pattern_engine().stop()
        typer.echo("Stopped.")


@app.command()
def stop() -> None:
    """Stop audio playback in this process."""
    engine = get_engine()
    if engine is None:
        typer.echo("Engine not running.")
        return
    engine.stop()
    get_pattern_engine().stop()
    typer.echo("Stopped.")


@app.command()
def version() -> None:
    """Print version."""
    typer.echo(f"audx {__version__}")


@app.command()
def doctor() -> None:
    """Run diagnostics."""
    typer.echo("audx doctor")
    typer.echo(f"Version: {__version__}")
    typer.echo(f"Python: {sys.version.split()[0]}")
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        typer.echo(f"Audio devices: {len(devices)}")
        typer.echo(f"Default device: {sd.default.device}")
    except Exception as exc:
        typer.echo(f"Audio check failed: {exc}")
    typer.echo(f"Samples dir: {SAMPLES_DIR} ({'exists' if SAMPLES_DIR.exists() else 'missing'})")
    typer.echo(f"Projects dir: {PROJECTS_DIR}")
    typer.echo(f"Config dir: {CONFIG_DIR}")


@pattern_app.command("create")
def pattern_create(
    name: str = typer.Argument(..., help="Pattern name"),
    dsl: str = typer.Argument(..., help="Pattern DSL, e.g. 'kick 4/4'"),
) -> None:
    """Create a pattern in the current process and print its parsed steps."""
    pattern = Pattern(name=name, dsl=dsl, length_beats=4)
    try:
        pattern.parse_dsl()
    except Exception as exc:
        typer.echo(f"DSL parse error: {exc}", err=True)
        raise typer.Exit(1) from exc
    get_pattern_engine().set_bpm(DEFAULT_BPM)
    get_pattern_engine().add_pattern(pattern)
    typer.echo(f"Pattern '{name}' created ({len(pattern.steps)} steps)")
    for step in pattern.steps:
        typer.echo(f"  beat {step.beat:.2f}: {step.sample} vel={step.velocity:.2f} ch={step.channel}")


@pattern_app.command("list")
def pattern_list() -> None:
    """List patterns in the current process."""
    engine = get_pattern_engine()
    if not engine.patterns:
        typer.echo("No patterns defined in this process.")
        return
    for name, pattern in engine.patterns.items():
        typer.echo(f"{name}: {pattern.dsl} ({len(pattern.steps)} steps)")


@pattern_app.command("delete")
def pattern_delete(name: str) -> None:
    """Delete a pattern from the current process."""
    deleted = get_pattern_engine().remove_pattern(name)
    typer.echo(f"Deleted {name}" if deleted else f"Pattern not found: {name}")


# Backwards-compatible flat command names from the earlier sprint.
@app.command("pattern-create")
def pattern_create_flat(name: str, dsl: str) -> None:
    pattern_create(name, dsl)


@app.command("patterns-list")
def pattern_list_flat() -> None:
    pattern_list()


@samples_app.command("index")
def samples_index(
    directory: Path = typer.Argument(..., help="Directory to index"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
) -> None:
    """Index a sample directory."""
    library = SampleLibrary(directory)
    result = library.build_index(recursive=recursive)
    typer.echo(f"Indexed {len(result)} samples under {directory}")


@samples_app.command("list")
def samples_list(
    query: str = typer.Option("", "--query", "-q", help="Search filter"),
    limit: int = typer.Option(20, "--limit", "-l"),
) -> None:
    """List indexed samples."""
    library = SampleLibrary(SAMPLES_DIR)
    results = library.search(query=query, limit=limit)
    if not results:
        typer.echo("No samples found.")
        return
    for sample in results:
        typer.echo(f"{sample['name']} ({sample['duration']:.1f}s) tags={sample['tags']}")


# Backwards-compatible flat names.
@app.command("samples-index")
def samples_index_flat(directory: Path, recursive: bool = typer.Option(True, "--recursive/--no-recursive")) -> None:
    samples_index(directory, recursive)


@app.command("samples-list")
def samples_list_flat(query: str = "", limit: int = 20) -> None:
    samples_list(query=query, limit=limit)


@projects_app.command("list")
def projects_list() -> None:
    """List saved project files."""
    projects = list_projects()
    if not projects:
        typer.echo("No projects found.")
        return
    for project in projects:
        typer.echo(f"{project.name} ({project.stat().st_size / 1024:.1f} KB)")


@app.command("projects-list")
def projects_list_flat() -> None:
    projects_list()


@app.command("render")
def render_pattern(
    dsl: str = typer.Argument(..., help="Pattern DSL to render"),
    output: Path = typer.Option(Path("render.wav"), "--output", "-o", help="Output WAV path"),
    sample: Path = typer.Option(..., "--sample", help="Sample file to trigger"),
    bpm: float = typer.Option(128.0, "--bpm", help="BPM"),
    bars: int = typer.Option(4, "--bars", help="Number of bars"),
) -> None:
    """Render a single pattern to WAV offline."""
    from audx.arrangement import Arrangement, render_arrangement

    pattern = Pattern(name=sample.stem, dsl=dsl)
    pattern.parse_dsl()
    library = SampleLibrary(sample.parent)
    library.build_index(recursive=False)
    arrangement = Arrangement(bpm=bpm)
    arrangement.add(pattern, start_bar=0, bars=bars)
    path = render_arrangement(arrangement, library, output)
    typer.echo(f"Rendered {path}")


@plugin_app.command("scan")
def plugins_scan() -> None:
    """Scan AU/VST/VST3 plugin directories. Discovery only, no hosting yet."""
    from audx.plugins import scan_plugins

    plugins = scan_plugins()
    if not plugins:
        typer.echo("No plugins found.")
        return
    for plugin in plugins:
        typer.echo(f"{plugin.kind}\t{plugin.name}\t{plugin.path}")


@push2_app.command("map")
def push2_map() -> None:
    """Print the default Push 2 MIDI mapping scaffold."""
    from audx.push2 import list_push2_map

    for control in list_push2_map():
        typer.echo(f"{control.name}\t{control.midi_type}\t{control.number}\t{control.description}")


@heartmula_app.command("status")
def heartmula_status() -> None:
    """Check whether the local Heartmula bridge is available."""
    from audx.heartmula import status

    check = status()
    typer.echo(f"{'available' if check.available else 'unavailable'}: {check.reason}")


@heartmula_app.command("generate")
def heartmula_generate(
    prompt: str,
    output: Path = typer.Option(Path("heartmula-output.wav"), "--output", "-o"),
    bpm: int = typer.Option(128, "--bpm"),
    bars: int = typer.Option(4, "--bars"),
) -> None:
    """Generate a stem via local heartlib if available."""
    from audx.heartmula import generate

    path = generate(prompt, output, bpm=bpm, bars=bars)
    typer.echo(f"Generated {path}")


@sadact_app.command("status")
def sadact_status(base_url: str = typer.Option("http://localhost:5742", "--url")) -> None:
    """Check sadact-finisher HTTP bridge."""
    from audx.sadact import SadactClient

    check = SadactClient(base_url=base_url).status()
    typer.echo(f"{'available' if check.available else 'unavailable'}: {check.detail}")


@sadact_app.command("process")
def sadact_process(
    stems_zip: Path,
    output: Path | None = typer.Option(None, "--output", "-o"),
    preset: str = typer.Option("loudness-14", "--preset"),
    base_url: str = typer.Option("http://localhost:5742", "--url"),
) -> None:
    """Send stems zip to sadact-finisher and write mastered output."""
    from audx.sadact import SadactClient

    path = SadactClient(base_url=base_url).process(stems_zip, output_path=output, preset=preset)
    typer.echo(f"Wrote {path}")


@daemon_app.command("serve")
def daemon_serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(5744, "--port"),
) -> None:
    """Run the minimal audxd local daemon."""
    from audx.daemon import run_daemon

    run_daemon(host=host, port=port)


@daemon_app.command("status")
def daemon_status() -> None:
    """Check audxd status."""
    from audx.daemon_client import daemon_status as get_status

    typer.echo(get_status())


@daemon_app.command("pattern")
def daemon_pattern(name: str, dsl: str) -> None:
    """Add a pattern to audxd."""
    from audx.daemon_client import daemon_add_pattern

    typer.echo(daemon_add_pattern(name, dsl))


@daemon_app.command("save")
def daemon_save(path: str, name: str | None = None) -> None:
    """Save audxd state to a project file."""
    from audx.daemon_client import daemon_save as save_state

    typer.echo(save_state(path, name=name))


if __name__ == "__main__":
    app()
