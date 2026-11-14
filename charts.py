"""Charts and the interactive dashboard."""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src.model import CATEGORIES, DEFAULT_VALUES, LABELS, PROGRAMS, evaluate

BG, CARD, TEXT, TEXT2, MUTED, GRID = "#1a1a19", "#222220", "#f0efec", "#c3c2b7", "#8a8980", "#3a3936"
BANK_COLORS = {"Bancolombia": "#c98500", "BBVA": "#3987e5", "DAVIbank": "#d95926",
               "Davivienda": "#e66767", "Banco Falabella": "#199e70", "Nu": "#9085e9"}
plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG, "axes.edgecolor": GRID, "axes.labelcolor": TEXT2,
    "xtick.color": MUTED, "ytick.color": MUTED, "text.color": TEXT, "font.size": 10,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "font.family": "DejaVu Sans",
})


def display_names(cards):
    short = {"Bancolombia": "Bcol", "BBVA": "BBVA", "DAVIbank": "DAVIbank", "Davivienda": "Davivienda",
             "Banco Falabella": "Falabella", "Nu": "Nu"}
    return ["Nu Mastercard" if b == "Nu" else f"{short[b]} {n.replace('American Express', 'Amex').replace('Mastercard', 'MC')}"
            for b, n in zip(cards.bank, cards.name)]


def card_colors(cards):
    """One hue per bank, lighter steps for the bank's other cards."""
    out = []
    seen = {}
    for b in cards.bank:
        k = seen.get(b, 0)
        seen[b] = k + 1
        base = np.array(matplotlib.colors.to_rgb(BANK_COLORS[b]))
        mix = min(0.12 * k, 0.6)
        out.append(matplotlib.colors.to_hex(base * (1 - mix) + np.array([0.94, 0.94, 0.93]) * mix))
    return out


def chart_3d(out, cards, base_mix):
    names = display_names(cards)
    colors = card_colors(cards)
    spend = np.geomspace(500_000, 25_000_000, 60)
    pv = np.linspace(5, 35, 61)
    S, P = np.meshgrid(spend, pv)
    single = evaluate(cards, S.ravel()[:, None] * base_mix[None], {"puntos_bbva": P.ravel()}, pairs=False)
    Z = (single.max(1) / 1e6).reshape(S.shape)
    W = single.argmax(1).reshape(S.shape)
    present = sorted(set(W.ravel()))
    m = len(present)
    idx = {k: i for i, k in enumerate(present)}
    Wn = np.vectorize(idx.get)(W).astype(float)
    scale = []
    for i, k in enumerate(present):
        scale += [[i / m, colors[k]], [(i + 1) / m, colors[k]]]
    hover = np.vectorize(lambda k: names[k])(W)
    fig = go.Figure()
    fig.add_surface(x=np.log10(S), y=P, z=Z, surfacecolor=Wn, cmin=0, cmax=m, colorscale=scale, showscale=False,
                    customdata=np.dstack([S / 1e6, hover]),
                    hovertemplate="Monthly spend %{customdata[0]:.1f}M COP<br>Puntos BBVA worth %{y:.1f} COP"
                                  "<br>Best card: %{customdata[1]}<br>Net value %{z:.2f}M COP/yr<extra></extra>",
                    lighting=dict(ambient=0.75, diffuse=0.6, specular=0.15))
    for k in present:
        fig.add_scatter3d(x=[None], y=[None], z=[None], mode="markers", marker=dict(size=8, color=colors[k]),
                          name=names[k] + (" (tied with Infinite, Blue Diamond)" if cards.id[k] == "bbva_platinum" else ""))
    ticks = [5e5, 1e6, 2e6, 5e6, 1e7, 2e7]
    fig.update_layout(
        title=dict(text="Best card among the 24 I track, by monthly spend and by what a Puntos BBVA point is worth<br>"
                        "<sup>Color = winning card. Height = its net annual value (rewards minus cuota de manejo after waivers). "
                        "Young-professional spending mix.</sup>", font=dict(color=TEXT, size=16)),
        paper_bgcolor=BG, font=dict(color=TEXT2, family="Inter, Arial"), height=720,
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.01, y=0.85),
        scene=dict(
            xaxis=dict(title="Monthly card spend (COP)", tickvals=np.log10(ticks),
                       ticktext=["0.5M", "1M", "2M", "5M", "10M", "20M"], backgroundcolor=CARD, gridcolor=GRID, color=TEXT2),
            yaxis=dict(title="Value of one Puntos BBVA point (COP)", backgroundcolor=CARD, gridcolor=GRID, color=TEXT2),
            zaxis=dict(title="Net value (M COP / yr)", backgroundcolor=CARD, gridcolor=GRID, color=TEXT2),
            camera=dict(eye=dict(x=-1.55, y=-1.55, z=0.85))),
        margin=dict(l=0, r=0, t=80, b=0))
    fig.write_html(out / "01_best_card_surface_3d.html", include_plotlyjs="cdn")
    try:
        fig.write_image(out / "01_best_card_surface_3d.png", width=1300, height=780, scale=1.5)
    except Exception as e:
        print("png export skipped:", e)
    return fig


