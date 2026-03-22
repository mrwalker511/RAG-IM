import json
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from markdown_it import MarkdownIt

from api.middleware import api_key_middleware, rate_limit_middleware
from api.routers import api_keys, documents, projects, query
from ragcore.bootstrap import ensure_bootstrap_project_api_key
from ragcore.config import settings
from ragcore.db.redis import close_redis_pool
from ragcore.db.session import engine

_WEBAPP_PATH = Path(__file__).resolve().parent / "static" / "index.html"
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HANDBOOK_DOCS = [
    ("README.md", "Product overview, auth model, quickstart, and deployment notes."),
    ("testing.md", "Shortest path to verify unit, DB-backed, and live stack behavior."),
    ("STATUS.md", "Current state, last validation, and known gaps."),
    ("ROADMAP.md", "What is done, what is next, and what stays deferred."),
    ("DECISIONS.md", "Architecture choices and the trade-offs behind them."),
    ("GUIDE.md", "Prompting standards for focused engineering requests."),
    ("AGENT.md", "Working rules and repo-specific notes for coding agents."),
    ("ERRORS.md", "Historical implementation mistakes and their corrections."),
]
_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": True}).enable("table")

# Dimensions known to be produced by each supported model.
_KNOWN_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "all-MiniLM-L6-v2": 384,
}


def _validate_embedding_dim() -> None:
    expected = _KNOWN_DIMS.get(settings.EMBEDDING_MODEL)
    if expected is not None and settings.EMBEDDING_DIM != expected:
        raise RuntimeError(
            f"EMBEDDING_DIM={settings.EMBEDDING_DIM} does not match "
            f"model '{settings.EMBEDDING_MODEL}' which produces {expected}-dimensional vectors. "
            f"Set EMBEDDING_DIM={expected} in your .env or update the Alembic migration."
        )


def _render_web_app() -> str:
    return _WEBAPP_PATH.read_text(encoding="utf-8").replace(
        "__BOOTSTRAP_API_KEY__",
        json.dumps(settings.BOOTSTRAP_API_KEY),
    )


def _load_handbook_doc(doc_name: str) -> tuple[str, str]:
    allowed = {name for name, _ in _HANDBOOK_DOCS}
    if doc_name not in allowed:
        raise FileNotFoundError(doc_name)
    path = _PROJECT_ROOT / doc_name
    return doc_name, path.read_text(encoding="utf-8")


