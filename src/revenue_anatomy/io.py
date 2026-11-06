"""File boundaries, provenance, and portable report output."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(
    os.environ.get("PROJECT_ROOT", _SOURCE_ROOT if (_SOURCE_ROOT / "pyproject.toml").exists() else Path.cwd())
)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value, indent=2, default=lambda x: x.item() if hasattr(x, "item") else str(x), allow_nan=False
        )
        + "\n"
    )


def fetch(url, path, refresh=False):
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if refresh or not path.exists():
        session = requests.Session()
        session.mount(
            "https://",
            HTTPAdapter(
                max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            ),
        )
        response = session.get(url, timeout=(20, 180), headers={"User-Agent": "AppliedAnalyticsResearch/1.0"})
        response.raise_for_status()
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(response.content)
        temp.replace(path)
        dump(
            path.with_suffix(path.suffix + ".provenance.json"),
            {
                "url": url,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "sha256": hashlib.sha256(response.content).hexdigest(),
                "bytes": len(response.content),
            },
        )
    metadata = path.with_suffix(path.suffix + ".provenance.json")
    if not metadata.exists():
        dump(
            metadata,
            {
                "url": url,
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "retrieved_at_utc": None,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "note": "Existing local download; original retrieval timestamp not captured",
            },
        )
    if metadata.exists():
        expected = json.loads(metadata.read_text())["sha256"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Cached source checksum mismatch: {path}")
    return path


def report(name, markdown, metrics):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    (out / "analysis.md").write_text(markdown)
    dump(out / "metrics.json", metrics)
    snapshots = {}
    for source in sorted((ROOT / "data/raw").glob("*.provenance.json")):
        snapshots[source.name] = json.loads(source.read_text())
    dump(out / "source_manifest.json", snapshots)
    import platform

    code_hashes = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "src").rglob("*.py"))
    }
    dump(
        out / "build_manifest.json",
        {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "source_code_sha256": code_hashes,
        },
    )
    styles = getSampleStyleSheet()
    styles["BodyText"].textColor = colors.HexColor("#26354b")
    story = [Paragraph(escape(name), styles["Title"]), Spacer(1, 12)]
    for paragraph in markdown.split("\n\n"):
        if not paragraph.strip():
            continue
        style = styles["Heading2"] if paragraph.startswith("#") else styles["BodyText"]
        story += [Paragraph(escape(paragraph.lstrip("# ")).replace("\n", "<br/>"), style), Spacer(1, 9)]
    SimpleDocTemplate(str(out / "analysis.pdf"), pagesize=A4, title=name, author="Guhan Purushothaman").build(
        story
    )


def chart(fig, name):
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    fig.update_layout(
        template="plotly_white", font=dict(family="Arial", color="#26354b"), paper_bgcolor="#f7f9fc"
    )
    fig.write_html(out / f"{name}.html", include_plotlyjs=True)


def theme(title, subtitle):
    import streamlit as st

    st.set_page_config(page_title=title, page_icon="◈", layout="wide")
    st.markdown(
        "<style>.stApp{background:#f7f9fc}h1,h2,h3{color:#17324d}[data-testid=stMetric]{background:white;padding:18px;border-radius:12px;border:1px solid #e1e7ed}</style>",
        unsafe_allow_html=True,
    )
    st.title(title)
    st.caption(subtitle)


def require(path, command):
    import streamlit as st

    if not Path(path).exists():
        st.info(f"Generate the project data first: `{command}`")
        st.stop()