def chart_heatmap(out, cards, personas):
    names = display_names(cards)
    vals = np.column_stack([evaluate(cards, s, pairs=False)[0] for s in personas.values()]) / 1e6
    order = np.argsort(-vals[:, 1])
    v = vals[order]
    cmap = LinearSegmentedColormap.from_list("div", ["#e66767", "#3a3936", "#3987e5"])
    lim = np.abs(v).max()
    fig, ax = plt.subplots(figsize=(10.5, 11))
    ax.imshow(v, cmap=cmap, norm=TwoSlopeNorm(0, -lim, lim), aspect="auto")
    ax.grid(False)
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            ax.text(j, i, f"{v[i, j]:+.2f}", ha="center", va="center", fontsize=8.5,
                    color=TEXT if abs(v[i, j]) > lim * 0.35 else TEXT2)
    ax.set_xticks(range(len(personas)))
    ax.set_xticklabels([f"{p}\n{sum(s)/1e6:.1f}M / month" for p, s in personas.items()], fontsize=9)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([names[k] for k in order], fontsize=9)
    ax.set_title("Net annual value of each card, M COP (rewards minus cuota de manejo after waivers)\n"
                 "Sorted by the young-professional column. Default point values.", loc="left", color=TEXT, fontsize=11, pad=48)
    fig.tight_layout()
    fig.savefig(out / "02_cards_by_profile.png", dpi=150)
    plt.close(fig)


def chart_banks(out, cards, base_mix):
    spend = np.linspace(300_000, 15_000_000, 250)
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.2), sharey=True)
    for ax, pv, title in [(axes[0], 30.0, "Puntos BBVA at 30 COP (BBVA's published value)"),
                          (axes[1], 10.0, "Puntos BBVA at 10 COP (conservative)")]:
        single = evaluate(cards, spend[:, None] * base_mix[None], {"puntos_bbva": pv}, pairs=False) / 1e6
        for bank, col in BANK_COLORS.items():
            ks = np.flatnonzero(cards.bank == bank)
            best = single[:, ks].max(1)
            which = cards.name.to_numpy()[ks][single[:, ks].argmax(1)]
            ax.plot(spend / 1e6, best, color=col, lw=2.4 if bank in ("BBVA", "DAVIbank") else 1.6,
                    label=f"{bank} (best: {pd.Series(which).mode()[0]})")
        ax.axhline(0, color=TEXT2, lw=0.8)
        ax.set_title(title, loc="left", color=TEXT, fontsize=11)
        ax.set_xlabel("Total monthly card spend (M COP), young-professional mix")
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    axes[0].set_ylabel("Net annual value of the bank's best card (M COP)")
    fig.suptitle("Best card of each bank as spend grows. The fee-free BBVA and fee-waivable DAVIbank cards lead at every level",
                 x=0.01, ha="left", color=TEXT, fontsize=12)
    fig.tight_layout()
    fig.savefig(out / "03_best_card_per_bank.png", dpi=150)
    plt.close(fig)


