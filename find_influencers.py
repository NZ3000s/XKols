#!/usr/bin/env python3
"""
Пошук інфлюенсерів у X (Twitter), які згадували Euphoria_fi або Polymarket 5 min.
Сортування за охватами (followers, engagement).
"""

import os
import base64
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# Ключі тільки з середовища — ніколи не хардкодити
CONSUMER_KEY = os.environ.get("X_CONSUMER_KEY") or os.environ.get("TWITTER_API_KEY")
CONSUMER_SECRET = os.environ.get("X_CONSUMER_SECRET") or os.environ.get("TWITTER_API_SECRET")

BASE = "https://api.twitter.com"


def get_bearer_token() -> str:
    """Отримати Bearer token (OAuth 2.0 App-Only)."""
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        raise SystemExit(
            "Потрібні X_CONSUMER_KEY та X_CONSUMER_SECRET у .env або в змінних середовища."
        )
    creds = base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    r = requests.post(
        f"{BASE}/oauth2/token",
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        data="grant_type=client_credentials",
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def search_tweets(
    bearer: str,
    query: str,
    *,
    max_results: int = 100,
    max_pages: int = 10,
    user_fields: str = "public_metrics,username,name,verified,created_at",
) -> tuple[list[dict], dict[str, dict]]:
    """Пошук останніх твітів (API v2 recent search). Повертає твіти та словник user_id -> user."""
    headers = {"Authorization": f"Bearer {bearer}"}
    url = f"{BASE}/2/tweets/search/recent"
    all_tweets = []
    users_by_id = {}
    next_token = None
    page = 0

    while page < max_pages:
        params = {
            "query": query,
            "max_results": min(max_results, 100),
            "tweet.fields": "created_at,public_metrics,author_id,text",
            "user.fields": user_fields,
            "expansions": "author_id",
        }
        if next_token:
            params["next_token"] = next_token

        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 429:
            print("Rate limit. Чекаємо 60 с...")
            time.sleep(60)
            continue
        r.raise_for_status()
        data = r.json()

        tweets = data.get("data") or []
        all_tweets.extend(tweets)

        for u in data.get("includes", {}).get("users", []):
            users_by_id[u["id"]] = u

        next_token = data.get("meta", {}).get("next_token")
        if not next_token:
            break
        page += 1
        time.sleep(1)

    return all_tweets, users_by_id


def build_influencer_list(tweets: list[dict], users_by_id: dict) -> list[dict]:
    """З твітів зібрати унікальних авторів з метриками та engagement."""
    by_author = {}
    for t in tweets:
        aid = t.get("author_id")
        if not aid:
            continue
        u = users_by_id.get(aid)
        if not u:
            continue
        metrics = u.get("public_metrics") or {}
        followers = metrics.get("followers_count") or 0
        # вже є — лише оновлюємо суму лайків/ретвітів з нових твітів
        if aid not in by_author:
            by_author[aid] = {
                "user_id": aid,
                "username": u.get("username", ""),
                "name": u.get("name", ""),
                "verified": u.get("verified", False),
                "followers_count": followers,
                "following_count": metrics.get("following_count") or 0,
                "tweet_count": metrics.get("tweet_count") or 0,
                "listed_count": metrics.get("listed_count") or 0,
                "tweets_found": 0,
                "total_likes": 0,
                "total_retweets": 0,
                "total_replies": 0,
            }
        rec = by_author[aid]
        rec["tweets_found"] += 1
        pm = t.get("public_metrics") or {}
        rec["total_likes"] += pm.get("like_count") or 0
        rec["total_retweets"] += pm.get("retweet_count") or 0
        rec["total_replies"] += pm.get("reply_count") or 0

    return list(by_author.values())


def main():
    print("Отримання Bearer token...")
    bearer = get_bearer_token()

    # Два окремі пошуки: Euphoria_fi / euphoria.fi та Polymarket 5 min
    queries = [
        '(Euphoria_fi OR euphoria.fi OR "x.com/Euphoria_fi") -is:retweet lang:en',
        '("Polymarket 5 min" OR "Polymarket 5min") -is:retweet lang:en',
    ]

    all_tweets = []
    all_users = {}

    for q in queries:
        label = "Euphoria_fi" if "Euphoria" in q else "Polymarket 5 min"
        print(f"Пошук: {label}...")
        tweets, users = search_tweets(bearer, q, max_results=100, max_pages=5)
        print(f"  знайдено твітів: {len(tweets)}, унікальних авторів: {len(users)}")
        all_tweets.extend(tweets)
        all_users.update(users)
        time.sleep(2)

    influencers = build_influencer_list(all_tweets, all_users)
    # Сортування: спочатку за followers, потім за сумарним engagement
    influencers.sort(
        key=lambda x: (
            x["followers_count"],
            x["total_likes"] + x["total_retweets"] * 2 + x["total_replies"],
        ),
        reverse=True,
    )

    out_csv = "influencers.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "username",
                "name",
                "user_id",
                "verified",
                "followers_count",
                "following_count",
                "tweets_found",
                "total_likes",
                "total_retweets",
                "total_replies",
                "profile_url",
            ],
        )
        w.writeheader()
        for row in influencers:
            w.writerow({
                "username": row["username"],
                "name": row["name"],
                "user_id": row["user_id"],
                "verified": row["verified"],
                "followers_count": row["followers_count"],
                "following_count": row["following_count"],
                "tweets_found": row["tweets_found"],
                "total_likes": row["total_likes"],
                "total_retweets": row["total_retweets"],
                "total_replies": row["total_replies"],
                "profile_url": f"https://x.com/{row['username']}",
            })

    print(f"\nЗнайдено інфлюенсерів: {len(influencers)}")
    print(f"Результати збережено в {out_csv}\n")
    print("Топ-15 за охватами (followers):")
    print("-" * 80)
    for i, x in enumerate(influencers[:15], 1):
        v = "✓" if x["verified"] else ""
        print(f"{i:2}. @{x['username']:<20} {x['followers_count']:>8} підписників  "
              f"твітів: {x['tweets_found']}  likes: {x['total_likes']}  {v}")
    print("-" * 80)


if __name__ == "__main__":
    main()
