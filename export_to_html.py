#!/usr/bin/env python3
"""
Reads recommendations.csv and generates an HTML page with embedded tweets and extra influencer info.
"""

import csv
import html
import os
from datetime import datetime

CSV_PATH = "recommendations.csv"
OUT_HTML = "recommendations.html"


def escape(s: str) -> str:
    return html.escape(s) if s else ""


def format_num(n: str | int) -> str:
    try:
        x = int(n)
        if x >= 1_000_000:
            return f"{x / 1_000_000:.1f}M"
        if x >= 1_000:
            return f"{x / 1_000:.1f}K"
        return str(x)
    except (ValueError, TypeError):
        return str(n)


def format_joined(created_at: str) -> str:
    """Format Twitter created_at (ISO) to 'Joined Mon YYYY' or empty."""
    if not created_at or not created_at.strip():
        return ""
    try:
        # API returns "2013-12-14T00:00:00.000Z"
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("Joined %b %Y")
    except Exception:
        return ""


def format_ratio(followers, following) -> str:
    try:
        g = int(following) if following not in (None, "") else 0
    except (ValueError, TypeError):
        g = 0
    if not g or g <= 0:
        return "—"
    try:
        f = int(followers) if followers not in (None, "") else 0
        ratio = f / g
        if ratio >= 10:
            return f"{ratio:.0f}x"
        if ratio >= 1:
            return f"{ratio:.1f}x"
        return f"1:{1/ratio:.0f}" if ratio > 0 else "—"
    except (ValueError, TypeError):
        return "—"


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, CSV_PATH)
    out_path = os.path.join(script_dir, OUT_HTML)

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            rows.append(row)

    has_tweet_urls = "tweet_url_1" in fieldnames
    has_created_at = "created_at" in fieldnames
    has_listed = "listed_count" in fieldnames

    order = {"Strong hire": 0, "Consider": 1, "Skip": 2}
    def key(r):
        rec = r.get("recommendation") or "Skip"
        try:
            er = float(r.get("engagement_rate") or 0)
        except ValueError:
            er = 0
        return (order.get(rec, 2), -er)
    rows.sort(key=key)

    cards_html = []
    for r in rows:
        rec = r.get("recommendation") or "Skip"
        rec_class = rec.lower().replace(" ", "-")
        username = r.get("username") or ""
        name = escape(r.get("name") or "")
        profile_url = r.get("profile_url") or f"https://x.com/{username}"
        followers = format_num(r.get("followers_count") or 0)
        following_raw = r.get("following_count") or 0
        try:
            followers_int = int(r.get("followers_count") or 0)
            following_int = int(following_raw or 0)
        except (ValueError, TypeError):
            followers_int, following_int = 0, 0
        engagement = r.get("total_engagement") or "0"
        er = r.get("engagement_rate") or "0"
        try:
            er_pct = f"{float(er) * 100:.2f}%"
        except ValueError:
            er_pct = "—"
        reason = escape(r.get("recommendation_reason") or "")
        joined = format_joined(r.get("created_at") or "") if has_created_at else ""
        listed = format_num(r.get("listed_count") or "") if has_listed and r.get("listed_count") else ""
        ratio = format_ratio(r.get("followers_count") or 0, r.get("following_count") or 0)
        tweets_found = r.get("tweets_found") or "0"
        total_likes = r.get("total_likes") or "0"
        total_retweets = r.get("total_retweets") or "0"
        total_replies = r.get("total_replies") or "0"

        # Extra info block (all in English)
        extra_parts = []
        if joined:
            extra_parts.append(f'<span title="Account creation date">{joined}</span>')
        if listed:
            extra_parts.append(f'<span title="List count (quality signal)">Listed {listed}</span>')
        if ratio and ratio != "—":
            extra_parts.append(f'<span title="Followers / Following">F/Following {ratio}</span>')
        extra_parts.append(f'<span title="Matching tweets in search">Matching tweets {tweets_found}</span>')
        extra_parts.append(f'<span title="Likes / RTs / Replies on those">♥ {total_likes} · RT {total_retweets} · ↩ {total_replies}</span>')
        extra_html = " · ".join(extra_parts)

        card = f'''
        <article class="card card-{rec_class}" data-recommendation="{escape(rec)}">
          <div class="card-header">
            <span class="badge badge-{rec_class}">{escape(rec)}</span>
            <a href="{escape(profile_url)}" target="_blank" rel="noopener" class="profile-link">@{escape(username)}</a>
            <span class="name">{name}</span>
          </div>
          <div class="card-metrics">
            <span title="Followers">Followers {followers}</span>
            <span title="Total engagements">Engagement {engagement}</span>
            <span title="Engagement rate">ER {er_pct}</span>
          </div>
          <div class="card-extra">{extra_html}</div>
          <p class="reason">{reason}</p>
          <div class="tweet-embeds">
'''
        for i in range(1, 4):
            url = r.get(f"tweet_url_{i}") if has_tweet_urls else ""
            if url and url.strip():
                # Official X embed: blockquote + link; widgets.js will render the tweet
                card += f'''
            <div class="tweet-embed-wrap">
              <blockquote class="twitter-tweet" data-dnt="true"><a href="{escape(url)}"></a></blockquote>
            </div>
'''
            else:
                text = (r.get(f"sample_tweet_{i}") or "").strip()
                if text:
                    card += f'''
            <div class="tweet-fallback">
              <p class="tweet-text">{escape(text[:500])}{"…" if len(text) > 500 else ""}</p>
            </div>
'''
        card += '''
          </div>
        </article>
'''
        cards_html.append(card)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Influencer recommendations · Euphoria / Polymarket 5 min</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #0d0d0f;
      --surface: #16161a;
      --surface2: #1c1c21;
      --text: #e4e4e7;
      --text2: #a1a1aa;
      --accent-strong: #22c55e;
      --accent-consider: #eab308;
      --accent-skip: #71717a;
      --border: #27272a;
      --link: #3b82f6;
      --link-hover: #60a5fa;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 1.5rem;
      background: var(--bg);
      color: var(--text);
      font-family: 'DM Sans', system-ui, sans-serif;
      font-size: 15px;
      line-height: 1.5;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}
    h1 {{ font-size: 1.75rem; font-weight: 700; margin-bottom: 0.25rem; }}
    .subtitle {{ color: var(--text2); margin-bottom: 1.5rem; }}
    .filters {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
    }}
    .filters button {{
      padding: 0.5rem 1rem;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text2);
      border-radius: 8px;
      cursor: pointer;
      font-family: inherit;
      font-size: 0.9rem;
    }}
    .filters button:hover {{ color: var(--text); background: var(--surface2); }}
    .filters button.active {{ color: var(--text); border-color: var(--accent-strong); background: var(--surface2); }}
    .filters button.active.consider {{ border-color: var(--accent-consider); }}
    .filters button.active.skip {{ border-color: var(--accent-skip); }}
    .grid {{ display: grid; gap: 1rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.25rem;
      transition: opacity 0.2s, transform 0.2s;
    }}
    .card:hover {{ border-color: #3f3f46; }}
    .card.card-strong-hire {{ border-left: 4px solid var(--accent-strong); }}
    .card.card-consider {{ border-left: 4px solid var(--accent-consider); }}
    .card.card-skip {{ border-left: 4px solid var(--accent-skip); opacity: 0.75; }}
    .card.hidden {{ display: none; }}
    .card-header {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 0.5rem;
    }}
    .badge {{
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.2rem 0.5rem;
      border-radius: 6px;
    }}
    .badge-strong-hire {{ background: rgba(34, 197, 94, 0.2); color: var(--accent-strong); }}
    .badge-consider {{ background: rgba(234, 179, 8, 0.2); color: var(--accent-consider); }}
    .badge-skip {{ background: rgba(113, 113, 122, 0.2); color: var(--accent-skip); }}
    .profile-link {{
      color: var(--link);
      text-decoration: none;
      font-weight: 600;
      font-family: 'JetBrains Mono', monospace;
    }}
    .profile-link:hover {{ color: var(--link-hover); text-decoration: underline; }}
    .name {{ color: var(--text2); font-size: 0.9rem; }}
    .card-metrics {{
      display: flex;
      gap: 1rem;
      margin-bottom: 0.35rem;
      font-size: 0.85rem;
      color: var(--text2);
    }}
    .card-extra {{
      font-size: 0.8rem;
      color: var(--text2);
      margin-bottom: 0.5rem;
      opacity: 0.9;
    }}
    .reason {{ margin: 0.5rem 0 0.75rem; font-size: 0.9rem; color: var(--text2); }}
    .tweet-embeds {{ margin-top: 0.75rem; }}
    .tweet-embed-wrap {{
      margin-bottom: 1rem;
      min-height: 120px;
    }}
    .tweet-embed-wrap .twitter-tweet {{ margin: 0 auto; }}
    .tweet-fallback {{
      margin-bottom: 0.75rem;
      padding: 0.6rem;
      background: var(--bg);
      border-radius: 8px;
      border: 1px solid var(--border);
    }}
    .tweet-fallback .tweet-text {{
      margin: 0;
      font-size: 0.9rem;
      color: var(--text2);
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .count {{ color: var(--text2); font-size: 0.9rem; margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Influencer recommendations</h1>
    <p class="subtitle">Euphoria.fi & Polymarket 5 min · embedded tweets & extra metrics to decide</p>
    <div class="filters">
      <button type="button" class="filter-btn active" data-filter="all">All</button>
      <button type="button" class="filter-btn" data-filter="Strong hire">Strong hire</button>
      <button type="button" class="filter-btn" data-filter="Consider">Consider</button>
      <button type="button" class="filter-btn" data-filter="Skip">Skip</button>
    </div>
    <p class="count">Total: {len(rows)}</p>
    <div class="grid">
      {"".join(cards_html)}
    </div>
  </div>
  <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>
  <script>
    document.querySelectorAll('.filter-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active', 'consider', 'skip'));
        btn.classList.add('active');
        if (btn.dataset.filter === 'Consider') btn.classList.add('consider');
        if (btn.dataset.filter === 'Skip') btn.classList.add('skip');
        const filter = btn.dataset.filter;
        document.querySelectorAll('.card').forEach(card => {{
          const rec = card.dataset.recommendation;
          card.classList.toggle('hidden', filter !== 'all' && rec !== filter);
        }});
      }});
    }});
  </script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Done: {OUT_HTML}")
    print(f"Open in browser: file://{out_path}")


if __name__ == "__main__":
    main()