def chart_monte_carlo(out, cards, sims):
    names = dict(zip(cards.id, display_names(cards)))
    colors = dict(zip(cards.id, card_colors(cards)))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15.5, 5.8))
    bins = np.arange(10, 30.01, 1)
    b = pd.cut(sims.puntos_bbva, bins)
    share = pd.crosstab(b, sims.winner, normalize="index")
    mids = (bins[:-1] + bins[1:]) / 2
    bottom = np.zeros(len(share))
    for cid in [c for c in cards.id if c in share.columns]:
        a1.bar(mids, share[cid], bottom=bottom, width=0.92, color=colors[cid], label=names[cid], edgecolor=BG, lw=1)
        bottom += share[cid].to_numpy()
    a1.set_xlabel("Value of one Puntos BBVA point in the simulation (COP)")
    a1.set_ylabel("Share of households where the card wins")
    a1.set_title("Who wins depends on one number: what a Puntos BBVA point is worth", loc="left", color=TEXT, fontsize=11)
    a1.legend(frameon=False, fontsize=8.5, loc="lower right")
    a1.set_ylim(0, 1)
    a1.grid(axis="x", visible=False)
    a1.set_axisbelow(True)
    gain = (sims.best_pair - sims.best_single)
    pos = gain[gain > 1] / 1e3
    a2.hist(pos.clip(upper=pos.quantile(0.99)), bins=50, color="#9085e9", edgecolor=BG, lw=0.6)
    a2.set_xlabel("Extra value from adding a second card (thousand COP per year), households where it helps")
    a2.set_ylabel("Households")
    a2.set_title(f"A second card helps in only {len(pos)/len(sims):.0%} of households", loc="left", color=TEXT, fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "04_monte_carlo.png", dpi=150)
    plt.close(fig)


