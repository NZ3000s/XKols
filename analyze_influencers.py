#!/usr/bin/env python3
"""
Аналіз контенту інфлюенсерів (що писали) + рекомендації для шилінгу.
Критерій: жива аудиторія (engagement rate), не лише кількість підписників.
"""

import csv
import time
from find_influencers import (
    get_bearer_token,
    search_tweets,
)

# Пороги для рекомендацій (engagement rate = сума взаємодій / (твітів × підписників))
MIN_FOLLOWERS_STRONG = 5_000
MIN_ER_STRONG = 0.0008      # 0.08% — явно жива аудиторія
MIN_ENGAGEMENT_STRONG = 20  # мінімум лайків+ретвітів+коментів на знайдені твіти

MIN_FOLLOWERS_CONSIDER = 2_000
MIN_ER_CONSIDER = 0.0002    # 0.02%
MIN_ENGAGEMENT_CONSIDER = 5

# Нижче — скіп (мертва або дуже мала аудиторія)
MAX_FOLLOWING_RATIO = 50  # following >> followers часто боти/фоллов-бек


def build_influencers_with_tweets(tweets: list, users_by_id: dict) -> list[dict]:
    """Збирає авторів з метриками та зразками текстів твітів."""
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
                "created_at": u.get("created_at") or "",
                "profile_image_url": u.get("profile_image_url") or "",
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
        pm = t.get("public_metrics") or {}
        rec["total_likes"] += pm.get("like_count") or 0
        rec["total_retweets"] += pm.get("retweet_count") or 0
        rec["total_replies"] += pm.get("reply_count") or 0
        text = (t.get("text") or "").strip()
        tweet_id = t.get("id")
        tweet_created = t.get("created_at") or ""
        if text and len(rec["sample_tweets"]) < 5:
            rec["sample_tweets"].append(text[:500])
            if tweet_id:
                rec["sample_tweet_ids"].append(tweet_id)
            if tweet_created:
                rec["sample_tweet_dates"].append(tweet_created)

    return list(by_author.values())


def engagement_rate(row: dict) -> float:
    """Engagement rate: сума взаємодій / (кількість твітів × підписників)."""
    total = row["total_likes"] + row["total_retweets"] + row["total_replies"]
    denom = row["tweets_found"] * max(row["followers_count"], 1)
    return total / denom if denom else 0.0


def total_engagement(row: dict) -> int:
    return row["total_likes"] + row["total_retweets"] + row["total_replies"]


def looks_like_promo(texts: list[str]) -> bool:
    """Евристика: чи виглядає контент як промо (посилання, позитив, згадки продуктів)."""
    if not texts:
        return False
    joined = " ".join(texts).lower()
    has_link = "http" in joined or "polymarket" in joined or "euphoria" in joined or ".fi" in joined
    positive = any(w in joined for w in ["check", "try", "new", "launch", "alpha", "gem", "🔥", "💎", "🚀"])
    return has_link or positive


def recommend(row: dict, er: float, total_eng: int) -> tuple[str, str]:
    """
    Повертає (рекомендація, причина).
    Рекомендації: "Strong hire", "Consider", "Skip"
    """
    followers = row["followers_count"]
    following = row["following_count"]
    sample = row.get("sample_tweets") or []

    # Bot / follow-back suspicion
    if followers > 0 and following > MAX_FOLLOWING_RATIO * followers:
        return ("Skip", "Following >> followers, likely bot or follow-back account")

    if total_eng == 0 and followers > 100_000:
        return ("Skip", "Large audience but zero engagement on these tweets — dead feed")

    if followers < 1_000:
        return ("Skip", "Too small audience for promo")

    # Strong hire
    if (
        followers >= MIN_FOLLOWERS_STRONG
        and er >= MIN_ER_STRONG
        and total_eng >= MIN_ENGAGEMENT_STRONG
    ):
        reason = f"ER {er:.2%}, {total_eng} engagements, live audience"
        if looks_like_promo(sample):
            reason += ", already does promo-style content"
        return ("Strong hire", reason)

    # Consider
    if (
        followers >= MIN_FOLLOWERS_CONSIDER
        and (er >= MIN_ER_CONSIDER or (total_eng >= MIN_ENGAGEMENT_CONSIDER and followers >= 10_000))
    ):
        reason = f"ER {er:.2%}, {total_eng} engagements"
        if er < MIN_ER_CONSIDER and total_eng >= MIN_ENGAGEMENT_CONSIDER:
            reason = f"Large audience ({followers}), some engagement ({total_eng})"
        return ("Consider", reason)

    if total_eng == 0:
        return ("Skip", "No engagement on found tweets — dead audience")
    if er < 0.00005:
        return ("Skip", f"Very low ER ({er:.2%})")
    return ("Skip", "Below Consider threshold")


