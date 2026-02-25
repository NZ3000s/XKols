#!/usr/bin/env python3
"""
Historical tweet search via TwitterAPI.io (no 7-day limit).
Only Euphoria_fi — for a separate, clear demo page.

Writes euphoria_historical.csv. Then: python3 export_to_html.py euphoria_historical.csv

Usage:
  python3 fetch_historical_twitterapi_io.py --since 2025-01-01
  python3 fetch_historical_twitterapi_io.py --since 2025-01-01 --until 2025-01-31
  python3 export_to_html.py euphoria_historical.csv
"""

import argparse
import csv
import os
import time
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

from analyze_influencers import (
    engagement_rate,
    recommend,
)

load_dotenv()

API_KEY = os.environ.get("TWITTERAPI_IO_API_KEY") or os.environ.get("TWITTERAPI_IO_KEY")
BASE = "https://api.twitterapi.io"


def parse_twitterapi_date(s: str) -> str:
    """Parse 'Tue Dec 10 07:00:30 +0000 2024' to ISO for CSV."""
    if not s or not s.strip():
        return ""
    try:
        # TwitterAPI.io format
        dt = datetime.strptime(s.strip(), "%a %b %d %H:%M:%S %z %Y")
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception:
        return ""


def search_historical(query: str, api_key: str, query_type: str = "Latest", max_pages: int = 50) -> list[dict]:
    """Paginate through TwitterAPI.io advanced_search. Returns list of tweet objects."""
    headers = {"X-API-Key": api_key}
    url = f"{BASE}/twitter/tweet/advanced_search"
    all_tweets = []
    cursor = ""
    for page in range(max_pages):
        params = {"query": query, "queryType": query_type}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            print("Rate limit, waiting 60s...")
            time.sleep(60)
            continue
        r.raise_for_status()
        data = r.json()
        tweets = data.get("tweets") or []
        all_tweets.extend(tweets)
        if not data.get("has_next_page") or not data.get("next_cursor"):
            break
        cursor = data.get("next_cursor") or ""
        print(f"  page {page + 1}: {len(tweets)} tweets, total {len(all_tweets)}", flush=True)
        time.sleep(2)
    return all_tweets


def build_influencers_from_twitterapi_tweets(tweets: list[dict]) -> list[dict]:
    """Aggregate by author, same structure as analyze_influencers.build_influencers_with_tweets output."""
    by_author = {}
    for t in tweets:
        author = t.get("author") or {}
        aid = author.get("id") or ""
        if not aid:
            continue
        if aid not in by_author:
            by_author[aid] = {
                "user_id": aid,
                "username": author.get("userName") or "",
                "name": author.get("name") or "",
                "verified": author.get("isBlueVerified") or False,
                "followers_count": int(author.get("followers") or 0),
                "following_count": int(author.get("following") or 0),
                "listed_count": 0,
                "created_at": author.get("createdAt") or "",
                "profile_image_url": author.get("profilePicture") or "",
                "tweets_found": 0,
                "total_likes": 0,
                "total_retweets": 0,
                "total_replies": 0,
                "sample_tweets": [],
                "sample_tweet_ids": [],
                "sample_tweet_dates": [],
            }
        rec = by_author[aid]
        rec["tweets_found"] += 1
        rec["total_likes"] += int(t.get("likeCount") or 0)
        rec["total_retweets"] += int(t.get("retweetCount") or 0)
        rec["total_replies"] += int(t.get("replyCount") or 0)
        text = (t.get("text") or "").strip()
        tid = t.get("id") or ""
        created = t.get("createdAt") or ""
        if text and len(rec["sample_tweets"]) < 5:
            rec["sample_tweets"].append(text[:500])
            if tid:
                rec["sample_tweet_ids"].append(str(tid))
            rec["sample_tweet_dates"].append(parse_twitterapi_date(created) or created)
    return list(by_author.values())


