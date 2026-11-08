"""HTML and inline-SVG rendering for the presenter deck. No external assets."""
from __future__ import annotations

import html
from dataclasses import dataclass, field

STAGE_W, STAGE_H = 1920, 1080
CAM_W, CAM_H = 520, 368
GREEN, RED, CYAN, AMBER, GREY = "#34d399", "#f87171", "#22d3ee", "#fbbf24", "#94a3b8"
VERDICT_BADGE = {"true": ("survived", "good"), "split": ("split", "warn"), "false": ("didn't survive", "bad")}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


@dataclass
class Page:
    key: str
    kind: str                    # "slide" | "finding"
    section: str
    title: str
    subtitle: str = ""
    chart: str = ""              # inline SVG
    chart_texts: list = field(default_factory=list)
    stats: list = field(default_factory=list)      # dicts: label, value, tone
    conclusion: str = ""
    verdict: str | None = None
    cards: list = field(default_factory=list)      # dicts: big, label, note
    banner: str = ""

    def visible(self) -> list[str]:
        out = [self.section, self.title, self.subtitle, self.conclusion, self.banner] + list(self.chart_texts)
        for s in self.stats:
            out += [s["label"], s["value"]]
        for c in self.cards:
            out += [c.get("big", ""), c.get("label", ""), c.get("note", "")]
        if self.verdict:
            out.append(VERDICT_BADGE[self.verdict][0])
        return [x for x in out if x]


