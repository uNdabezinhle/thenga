from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
src = (ROOT / "northbound-prototype.html").read_text(encoding="utf-8")
start = src.index("<style>")
end = src.index("</style>") + len("</style>")
css = src[start:end]

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Northbound — Reka commerce</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700;800&family=Public+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
{css}
</head>
<body>
<div class="shell">
  <header class="topbar">
    <div class="wordmark">North<span>bound</span></div>
    <div class="sep"></div>
    <div class="tagline">Live client &mdash; wired to the Reka DRF API</div>
    <div class="spacer"></div>
    <div class="pill" id="sessionpill">guest session</div>
    <div class="pill" id="netpill">v1 &middot; live</div>
  </header>
  <div class="stage">
    <main class="left">
      <div class="phone">
        <div class="notch"></div>
        <div class="statusbar">
          <span>9:41</span>
          <span class="rt"><svg width="14" height="10" viewBox="0 0 14 10" fill="currentColor"><rect x="0" y="6" width="2.5" height="4" rx="1"/><rect x="3.8" y="4" width="2.5" height="6" rx="1"/><rect x="7.6" y="2" width="2.5" height="8" rx="1"/><rect x="11.4" y="0" width="2.5" height="10" rx="1"/></svg>
          </span>
        </div>
        <div class="viewport" id="viewport"></div>
        <nav class="bottomnav" id="bottomnav"></nav>
      </div>
      <p class="hint">Tap through the app. Every action hits the <b>real</b> <span class="mono">/api/v1/</span> backend — watch the inspector.</p>
    </main>
    <aside class="console">
      <div class="ctabs" id="ctabs"></div>
      <div class="cbody" id="cbody"></div>
    </aside>
  </div>
</div>
<script>window.REKA_API_BASE = window.REKA_API_BASE || 'http://127.0.0.1:8000';</script>
<script src="app.js"></script>
</body>
</html>
"""
out = ROOT / "frontend" / "index.html"
out.write_text(html, encoding="utf-8")
print(f"wrote {out} ({len(html)} bytes)")
