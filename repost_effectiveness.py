#!/usr/bin/env python3
"""
Оцінка ефективності інфлюенсерів за репостами ($125 за пост).
Завантажує метрики твітів через TwitterAPI.io, рахує показники, виводить CSV + HTML.
"""

import os
import re
from decimal import Decimal

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("TWITTERAPI_IO_API_KEY") or os.environ.get("TWITTERAPI_IO_KEY")
BASE = "https://api.twitterapi.io"
COST_PER_POST = 125  # USD

# Репости для оцінки (URL або твіти з однаковою вартістю)
TWEET_URLS = [
    "https://x.com/_thespacebyte/status/2026201518702014668",
    "https://x.com/al_thedefimaxi/status/2026020481678155826",
    "https://x.com/CRYPTOKRALI3/status/2026018373209932135",
    "https://x.com/defi_tycoon/status/2026005423925432819",
    "https://x.com/Diamondweb_3/status/2026300978580861140",
    "https://x.com/Eliteonchain/status/2026312171022336050",
    "https://x.com/Ellaweb_3/status/2026279037375496334",
    "https://x.com/haloETH/status/2026276326504800526",
    "https://x.com/helgaweb_3/status/2026019623175348485",
    "https://x.com/kingfxyo/status/2026325878486057091",
    "https://x.com/LucasWeb3_/status/2026030394429055052",
    "https://x.com/Mekarly/status/2026020638352191738",
    "https://x.com/moha_web3/status/2026279186856378493",
    "https://x.com/MookieNFT/status/2026242303606579567",
    "https://x.com/NickAlphas/status/2026025208415453415",
    "https://x.com/raintures/status/2026008894653239385",
    "https://x.com/Redlion35/status/2026279188651549173",
    "https://x.com/worldoffisher/status/2026023156356465057",
    "https://x.com/worldofmercek/status/2026002379800236096",
]


def tweet_id_from_url(url: str) -> str:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else ""


def fetch_tweets_by_ids(api_key: str, tweet_ids: list[str]) -> list[dict]:
    """GET /twitter/tweets?tweet_ids=id1,id2,..."""
    if not tweet_ids:
        return []
    headers = {"X-API-Key": api_key}
    url = f"{BASE}/twitter/tweets"
    params = {"tweet_ids": ",".join(tweet_ids)}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("tweets") or []


def format_num(n) -> str:
    try:
        x = int(n)
        if x >= 1_000_000:
            return f"{x/1_000_000:.1f}M"
        if x >= 1_000:
            return f"{x/1_000:.1f}K"
        return str(x)
    except (TypeError, ValueError):
        return str(n or "0")


