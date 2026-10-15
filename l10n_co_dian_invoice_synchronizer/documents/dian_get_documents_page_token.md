# DIAN `POST /Document/GetDocumentsPageToken`

Internal, undocumented endpoint used by the DIAN catalog web app
(`catalogo-vpfe.dian.gov.co`) to list received/sent electronic documents on
the "Received documents" page. It is what `dian.api.client` (see
`models/dian_api_client.py`, methods `_get_documents_for_date_range` and
`_post_get_documents_page_token`) calls to fetch invoices for a date range.

This document records how it actually behaves, reverse-engineered from a live
capture of DIAN's own frontend (page source + a captured request/response) on
**2026-09-23**. There is no official documentation for this endpoint — if
DIAN changes its implementation, this description (and the client code) may
go stale and need to be re-verified the same way (see "How this was
verified" below).

## Why it isn't plain offset pagination

The endpoint looks like a standard DataTables server-side-processing
endpoint (`draw`/`start`/`length` in, `data`/`recordsTotal`/`recordsFiltered`
out), but underneath it is backed by Azure Cosmos DB, which has no real
`OFFSET`/`SKIP` past a certain point — only forward-only continuation
tokens. To work around that, DIAN's backend fetches and caches results in
**blocks of ~150 records** and expects the caller to walk those blocks in
order using a `blockIndex` + a continuation token, not an arbitrary global
offset.

DIAN's own frontend JS (`/Document/Received` page) implements this with a
`maxItemCount = 150` constant, a client-side `blockCache` (one entry per
`blockIndex`) and a `continuationTokens` map (one token per `blockIndex`,
used to request the *next* block). UI pages (10/25/50/100 rows) are then
sliced out of the cached block in the browser, with no additional server
round-trip, until the viewer scrolls past the cached block.

**The real per-block size is not actually fixed at 150** — it is whatever
Cosmos DB's own continuation semantics happen to return for that query
(observed in a live sync: 153, 150, 152, 153, 150, then a 96-record tail —
never a strict multiple of 150). `maxItemCount = 150` in DIAN's frontend is
only a *nominal* value it uses to compute which `blockIndex` a given UI
`start` offset falls into; it is not a promise about how many records a
block actually contains. Our client does not rely on any fixed block size —
see "Algorithm" below.

## Request (`application/x-www-form-urlencoded`)

Sent with `X-Requested-With: XMLHttpRequest` and the DIAN session cookies
(`ASP.NET_SessionId`, `.AspNet.ApplicationCookie`, `ARRAffinity*`).

| Field | Meaning |
|---|---|
| `__RequestVerificationToken` | ASP.NET anti-forgery token. Must be the value from the hidden form field on the authenticated HTML page (double-submit cookie pattern) — a JSON body or a mismatched token is rejected. |
| `draw` | DataTables echo parameter, purely cosmetic (returned unchanged in the response); not used for pagination logic. |
| `start` | Offset **within the current block being requested**, not a global offset. In practice this should always be `0`: we always request a full block from its own beginning (see "Algorithm" below). |
| `length` | Page size DIAN's UI would display (10/25/50/100). Does **not** limit `blockData`, which has its own server-determined size regardless of this value — see "Response" below. We send `DIAN_INVOICES_PER_PAGE` (50, one of the site's own valid values) purely to keep the request shaped like a real browser request; it has no observed effect on our client's behavior. |
| `DocumentKey`, `SerieAndNumber`, `SenderCode`, `ReceiverCode` | Free-text search filters (DataTables-style). When set, they reduce `recordsFiltered` below `recordsTotal`. Always empty in our client (we only filter by date). |
| `StartDate`, `EndDate` | Date range filter, `YYYY-MM-DD`. |
| `DocumentTypeId` | `"00"` = all document types. |
| `Status` | `"0"` = all statuses. |
| `IsNextPage` | `"false"` for the first block (`blockIndex == 0`); `"true"` for every following block. Tells the backend whether to start a fresh Cosmos query or continue from `ContinuationToken`. |
| `FilterType` | `"3"` in every observed request; purpose unclear, left as a fixed value matching DIAN's own frontend. |
| `blockIndex` | 0-based index of the block being requested. Increment by 1 each time a new block is fetched. |
| `RadianStatus` | `"0"` = all Radian statuses. |
| `ContinuationToken` | **Capital "C"** — confirmed from a live capture, easy to get wrong by guessing camelCase. Must be the token returned by the **previous** block's response (`continuationToken` in the JSON body), empty string for `blockIndex == 0`. Sending the *current* block's own token, or none at all past block 0, is what causes the "empty page" bug described below. |

## Response (`application/json`)

