#!/usr/bin/env python3
"""
Reads recommendations.csv and generates an HTML page with embedded tweets and extra influencer info.
"""

import csv
import html
import os
import re
from datetime import datetime

CSV_PATH = "recommendations.csv"
OUT_HTML = "recommendations.html"


def escape(s: str) -> str:
    return html.escape(s) if s else ""


def linkify(text: str) -> str:
    """Make URLs in already-escaped text clickable."""
    if not text:
        return ""
    # Match http(s) URLs, avoid double-linking
    return re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noopener" class="tweet-link">\1</a>',
        text,
    )


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
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("Joined %b %Y")
    except Exception:
        return ""


def format_tweet_date(created_at: str) -> str:
    """Format tweet created_at (ISO) to 'Mon DD, YYYY' or empty."""
    if not created_at or not created_at.strip():
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return ""


def tweet_id_from_url(url: str) -> str:
    """Extract tweet ID from x.com or twitter.com status URL."""
    if not url:
        return ""
    url = url.strip()
    # .../status/1234567890 or .../status/1234567890?s=20
    if "/status/" in url:
        part = url.split("/status/")[-1]
        return part.split("?")[0].split("/")[0].strip()
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
        profile_image_url = (r.get("profile_image_url") or "").strip()
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

        # One compact header line: badge, handle, followers, ER, likes
        meta_parts = [f'<span class="meta-followers">{followers} fol.</span>', f'<span class="meta-er">ER {er_pct}</span>', f'<span class="meta-eng">♥ {total_likes} RT {total_retweets} ↩ {total_replies}</span>']
        if joined:
            meta_parts.append(f'<span class="meta-joined">{joined}</span>')
        meta_line = " · ".join(meta_parts)

        card = f'''
        <article class="card card-{rec_class}" data-recommendation="{escape(rec)}">
          <div class="card-top">
            <span class="badge badge-{rec_class}">{escape(rec)}</span>
            <a href="{escape(profile_url)}" target="_blank" rel="noopener" class="profile-link">@{escape(username)}</a>
            <span class="card-meta">{meta_line}</span>
          </div>
          <div class="tweet-embeds">
'''
        for i in range(1, 4):
            url = r.get(f"tweet_url_{i}") or ""
            text = (r.get(f"sample_tweet_{i}") or "").strip()
            tweet_date_raw = (r.get(f"tweet_date_{i}") or "").strip()
            tweet_date_str = format_tweet_date(tweet_date_raw) if tweet_date_raw else ""
            if not text and not url:
                continue
            tweet_url = url.strip() or profile_url
            if "x.com" in tweet_url and "twitter.com" not in tweet_url:
                tweet_url = tweet_url.replace("https://x.com/", "https://twitter.com/", 1)
            safe_text = escape(text[:600]) + ("…" if len(text) > 600 else "")
            safe_text = linkify(safe_text)
            avatar_html = f'<img src="{escape(profile_image_url)}" alt="" class="tweet-avatar-img" loading="lazy" referrerpolicy="no-referrer">' if profile_image_url else '<div class="tweet-avatar" aria-hidden="true"></div>'
            date_html = f'<span class="tweet-date">{escape(tweet_date_str)}</span>' if tweet_date_str else ""
            card += f'''
            <div class="tweet-card">
              <div class="tweet-card-header">
                {avatar_html}
                <span class="tweet-handle">@{escape(username)}</span>
                {date_html}
              </div>
              <div class="tweet-card-body">{safe_text or "—"}</div>
              <div class="tweet-card-actions">
                <span class="tweet-stat">♥ {total_likes}</span>
                <span class="tweet-stat">RT {total_retweets}</span>
                <span class="tweet-stat">↩ {total_replies}</span>
                <a href="{escape(tweet_url)}" target="_blank" rel="noopener" class="tweet-view-link">View on X</a>
              </div>
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
    .grid {{ display: grid; gap: 0.75rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0.75rem 1rem;
      transition: opacity 0.2s;
    }}
    .card:hover {{ border-color: #3f3f46; }}
    .card.card-strong-hire {{ border-left: 4px solid var(--accent-strong); }}
    .card.card-consider {{ border-left: 4px solid var(--accent-consider); }}
    .card.card-skip {{ border-left: 4px solid var(--accent-skip); opacity: 0.75; }}
    .card.hidden {{ display: none; }}
    .card-top {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      flex-wrap: wrap;
      margin-bottom: 0.5rem;
      font-size: 0.8rem;
    }}
    .badge {{
      font-size: 0.65rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.15rem 0.4rem;
      border-radius: 4px;
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
    .card-meta {{ color: var(--text2); }}
    .tweet-embeds {{ margin-top: 0.5rem; }}
    .tweet-card {{
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 0.75rem 1rem;
      margin-bottom: 0.5rem;
    }}
    .tweet-card:last-child {{ margin-bottom: 0; }}
    .tweet-card-header {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.5rem;
    }}
    .tweet-avatar, .tweet-avatar-img {{
      width: 40px;
      height: 40px;
      border-radius: 50%;
      flex-shrink: 0;
      object-fit: cover;
    }}
    .tweet-avatar {{
      background: linear-gradient(135deg, var(--surface2) 0%, var(--border) 100%);
    }}
    .tweet-handle {{
      font-weight: 600;
      color: var(--text);
      font-size: 0.95rem;
    }}
    .tweet-date {{
      color: var(--text2);
      font-size: 0.85rem;
      margin-left: 0.25rem;
    }}
    .tweet-date::before {{
      content: "· ";
      margin-right: 0.15rem;
    }}
    .tweet-card-body {{
      font-size: 0.95rem;
      line-height: 1.5;
      color: var(--text);
      white-space: pre-wrap;
      word-break: break-word;
      margin-bottom: 0.5rem;
    }}
    .tweet-card-body .tweet-link {{
      color: var(--link);
      text-decoration: none;
    }}
    .tweet-card-body .tweet-link:hover {{ text-decoration: underline; }}
    .tweet-card-actions {{
      display: flex;
      align-items: center;
      gap: 1rem;
      font-size: 0.85rem;
      color: var(--text2);
    }}
    .tweet-stat {{ margin-right: 0.25rem; }}
    .tweet-view-link {{
      color: var(--link);
      text-decoration: none;
      margin-left: auto;
    }}
    .tweet-view-link:hover {{ text-decoration: underline; }}
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
