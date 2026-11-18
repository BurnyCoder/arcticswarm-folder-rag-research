"""Build the interactive results explorer: docs/index.html (single self-contained file).

Global context: CLAUDE.md asks for an interactive UI to explore positive and negative
results. This script embeds results/<tag>/judged.jsonl + metrics.json into one HTML
page (vanilla JS, no external requests): a summary table, a quality-vs-agents chart
(SVG), and a per-question browser that shows, for every arm, the final answer, the
judge verdict or rubric scores, the cost and tool usage, and the full response
(collapsible). All rows are shown, nothing is filtered or cherry-picked.

Usage: uv run python scripts/build_site.py --tag day1
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PAGE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ArcticSwarm folder-RAG results explorer</title>
<style>
:root{--fg:#1d1d1f;--muted:#6b7280;--line:#e5e7eb;--accent:#2a6fdb;--ok:#15803d;--bad:#b91c1c;--bg:#fff;--card:#f9fafb}
@media (prefers-color-scheme: dark){:root{--fg:#e5e7eb;--muted:#9ca3af;--line:#374151;--bg:#111827;--card:#1f2937;--accent:#60a5fa}}
body{font:14px/1.5 system-ui,Segoe UI,sans-serif;color:var(--fg);background:var(--bg);margin:0;padding:24px;max-width:1200px;margin:auto}
h1{font-size:22px;margin:0 0 4px} h2{font-size:17px;margin:28px 0 8px} .muted{color:var(--muted)}
table{border-collapse:collapse;width:100%;font-size:13px} th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
th{position:sticky;top:0;background:var(--bg)} .num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--ok);font-weight:600} .bad{color:var(--bad);font-weight:600}
select,input{font:inherit;padding:4px 6px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;margin:10px 0}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px;max-height:420px;overflow:auto;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px}
.pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 8px;margin:2px;font-size:12px}
svg text{fill:var(--fg);font-size:11px}
</style></head><body>
<h1>ArcticSwarm for RAG over local folders: results explorer</h1>
<div class="muted">Claude Haiku 5.5 for every role. Day 1 (2026-11-18), pre-registered, n = 20 paired questions per arm (10 MultiHop-RAG and 10 SWE-QA). Exploratory: CIs are wide.</div>
<h2>Summary</h2><div id="summary"></div>
<h2>Quality vs number of agents</h2><div id="chart"></div>
<div class="muted">Error bars: 95% Wilson CI (MultiHop-RAG accuracy) and bootstrap CI (SWE-QA score / 100). x = max agents (1 = single agent B2; 16 = ArcticSwarm default M).</div>
<h2>Per-question browser</h2>
<div>Dataset <select id="ds"><option value="">all</option><option>MULTIHOPRAG</option><option>SWEQA</option></select>
Question <select id="q"></select> <label><input type="checkbox" id="full"> show full responses</label></div>
<div id="detail"></div>
<script>
const ROWS = __ROWS__;
const METRICS = __METRICS__;
const cap = c => c==="B2"?1:(c==="M"?16:parseInt(c.slice(5)));
const label = c => c==="B2"?"Single agent (B2)":(c==="M"?"Swarm cap 16 (M)":"Swarm cap "+cap(c));
const conds = Object.keys(METRICS.summary).sort((a,b)=>cap(a)-cap(b));
const pct = v => v==null?"–":(100*v).toFixed(0)+"%";
const esc = s => (s||"").replace(/[&<>]/g, ch=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[ch]));
function summary(){
  let h = "<table><tr><th>Arm</th><th class=num>max agents</th><th class=num>agents spawned/q</th><th class=num>MultiHop-RAG acc. [95% CI]</th><th class=num>SWE-QA /100 [95% CI]</th><th class=num>$/question</th><th class=num>median s</th><th class=num>tool calls/q</th></tr>";
  for (const c of conds){ const s = METRICS.summary[c];
    h += `<tr><td>${label(c)}</td><td class=num>${cap(c)}</td><td class=num>${s.agents_spawned_mean==null?"–":s.agents_spawned_mean.toFixed(1)}</td>`+
      `<td class=num>${pct(s.mhr_judge_acc)} [${pct(s.mhr_judge_ci[0])}, ${pct(s.mhr_judge_ci[1])}]</td>`+
      `<td class=num>${s.swe_mean.toFixed(1)} [${s.swe_ci[0].toFixed(1)}, ${s.swe_ci[1].toFixed(1)}]</td>`+
      `<td class=num>${s.cost_usd_per_q.toFixed(3)}</td><td class=num>${s.latency_s_median.toFixed(0)}</td><td class=num>${s.tool_calls_mean.toFixed(1)}</td></tr>`; }
  const t = METRICS.tests||{};
  if (t.H1) h += `</table><p class=muted>Pre-registered M vs B2: MultiHop-RAG diff ${pct(t.H1.diff)} (Holm p=${t.H1.p_holm.toFixed(3)}); SWE-QA diff ${t.H3.diff.toFixed(1)} [${t.H3.ci[0].toFixed(1)}, ${t.H3.ci[1].toFixed(1)}] (Holm p=${t.H3.p_holm.toFixed(3)}).</p>`;
  document.getElementById("summary").innerHTML = h;
}
function chart(){
  const W=640,H=260,L=50,B=30,T=10; const xs=conds.map(cap); const lx=x=>L+(Math.log2(x)/4)*(W-L-20); const ly=y=>T+(1-y)*(H-T-B);
  let s=`<svg width=${W} height=${H} role=img aria-label="quality vs agents">`;
  for (let y=0;y<=1.0001;y+=0.25){ s+=`<line x1=${L} x2=${W-20} y1=${ly(y)} y2=${ly(y)} stroke="currentColor" opacity=.12 /><text x=${L-8} y=${ly(y)+4} text-anchor=end>${y.toFixed(2)}</text>`; }
  for (const x of xs){ s+=`<text x=${lx(x)} y=${H-10} text-anchor=middle>${x}</text>`; }
  const series=[["MultiHop-RAG accuracy","#2a6fdb",c=>[METRICS.summary[c].mhr_judge_acc,...METRICS.summary[c].mhr_judge_ci]],
                ["SWE-QA score / 100","#e07b39",c=>[METRICS.summary[c].swe_mean/100,METRICS.summary[c].swe_ci[0]/100,METRICS.summary[c].swe_ci[1]/100]]];
  series.forEach(([name,col,f],k)=>{ let pts=conds.map(c=>{const [v,lo,hi]=f(c); return [lx(cap(c))+(k?4:-4),ly(v),ly(lo),ly(hi)];});
    s+=`<polyline fill=none stroke=${col} stroke-width=2 points="${pts.map(p=>p[0]+","+p[1]).join(" ")}" />`;
    pts.forEach(p=>{ s+=`<line x1=${p[0]} x2=${p[0]} y1=${p[2]} y2=${p[3]} stroke=${col} /><circle cx=${p[0]} cy=${p[1]} r=4 fill=${col} />`; });
    s+=`<rect x=${W-210} y=${14+k*16} width=10 height=10 fill=${col} /><text x=${W-195} y=${23+k*16}>${name}</text>`; });
  s+=`<text x=${(W)/2} y=${H} text-anchor=middle>max agents (log2)</text></svg>`;
  document.getElementById("chart").innerHTML=s;
}
function questions(){
  const ds=document.getElementById("ds").value; const ids=[...new Set(ROWS.filter(r=>!ds||r.dataset===ds).map(r=>r.id))];
  document.getElementById("q").innerHTML=ids.map(i=>`<option>${i}</option>`).join(""); detail();
}
function detail(){
  const id=document.getElementById("q").value, full=document.getElementById("full").checked;
  const rs=ROWS.filter(r=>r.id===id).sort((a,b)=>cap(a.condition)-cap(b.condition)); if(!rs.length) return;
  let h=`<div class=card><b>${esc(rs[0].question)}</b><div class=muted>${rs[0].dataset} · ${esc(rs[0].stratum)} · folder ${esc(rs[0].folder)}</div><details><summary>Gold answer</summary><pre>${esc(rs[0].answer)}</pre></details></div>`;
  for (const r of rs){
    const verdict = r.dataset==="MULTIHOPRAG" ? (r.judge_correct?"<span class=ok>correct</span>":"<span class=bad>incorrect</span>") : `<b>${r.sweqa_total}</b>/100 `+Object.entries(r.sweqa_scores||{}).map(([k,v])=>`<span class=pill>${k} ${v}</span>`).join("");
    const tools=Object.entries(r.tool_calls||{}).filter(([k,v])=>v).map(([k,v])=>`<span class=pill>${k} ${v}</span>`).join("");
    h+=`<div class=card><b>${label(r.condition)}</b>: ${verdict} · $${(r.cost_usd||0).toFixed(3)} · ${(r.duration_s||0).toFixed(0)} s · agents ${r.agents_spawned??(r.condition==="B2"?1:"–")}<div>${tools}</div>`+
       `<div><b>FINAL ANSWER:</b> ${esc(r.final_answer)||"<i>(missing)</i>"}</div>`+(r.judge_reason?`<div class=muted>judge: ${esc(r.judge_reason)}</div>`:"")+
       (full?`<pre>${esc(r.response)}</pre>`:`<details><summary>full response (${(r.response||"").length} chars)</summary><pre>${esc(r.response)}</pre></details>`)+`</div>`;
  }
  document.getElementById("detail").innerHTML=h;
}
document.getElementById("ds").onchange=questions; document.getElementById("q").onchange=detail; document.getElementById("full").onchange=detail;
summary(); chart(); questions();
</script></body></html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="day1")
    ap.add_argument("--split", default="", help="also write <dir>/index.html + <dir>/data.json (data fetched, for hosting)")
    a = ap.parse_args()
    res = ROOT / "results" / a.tag
    keep = ("condition", "id", "dataset", "folder", "stratum", "question", "answer", "response", "final_answer",
            "judge_correct", "judge_reason", "exact_match", "sweqa_total", "sweqa_scores", "cost_usd", "duration_s",
            "tool_calls", "agents_spawned", "evidence_recall")
    rows = [{k: r.get(k) for k in keep} for r in map(json.loads, (res / "judged.jsonl").open(encoding="utf-8"))]
    metrics = json.loads((res / "metrics.json").read_text(encoding="utf-8"))
    # json.dumps then neutralise "</" so embedded text can never close the <script> tag.
    page = PAGE.replace("__ROWS__", json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")) \
               .replace("__METRICS__", json.dumps(metrics, ensure_ascii=False, default=float).replace("</", "<\\/"))
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(page, encoding="utf-8")
    if a.split:
        # Hosted variant: data beside the page as data.json, loaded with fetch().
        d = Path(a.split)
        d.mkdir(parents=True, exist_ok=True)
        (d / "data.json").write_text(json.dumps({"rows": rows, "metrics": metrics}, ensure_ascii=False, default=float),
                                     encoding="utf-8")
        hosted = PAGE.replace("const ROWS = __ROWS__;", "let ROWS = [];").replace("const METRICS = __METRICS__;", "let METRICS = {summary:{}};")
        init = "summary(); chart(); questions();"
        hosted = hosted.replace(init, "fetch('data.json').then(r=>r.json()).then(d=>{ROWS=d.rows; METRICS=d.metrics; "
                                      "conds.splice(0, conds.length, ...Object.keys(METRICS.summary).sort((a,b)=>cap(a)-cap(b))); " + init + "});")
        (d / "index.html").write_text(hosted, encoding="utf-8")
        print("hosted variant:", d)
    print(out, f"{len(page)/1e6:.1f} MB", html.escape("ok"))


if __name__ == "__main__":
    main()
