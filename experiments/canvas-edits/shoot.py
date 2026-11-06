"""shoot.py — a screenshot of the score canvas around some notes, with those notes circled in red, the way the composer
points at notes when he screenshots the canvas. Uses the project's studio/score-canvas.html (headless Chrome)."""
import sys
from pathlib import Path

JS = r"""(rows) => {
  const els = rows.map(r => document.querySelector(`[data-row="${r}"]`)).filter(Boolean);
  if (!els.length) return null;
  const sys = els.map(e => e.closest('.system') || e.ownerSVGElement);
  let L = 1e9, T = 1e9, R = -1e9, B = -1e9;
  for (const s of sys) { const b = s.getBoundingClientRect(); L = Math.min(L, b.left); T = Math.min(T, b.top); R = Math.max(R, b.right); B = Math.max(B, b.bottom); }
  for (const e of els) {
    const b = e.getBoundingClientRect(); const d = document.createElement('div');
    d.style.cssText = 'position:absolute;pointer-events:none;z-index:99;border:3px solid #e0201b;border-radius:50%;'
      + 'left:' + (b.left + scrollX - 9) + 'px;top:' + (b.top + scrollY - 9) + 'px;width:' + (b.width + 12) + 'px;height:' + (b.height + 12) + 'px';
    document.body.appendChild(d);
  }
  return {x: Math.max(0, L + scrollX - 24), y: Math.max(0, T + scrollY - 34), w: (R - L) + 48, h: (B - T) + 76};
}"""


def shoot(page_html, rows, out_png, width=1100):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        pg = b.new_page(viewport={"width": width, "height": 900}, device_scale_factor=2)
        pg.goto(Path(page_html).resolve().as_uri()); pg.wait_for_timeout(1200)
        box = pg.evaluate(JS, list(rows))
        if not box:
            b.close(); raise RuntimeError(f"rows {rows} not on the canvas")
        pg.screenshot(path=str(out_png), clip={"x": box["x"], "y": box["y"], "width": box["w"], "height": box["h"]}, full_page=True)
        b.close()


if __name__ == "__main__":
    shoot(sys.argv[1], [int(x) for x in sys.argv[3:]], sys.argv[2])
