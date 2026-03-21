import asyncio
import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="RAG Framework CLI")
project_app = typer.Typer(help="Manage projects")
ingest_app = typer.Typer(help="Ingest documents")
app.add_typer(project_app, name="project")
app.add_typer(ingest_app, name="ingest")

console = Console()

_API_BASE = os.getenv("RAG_API_URL", "http://localhost:8000")
_API_KEY = os.getenv("RAG_API_KEY", "")


def _headers() -> dict:
    return {"X-API-Key": _API_KEY} if _API_KEY else {}


# ---------------------------------------------------------------------------
# project commands
# ---------------------------------------------------------------------------

@project_app.command("create")
def project_create(name: str = typer.Argument(..., help="Project name")):
    """Create a new project."""
    import httpx
    resp = httpx.post(f"{_API_BASE}/projects", json={"name": name}, headers=_headers())
    resp.raise_for_status()
    data = resp.json()
    console.print(f"[green]Created project:[/green] {data['name']} ({data['id']})")


@project_app.command("list")
def project_list():
    """List all projects."""
    import httpx
    resp = httpx.get(f"{_API_BASE}/projects", headers=_headers())
    resp.raise_for_status()
    data = resp.json()
    table = Table("ID", "Name", "Created At")
    for p in data["projects"]:
        table.add_row(p["id"], p["name"], p["created_at"])
    console.print(table)


@project_app.command("delete")
def project_delete(name: str = typer.Argument(..., help="Project name")):
    """Delete a project and all its data."""
    import httpx
    # Resolve by name
    resp = httpx.get(f"{_API_BASE}/projects", headers=_headers())
    resp.raise_for_status()
    projects = resp.json()["projects"]
    match = next((p for p in projects if p["name"] == name), None)
    if not match:
        console.print(f"[red]Project '{name}' not found[/red]")
        raise typer.Exit(1)
    confirm = typer.confirm(f"Delete project '{name}' and all data?")
    if not confirm:
        raise typer.Abort()
    del_resp = httpx.delete(f"{_API_BASE}/projects/{match['id']}", headers=_headers())
    del_resp.raise_for_status()
    console.print(f"[green]Deleted project:[/green] {name}")


# ---------------------------------------------------------------------------
# ingest commands
# ---------------------------------------------------------------------------

@ingest_app.command("run")
def ingest_run(
    project: str = typer.Argument(..., help="Project name"),
    path: Path = typer.Argument(..., help="File or directory to ingest"),
):
    """Ingest a file or directory into a project."""
    import httpx
    # Resolve project ID
    resp = httpx.get(f"{_API_BASE}/projects", headers=_headers())
    resp.raise_for_status()
    projects = resp.json()["projects"]
    match = next((p for p in projects if p["name"] == project), None)
    if not match:
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)

    files = [path] if path.is_file() else list(path.rglob("*"))
    files = [f for f in files if f.is_file()]

    for f in files:
        with open(f, "rb") as fh:
            upload_resp = httpx.post(
                f"{_API_BASE}/projects/{match['id']}/documents",
                files={"file": (f.name, fh)},
                headers=_headers(),
                timeout=60,
            )
        upload_resp.raise_for_status()
        job = upload_resp.json()
        console.print(f"Queued [cyan]{f.name}[/cyan] — job_id: {job['job_id']}")


@ingest_app.command("status")
def ingest_status(job_id: str = typer.Argument(..., help="Job ID from ingest run")):
    """Check ingestion job status via ARQ/Redis."""
    import asyncio as _asyncio
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.jobs import Job, JobStatus

    async def _check():
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        pool = await create_pool(RedisSettings.from_dsn(redis_url))
        job = Job(job_id, pool)
        job_status = await job.status()
        info = await job.info()
        await pool.close()
        return job_status, info

    job_status, info = _asyncio.run(_check())
    console.print(f"Job [cyan]{job_id}[/cyan]: [bold]{job_status.value}[/bold]")
    if info and info.result is not None:
        console.print(f"Result: {info.result}")
    if info and info.enqueue_time:
        console.print(f"Enqueued: {info.enqueue_time}")


# ---------------------------------------------------------------------------
# query command
# ---------------------------------------------------------------------------

@app.command("query")
def query_cmd(
    project: str = typer.Argument(..., help="Project name"),
    question: str = typer.Argument(..., help="Question to ask"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    stream: bool = typer.Option(False, "--stream", "-s"),
):
    """Query a project."""
    import httpx

    resp = httpx.get(f"{_API_BASE}/projects", headers=_headers())
    resp.raise_for_status()
    projects = resp.json()["projects"]
    match = next((p for p in projects if p["name"] == project), None)
    if not match:
        console.print(f"[red]Project '{project}' not found[/red]")
        raise typer.Exit(1)

    if stream:
        with httpx.stream(
            "GET",
            f"{_API_BASE}/projects/{match['id']}/query/stream",
            params={"q": question},
            headers=_headers(),
            timeout=120,
        ) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if line.startswith("data: ") and not line.endswith("[DONE]"):
                    console.print(line[6:], end="")
        console.print()
    else:
        q_resp = httpx.post(
            f"{_API_BASE}/projects/{match['id']}/query",
            json={"query": question, "top_k": top_k},
            headers=_headers(),
            timeout=120,
        )
        q_resp.raise_for_status()
        data = q_resp.json()
        console.print(f"\n[bold]Answer:[/bold]\n{data['answer']}\n")
        if data["sources"]:
            table = Table("File", "Chunk", "Score")
            for s in data["sources"]:
                table.add_row(s["filename"], str(s["chunk_index"]), f"{s['score']:.4f}")
            console.print(table)


if __name__ == "__main__":
    app()