def dashboard(out, cards, personas, metrics, fig3d):
    card_js = cards.assign(short=display_names(cards), color=card_colors(cards)).to_dict(orient="records")
    mc = metrics["monte_carlo"]
    prog_labels = {"puntos_colombia": "Puntos Colombia (Bancolombia)", "puntos_bbva": "Puntos BBVA",
                   "davipuntos": "Davipuntos (Davivienda)", "one_rewards": "One Rewards (DAVIbank)",
                   "cmr_puntos": "CMR Puntos (Falabella)"}
    val_inputs = "".join(f'<label>{prog_labels[p]} (COP)<input id="v_{p}" type="number" step="0.5" value="{DEFAULT_VALUES[p]}"></label>'
                         for p in PROGRAMS)
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Credit Card Rewards Optimizer - my 24 Colombian cards</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root{{--bg:{BG};--card:{CARD};--text:{TEXT};--text2:{TEXT2};--muted:{MUTED};--grid:{GRID}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font:14px/1.5 Inter,system-ui,Arial,sans-serif}}
.wrap{{max-width:1360px;margin:0 auto;padding:28px 22px 60px}}h1{{font-size:26px;margin:0 0 4px}}
.sub{{color:var(--text2);margin:0 0 22px}}.grid{{display:grid;gap:16px}}.g2{{grid-template-columns:370px 1fr}}
.g4{{grid-template-columns:repeat(4,1fr)}}.panel{{background:var(--card);border:1px solid var(--grid);border-radius:12px;padding:16px}}
h2{{font-size:15px;margin:0 0 10px}}label{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:5px 0;color:var(--text2)}}
input[type=number]{{width:120px;background:var(--bg);color:var(--text);border:1px solid var(--grid);border-radius:6px;padding:5px 8px;text-align:right;font:inherit}}
.tile .v{{font-size:22px;font-weight:600}}.tile .l{{color:var(--muted);font-size:12px}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:5px 6px;border-bottom:1px solid var(--grid);text-align:left}}th{{color:var(--muted);font-weight:500}}
.dot{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
.note{{color:var(--muted);font-size:12px}}button{{background:var(--bg);color:var(--text2);border:1px solid var(--grid);border-radius:6px;padding:5px 9px;margin:2px 4px 2px 0;cursor:pointer;font:inherit;font-size:12px}}
button:hover{{color:var(--text);border-color:var(--muted)}}details{{margin-top:10px}}summary{{cursor:pointer;color:var(--text)}}
.cards label{{justify-content:flex-start;margin:2px 0;font-size:12.5px}}.bank{{margin-top:6px;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}}
@media(max-width:900px){{.g2,.g4{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>Credit Card Rewards Optimizer</h1>
<p class="sub">The 24 credit cards in my bank spreadsheets (Bancolombia, BBVA, DAVIbank, Davivienda, Banco Falabella, Nu), valued in pesos: points times what a point is worth, minus the cuota de manejo after waivers. Conditions published November 2026.</p>
<div class="grid g2">
<div class="panel"><h2>Monthly spend (COP)</h2><div id="presets"></div><div id="inputs"></div>
<label>Average purchase (COP)<input id="v_avg_ticket" type="number" step="5000" value="{DEFAULT_VALUES['avg_ticket']}"></label>
<details open><summary>What a point is worth</summary>{val_inputs}
<label>TRM (COP per USD)<input id="v_trm" type="number" step="10" value="{DEFAULT_VALUES['trm']}"></label></details>
<details><summary>Cards to consider</summary><div class="cards" id="cardlist"></div>
<button id="all">All</button><button id="none">None</button></details>
<p class="note">Point values are what a point buys when redeemed, not cash. BBVA only publishes 30 COP in its business loyalty rules; try lower values.</p>
</div>
<div class="grid" style="gap:16px;align-content:start">
<div class="grid g4">
<div class="panel tile"><div class="l">Best single card</div><div class="v" id="t1">-</div></div>
<div class="panel tile"><div class="l">Its net value per year</div><div class="v" id="t2">-</div></div>
<div class="panel tile"><div class="l">Best two-card wallet</div><div class="v" id="t3" style="font-size:16px">-</div></div>
<div class="panel tile"><div class="l">Extra from the second card</div><div class="v" id="t4">-</div></div>
</div>
<div class="panel"><div id="rank" style="height:620px"></div></div>
</div></div>
<div class="grid" style="grid-template-columns:1fr 1fr;margin-top:16px">
<div class="panel"><h2>Where each peso goes in the best wallet</h2><table id="route"></table></div>
<div class="panel"><div id="curve" style="height:420px"></div></div></div>
<div class="panel" style="margin-top:16px"><div id="surf" style="height:720px"></div></div>
<div class="grid g4" style="margin-top:16px">
<div class="panel tile"><div class="l">Simulated households</div><div class="v">{mc['n']:,}</div></div>
<div class="panel tile"><div class="l">BBVA wins when a point is worth 25-30 COP</div><div class="v">{mc['bbva_win_share_by_point_value']['(25, 30]']*100:.0f}%</div></div>
<div class="panel tile"><div class="l">...and when it is worth 10-15 COP</div><div class="v">{mc['bbva_win_share_by_point_value']['(10, 15]']*100:.0f}%</div></div>
<div class="panel tile"><div class="l">A second card adds value</div><div class="v">{mc['share_where_second_card_adds_value']*100:.0f}%</div></div>
</div>
<p class="note" style="margin-top:18px">Not modeled: income requirements and approval, introductory free months, welcome bonuses, promotions, interest (balance paid in full), and benefits such as VIP lounges and insurance. {metrics['cards_with_assumed_values']} of 24 cards have at least one assumed value, flagged in data/cards.csv. Numbers from outputs/metrics.json.</p>
</div>
<script>
const CARDS={json.dumps(card_js)};const CATS={json.dumps(CATEGORIES)};const LABELS={json.dumps(LABELS)};
const PERSONAS={json.dumps(personas)};const PROGRAMS={json.dumps(PROGRAMS)};
const BG="{BG}",TEXT="{TEXT}",TEXT2="{TEXT2}",GRID="{GRID}",BANKC={json.dumps(BANK_COLORS)};
const fmt=x=>(x<0?"-":"")+"$"+Math.abs(Math.round(x)).toLocaleString("en-US");
const $=id=>document.getElementById(id);
CATS.forEach((c,i)=>$("inputs").insertAdjacentHTML("beforeend",`<label>${{LABELS[c]}}<input id="c_${{c}}" type="number" step="50000" value="${{PERSONAS["Young professional"][i]}}"></label>`));
Object.keys(PERSONAS).forEach(p=>{{const b=document.createElement("button");b.textContent=p;b.onclick=()=>{{CATS.forEach((c,i)=>$("c_"+c).value=PERSONAS[p][i]);run()}};$("presets").appendChild(b)}});
let lastBank="";CARDS.forEach((c,k)=>{{if(c.bank!=lastBank){{$("cardlist").insertAdjacentHTML("beforeend",`<div class="bank">${{c.bank}}</div>`);lastBank=c.bank}}
 $("cardlist").insertAdjacentHTML("beforeend",`<label><input type="checkbox" id="k_${{k}}" checked> <span class="dot" style="background:${{c.color}}"></span>${{c.name}}</label>`)}});
$("all").onclick=()=>{{CARDS.forEach((c,k)=>$("k_"+k).checked=true);run()}};$("none").onclick=()=>{{CARDS.forEach((c,k)=>$("k_"+k).checked=false);run()}};
function vals(){{const v={{trm:+$("v_trm").value,avg_ticket:+$("v_avg_ticket").value}};PROGRAMS.forEach(p=>v[p]=+$("v_"+p).value);return v}}
function rates(cd,v){{const pp=cd.program=="none"?0:v[cd.program];const sc=cd.unit=="per_usd"?1/v.trm:1/1000;return CATS.map(c=>cd[c]*sc*pp)}}
function fee(cd,m,v){{let f=cd.fee_month_cop;if(cd.waiver=="purchases"&&m/v.avg_ticket>=cd.waiver_full)f=0;
 if(cd.waiver=="billing"){{if(m>=cd.waiver_full)f=0;else if(m>=cd.waiver_partial)f*=0.5}}return 12*f}}
function single(spend,v){{const tot=spend.reduce((a,b)=>a+b,0);return CARDS.map(cd=>{{const r=rates(cd,v);return 12*spend.reduce((s,x,i)=>s+x*r[i],0)-fee(cd,tot,v)}})}}
function pair(spend,v,on){{const s=single(spend,v);let best=null;on.forEach(i=>{{if(!best||s[i]>best.val)best={{val:s[i],i,j:i,route:spend.map(()=>i)}}}});
 const tot=spend.reduce((a,b)=>a+b,0);
 for(let a=0;a<on.length;a++)for(let b=a+1;b<on.length;b++){{const i=on[a],j=on[b],ri=rates(CARDS[i],v),rj=rates(CARDS[j],v);let val=0,si=0;const route=[];
  spend.forEach((x,k)=>{{if(ri[k]>=rj[k]){{val+=12*x*ri[k];si+=x;route.push(i)}}else{{val+=12*x*rj[k];route.push(j)}}}});
  const sj=tot-si;if(si>0)val-=fee(CARDS[i],si,v);if(sj>0)val-=fee(CARDS[j],sj,v);
  if(val>best.val+1e-6)best={{val,i,j,route}}}}return best}}
const L={{paper_bgcolor:"rgba(0,0,0,0)",plot_bgcolor:"rgba(0,0,0,0)",font:{{color:TEXT2,family:"Inter,Arial"}}}};
function run(){{const spend=CATS.map(c=>+$("c_"+c).value||0),v=vals();const on=CARDS.map((c,k)=>k).filter(k=>$("k_"+k).checked);
 if(!on.length){{["t1","t2","t3","t4"].forEach(t=>$(t).textContent="-");return}}
 const s=single(spend,v),ord=on.slice().sort((a,b)=>s[a]-s[b]||b-a),best=ord[ord.length-1],p=pair(spend,v,on);
 $("t1").textContent=CARDS[best].short;$("t2").textContent=fmt(s[best]);
 $("t3").textContent=p.i==p.j?CARDS[p.i].short+" alone":CARDS[p.i].short+" + "+CARDS[p.j].short;$("t4").textContent=fmt(p.val-s[best]);
 const mx=Math.max(0,...ord.map(k=>s[k])),mn=Math.min(0,...ord.map(k=>s[k])),span=Math.max(mx-mn,1);
 Plotly.react("rank",[{{type:"bar",orientation:"h",y:ord.map(k=>CARDS[k].short),x:ord.map(k=>s[k]),marker:{{color:ord.map(k=>CARDS[k].color)}},
  text:ord.map(k=>fmt(s[k])),textposition:"outside",cliponaxis:false,hovertemplate:"%{{y}}: %{{x:$,.0f}} COP/yr<extra></extra>"}}],
  {{...L,margin:{{l:210,r:30,t:40,b:40}},title:{{text:"Net annual value by card (COP)",font:{{color:TEXT,size:14}}}},
  xaxis:{{gridcolor:GRID,zerolinecolor:TEXT2,tickformat:"$,.2s",range:[mn-(mn<0?0.25:0.02)*span,mx+0.22*span]}},yaxis:{{gridcolor:"rgba(0,0,0,0)",tickfont:{{size:11}}}}}},{{displayModeBar:false,responsive:true}});
 let rows="<tr><th>Category</th><th>Monthly</th><th>Card</th><th>Return</th></tr>";
 CATS.forEach((c,k)=>{{if(!spend[k])return;const cd=CARDS[p.route[k]],rr=rates(cd,v)[k];rows+=`<tr><td>${{LABELS[c]}}</td><td>${{fmt(spend[k])}}</td><td><span class="dot" style="background:${{cd.color}}"></span>${{cd.short}}</td><td>${{(rr*100).toFixed(2)}}%</td></tr>`}});
 $("route").innerHTML=rows;
 const tot=spend.reduce((a,b)=>a+b,0)||1,mix=spend.map(x=>x/tot),xs=[];for(let k=0;k<=70;k++)xs.push(3e5*Math.pow(80,k/70));
 const banks=[...new Set(on.map(k=>CARDS[k].bank))];
 const vs=xs.map(x=>single(mix.map(m=>m*x),v));
 const traces=banks.map(b=>{{const ks=on.filter(k=>CARDS[k].bank==b);return{{x:xs.map(x=>x/1e6),y:vs.map(r=>Math.max(...ks.map(k=>r[k]))),name:b,mode:"lines",
  line:{{color:BANKC[b],width:b==CARDS[best].bank?3:1.6}},hovertemplate:b+": %{{y:$,.0f}}<extra></extra>"}}}});
 traces.push({{x:[tot/1e6],y:[s[best]],mode:"markers",name:"You",marker:{{size:12,color:TEXT,line:{{color:BG,width:2}}}},hovertemplate:"You: %{{y:$,.0f}}<extra></extra>"}});
 Plotly.react("curve",traces,{{...L,margin:{{l:70,r:20,t:50,b:60}},title:{{text:"Best card of each bank as your spend grows (your mix)",font:{{color:TEXT,size:14}}}},
  xaxis:{{type:"log",title:"Monthly card spend (M COP)",gridcolor:GRID,tickvals:[0.3,0.5,1,2,5,10,20],ticktext:["0.3","0.5","1","2","5","10","20"]}},
  yaxis:{{title:"COP per year",gridcolor:GRID,zerolinecolor:TEXT2,tickformat:"$,.2s"}},hovermode:"x unified",legend:{{orientation:"h",y:-0.25}}}},{{displayModeBar:false,responsive:true}})}}
document.querySelectorAll("input").forEach(e=>e.addEventListener("input",run));run();
const SURF={fig3d.to_json()};SURF.layout.paper_bgcolor="rgba(0,0,0,0)";Plotly.newPlot("surf",SURF.data,SURF.layout,{{responsive:true}});
</script></body></html>"""
    (out.parent / "dashboard.html").write_text(html, encoding="utf-8")


def make_all(out, cards, personas, base_mix, metrics, sims):
    fig3d = chart_3d(out, cards, base_mix)
    chart_heatmap(out, cards, personas)
    chart_banks(out, cards, base_mix)
    chart_monte_carlo(out, cards, sims)
    dashboard(out, cards, personas, metrics, fig3d)