# --------------------------------------------------------------------------- charts
class SVG:
    def __init__(self, w, h):
        self.w, self.h, self.parts, self.texts = w, h, [], []

    def text(self, x, y, s, size=26, fill=GREY, anchor="start", weight=400, mono=False, cls="pop", delay=0.0):
        self.texts.append(s)
        fam = "var(--mono)" if mono else "var(--sans)"
        self.parts.append(f'<text class="{cls}" style="--d:{delay:.2f}s" x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
                          f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" font-family="{fam}">{esc(s)}</text>')

    def raw(self, s):
        self.parts.append(s)

    def done(self) -> str:
        return (f'<svg class="chart" viewBox="0 0 {self.w} {self.h}" width="{self.w}" height="{self.h}" '
                f'xmlns="http://www.w3.org/2000/svg">' + "".join(self.parts) + "</svg>")


def bars(items, w=1180, h=600) -> tuple[str, list]:
    """Vertical bars from a zero line. items: (label, value_text, value, tone)."""
    s = SVG(w, h)
    vals = [abs(v) for _, _, v, _ in items if v == v] or [1]
    vmax = max(vals) or 1
    has_neg = any(v < 0 for _, _, v, _ in items)
    has_pos = any(v > 0 for _, _, v, _ in items)
    top, bottom = 70, h - 80
    if has_neg and has_pos:
        zero = (top + bottom) / 2
        span = (bottom - top) / 2
    elif has_neg:
        zero, span = top + 10, bottom - top - 10
    else:
        zero, span = bottom, bottom - top
    n = len(items)
    slot = (w - 80) / n
    bw = min(220, slot * 0.55)
    s.raw(f'<line x1="40" x2="{w - 40}" y1="{zero:.1f}" y2="{zero:.1f}" stroke="#334155" stroke-width="2"/>')
    for i, (label, txt, v, tone) in enumerate(items):
        cx = 40 + slot * (i + 0.5)
        hgt = abs(v) / vmax * span if v == v else 0
        y = zero - hgt if v >= 0 else zero
        col = {"good": GREEN, "bad": RED, "cyan": CYAN, "amber": AMBER}.get(tone, CYAN)
        origin = "bottom" if v >= 0 else "top"
        s.raw(f'<rect class="grow" style="--d:{0.15 + 0.12 * i:.2f}s;transform-origin:{origin}" x="{cx - bw / 2:.1f}" '
              f'y="{y:.1f}" width="{bw:.1f}" height="{max(hgt, 2):.1f}" rx="10" fill="{col}"/>')
        vy = (y - 18) if v >= 0 else (y + hgt + 44)
        s.text(cx, vy, txt, 36, "#e2e8f0", "middle", 700, True, delay=0.5 + 0.12 * i)
        ly = (zero + 46) if v >= 0 else (zero - 20)
        s.text(cx, ly, label, 28, GREY, "middle", 500, delay=0.3 + 0.12 * i)
    return s.done(), s.texts


def forest(rows, w=1180, h=640, note="no difference") -> tuple[str, list]:
    """Dot and 95% interval per row. rows: (label, point_text, point, lo, hi, emphasis)."""
    s = SVG(w, h)
    left, right = 230, w - 170
    span = max([abs(x) for r in rows for x in (r[2], r[3], r[4]) if x == x] or [1]) * 1.1 or 1
    def X(v):
        return left + (v + span) / (2 * span) * (right - left)
    top, step = 50, (h - 110) / max(len(rows), 1)
    zx = X(0)
    s.raw(f'<line x1="{zx:.1f}" x2="{zx:.1f}" y1="{top - 20}" y2="{h - 50}" stroke="#475569" stroke-width="2" stroke-dasharray="6 8"/>')
    s.text(zx, h - 14, note, 22, GREY, "middle", 400, delay=0.1)
    for i, (label, txt, p, lo, hi, emph) in enumerate(rows):
        y = top + step * (i + 0.5)
        col = GREEN if p == p and p > 0 else RED
        d = 0.15 + 0.08 * i
        if emph:
            s.raw(f'<rect class="pop" style="--d:{d:.2f}s" x="10" y="{y - step / 2 + 4:.1f}" width="{w - 20}" '
                  f'height="{step - 8:.1f}" rx="12" fill="#111a2e"/>')
        s.text(20, y + 9, label, 26 if not emph else 28, "#e2e8f0" if emph else GREY, "start", 700 if emph else 500, delay=d)
        if lo == lo and hi == hi:
            s.raw(f'<line class="draw" style="--d:{d + 0.1:.2f}s" x1="{X(lo):.1f}" x2="{X(hi):.1f}" y1="{y:.1f}" y2="{y:.1f}" '
                  f'stroke="{col}" stroke-width="5" stroke-linecap="round" pathLength="1"/>')
        if p == p:
            s.raw(f'<circle class="pop" style="--d:{d + 0.3:.2f}s" cx="{X(p):.1f}" cy="{y:.1f}" r="{12 if emph else 9}" fill="{col}"/>')
        s.text(w - 10, y + 9, txt, 26, col if p == p else GREY, "end", 700, True, delay=d + 0.35)
    return s.done(), s.texts


def hbars(rows, w=1180, h=640) -> tuple[str, list]:
    """Horizontal bars: rows (label, value_text, value, tone). Values >= 0 or mixed."""
    s = SVG(w, h)
    left, right = 330, w - 190
    vmax = max([abs(r[2]) for r in rows if r[2] == r[2]] or [1]) or 1
    neg = any(r[2] < 0 for r in rows)
    zx = (left + right) / 2 if neg else left
    span = (right - left) / 2 if neg else right - left
    step = (h - 40) / max(len(rows), 1)
    for i, (label, txt, v, tone) in enumerate(rows):
        y = 20 + step * i
        bh = min(46, step * 0.62)
        ln = abs(v) / vmax * span if v == v else 0
        x = zx if v >= 0 else zx - ln
        col = {"good": GREEN, "bad": RED, "cyan": CYAN, "amber": AMBER}.get(tone, CYAN)
        d = 0.15 + 0.07 * i
        s.text(20, y + bh / 2 + 9, label, 26, "#e2e8f0", "start", 500, delay=d)
        s.raw(f'<rect class="grow-x" style="--d:{d:.2f}s;transform-origin:{"left" if v >= 0 else "right"}" x="{x:.1f}" '
              f'y="{y:.1f}" width="{max(ln, 2):.1f}" height="{bh:.1f}" rx="8" fill="{col}"/>')
        s.text(w - 10, y + bh / 2 + 9, txt, 26, col, "end", 700, True, delay=d + 0.3)
    return s.done(), s.texts


# --------------------------------------------------------------------------- pages
def page_html(p: Page, i: int, synthetic: bool) -> str:
    eyebrow = p.section.upper() + (f" · {synthetic.upper()}" if synthetic else "")   # synthetic = data label
    if p.kind == "slide":
        cards = "".join(
            f'<div class="card rise" style="--d:{0.25 + 0.15 * k:.2f}s"><div class="badge-n">{k + 1}</div>'
            f'<div class="big">{esc(c.get("big", ""))}</div><div class="clabel">{esc(c.get("label", ""))}</div>'
            + (f'<div class="cnote">{esc(c["note"])}</div>' if c.get("note") else "") + "</div>"
            for k, c in enumerate(p.cards))
        banner = f'<div class="banner rise" style="--d:0.1s">{esc(p.banner)}</div>' if p.banner else ""
        return (f'<section class="page slide" data-key="{esc(p.key)}" data-section="{esc(p.section)}">'
                f'<div class="eyebrow rise">{esc(eyebrow)}</div>{banner}'
                f'<h1 class="stitle rise" style="--d:0.05s">{esc(p.title)}</h1>'
                f'<p class="tagline rise" style="--d:0.15s">{esc(p.subtitle)}</p>'
                f'<div class="cards n{len(p.cards)}">{cards}</div></section>')
    stats = "".join(
        f'<div class="stat rise" style="--d:{0.35 + 0.15 * k:.2f}s"><div class="sval {s.get("tone", "")}">{esc(s["value"])}</div>'
        f'<div class="slabel">{esc(s["label"])}</div></div>' for k, s in enumerate(p.stats[:2]))
    badge = ""
    if p.verdict:
        t, tone = VERDICT_BADGE[p.verdict]
        badge = f'<span class="verdict {tone}">{esc(t)}</span>'
    return (f'<section class="page finding" data-key="{esc(p.key)}" data-section="{esc(p.section)}">'
            f'<div class="eyebrow rise">{esc(eyebrow)}</div>'
            f'<h1 class="title rise" style="--d:0.05s">{esc(p.title)}</h1>'
            f'<p class="subtitle rise" style="--d:0.12s">{esc(p.subtitle)}</p>'
            f'<div class="chartbox">{p.chart}</div>'
            f'<div class="side"><div class="stats">{stats}</div>'
            f'<div class="conclusion rise" style="--d:0.8s">{badge}<p>{esc(p.conclusion)}</p></div></div>'
            f'</section>')


CSS = r"""
:root{--bg:#0b0f1a;--panel:#111a2e;--cyan:#22d3ee;--amber:#fbbf24;--green:#34d399;--red:#f87171;--grey:#94a3b8;
--white:#f8fafc;--mono:ui-monospace,"SFMono-Regular","DejaVu Sans Mono",Menlo,Consolas,monospace;
--sans:"Inter","Segoe UI","Helvetica Neue","DejaVu Sans",Arial,sans-serif}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%;overflow:hidden;background:#05070d;color:var(--white);font-family:var(--sans)}
#stage{position:absolute;left:0;top:0;width:1920px;height:1080px;background:var(--bg);transform-origin:0 0;overflow:hidden}
.page{position:absolute;inset:0;display:none;padding:76px 96px 0 96px}
.page.active{display:block}
.eyebrow{font-family:var(--mono);font-size:22px;letter-spacing:.22em;color:var(--cyan);text-transform:uppercase;white-space:nowrap}
.title{font-size:66px;font-weight:800;margin-top:18px;letter-spacing:-.01em;white-space:nowrap}
.subtitle{font-size:30px;color:var(--grey);margin-top:12px;white-space:nowrap;max-width:1728px;overflow:hidden}
.chartbox{position:absolute;left:96px;top:330px;width:1180px;height:660px}
.chart{display:block;overflow:visible}
.side{position:absolute;left:1340px;top:330px;width:484px;height:372px;display:flex;flex-direction:column;justify-content:space-between}
.stats{display:flex;flex-direction:column;gap:14px}
.stat .sval{font-family:var(--mono);font-size:64px;font-weight:800;color:var(--cyan);line-height:1.05;white-space:nowrap}
.stat .sval.good{color:var(--green)}.stat .sval.bad{color:var(--red)}
.stat .slabel{font-size:22px;color:var(--grey);margin-top:2px;white-space:nowrap}
.conclusion{font-size:24px;line-height:1.35;color:#e2e8f0}
.conclusion p{margin-top:10px}
.verdict{display:inline-block;font-family:var(--mono);text-transform:uppercase;letter-spacing:.12em;font-size:20px;font-weight:700;
padding:7px 16px;border-radius:999px}
.verdict.good{background:rgba(52,211,153,.15);color:var(--green);border:2px solid var(--green)}
.verdict.warn{background:rgba(251,191,36,.15);color:var(--amber);border:2px solid var(--amber)}
.verdict.bad{background:rgba(248,113,113,.15);color:var(--red);border:2px solid var(--red)}
.slide .stitle{font-size:96px;font-weight:800;margin-top:26px;color:var(--white);white-space:nowrap}
.slide .tagline{font-size:34px;color:var(--grey);margin-top:16px;white-space:nowrap}
.banner{display:inline-block;margin-top:22px;font-family:var(--mono);font-size:22px;letter-spacing:.14em;color:#0b0f1a;
background:var(--amber);padding:8px 18px;border-radius:8px;text-transform:uppercase}
.cards{position:absolute;left:96px;right:96px;top:400px;display:flex;gap:28px}
.cards.n4 .card,.cards.n3 .card,.cards.n2 .card,.cards.n1 .card{flex:1}
.card{background:var(--panel);border:1px solid #1e293b;border-radius:24px;padding:30px 30px 26px;min-height:250px;max-height:290px}
.badge-n{width:46px;height:46px;border-radius:50%;background:var(--amber);color:#0b0f1a;font-family:var(--mono);font-weight:800;
font-size:24px;display:flex;align-items:center;justify-content:center}
.card .big{font-family:var(--mono);font-size:62px;font-weight:800;color:var(--cyan);margin-top:20px;white-space:nowrap}
.card .clabel{font-size:28px;color:var(--white);margin-top:6px;white-space:nowrap}
.card .cnote{font-size:21px;color:var(--grey);margin-top:6px;white-space:nowrap}
#pageno{position:absolute;left:96px;bottom:34px;font-family:var(--mono);font-size:18px;color:#475569;letter-spacing:.15em}
#cam{position:absolute;right:0;bottom:0;width:520px;height:368px;border:3px dashed var(--cyan);display:none;
background:rgba(34,211,238,.06);pointer-events:none}
#cam.on{display:block}
#menu{position:absolute;left:96px;top:120px;width:900px;background:rgba(17,26,46,.97);border:1px solid #1e293b;border-radius:20px;
padding:28px 36px;display:none;z-index:5}
#menu.on{display:block}
#menu div{font-size:30px;padding:10px 0;cursor:pointer;color:var(--white)}
#menu div span{font-family:var(--mono);color:var(--amber);margin-right:18px}
#ring{position:fixed;width:44px;height:44px;margin:-22px 0 0 -22px;border:3px solid var(--amber);border-radius:50%;
pointer-events:none;z-index:20;opacity:0;transition:opacity .2s}
#ink{position:fixed;inset:0;pointer-events:none;z-index:19}
/* build-in */
.page.active .rise{animation:rise .7s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--d,0s)}
.page.active .pop{animation:pop .6s ease-out both;animation-delay:var(--d,0s)}
.page.active .grow{transform-box:fill-box;animation:grow .9s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--d,0s)}
.page.active .grow-x{transform-box:fill-box;animation:growx .9s cubic-bezier(.2,.8,.2,1) both;animation-delay:var(--d,0s)}
.page.active .draw{stroke-dasharray:1;animation:draw .8s ease-out both;animation-delay:var(--d,0s)}
@keyframes rise{from{opacity:0;transform:translateY(24px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes growx{from{transform:scaleX(0)}to{transform:scaleX(1)}}
@keyframes draw{from{stroke-dashoffset:1}to{stroke-dashoffset:0}}
body.static .page *{animation:none!important}
body.static #ring{display:none}
"""

JS = r"""
(function(){
const stage=document.getElementById('stage');
const pages=[...document.querySelectorAll('.page')];
const pn=document.getElementById('pageno');
let cur=0;
function fit(){const s=Math.min(innerWidth/1920,innerHeight/1080);
 stage.style.transform=`translate(${(innerWidth-1920*s)/2}px,${(innerHeight-1080*s)/2}px) scale(${s})`;}
function show(i,replay){i=Math.max(0,Math.min(pages.length-1,i));
 pages.forEach(p=>p.classList.remove('active'));
 const p=pages[i]; if(replay){void p.offsetWidth;} p.classList.add('active'); cur=i;
 pn.textContent=(i+1)+' / '+pages.length;
 if(location.hash!=='#'+(i+1)) history.replaceState(null,'','#'+(i+1));}
function replay(){const p=pages[cur];p.classList.remove('active');void p.offsetWidth;p.classList.add('active');}
function fromHash(){const n=parseInt((location.hash||'#1').slice(1),10);show(isNaN(n)?0:n-1);}
addEventListener('resize',fit);addEventListener('hashchange',fromHash);
addEventListener('keydown',e=>{
 const k=e.key;
 if(['ArrowRight','ArrowDown',' ','PageDown','Enter'].includes(k)){show(cur+1);e.preventDefault();}
 else if(['ArrowLeft','ArrowUp','PageUp','Backspace'].includes(k)){show(cur-1);e.preventDefault();}
 else if(k==='Home'){show(0);}
 else if(k==='End'){show(pages.length-1);}
 else if(k==='r'||k==='R'){replay();}
 else if(k==='f'||k==='F'){document.getElementById('cam').classList.toggle('on');}
 else if(k==='m'||k==='M'){document.getElementById('menu').classList.toggle('on');}
 else if(k==='Escape'){document.getElementById('menu').classList.remove('on');}
});
// section menu
const menu=document.getElementById('menu');const seen=new Set();
pages.forEach((p,i)=>{const s=p.dataset.section;if(seen.has(s))return;seen.add(s);
 const d=document.createElement('div');const b=document.createElement('span');b.textContent='>';d.appendChild(b);
 d.appendChild(document.createTextNode(s));d.onclick=()=>{show(i);menu.classList.remove('on');};menu.appendChild(d);});
// pointer ring and highlighter
const ring=document.getElementById('ring');const ink=document.getElementById('ink');const ctx=ink.getContext('2d');
let strokes=[],drawing=null;
function size(){ink.width=innerWidth*devicePixelRatio;ink.height=innerHeight*devicePixelRatio;ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);}
size();addEventListener('resize',size);
addEventListener('mousemove',e=>{ring.style.left=e.clientX+'px';ring.style.top=e.clientY+'px';ring.style.opacity=1;
 if(drawing){drawing.pts.push([e.clientX,e.clientY]);drawing.t=performance.now();}});
addEventListener('mouseleave',()=>{ring.style.opacity=0;});
addEventListener('mousedown',e=>{drawing={pts:[[e.clientX,e.clientY]],t:performance.now()};strokes.push(drawing);});
addEventListener('mouseup',()=>{if(drawing)drawing.t=performance.now();drawing=null;});
(function loop(){ctx.clearRect(0,0,innerWidth,innerHeight);const now=performance.now();
 strokes=strokes.filter(s=>s===drawing||now-s.t<4000);
 for(const s of strokes){const age=s===drawing?0:now-s.t;const a=age<2500?0.45:0.45*(1-(age-2500)/1500);
  ctx.strokeStyle=`rgba(253,224,71,${Math.max(a,0)})`;ctx.lineWidth=22;ctx.lineCap='round';ctx.lineJoin='round';
  ctx.beginPath();s.pts.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.stroke();}
 requestAnimationFrame(loop);})();
window.deck={go:i=>show(i),count:()=>pages.length,finish:()=>document.body.classList.add('static'),replay};
fit();fromHash();
})();
"""


def document(pages: list[Page], synthetic: bool, title: str) -> str:
    body = "".join(page_html(p, i, synthetic) for i, p in enumerate(pages))
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
            f'<div id="stage">{body}<div id="pageno"></div><div id="cam"></div><div id="menu"></div></div>'
            f'<canvas id="ink"></canvas><div id="ring"></div><script>{JS}</script></body></html>')