def _doc_title(markdown_text: str, fallback: str) -> str:
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _render_handbook_frame(title: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --bg: #f7f1e7;
      --bg-alt: #efe4d2;
      --panel: rgba(255, 250, 243, 0.92);
      --ink: #1f2933;
      --muted: #59636a;
      --line: rgba(31, 41, 51, 0.12);
      --brand: #0f766e;
      --brand-deep: #134e4a;
      --accent: #9a3412;
      --shadow: 0 24px 64px rgba(40, 37, 29, 0.14);
      --radius: 24px;
      --code-bg: #f3eadb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Segoe UI", "Trebuchet MS", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(154, 52, 18, 0.14), transparent 22%),
        linear-gradient(160deg, var(--bg) 0%, var(--bg-alt) 100%);
    }}
    .shell {{
      width: min(1180px, calc(100vw - 28px));
      margin: 28px auto 48px;
    }}
    .frame {{
      border: 1px solid var(--line);
      border-radius: 30px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
      backdrop-filter: blur(12px);
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 252, 247, 0.82);
    }}
    .brand {{
      display: grid;
      gap: 4px;
    }}
    .eyebrow {{
      margin: 0;
      font-size: 12px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: var(--brand-deep);
    }}
    .brand strong {{
      font-size: 1.1rem;
    }}
    .nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .nav a {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 16px;
      border-radius: 999px;
      text-decoration: none;
      color: white;
      font-weight: 700;
      background: linear-gradient(135deg, var(--brand) 0%, var(--brand-deep) 100%);
      box-shadow: 0 12px 28px rgba(15, 118, 110, 0.22);
    }}
    .nav a.secondary {{
      color: var(--ink);
      background: white;
      border: 1px solid var(--line);
      box-shadow: none;
    }}
    .content {{
      padding: 28px;
    }}
    .intro {{
      margin-bottom: 22px;
    }}
    .intro h1 {{
      margin: 0;
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1;
      letter-spacing: -0.04em;
    }}
    .intro p {{
      margin: 12px 0 0;
      color: var(--muted);
      max-width: 760px;
    }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
    }}
    .card {{
      padding: 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
    }}
    .card h2, .card h3 {{
      margin: 0 0 8px;
      font-size: 1.05rem;
    }}
    .card p {{
      margin: 0 0 14px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .card a {{
      color: var(--brand-deep);
      font-weight: 700;
      text-decoration: none;
    }}
    article.doc {{
      padding: 28px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
      line-height: 1.7;
    }}
    article.doc h1, article.doc h2, article.doc h3 {{
      line-height: 1.15;
      letter-spacing: -0.03em;
    }}
    article.doc table {{
      width: 100%;
      border-collapse: collapse;
      margin: 18px 0;
      font-size: 0.95rem;
    }}
    article.doc th, article.doc td {{
      padding: 10px 12px;
      border: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
    }}
    article.doc code {{
      padding: 2px 6px;
      border-radius: 8px;
      background: var(--code-bg);
      font-family: "SFMono-Regular", "Menlo", "Consolas", monospace;
      font-size: 0.92em;
    }}
    article.doc pre {{
      overflow-x: auto;
      padding: 16px;
      border-radius: 18px;
      background: #1f2933;
      color: #f9fafb;
    }}
    article.doc pre code {{
      padding: 0;
      background: transparent;
      color: inherit;
    }}
    article.doc a {{
      color: var(--accent);
    }}
    @media (max-width: 780px) {{
      .shell {{ width: min(100vw - 18px, 1180px); }}
      .topbar, .content, article.doc {{ padding: 18px; }}
      .topbar {{ align-items: start; flex-direction: column; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="frame">
      {content}
    </section>
  </main>
</body>
</html>"""


def _render_handbook_index() -> str:
    cards = []
    for filename, summary in _HANDBOOK_DOCS:
        title = _doc_title((_PROJECT_ROOT / filename).read_text(encoding="utf-8"), filename)
        cards.append(
            f"""
            <article class="card">
              <h2>{escape(title)}</h2>
              <p>{escape(summary)}</p>
              <a href="/handbook/{escape(filename)}">Open {escape(filename)}</a>
            </article>
            """
        )
    content = f"""
      <header class="topbar">
        <div class="brand">
          <p class="eyebrow">Project Handbook</p>
          <strong>Browse the repo docs in the browser</strong>
        </div>
        <nav class="nav">
          <a class="secondary" href="/">Control Room</a>
          <a href="/docs">OpenAPI</a>
        </nav>
      </header>
      <div class="content">
        <section class="intro">
          <h1>Markdown docs, surfaced as pages.</h1>
          <p>
            This view renders the checked-in project documentation directly from the repo.
            It is intended for fast browsing during deployment, testing, and handoff work.
          </p>
        </section>
        <section class="cards">
          {''.join(cards)}
        </section>
      </div>
    """
    return _render_handbook_frame("Project Handbook", content)


def _render_handbook_doc(doc_name: str) -> str:
    filename, markdown_text = _load_handbook_doc(doc_name)
    title = _doc_title(markdown_text, filename)
    rendered = _MARKDOWN.render(markdown_text)
    content = f"""
      <header class="topbar">
        <div class="brand">
          <p class="eyebrow">Project Handbook</p>
          <strong>{escape(filename)}</strong>
        </div>
        <nav class="nav">
          <a class="secondary" href="/handbook">All Docs</a>
          <a href="/">Control Room</a>
        </nav>
      </header>
      <div class="content">
        <section class="intro">
          <h1>{escape(title)}</h1>
          <p>The content below is rendered from the checked-in <code>{escape(filename)}</code> file.</p>
        </section>
        <article class="doc">
          {rendered}
        </article>
      </div>
    """
    return _render_handbook_frame(f"{title} | Handbook", content)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_embedding_dim()
    await ensure_bootstrap_project_api_key()
    yield
    await engine.dispose()
    await close_redis_pool()


def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Framework API",
        description="Reusable multi-project Retrieval-Augmented Generation API",
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["X-API-Key", "Content-Type", "Authorization"],
    )
    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(api_key_middleware)

    app.include_router(projects.router)
    app.include_router(documents.router)
    app.include_router(query.router)
    app.include_router(api_keys.router)

    @app.get("/", include_in_schema=False)
    async def index():
        return HTMLResponse(_render_web_app())

    @app.get("/handbook", include_in_schema=False)
    async def handbook_index():
        return HTMLResponse(_render_handbook_index())

    @app.get("/handbook/{doc_name:path}", include_in_schema=False)
    async def handbook_doc(doc_name: str):
        try:
            return HTMLResponse(_render_handbook_doc(doc_name))
        except FileNotFoundError:
            return HTMLResponse(_render_handbook_frame(
                "Document Not Found",
                """
                <header class="topbar">
                  <div class="brand">
                    <p class="eyebrow">Project Handbook</p>
                    <strong>Document not found</strong>
                  </div>
                  <nav class="nav">
                    <a class="secondary" href="/handbook">All Docs</a>
                    <a href="/">Control Room</a>
                  </nav>
                </header>
                <div class="content">
                  <section class="intro">
                    <h1>Document not found.</h1>
                    <p>The requested Markdown file is not in the published handbook list.</p>
                  </section>
                </div>
                """,
            ), status_code=404)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
