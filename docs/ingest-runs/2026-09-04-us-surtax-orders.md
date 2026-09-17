# Ingest run — Canada United States Surtax Order (2026), 2026-09-04

Scope version: `2026-09-04-us-surtax-orders`
Jurisdiction: `ca` · Document class: `rulemaking`

## What was ingested

The two Orders in Council that impose Canada's counter-tariffs on U.S. goods,
both made **2026-09-04** and in force **2026-09-08**:

| P.C. | Title | Enabling authority |
|---|---|---|
| 2026-0785 | United States Surtax Order (2026) | Customs Tariff s. 53(2), para. 79(a), s. 115 |
| 2026-0786 | Order Amending the United States Surtax Order (Steel and Aluminum 2025) | Customs Tariff s. 53(2), para. 79(a) |

These supersede the announcement-stage sources ingested under
`2026-08-25-us-countermeasures` (PR #637) as the citable authority. That scope
remains valid as the Finance announcement record; this one carries the law.

## Sources and capture

| File | Bytes | SHA-256 |
|---|---|---|
| `2026-09-04-pc-2026-0785-us-surtax-order-2026.html` | 57,589 | `d9eab33ccd0e8e9ee16e31898f5d735c2931c8170088b06e1303e4b1ab4106b6` |
| `2026-09-04-pc-2026-0786-order-amending-steel-aluminum-2025.html` | 43,413 | `9be01707d7f62c6305be0b8a89749e2465f1577b11dbb6ec0d4559c24e82befd` |

- URLs: `https://orders-in-council.canada.ca/attachment.php?attach=48943&lang=en`
  and `…attach=48944&lang=en`
- Captured 2026-09-17 by HTTPS GET with a browser User-Agent.
- **Both were fetched twice and were byte-identical**, so these digests pin a
  stable document identity — unlike `www.canada.ca` pages, which embed
  per-request nonces and cannot be re-hashed to the same value.

## Extraction

Each attachment is bilingual in a single document: English preamble, French
preamble, English Order, French Order. The builder takes the English preamble
plus every visible English paragraph from the English Order title up to the
French Order title.

The OIC markup leaves `<p>` tags unclosed, so `html.parser` nests them and an
ancestor `<p>` repeats all of its descendants' text; the builder therefore reads
**leaf paragraphs only**. Visible text is normalized by the standard corpus
whitespace normalizer.

Block kinds: `paragraph` for operative text, `schedule` for schedule headings,
`tariff-item` for each 8-digit tariff item. Schedule membership, surtax rate,
and (for the amending Order) the metal are carried in block metadata.

## Scope census

- Documents: 2 · Provisions: **743** · Coverage: complete, no missing/extra/duplicate
- Tariff-item provisions: 643 = **629 rate-bearing** + 14 Chapter 98/99 items

United States Surtax Order (2026):

| Schedule | Meaning | Items |
|---|---|---|
| 1 | 15% surtax | 21 |
| 2 | 25% surtax | 172 |
| 3 | 50% surtax | 142 |
| 4 | Ch. 98/99 items that remain subject despite the para. 2(a) exemption | 14 |

Order Amending (Steel and Aluminum 2025) — replaces SOR/2025-95 Schedules 1–2:

| Schedule | Meaning | Items |
|---|---|---|
| 1 | aluminum, 25% | 2 |
| 1.1 | aluminum, 50% | 27 |
| 2 | steel, 25% | 21 |
| 2.1 | steel, 50% | 244 |

The amending Order's 294 items are exclusively HS chapters 72 (134), 73 (131)
and 76 (29). The builder asserts this.

## Cross-check against the Finance product list

The builder reconciles its rate-bearing items against the pinned 2026-08-25
Finance product list (`--finance-tsv`) and **fails the run** on any difference:

```
orders_count      629
finance_count     629
matched           629
only_in_orders    []
only_in_finance   []
rate_mismatches   {}
```

Rate tiers agree exactly: 15% = 21, 25% = 195, 50% = 413.

## Reproduction

```bash
PYTHONPATH=src .venv/bin/python \
  <path>/build_ca_surtax_orders.py \
  --base data/corpus \
  --finance-tsv <path>/pins/2026-08-25-finance-product-list-extracted.tsv
```

Run twice; generated artifact hashes were identical both times:

| Artifact | SHA-256 |
|---|---|
| `coverage/ca/rulemaking/2026-09-04-us-surtax-orders.json` | `ef5af7c89244b7cff225479a0200bcb4d152f55bc5763fe9d73c64f91b9225ba` |
| `inventory/ca/rulemaking/2026-09-04-us-surtax-orders.json` | `cc0a97405eda17bfe58ce1dbce7279e1efb75e8a67f887d67f5849487d1e844e` |
| `provisions/ca/rulemaking/2026-09-04-us-surtax-orders.jsonl` | `fc25052140c773bed482721d1ca0044dbdfa8bbe7a4cafb8ddb3e73cd6da50ec` |

The builder verifies its own output before writing: 2 documents, 643
tariff-item rows, 629 rate-bearing items in the expected tiers, 14 Chapter
98/99 items, amending-Order items restricted to HS 72/73/76, and complete
coverage.

## ⚠ Registration status — unresolved at ingest time

Neither Order had appeared in the Canada Gazette Part II as of 2026-09-17.
Part II Vol. 160 No. 18 (2026-09-09) carries only SOR/2026-182, -183 and -185,
and 2026 has had no Extra edition since 2026-06-08 — unlike the March 2025
precedent, where surtax orders were published in Extra editions.

The registration numbers are **inferred** as **SOR/2026-186** (P.C. 2026-0785)
and **SOR/2026-187** (P.C. 2026-0786), from CBSA surtax codes `26186A/B/C` and
`26187A/B/C/D` (Customs Notices 26-23 and 25-11, both dated 2026-09-07), on a
`YY + zero-padded SOR number + tier letter` convention verified against four
prior orders: 25066A→SOR/2025-66, 25095A→SOR/2025-95, 25118A→SOR/2025-118,
25267A→SOR/2025-267. The tier letters also line up with each Order's schedules.

These SOR numbers are recorded in source metadata as inferred and are **not**
asserted as verified. Confirm against Canada Gazette Part II Vol. 160 No. 19,
due **2026-09-23**.

Consequence for the ingest: none of the provision text depends on the SOR
number. Coming into force is fixed by s. 10 of the Order itself, and CBSA
published effective-date guidance on 2026-09-07.

## Related instruments (referenced, not ingested here)

- **SOR/2025-122** United States Surtax Remission Order (2025) — amended in
  place by ss. 3–8 of the 2026 Order to extend every head of remission to the
  new surtax. No separate new remission order was made.
- **SOR/2025-267** Steel Derivative Goods Surtax Order — s. 9 adds the 2026
  Order to its anti-stacking list; the two surtaxes are not cumulative.
- **SOR/2025-95** United States Surtax Order (Steel and Aluminum 2025) — the
  order amended by P.C. 2026-0786.
- **SOR/2025-118** United States Surtax Order (Motor Vehicles 2025) — unchanged
  and still in force; its 19 HS-87 lines at 25% are why Finance's consolidated
  page shows 648 entries for Sept 8 rather than 629.
