"""
Generate docs/index.html — a single self-contained dashboard (data embedded,
no external assets, works on GitHub Pages or double-clicked locally).

Tabs: 最新安排 Latest · 发行安排 Schedule · 实际发行 Realized · 分析 Analysis · 说明 About

    python src/build_dashboard.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from celma import DATA_CLEAN, DOCS

REPO_URL = "https://github.com/leyixu26/celma-lgb"


def _num(v, nd=2):
    return None if pd.isna(v) else round(float(v), nd)


def payload() -> dict:
    sched = pd.read_csv(DATA_CLEAN / "schedule.csv", dtype={"article_id": str})
    real = pd.read_csv(DATA_CLEAN / "realized.csv")
    sc = pd.read_csv(DATA_CLEAN / "scorecard.csv")
    nat = pd.read_csv(DATA_CLEAN / "national_monthly.csv")
    ver = json.loads((DATA_CLEAN / "verification.json").read_text(encoding="utf-8"))
    recon = pd.read_csv(DATA_CLEAN / "reconciliation.csv")

    s = sched.sort_values("publish_date", ascending=False, na_position="last")
    s_rows = [[r.publish_date, r.issuer, r.plan_period if pd.notna(r.plan_period) else "",
               _num(r.new_general_yi), _num(r.new_special_yi), _num(r.refinance_yi),
               _num(r.total_planned_yi), r.article_id]
              for r in s.itertuples()]

    r2 = real.sort_values("issue_date", ascending=False, na_position="last")
    r_rows = [[r.issue_date, r.issuer, r.bond_name, r.bond_type if pd.notna(r.bond_type) else "",
               r.tenor_label if pd.notna(r.tenor_label) else "", _num(r.coupon_pct),
               _num(r.amount_yi), _num(r.new_amount_yi), _num(r.refinance_amount_yi)]
              for r in r2.itertuples()]

    pm = recon[recon["has_plan"]]
    dr = pm[pm["delivery_ratio"].notna()]
    stats = {
        "lead_med": round(float(pm["lead_wd"].median()), 0),
        "on_time": round(100 * pm["on_time"].mean(), 0),
        "coverage": round(100 * recon[recon["has_issuance"]]["has_plan"].mean(), 0),
        "exact_pct": round(100 * ((dr["delivery_ratio"] - 1).abs() <= 0.01).mean(), 0),
        "within10_pct": round(100 * ((dr["delivery_ratio"] - 1).abs() <= 0.10).mean(), 0),
    }
    nat2 = nat[nat["period"] >= "2021-01"]
    return {
        "ver": ver, "stats": stats, "repo": REPO_URL,
        "schedule": s_rows, "realized": r_rows,
        "scorecard": [[r.issuer, _num(r.median_lead_wd, 1), _num(r.coverage_pct, 1),
                       _num(r.on_time_pct, 1), _num(r.median_delivery_ratio),
                       _num(r.score, 1)] for r in sc.itertuples()],
        "national": [[r.period, _num(r.planned_total_yi, 0), _num(r.realized_comparable_yi, 0)]
                     for r in nat2.itertuples()],
    }


TEMPLATE = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>中国地方债发行安排 · LGB Issuance Monitor</title>
<style>
:root{--ink:#1a202c;--mut:#64748b;--line:#e2e8f0;--blue:#1D66A0;--gold:#C8922A;--bg:#f8fafc}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:1150px;margin:0 auto;padding:0 20px 60px}
header{padding:26px 0 12px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600;margin-left:8px;vertical-align:1px}
.badge.ok{background:#dcfce7;color:#166534}.badge.bad{background:#fee2e2;color:#991b1b}
nav{display:flex;gap:4px;margin:14px 0 22px;border-bottom:1px solid var(--line);flex-wrap:wrap}
nav button{border:0;background:none;padding:9px 14px;font-size:14px;color:var(--mut);cursor:pointer;border-bottom:2px solid transparent;font-family:inherit}
nav button.on{color:var(--blue);border-bottom-color:var(--blue);font-weight:600}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:18px}
h2{font-size:15px;margin:0 0 12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th{position:sticky;top:0;background:#fff;text-align:left;color:var(--mut);font-weight:600;font-size:12px;padding:7px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:6px 8px;border-bottom:1px solid #f1f5f9;white-space:nowrap}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.name{max-width:340px;overflow:hidden;text-overflow:ellipsis}
tr:hover td{background:#f8fafc}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.filters{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap}
select,input[type=search]{font:inherit;font-size:13px;padding:6px 9px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}
.stat{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat .v{font-size:24px;font-weight:700;color:var(--blue)}
.stat .k{font-size:12px;color:var(--mut);margin-top:2px;line-height:1.35}
.note{color:var(--mut);font-size:12px;margin-top:8px}
.tbl{max-height:560px;overflow:auto;border:1px solid var(--line);border-radius:8px}
.bar{display:inline-block;height:9px;background:var(--blue);border-radius:3px;vertical-align:middle;margin-right:6px}
.tag{font-size:11px;padding:1px 7px;border-radius:999px;background:#eff6ff;color:var(--blue)}
.tag.g{background:#f0fdf4;color:#166534}
footer{color:var(--mut);font-size:12px;margin-top:28px;line-height:1.6}
.about p{font-size:13.5px;line-height:1.7;margin:8px 0}
svg text{font-family:inherit}
@media(max-width:640px){td.name{max-width:150px}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>中国地方债发行安排 <span style="color:var(--mut);font-weight:400">LGB Issuance Monitor</span>
    <span id="vbadge" class="badge"></span></h1>
  <div class="sub">数据源 celma.org.cn（财政部地方政府债券信息公开平台）· 数据截至 <b id="asof"></b> · 更新于 <span id="rundate"></span></div>
</header>
<nav id="nav">
  <button data-t="latest" class="on">最新安排</button>
  <button data-t="schedule">发行安排</button>
  <button data-t="realized">实际发行</button>
  <button data-t="analysis">分析</button>
  <button data-t="about">说明</button>
</nav>

<section id="t-latest">
  <div class="card"><h2 id="latestTitle"></h2>
    <div class="tbl"><table id="latestTbl"></table></div>
    <div class="note">单位：亿元。新增一般 / 新增专项 / 再融资 为各省《发行安排》标准表所列计划金额；「—」= 该文件未按标准表披露金额。点击日期打开 celma 原文。</div>
  </div>
  <div class="card"><h2>最近发布（最新 15 条）</h2>
    <div class="tbl"><table id="recentTbl"></table></div>
  </div>
</section>

<section id="t-schedule" hidden>
  <div class="card"><h2>发行安排 · 全部历史</h2>
    <div class="filters">
      <select id="sIss"></select><select id="sYr"></select>
      <input type="search" id="sQ" placeholder="搜索…">
      <span class="note" id="sCount"></span>
    </div>
    <div class="tbl"><table id="schedTbl"></table></div>
    <div class="note">显示前 400 行；完整数据见 <a id="csvSched" target="_blank">schedule.csv</a>。</div>
  </div>
</section>

<section id="t-realized" hidden>
  <div class="card"><h2>实际发行 · 发行结果</h2>
    <div class="filters">
      <select id="rIss"></select><select id="rYr"></select><select id="rTy"></select>
      <input type="search" id="rQ" placeholder="搜索债券名称…">
      <span class="note" id="rCount"></span>
    </div>
    <div class="tbl"><table id="realTbl"></table></div>
    <div class="note">显示前 400 行；完整数据见 <a id="csvReal" target="_blank">realized.csv</a>。</div>
  </div>
</section>

<section id="t-analysis" hidden>
  <div class="stats" id="statCards"></div>
  <div class="card"><h2>全国月度：计划 vs 实际（新增+再融资，亿元）</h2>
    <div id="natChart"></div>
    <div class="note">金色线 = 各省《发行安排》计划金额加总；蓝色面 = 实际发行（新增+再融资，不含置换）。2023 年起计划对实际的覆盖率达 ~90%。</div>
  </div>
  <div class="card"><h2>分省记分卡（按可用性得分排序）</h2>
    <div class="tbl" style="max-height:520px"><table id="scoreTbl"></table></div>
    <div class="note">得分 = 0.5·提前量(封顶20个工作日) + 0.5·覆盖率×按时率。负提前量 = 事后补发。交付比 = 实际÷计划（中位数）。定义详见 METHODOLOGY。</div>
  </div>
</section>

<section id="t-about" hidden>
  <div class="card about"><h2>数据与方法</h2>
    <p><b>来源。</b>celma.org.cn — 财政部指定的地方政府债券信息公开唯一网络平台。两套数据：<b>发行安排</b>（各省逐月发行计划，含标准表计划金额）与<b>发行结果</b>（实际发行明细）。仅存储客观字段（金额、日期、代码、类型），不存储文件正文。</p>
    <p><b>完整性验证。</b>每次更新自动核对来源自身口径：实际发行与 API 的 <code>total</code>/<code>sumCount</code> 对账；发行安排抓取循环直至条数等于网站「共 N 条」。全部核对项见 <a id="verLink" target="_blank">VERIFICATION.md</a>；本页顶部徽章为当次结果。</p>
    <p><b>逐行溯源。</b>发行安排每行含 celma 原文链接，可点击与网站直接比对。</p>
    <p><b>方法与结论。</b>管道、口径、公式与研究结论：<a id="methLink" target="_blank">METHODOLOGY.md</a>。</p>
    <p><b>数据下载。</b><span id="csvLinks"></span></p>
    <div id="verDetail"></div>
  </div>
</section>

<footer>本页面为静态文件，数据嵌入页面内；由数据管道自动生成。仓库：<a id="repoLink" target="_blank"></a></footer>
</div>

<script id="data" type="application/json">@@DATA@@</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const fmt = v => v==null ? '—' : v.toLocaleString('zh-CN',{maximumFractionDigits:2});
const art = id => 'https://www.celma.org.cn/dfzfxjh/'+id+'.jhtml';
const esc = s => String(s??'').replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// header
document.getElementById('asof').textContent = D.ver.as_of;
document.getElementById('rundate').textContent = D.ver.run_date;
const vb = document.getElementById('vbadge');
vb.textContent = D.ver.verified ? '✓ 已对账验证' : '⚠ 验证未通过';
vb.className = 'badge ' + (D.ver.verified ? 'ok' : 'bad');
document.getElementById('repoLink').textContent = D.repo; document.getElementById('repoLink').href = D.repo;
document.getElementById('verLink').href = D.repo + '/blob/main/VERIFICATION.md';
document.getElementById('methLink').href = D.repo + '/blob/main/docs/METHODOLOGY.md';
document.getElementById('csvSched').href = D.repo + '/blob/main/data/clean/schedule.csv';
document.getElementById('csvReal').href = D.repo + '/blob/main/data/clean/realized.csv';
document.getElementById('csvLinks').innerHTML = ['schedule','realized','reconciliation','scorecard','national_monthly']
  .map(n=>'<a target="_blank" href="'+D.repo+'/blob/main/data/clean/'+n+'.csv">'+n+'.csv</a>').join(' · ');

// tabs
document.getElementById('nav').addEventListener('click', e=>{
  if(e.target.tagName!=='BUTTON') return;
  document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on', b===e.target));
  document.querySelectorAll('section').forEach(s=>s.hidden = s.id !== 't-'+e.target.dataset.t);
});

// ---- Latest
const SCH = D.schedule; // [pub, issuer, period, gen, spec, refi, total, id]
// headline month = latest period with >=3 issuers (a lone far-ahead early post
// shouldn't displace the month the team actually cares about)
const perCount = {};
SCH.forEach(r=>{ if(r[2]) perCount[r[2]]=(perCount[r[2]]||0)+1; });
const periodsDesc = Object.keys(perCount).sort().reverse();
const latestPeriod = periodsDesc.find(p=>perCount[p]>=3) || periodsDesc[0];
document.getElementById('latestTitle').textContent = latestPeriod + ' 发行安排（' +
  SCH.filter(r=>r[2]===latestPeriod).length + ' 省份已发布）';
const SHEAD = '<tr><th>发布日期</th><th>省份</th><th>计划月份</th><th class="n">新增一般</th><th class="n">新增专项</th><th class="n">再融资</th><th class="n">合计</th></tr>';
const srow = r => '<tr><td><a target="_blank" href="'+art(r[7])+'">'+r[0]+'</a></td><td>'+esc(r[1])+'</td><td>'+r[2]+
  '</td><td class="n">'+fmt(r[3])+'</td><td class="n">'+fmt(r[4])+'</td><td class="n">'+fmt(r[5])+'</td><td class="n"><b>'+fmt(r[6])+'</b></td></tr>';
document.getElementById('latestTbl').innerHTML = SHEAD +
  SCH.filter(r=>r[2]===latestPeriod).sort((a,b)=>(b[6]??-1)-(a[6]??-1)).map(srow).join('');
document.getElementById('recentTbl').innerHTML = SHEAD + SCH.slice(0,15).map(srow).join('');

// ---- Schedule tab
const issuers = [...new Set(SCH.map(r=>r[1]))].sort();
const sYears = [...new Set(SCH.map(r=>(r[0]||'').slice(0,4)))].filter(Boolean).sort().reverse();
const fill=(el,opts,all)=>{el.innerHTML='<option value="">'+all+'</option>'+opts.map(o=>'<option>'+o+'</option>').join('')};
fill(document.getElementById('sIss'), issuers, '全部省份');
fill(document.getElementById('sYr'), sYears, '全部年份');
function drawSched(){
  const iss=document.getElementById('sIss').value, yr=document.getElementById('sYr').value,
        q=document.getElementById('sQ').value.trim();
  const rows = SCH.filter(r=>(!iss||r[1]===iss)&&(!yr||(r[0]||'').startsWith(yr))&&(!q||(r[1]+r[2]).includes(q)));
  document.getElementById('sCount').textContent = rows.length+' 条';
  document.getElementById('schedTbl').innerHTML = SHEAD + rows.slice(0,400).map(srow).join('');
}
['sIss','sYr','sQ'].forEach(id=>document.getElementById(id).addEventListener('input',drawSched));
drawSched();

// ---- Realized tab
const REAL = D.realized; // [date, issuer, name, type, tenor, coupon, amount, new, refi]
fill(document.getElementById('rIss'), issuers, '全部省份');
fill(document.getElementById('rYr'), [...new Set(REAL.map(r=>(r[0]||'').slice(0,4)))].filter(Boolean).sort().reverse(), '全部年份');
fill(document.getElementById('rTy'), ['一般债券','专项债券'], '全部类型');
const RHEAD='<tr><th>发行日</th><th>省份</th><th>债券名称</th><th>类型</th><th>期限</th><th class="n">票面%</th><th class="n">金额(亿)</th><th>性质</th></tr>';
function kind(r){ if(r[7]>0&&r[8]>0)return '<span class="tag g">新增</span><span class="tag">再融资</span>';
  if(r[8]>0)return '<span class="tag">再融资</span>'; if(r[7]>0)return '<span class="tag g">新增</span>'; return ''; }
function drawReal(){
  const iss=document.getElementById('rIss').value, yr=document.getElementById('rYr').value,
        ty=document.getElementById('rTy').value, q=document.getElementById('rQ').value.trim();
  const rows = REAL.filter(r=>(!iss||r[1]===iss)&&(!yr||(r[0]||'').startsWith(yr))&&(!ty||r[3]===ty)&&(!q||r[2].includes(q)));
  document.getElementById('rCount').textContent = rows.length+' 只 · 合计 '+fmt(rows.reduce((s,r)=>s+(r[6]||0),0))+' 亿';
  document.getElementById('realTbl').innerHTML = RHEAD + rows.slice(0,400).map(r=>
    '<tr><td>'+r[0]+'</td><td>'+esc(r[1])+'</td><td class="name" title="'+esc(r[2])+'">'+esc(r[2])+'</td><td>'+r[3]+
    '</td><td>'+r[4]+'</td><td class="n">'+fmt(r[5])+'</td><td class="n">'+fmt(r[6])+'</td><td>'+kind(r)+'</td></tr>').join('');
}
['rIss','rYr','rTy','rQ'].forEach(id=>document.getElementById(id).addEventListener('input',drawReal));
drawReal();

// ---- Analysis
const S = D.stats;
document.getElementById('statCards').innerHTML = [
  [S.lead_med+' 个工作日','计划 → 首次发行 提前量（中位数）'],
  [S.on_time+'%','按时发布（≤上月20日，财库〔2020〕36号）'],
  [S.coverage+'%','覆盖率：有发行的省·月中已发布计划的比例'],
  [S.exact_pct+'%','金额执行 ±1% 以内（'+S.within10_pct+'% 在 ±10% 内）'],
].map(x=>'<div class="stat"><div class="v">'+x[0]+'</div><div class="k">'+x[1]+'</div></div>').join('');

(function chart(){
  const N=D.national, W=1060,H=300,P={l:56,r:10,t:12,b:26};
  const max=Math.max(...N.map(r=>Math.max(r[1]||0,r[2]||0)))*1.06;
  const x=i=>P.l+(W-P.l-P.r)*i/(N.length-1), y=v=>H-P.b-(H-P.t-P.b)*v/max;
  let area='M'+x(0)+','+y(N[0][2]||0);
  N.forEach((r,i)=>area+=' L'+x(i)+','+y(r[2]||0));
  area+=' L'+x(N.length-1)+','+(H-P.b)+' L'+x(0)+','+(H-P.b)+' Z';
  const line=N.map((r,i)=>(i?'L':'M')+x(i)+','+y(r[1]||0)).join(' ');
  let ticks='',grid='';
  N.forEach((r,i)=>{ if(r[0].endsWith('-01')){ ticks+='<text x="'+x(i)+'" y="'+(H-8)+'" font-size="11" fill="#64748b" text-anchor="middle">'+r[0].slice(0,4)+'</text>';
    grid+='<line x1="'+x(i)+'" y1="'+P.t+'" x2="'+x(i)+'" y2="'+(H-P.b)+'" stroke="#eef2f7"/>' }});
  let ylab='';
  for(let k=0;k<=4;k++){const v=max*k/4; ylab+='<text x="'+(P.l-8)+'" y="'+(y(v)+4)+'" font-size="11" fill="#64748b" text-anchor="end">'+Math.round(v).toLocaleString()+'</text>'
    +'<line x1="'+P.l+'" y1="'+y(v)+'" x2="'+(W-P.r)+'" y2="'+y(v)+'" stroke="#eef2f7"/>'}
  document.getElementById('natChart').innerHTML =
    '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'+grid+ylab+
    '<path d="'+area+'" fill="#1D66A0" opacity="0.25"/><path d="'+line+'" fill="none" stroke="#C8922A" stroke-width="2"/>'+ticks+'</svg>';
})();

const scHead='<tr><th>#</th><th>省份</th><th class="n">提前量(工作日)</th><th class="n">覆盖率%</th><th class="n">按时率%</th><th class="n">交付比</th><th>得分</th></tr>';
document.getElementById('scoreTbl').innerHTML = scHead + D.scorecard.map((r,i)=>
  '<tr><td>'+(i+1)+'</td><td>'+esc(r[0])+'</td><td class="n">'+fmt(r[1])+'</td><td class="n">'+fmt(r[2])+'</td><td class="n">'+fmt(r[3])+
  '</td><td class="n">'+fmt(r[4])+'</td><td><span class="bar" style="width:'+Math.max(2,(r[5]||0))+'px"></span>'+fmt(r[5])+'</td></tr>').join('');

// ---- verification detail
document.getElementById('verDetail').innerHTML = '<h2 style="margin-top:18px">本次验证结果</h2><table>'+
  '<tr><th>#</th><th>核对项</th><th>结果</th><th>明细</th></tr>'+
  D.ver.checks.map(c=>'<tr><td>'+c.id+'</td><td>'+esc(c.desc)+'</td><td>'+(c.ok?'✅':'❌')+'</td><td>'+esc(c.detail)+'</td></tr>').join('')+'</table>';
</script>
</body>
</html>
"""


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload(), ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.replace("@@DATA@@", data.replace("</", "<\\/"))
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
    print(f"dashboard: {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