```json
{
  "draw": 1,
  "start": 0,
  "recordsTotal": 388,
  "recordsFiltered": 388,
  "data": [ /* up to `length` items */ ],
  "blockData": [ /* the authoritative block, size varies (observed 96-153) */ ],
  "continuationToken": "[{\"compositeToken\": ... }]"
}
```

| Field | Meaning |
|---|---|
| `recordsTotal` | Total records for the base query (date range + `DocumentTypeId`/`Status`/`RadianStatus`), **before** the free-text search filters (`DocumentKey`, `SerieAndNumber`, `SenderCode`, `ReceiverCode`). |
| `recordsFiltered` | Total records **after** applying those free-text filters on top of `recordsTotal`. This is the number to compare pagination progress against — it equals `recordsTotal` whenever those filter fields are empty (our case). |
| `data` | A `length`-sized slice. **DIAN's own frontend does not use this to populate the results table** — it only uses it for one special case (auto-triggering a ZIP download when a unique-key search matches exactly one document). Do not rely on it for the document list; it may be empty even when there are more documents to fetch (see below). |
| `blockData` | The real payload: the full current block, regardless of the `length` that was requested. Its size is server-determined and varies (observed 96-153 records in a single sync, never a fixed number) — do not assume any particular size. This is what must be used to build the document list. |
| `continuationToken` | Opaque Cosmos DB continuation token for the **next** block (a JSON string wrapping a `compositeToken`/`resumeValues`/`rid`/`skipCount` structure). Must be stored and echoed back as `ContinuationToken` on the request for `blockIndex + 1`. |

## Algorithm our client implements

Mirrors DIAN's own frontend exactly (see `_get_documents_for_date_range` /
`_post_get_documents_page_token` in `models/dian_api_client.py`):

1. `block_index = 0`, `continuation_token = ''`.
2. POST with `start=0`, `blockIndex=block_index`,
   `IsNextPage = "true" if block_index > 0 else "false"`,
   `ContinuationToken = continuation_token`.
3. Read the block from `blockData` (not `data`). Save
   `continuation_token = response["continuationToken"]` for the *next*
   request, and add `len(blockData)` to a running `total_received` counter.
4. Stop when a request returns an empty `blockData` (no more results), or
   once `total_received >= recordsFiltered`. The stop condition is based on
   this real running total, not on an assumed block size — the actual size
   per block is server-determined and varies (see "Known caveats"), so
   `block_index * <some nominal size>` is not a reliable proxy for how many
   records have actually been received.
5. Otherwise `block_index += 1` and go to step 2.

## The bug this fixes

The original client implementation sent a **global, accumulating** `start`
(0, 50, 100, 150, ...), always `blockIndex=0`, always `IsNextPage="false"`,
and never sent `ContinuationToken`, while reading only `data`. This worked
by coincidence for requests that stayed inside the first 150-record block,
but the moment `start` crossed 150, the server had nothing left to serve at
that (now out-of-range) offset for a block it considered already exhausted:
`data` came back empty (or with a single stray record right at the
boundary), silently truncating the sync well before the real end of the
date range.

## Known caveats

- The per-block size is **not** fixed. A live sync of 854 records was
  served across 6 blocks of sizes 153, 150, 152, 153, 150, 96 — close to
  DIAN's nominal `maxItemCount = 150` but never exactly that, and the last
  block is simply whatever remains. Our client never assumes a block size
  (see "Algorithm"); do not reintroduce a `block_index * <fixed size>` stop
  condition, since a run of smaller-than-nominal blocks would make it stop
  before `recordsFiltered` is actually reached.
- DIAN's own frontend comments that its nominal block size "may be updated
  dynamically" (`maxItemCount = 150; // Se actualizará dinámicamente si es
  necesario`), even though no code path observed in the captured page ever
  changes it. This is consistent with the block size being decided
  server-side (Cosmos DB's own continuation/paging behavior) rather than
  being something the client controls or can rely on — if DIAN's backend
  behavior changes in a way our algorithm doesn't anticipate, re-verify
  against a live capture if `recordsFiltered` and the actual imported count
  ever diverge (see `dian.sync.unaccounted_count`).
- A `403` response means the session/anti-forgery token expired; a new
  `token_url` must be generated from the DIAN portal.
- Items with `DocumentTypeName == "Application response"` are legitimate
  block entries but are excluded from the imported document list (counted
  separately as `application_response_count`).

## How this was verified

Captured from a real, authenticated browser session against
`catalogo-vpfe.dian.gov.co`: the page HTML/JS (`/Document/Received`), the
exact `curl` request DIAN's own JS sends, its response headers, and the full
JSON response body. The pagination JS lives around the `maxItemCount`,
`blockCache`, and `continuationTokens` variables in that page's inline
`<script>` block, inside the DataTables `"ajax"` function for
`#tableDocuments`.
