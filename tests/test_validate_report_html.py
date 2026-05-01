from __future__ import annotations

from pathlib import Path

from tools.research.validate_report_html import validate_html_report


def _locked_like_html() -> str:
    sections = "\n".join(
        f'<div class="section" id="{sid}"></div>'
        for sid in (
            "section-summary",
            "section-financials",
            "section-prediction",
            "section-sankey",
            "section-porter",
            "section-appendix",
        )
    )
    summary = "\n".join('<p class="summary-para">x</p>' for _ in range(4))
    kpis = "\n".join('<div class="kpi-card"></div>' for _ in range(4))
    trends = "\n".join('<div class="trend-card"></div>' for _ in range(5))
    porters = "\n".join(f'<div id="porter-panel-{i}"></div>' for i in ("company", "industry", "forward"))
    radar = "\n".join(f'<canvas id="chart-radar-{i}"></canvas>' for i in ("company", "industry", "forward"))
    filler = "\n".join("<!-- locked filler -->" for _ in range(520))
    return f"""<!doctype html>
<html>
<head><style>CANONICAL CSS</style></head>
<body>
{sections}
<div id="section-summary">{summary}</div>
<div id="section-financials">{kpis}{trends}</div>
<div id="section-sankey"><svg id="chart-sankey-actual"></svg><svg id="chart-sankey-forecast"></svg></div>
<div id="section-porter">{porters}{radar}</div>
<script>
LOCKED JAVASCRIPT
DATA VARIABLES
const waterfallData = [];
const sankeyActualData = {{}};
const sankeyForecastData = {{}};
const porterScores = {{}};
function drawWaterfall() {{}}
function drawSankey() {{}}
function drawRadar() {{}}
</script>
{filler}
</body>
</html>"""


def test_validate_report_html_rejects_simplified_page(tmp_path: Path) -> None:
    html = tmp_path / "Simple_Research_CN.html"
    html.write_text("<html><body><h1>简化版</h1></body></html>", encoding="utf-8")

    result = validate_html_report(html)

    assert result["status"] == "critical"
    assert any("missing locked-template marker" in e for e in result["errors"])
    assert any("line count is too low" in e for e in result["errors"])


def test_validate_report_html_accepts_locked_like_page(tmp_path: Path) -> None:
    skeleton = tmp_path / "_locked_cn_skeleton.html"
    html = tmp_path / "Company_Research_CN.html"
    payload = _locked_like_html()
    skeleton.write_text(payload, encoding="utf-8")
    html.write_text(payload.replace("locked filler", "filled filler"), encoding="utf-8")

    result = validate_html_report(html, skeleton)

    assert result["status"] == "pass"
    assert result["errors"] == []