def main():
    if not API_KEY:
        raise SystemExit("Set TWITTERAPI_IO_API_KEY in .env")
    ids = [tweet_id_from_url(u) for u in TWEET_URLS]
    ids = [i for i in ids if i]
    if not ids:
        raise SystemExit("No valid tweet IDs")
    print(f"Fetching {len(ids)} tweets...")
    tweets = fetch_tweets_by_ids(API_KEY, ids)
    if not tweets:
        raise SystemExit("No tweets returned (check API key / IDs)")
    rows = []
    for t in tweets:
        author = t.get("author") or {}
        followers = int(author.get("followers") or 0)
        views = int(t.get("viewCount") or 0)
        likes = int(t.get("likeCount") or 0)
        retweets = int(t.get("retweetCount") or 0)
        replies = int(t.get("replyCount") or 0)
        quotes = int(t.get("quoteCount") or 0)
        bookmarks = int(t.get("bookmarkCount") or 0)
        engagement = likes + retweets + replies
        # Показники ефективності
        er_views = (engagement / views * 100) if views else 0
        cost_per_1k_views = (COST_PER_POST / (views / 1000)) if views else None
        cost_per_engagement = (COST_PER_POST / engagement) if engagement else None
        reach_pct = (views / followers * 100) if followers else 0  # % аудиторії що побачила
        # Простий score: нижчий cost per 1k views = краще; вищий engagement rate = краще
        score = 0
        if cost_per_1k_views is not None and cost_per_1k_views > 0:
            score += 50 / min(cost_per_1k_views, 50)  # до 50 балів за дешевий CPM
        if er_views > 0:
            score += min(er_views * 2, 50)  # до 50 за ER
        rows.append({
            "username": author.get("userName") or "",
            "name": author.get("name") or "",
            "tweet_url": t.get("url") or "",
            "followers": followers,
            "views": views,
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
            "quotes": quotes,
            "bookmarks": bookmarks,
            "engagement": engagement,
            "engagement_rate_pct": round(er_views, 2),
            "reach_pct": round(reach_pct, 1),
            "cost_per_1k_views": round(cost_per_1k_views, 2) if cost_per_1k_views is not None else None,
            "cost_per_engagement": round(cost_per_engagement, 2) if cost_per_engagement is not None else None,
            "effectiveness_score": round(score, 1),
        })
    rows.sort(key=lambda x: (-(x["effectiveness_score"]), -x["views"]))
    # CSV
    import csv
    out_csv = "repost_effectiveness.csv"
    fieldnames = [
        "username", "name", "tweet_url", "followers", "views", "likes", "retweets", "replies",
        "quotes", "bookmarks", "engagement", "engagement_rate_pct", "reach_pct",
        "cost_per_1k_views", "cost_per_engagement", "effectiveness_score",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"Wrote {out_csv}")
    # HTML
    out_html = "repost_effectiveness.html"
    trs = []
    for i, r in enumerate(rows, 1):
        cpm = r["cost_per_1k_views"]
        cpe = r["cost_per_engagement"]
        trs.append(f"""
        <tr>
          <td>{i}</td>
          <td><a href="{r['tweet_url']}" target="_blank" rel="noopener">@{r['username']}</a></td>
          <td>{format_num(r['followers'])}</td>
          <td>{format_num(r['views'])}</td>
          <td>{r['likes']}</td>
          <td>{r['retweets']}</td>
          <td>{r['replies']}</td>
          <td>{r['engagement']}</td>
          <td>{r['engagement_rate_pct']}%</td>
          <td>{r['reach_pct']}%</td>
          <td>${cpm if cpm is not None else '—'}</td>
          <td>${cpe if cpe is not None else '—'}</td>
          <td><strong>{r['effectiveness_score']}</strong></td>
        </tr>""")
    table_body = "\n".join(trs)
    formulas_html = f"""
    <section class="formulas">
      <h2>Formulas</h2>
      <table class="formula-table">
        <thead><tr><th>Metric</th><th>Formula</th></tr></thead>
        <tbody>
          <tr><td>Engagement</td><td><code>Likes + Retweets + Replies</code></td></tr>
          <tr><td>Engagement rate %</td><td><code>(Engagement ÷ Views) × 100</code></td></tr>
          <tr><td>Reach %</td><td><code>(Views ÷ Followers) × 100</code></td></tr>
          <tr><td>$ / 1K views</td><td><code>{COST_PER_POST} ÷ (Views ÷ 1000)</code></td></tr>
          <tr><td>$ / engagement</td><td><code>{COST_PER_POST} ÷ Engagement</code></td></tr>
          <tr><td>Effectiveness score</td><td><code>50 ÷ min(Cost per 1K views, 50) + min(Engagement rate % × 2, 50)</code> <span class="formula-note">(lower cost & higher ER = higher score)</span></td></tr>
        </tbody>
      </table>
    </section>
"""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <title>Repost effectiveness · ${COST_PER_POST}/post</title>
  <style>
    :root {{ --bg:#0d0d0f; --surface:#16161a; --text:#e4e4e7; --text2:#a1a1aa; --link:#3b82f6; --border:#27272a; }}
    body {{ margin:0; padding:1.5rem; background:var(--bg); color:var(--text); font-family: system-ui, sans-serif; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .subtitle {{ color: var(--text2); margin-bottom: 1rem; }}
    .formulas {{ margin-bottom: 1.5rem; }}
    .formulas h2 {{ font-size: 1rem; margin-bottom: 0.5rem; color: var(--text2); }}
    .formula-table {{ width: auto; min-width: 400px; font-size: 0.9rem; }}
    .formula-table td:first-child {{ font-weight: 500; padding-right: 1rem; }}
    .formula-table code {{ background: var(--bg); padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.85em; }}
    .formula-note {{ color: var(--text2); font-size: 0.8em; font-weight: normal; }}
    table {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 0.6rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: var(--border); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }}
    tr:hover {{ background: rgba(255,255,255,0.03); }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .metrics {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; font-size: 0.9rem; color: var(--text2); }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Repost effectiveness</h1>
    <p class="subtitle">${COST_PER_POST} per post · who to hire next (by views, engagement, cost efficiency)</p>
    {formulas_html}
    <div class="metrics">
      <span>Cost per post: <strong>${COST_PER_POST}</strong></span>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Influencer</th>
          <th>Followers</th>
          <th>Views</th>
          <th>Likes</th>
          <th>RT</th>
          <th>Replies</th>
          <th>Engagement</th>
          <th>ER %</th>
          <th>Reach %</th>
          <th>$ / 1K views</th>
          <th>$ / eng.</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {table_body}
      </tbody>
    </table>
  </div>
</body>
</html>"""
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {out_html}")

    # Interactive HTML: total budget or per-influencer cost, recalc on input
    trs_interactive = []
    for i, r in enumerate(rows):
        trs_interactive.append(f"""
        <tr data-views="{r['views']}" data-engagement="{r['engagement']}" data-er="{r['engagement_rate_pct']}" data-reach="{r['reach_pct']}">
          <td>{i + 1}</td>
          <td><a href="{r['tweet_url']}" target="_blank" rel="noopener">@{r['username']}</a></td>
          <td>{format_num(r['followers'])}</td>
          <td>{format_num(r['views'])}</td>
          <td>{r['likes']}</td>
          <td>{r['retweets']}</td>
          <td>{r['replies']}</td>
          <td>{r['engagement']}</td>
          <td>{r['engagement_rate_pct']}%</td>
          <td>{r['reach_pct']}%</td>
          <td class="cost-cell"><input type="number" min="0" step="1" value="{COST_PER_POST}" class="cost-input" data-row="{i}"></td>
          <td class="cpm-cell">—</td>
          <td class="cpe-cell">—</td>
          <td class="score-cell"><strong>—</strong></td>
        </tr>""")
    table_body_interactive = "\n".join(trs_interactive)
    out_html_interactive = "repost_effectiveness_interactive.html"
    html_interactive = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <title>Repost effectiveness · Calculator</title>
  <style>
    :root {{ --bg:#0d0d0f; --surface:#16161a; --text:#e4e4e7; --text2:#a1a1aa; --link:#3b82f6; --border:#27272a; }}
    body {{ margin:0; padding:1.5rem; background:var(--bg); color:var(--text); font-family: system-ui, sans-serif; }}
    .container {{ max-width: 1200px; margin: 0 auto; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .subtitle {{ color: var(--text2); margin-bottom: 1rem; }}
    .controls {{ display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; margin-bottom: 1rem; padding: 1rem; background: var(--surface); border-radius: 8px; }}
    .controls label {{ display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }}
    .controls input[type="radio"] {{ accent-color: var(--link); }}
    .total-input-wrap {{ display: flex; align-items: center; gap: 0.5rem; }}
    .total-input-wrap input {{ width: 100px; padding: 0.4rem; background: var(--bg); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 1rem; }}
    .cost-cell .cost-input {{ width: 70px; padding: 0.3rem; background: var(--bg); border: 1px solid var(--border); border-radius: 4px; color: var(--text); }}
    table {{ width: 100%; border-collapse: collapse; background: var(--surface); border-radius: 12px; overflow: hidden; }}
    th, td {{ padding: 0.6rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }}
    th {{ background: var(--border); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }}
    tr:hover {{ background: rgba(255,255,255,0.03); }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .cost-cell.total-mode input {{ pointer-events: none; opacity: 0.8; }}
    .formulas {{ margin-bottom: 1.5rem; }}
    .formulas h2 {{ font-size: 1rem; margin-bottom: 0.5rem; color: var(--text2); }}
    .formula-table {{ width: auto; min-width: 400px; font-size: 0.9rem; }}
    .formula-table td:first-child {{ font-weight: 500; padding-right: 1rem; }}
    .formula-table code {{ background: var(--bg); padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.85em; }}
    .formula-note {{ color: var(--text2); font-size: 0.8em; font-weight: normal; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Repost effectiveness · Calculator</h1>
    <p class="subtitle">Enter total budget or cost per influencer — metrics recalc automatically.</p>
    <section class="formulas">
      <h2>Formulas</h2>
      <table class="formula-table">
        <thead><tr><th>Metric</th><th>Formula</th></tr></thead>
        <tbody>
          <tr><td>Engagement</td><td><code>Likes + Retweets + Replies</code></td></tr>
          <tr><td>Engagement rate %</td><td><code>(Engagement ÷ Views) × 100</code></td></tr>
          <tr><td>Reach %</td><td><code>(Views ÷ Followers) × 100</code></td></tr>
          <tr><td>$ / 1K views</td><td><code>Cost ÷ (Views ÷ 1000)</code></td></tr>
          <tr><td>$ / engagement</td><td><code>Cost ÷ Engagement</code></td></tr>
          <tr><td>Effectiveness score</td><td><code>50 ÷ min(Cost per 1K views, 50) + min(Engagement rate % × 2, 50)</code> <span class="formula-note">(lower cost & higher ER = higher score)</span></td></tr>
        </tbody>
      </table>
    </section>
    <div class="controls">
      <label><input type="radio" name="mode" value="total" id="mode-total"> Total budget (split equally among all)</label>
      <label><input type="radio" name="mode" value="per" id="mode-per" checked> Per influencer</label>
      <span class="total-input-wrap" id="total-wrap" style="display:none;">
        <label for="total-budget">Total $</label>
        <input type="number" id="total-budget" min="0" step="1" value="{COST_PER_POST * len(rows)}" placeholder="Total">
      </span>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Influencer</th>
          <th>Followers</th>
          <th>Views</th>
          <th>Likes</th>
          <th>RT</th>
          <th>Replies</th>
          <th>Engagement</th>
          <th>ER %</th>
          <th>Reach %</th>
          <th>Cost $</th>
          <th>$ / 1K views</th>
          <th>$ / eng.</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody id="tbody">
        {table_body_interactive}
      </tbody>
    </table>
  </div>
  <script>
    const N = {len(rows)};
    const defaultCost = {COST_PER_POST};
    const totalInput = document.getElementById('total-budget');
    const totalWrap = document.getElementById('total-wrap');
    const tbody = document.getElementById('tbody');
    const modeTotal = document.getElementById('mode-total');
    const modePer = document.getElementById('mode-per');
    const costInputs = tbody.querySelectorAll('.cost-input');

    function recalcRow(tr, cost) {{
      const views = +tr.dataset.views;
      const engagement = +tr.dataset.engagement;
      const er = +tr.dataset.er;
      cost = +cost || 0;
      let cpm = null, cpe = null, score = 0;
      if (views > 0 && cost > 0) cpm = cost / (views / 1000);
      if (engagement > 0 && cost > 0) cpe = cost / engagement;
      if (cpm != null && cpm > 0) score += 50 / Math.min(cpm, 50);
      if (er > 0) score += Math.min(er * 2, 50);
      tr.querySelector('.cpm-cell').textContent = cpm != null ? '$' + cpm.toFixed(2) : '—';
      tr.querySelector('.cpe-cell').textContent = cpe != null ? '$' + cpe.toFixed(2) : '—';
      tr.querySelector('.score-cell strong').textContent = score.toFixed(1);
    }}

    function applyTotal() {{
      const total = +totalInput.value || 0;
      const each = N ? (total / N) : 0;
      tbody.querySelectorAll('tr').forEach((tr, i) => {{
        const inp = tr.querySelector('.cost-input');
        inp.value = Math.round(each * 100) / 100;
        recalcRow(tr, each);
      }});
    }}

    function setupPerMode() {{
      tbody.querySelectorAll('tr').forEach(tr => {{
        const inp = tr.querySelector('.cost-input');
        inp.disabled = false;
        inp.style.pointerEvents = '';
        recalcRow(tr, inp.value);
      }});
    }}

    modeTotal.addEventListener('change', function() {{
      totalWrap.style.display = this.checked ? 'flex' : 'none';
      tbody.classList.add('total-mode');
      tbody.querySelectorAll('.cost-cell').forEach(c => c.classList.add('total-mode'));
      if (this.checked) {{ totalInput.value = Array.from(costInputs).reduce((s, i) => s + (+i.value || 0), 0); applyTotal(); }}
    }});
    modePer.addEventListener('change', function() {{
      totalWrap.style.display = 'none';
      tbody.classList.remove('total-mode');
      tbody.querySelectorAll('.cost-cell').forEach(c => c.classList.remove('total-mode'));
      if (this.checked) setupPerMode();
    }});
    totalInput.addEventListener('input', applyTotal);
    totalInput.addEventListener('change', applyTotal);
    costInputs.forEach(inp => {{
      inp.addEventListener('input', function() {{ recalcRow(this.closest('tr'), this.value); }});
      inp.addEventListener('change', function() {{ recalcRow(this.closest('tr'), this.value); }});
    }});
    if (modePer.checked) setupPerMode();
    else {{ totalWrap.style.display = 'flex'; tbody.classList.add('total-mode'); tbody.querySelectorAll('.cost-cell').forEach(c => c.classList.add('total-mode')); applyTotal(); }}
  </script>
</body>
</html>"""
    with open(out_html_interactive, "w", encoding="utf-8") as f:
        f.write(html_interactive)
    print(f"Wrote {out_html_interactive}")

    print("\nTop by effectiveness score:")
    for r in rows[:5]:
        print(f"  @{r['username']}: score {r['effectiveness_score']}, views {format_num(r['views'])}, $/1K views ${r['cost_per_1k_views'] or '—'}")


if __name__ == "__main__":
    main()
