# Twitter/X Integration in News Agent

**Date**: 2026-02-12
**Status**: Approved

## Overview

Add Twitter/X post fetching as a supplementary data source in the News Agent. Tweets with cashtag mentions are fetched concurrently alongside the primary news source (AV/NewsAPI) and surfaced as a separate `twitter_posts` field.

## Architecture

```
NewsAgent.fetch_data()
  ├── _fetch_av_news()          # Primary (existing)
  ├── _fetch_from_newsapi()     # Fallback (existing)
  └── _fetch_twitter_posts()    # NEW - runs concurrently, always
        ├── GET /2/tweets/search/recent
        │   query: "$TICKER -is:retweet lang:en"
        │   tweet.fields: created_at,public_metrics,author_id
        │   max_results: 20
        └── Filter by engagement (likes+RTs >= 2)
```

## Data Flow

1. `fetch_data()` fires `_fetch_twitter_posts()` concurrently with the primary AV/NewsAPI fetch via `asyncio.gather()`
2. Twitter results stored in `raw_data["twitter_posts"]` — list of dicts with `text`, `created_at`, `metrics`, `url`
3. `analyze()` includes tweet count and summary stats in output
4. Sentiment agent receives tweet data through existing `set_context_data()` pipeline

## Config Changes

- Add `TWITTER_BEARER_TOKEN` to `Config` class
- Add `TWITTER_MAX_RESULTS` config option (default: 20, max: 100)
- No new agent or enable/disable flag — presence of bearer token activates

## Error Handling

- Twitter API failure logs warning and continues with zero tweets
- URL-encoded bearer token used as-is (no decoding)
- Rate limit: 450 req/15min is sufficient

## Output

- `twitter_posts` field in news agent output with top tweets by engagement
- Tweet count and engagement stats
- Social buzz metrics (total tweets, avg engagement, sentiment distribution)