def main():
    parser = argparse.ArgumentParser(description="Historical tweets via TwitterAPI.io")
    parser.add_argument("--since", required=True, help="Start date YYYY-MM-DD (e.g. 2025-01-01)")
    parser.add_argument("--until", default="", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pagination pages (default 50)")
    parser.add_argument("--output", default="euphoria_historical.csv", help="Output CSV (default: euphoria_historical.csv)")
    args = parser.parse_args()
    if not API_KEY:
        raise SystemExit("Set TWITTERAPI_IO_API_KEY (or TWITTERAPI_IO_KEY) in .env")
    since = args.since.strip()
    until = (args.until or datetime.now(timezone.utc).strftime("%Y-%m-%d")).strip()
    # Euphoria_fi only — for separate historical demo page
    query = f'(Euphoria_fi OR euphoria.fi) since:{since}_00:00:00_UTC until:{until}_23:59:59_UTC -is:retweet lang:en'
    print(f"Query (Euphoria only): {query[:70]}...")
    print("Fetching from TwitterAPI.io...")
    tweets = search_historical(query, API_KEY, query_type="Latest", max_pages=args.max_pages)
    print(f"Total tweets: {len(tweets)}")
    if not tweets:
        print("No tweets found. Try widening --since/--until or check API key/credits.")
        return
    influencers = build_influencers_from_twitterapi_tweets(tweets)
    for row in influencers:
        er = engagement_rate(row)
        total_eng = row["total_likes"] + row["total_retweets"] + row["total_replies"]
        row["engagement_rate"] = er
        row["total_engagement"] = total_eng
        rec, reason = recommend(row, er, total_eng)
        row["recommendation"] = rec
        row["recommendation_reason"] = reason
    order = {"Strong hire": 0, "Consider": 1, "Skip": 2}
    influencers.sort(key=lambda x: (order.get(x["recommendation"], 2), -x["engagement_rate"], -x["followers_count"]))
    out_csv = args.output
    base = "https://x.com"
    fieldnames = [
        "recommendation", "username", "name", "profile_url", "profile_image_url",
        "followers_count", "following_count", "listed_count", "created_at",
        "tweets_found", "total_likes", "total_retweets", "total_replies",
        "total_engagement", "engagement_rate", "recommendation_reason",
        "sample_tweet_1", "sample_tweet_2", "sample_tweet_3",
        "tweet_date_1", "tweet_date_2", "tweet_date_3",
        "tweet_url_1", "tweet_url_2", "tweet_url_3",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in influencers:
            uname = row["username"]
            ids = row.get("sample_tweet_ids") or []
            dates = row.get("sample_tweet_dates") or []
            acct_created = (row.get("created_at") or "").strip()
            if acct_created and " +0000 " in acct_created:
                acct_created = parse_twitterapi_date(acct_created) or acct_created
            r = {
                "recommendation": row["recommendation"],
                "username": uname,
                "name": row["name"],
                "profile_url": f"{base}/{uname}",
                "profile_image_url": row.get("profile_image_url") or "",
                "followers_count": row["followers_count"],
                "following_count": row["following_count"],
                "listed_count": row.get("listed_count") or "",
                "created_at": acct_created,
                "tweets_found": row["tweets_found"],
                "total_likes": row["total_likes"],
                "total_retweets": row["total_retweets"],
                "total_replies": row["total_replies"],
                "total_engagement": row["total_engagement"],
                "engagement_rate": f"{row['engagement_rate']:.4f}",
                "recommendation_reason": row["recommendation_reason"],
            }
            for i in range(1, 4):
                samples = row.get("sample_tweets") or []
                r[f"sample_tweet_{i}"] = samples[i - 1] if len(samples) >= i else ""
                r[f"tweet_date_{i}"] = dates[i - 1] if len(dates) >= i else ""
                r[f"tweet_url_{i}"] = f"{base}/{uname}/status/{ids[i-1]}" if len(ids) >= i else ""
            w.writerow(r)
    strong = sum(1 for x in influencers if x["recommendation"] == "Strong hire")
    consider = sum(1 for x in influencers if x["recommendation"] == "Consider")
    print(f"\nWrote {out_csv} ({len(influencers)} influencers, Strong hire: {strong}, Consider: {consider})")
    base = os.path.splitext(out_csv)[0]
    print(f"Run: python3 export_to_html.py {out_csv}")
    print(f"Then open: {base}.html")


if __name__ == "__main__":
    main()