def main():
    print("Отримання Bearer token...")
    bearer = get_bearer_token()

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
        print(f"  твітів: {len(tweets)}, авторів: {len(users)}")
        all_tweets.extend(tweets)
        all_users.update(users)
        time.sleep(2)

    influencers = build_influencers_with_tweets(all_tweets, all_users)

    # Додаємо ER, рекомендацію, причину
    for row in influencers:
        er = engagement_rate(row)
        total_eng = total_engagement(row)
        row["engagement_rate"] = er
        row["total_engagement"] = total_eng
        rec, reason = recommend(row, er, total_eng)
        row["recommendation"] = rec
        row["recommendation_reason"] = reason

    # Сортування: спочатку Strong hire, потім Consider, потім за ER та followers
    order = {"Strong hire": 0, "Consider": 1, "Skip": 2}
    influencers.sort(
        key=lambda x: (
            order.get(x["recommendation"], 2),
            -x["engagement_rate"],
            -x["followers_count"],
        ),
    )

    out_csv = "recommendations.csv"
    base = "https://x.com"
    fieldnames = [
        "recommendation",
        "username",
        "name",
        "profile_url",
        "profile_image_url",
        "followers_count",
        "following_count",
        "listed_count",
        "created_at",
        "tweets_found",
        "total_likes",
        "total_retweets",
        "total_replies",
        "total_engagement",
        "engagement_rate",
        "recommendation_reason",
        "sample_tweet_1",
        "sample_tweet_2",
        "sample_tweet_3",
        "tweet_date_1",
        "tweet_date_2",
        "tweet_date_3",
        "tweet_url_1",
        "tweet_url_2",
        "tweet_url_3",
    ]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in influencers:
            uname = row["username"]
            ids = row.get("sample_tweet_ids") or []
            r = {
                "recommendation": row["recommendation"],
                "username": uname,
                "name": row["name"],
                "profile_url": f"{base}/{uname}",
                "profile_image_url": row.get("profile_image_url") or "",
                "followers_count": row["followers_count"],
                "following_count": row["following_count"],
                "listed_count": row.get("listed_count") or "",
                "created_at": row.get("created_at") or "",
                "tweets_found": row["tweets_found"],
                "total_likes": row["total_likes"],
                "total_retweets": row["total_retweets"],
                "total_replies": row["total_replies"],
                "total_engagement": row["total_engagement"],
                "engagement_rate": f"{row['engagement_rate']:.4f}",
                "recommendation_reason": row["recommendation_reason"],
            }
            dates = row.get("sample_tweet_dates") or []
            for i in range(1, 4):
                samples = row.get("sample_tweets") or []
                r[f"sample_tweet_{i}"] = samples[i - 1] if len(samples) >= i else ""
                r[f"tweet_date_{i}"] = dates[i - 1] if len(dates) >= i else ""
                r[f"tweet_url_{i}"] = f"{base}/{uname}/status/{ids[i-1]}" if len(ids) >= i else ""
            w.writerow(r)

    strong = sum(1 for x in influencers if x["recommendation"] == "Strong hire")
    consider = sum(1 for x in influencers if x["recommendation"] == "Consider")
    skip = sum(1 for x in influencers if x["recommendation"] == "Skip")

    print(f"\nРезультати збережено в {out_csv}")
    print(f"Strong hire: {strong} | Consider: {consider} | Skip: {skip}\n")
    print("Топ рекомендацій (Strong hire + Consider):")
    print("-" * 100)
    for x in influencers:
        if x["recommendation"] == "Skip":
            continue
        v = "✓" if x["verified"] else ""
        er = x["engagement_rate"]
        samples = (x.get("sample_tweets") or [])[:1]
        preview = (samples[0][:80] + "…") if samples and len(samples[0]) > 80 else (samples[0] if samples else "")
        print(f"{x['recommendation']:12} @{x['username']:<18} {x['followers_count']:>8} підп.  ER:{er:.2%}  "
              f"взаємодій:{x['total_engagement']}  {v}")
        if preview:
            print(f"             «{preview}»")
    print("-" * 100)


if __name__ == "__main__":
    main()
