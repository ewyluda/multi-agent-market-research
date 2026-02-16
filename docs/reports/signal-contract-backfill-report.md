# Signal Contract V2 Backfill Audit Report

- Started: `2026-02-16T01:40:50.824956+00:00`
- Ended: `2026-02-16T01:40:50.860732+00:00`
- Scope: `180` day window from `2025-08-20T01:40:50.824956+00:00`
- Batch size: `200`
- Dry run: `false`

## Summary

| Metric | Value |
| --- | ---: |
| Scanned | 28 |
| Eligible | 28 |
| Updated | 28 |
| Skipped (existing valid) | 0 |
| Skipped (missing payload) | 0 |
| Skipped (missing agent results) | 0 |
| Skipped (missing recommendation) | 0 |
| Failed (validation) | 0 |
| Failed (write) | 0 |
| Hard failure rate | 0.00% |

## Execution Checklist

- [x] 180-day scope applied
- [x] Deterministic contract builder used
- [x] Contract validation enforced before write
- [x] Additive write path used (legacy keys preserved)
- [x] Batch processing + checkpoint cursor used

## Spot-Check Template (20 Random Rows)

Use this table for manual QA after backfill:

| analysis_id | ticker | schema_version=v2 | signal_contract_v2 valid | legacy keys unchanged | notes |
| --- | --- | --- | --- | --- | --- |
| 11 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 5 | BE | yes | yes | n/a | historical row has sparse legacy metrics |
| 13 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 21 | NBIS | yes | yes | n/a | historical row has sparse legacy metrics |
| 2 | BE | yes | yes | n/a | historical row has sparse legacy metrics |
| 3 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 18 | GOOGL | yes | yes | n/a | historical row has sparse legacy metrics |
| 4 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 12 | BE | yes | yes | n/a | historical row has sparse legacy metrics |
| 19 | HOOD | yes | yes | n/a | historical row has sparse legacy metrics |
| 24 | RKLB | yes | yes | n/a | historical row has sparse legacy metrics |
| 17 | NVDA | yes | yes | n/a | historical row has sparse legacy metrics |
| 7 | HOOD | yes | yes | n/a | historical row has sparse legacy metrics |
| 1 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 22 | RDW | yes | yes | n/a | historical row has sparse legacy metrics |
| 16 | RKLB | yes | yes | n/a | historical row has sparse legacy metrics |
| 26 | AAPL | yes | yes | n/a | historical row has sparse legacy metrics |
| 14 | BE | yes | yes | n/a | historical row has sparse legacy metrics |
| 25 | COIN | yes | yes | n/a | historical row has sparse legacy metrics |
| 28 | CRWV | yes | yes | n/a | historical row has sparse legacy metrics |

## Idempotency Check

Dry-run rerun command:

```bash
python -m src.backfill_signal_contract --db-path market_research.db --days 180 --batch-size 200 --dry-run
```

Observed result:
- scanned: `28`
- eligible: `0`
- updated: `0`
- skipped_existing_valid: `28`
