# DIAN `POST /Document/GetDocumentsPageToken`

Internal, undocumented endpoint used by the DIAN catalog web app
(`catalogo-vpfe.dian.gov.co`) to list received/sent electronic documents on
the "Received documents" page (`/Document/Received`). It is what
`dian.api.client` (`models/dian_api_client.py`) calls to fetch the documents
received in a date range.

There is no official documentation: everything here was reverse-engineered
from live captures of DIAN's own frontend. **DIAN currently serves two
different contracts** for this endpoint, apparently rolled out per tenant:

| Contract | Captured | Status |
|---|---|---|
| **Token** (`hasMore` / `continuationToken`, documents in `data`) | 2026-10-05 | Current |
| **Block** (`blockIndex` / `IsNextPage`, documents in `blockData`) | 2026-09-23 | Legacy, still served to some tenants |

The client supports both (see [Protocol selection](#protocol-selection)) and
records the one it used on each synchronization (`dian.sync.dian_protocol`).

## Common to both contracts

- `POST`, body `application/x-www-form-urlencoded` (a JSON body is rejected),
  with `X-Requested-With: XMLHttpRequest` and the DIAN session cookies
  (`ASP.NET_SessionId`, `.AspNet.ApplicationCookie`, `ARRAffinity*`) obtained
  by following the token URL generated in the DIAN portal.
- `__RequestVerificationToken`: ASP.NET anti-forgery token (double-submit
  pattern). Must be the value of the hidden form field of the authenticated
  HTML page, not the cookie of the same name.
- Filters: `StartDate` / `EndDate` (`YYYY-MM-DD`), `DocumentTypeId=00` (all
  types), `Status=0` (all), `RadianStatus=0` (all), `FilterType=3` (fixed
  value, purpose unknown); `DocumentKey`, `SerieAndNumber`, `SenderCode`,
  `ReceiverCode` are free-text filters, always empty in our client.
- `ContinuationToken` (capital "C"): opaque Cosmos DB token returned by the
  previous response as `continuationToken`; empty for the first request.
- Response: JSON with `recordsTotal` / `recordsFiltered` (total for the
  range; they are equal when the free-text filters are empty) and the
  documents. Each document has the same fields in both contracts: `Id`
  (CUFE/CUDE), `DocumentTypeId`, `DocumentTypeName`, `SerieAndNumber`,
  `SenderCode`, `SenderName`, `ReceiverCode`, `ReceiverName`,
  `ReceptionDate` (`/Date(ms)/`), `StatusName`, `RadianStatusName`,
  `TotalAmount`, `TaxAmountIva5Percent`, `TaxAmountIva19Percent`,
  `TaxAmountIva`, `TaxAmountIca`, `TaxAmountIpc`, and more (see
  `_process_raw_documents`). The token contract adds a `TaxesDetail` object.
- Stored besides the above: `EmissionDate` (`emission_date`, a date: it is
  00:00 UTC of the emission day), `DocumentTypeId` (`type_code`) and `Status`
  (`status_code`). Events are recognized by `DocumentTypeId=96`.
- Taxes (capture 2026-10-20): `TaxAmountIva` carries the IVA total, but
  `TaxAmountIva5Percent` / `TaxAmountIva19Percent` and every `TaxesDetail`
  amount usually come as `0`. Each tax field takes the non-zero value of the
  top level or of `TaxesDetail`; the 5%/19% split is not guessed, the XML
  (`l10n_co_bloodo`) fills it.
- `StartDate` / `EndDate` filter by **emission** date, so the reception date
  of a document can fall after `EndDate`: already imported documents are
  detected by CUFE, never by date.
- `recordsFiltered` includes the `Application response` events (DIAN events
  such as acknowledgments), which the client counts in
  `application_response_count` and does not import.
- `403` means the session or the anti-forgery token expired: a new token URL
  must be generated in the DIAN portal.

## Token contract (current, 2026-10-05)

### Request

Same fields DIAN's own "Buscar" button sends:

```
DocumentKey=&SerieAndNumber=&SenderCode=&ReceiverCode=
&StartDate=2026-08-01&EndDate=2026-08-06
&DocumentTypeId=00&Status=0&RadianStatus=0&ReferencesType=00&FilterType=3
&SearchRequested=true&ContinuationToken=
&__RequestVerificationToken=<hidden form token>
```

| Field | Meaning |
|---|---|
| `SearchRequested` | `true`. New in this contract; without it (old body) the response is empty. |
| `ReferencesType` | `00` ("Todos..." in the page's "Tipo de referencia" select). New in this contract. |
| `ContinuationToken` | `""` for the first page, then the `continuationToken` of the previous response. |

No `draw`, `start`, `length`, `blockIndex` or `IsNextPage`.

### Response

```json
{
  "draw": 0, "start": 0,
  "recordsTotal": 29, "recordsFiltered": 29,
  "data": [ { "Id": "<CUFE>", "DocumentTypeName": "Factura electrónica", "...": "..." } ],
  "hasMore": false,
  "continuationToken": ""
}
```

| Field | Meaning |
|---|---|
| `data` | The documents of this page (up to 50 observed). |
| `recordsTotal` / `recordsFiltered` | **Count of this page, not of the whole range.** Capture 2026-10-06 (FD San Jorge, 2026-10-01 to 10-06): `50` / `50` with `hasMore: true`. The range total is the sum over the pages. |
| `hasMore` | `true` while there are more pages. |
| `continuationToken` | Token to request the next page: a JSON string, e.g. `[{"compositeToken":{"token":null,"range":{"min":"00BE…","max":"00D0…"}},"resumeValues":["2026-10-05T23:17:54.89964Z"],"rid":"YrlvAPkjDd0CXoYAAADmAQ==","skipCount":1}]` (results are ordered by reception date, newest first). Empty when `hasMore` is `false`. |

### Algorithm (`_get_documents_token_protocol`)

1. Request with `ContinuationToken=""`.
2. Read the documents from `data`.
3. Add the page's `recordsFiltered` to the range total. (If a page ever
   reports more records than it carries, it is taken as a range total and
   the largest reported value is used instead of the sum.)
4. If `hasMore` is `false` (or the page is empty), stop.
5. Otherwise request again with `ContinuationToken = continuationToken` and
   go to 2. Stops with a warning if the token comes empty or repeated, or
   after `DIAN_MAX_PAGES` pages.

**Confirmed (capture 2026-10-07, FD San Jorge, 3 consecutive pages):** the
body of every page is identical to the first one except `ContinuationToken`,
which is exactly the `continuationToken` string of the previous response
(compared byte by byte). The `__RequestVerificationToken` and the cookies
stay the same for the whole session, and so do the headers. The token is a
JSON array with `compositeToken`, `resumeValues` (reception date of the last
document served, decreasing page after page), `rid` and `skipCount`;
`compositeToken.token` is `null` on the first one and an opaque Cosmos DB
string afterwards. It is passed through as is, never parsed. A mismatch shows as a warning in the log ("received N records
but DIAN reported M") and in the sync's "Unaccounted Records".

## Block contract (legacy, 2026-09-23)

### Why blocks

The backend is Azure Cosmos DB, which only has forward continuation tokens,
no real offset. DIAN's backend serves results in **blocks of ~150 records**
and the caller walks them in order with `blockIndex` + continuation token.
DIAN's frontend (`maxItemCount = 150`, `blockCache`, `continuationTokens` in
the page's inline script) caches each block and slices the UI pages
(10/25/50/100 rows) from it in the browser.

The real block size is **not** fixed: a live sync of 854 records came in
blocks of 153, 150, 152, 153, 150 and 96. Never stop based on
`block_index * <fixed size>`.

### Request

| Field | Meaning |
|---|---|
| `draw` | DataTables echo, cosmetic. The client sends `blockIndex + 1`. |
| `start` | Offset within the requested block; always `0` (we request whole blocks). |
| `length` | UI page size (`50`); does **not** limit `blockData`. |
| `blockIndex` | 0-based index of the requested block. |
| `IsNextPage` | `"false"` for block 0, `"true"` for the following ones. |
| `ContinuationToken` | `""` for block 0, then the `continuationToken` returned by the **previous** block (sending the current block's own token, or none past block 0, returns empty blocks). |

### Response

```json
{
  "draw": 1, "start": 0,
  "recordsTotal": 388, "recordsFiltered": 388,
  "data": [ "/* `length`-sized slice, NOT the document list */" ],
  "blockData": [ "/* the whole block, size varies (96-153) */" ],
  "continuationToken": "[{\"compositeToken\": ... }]"
}
```

`blockData` is the document list. `data` is only a `length`-sized slice that
DIAN's own frontend uses for one special case (auto-download on a unique-key
search); it may be empty while there are more documents.

### Algorithm (`_get_documents_block_protocol`)

1. `block_index = 0`, `continuation_token = ""`.
2. Request with `blockIndex=block_index`, `IsNextPage = block_index > 0`,
   `ContinuationToken = continuation_token`.
3. Read the documents from `blockData`; keep `continuationToken` for the
   next request; add `len(blockData)` to `total_received`.
4. Stop when `blockData` is empty or `total_received >= recordsFiltered`
   (or after `DIAN_MAX_PAGES` blocks); otherwise `block_index += 1` and go
   to 2.

An earlier implementation sent a global, accumulating `start`
(0, 50, 100, ...), always `blockIndex=0`, never `ContinuationToken`, and read
`data`: it silently truncated every sync once `start` crossed the first block.

## Differences between the contracts

| | Token (current) | Block (legacy) |
|---|---|---|
| Pagination fields sent | `ContinuationToken` only | `draw`, `start`, `length`, `blockIndex`, `IsNextPage`, `ContinuationToken` |
| New fields sent | `SearchRequested=true`, `ReferencesType=00` | — |
| Documents in | `data` | `blockData` (`data` is a UI slice, ignore it) |
| End of pagination | `hasMore == false` | empty `blockData` or `recordsFiltered` reached |
| `recordsFiltered` | count of the page (range total = sum of pages) | total of the range |
| Page size | 50 | ~150 per block, varies (96–153) |
| `draw` in response | `0` | echo of the request |
| Extra item fields | `TaxesDetail` | — |
| Old body sent to a token tenant | answers `recordsFiltered: 0`, empty `data` | — |
| New body sent to a block tenant | not observed | — |

## Protocol selection

System parameter `l10n_co_dian_invoice_synchronizer.documents_protocol`
(Settings › Technical › System Parameters):

| Value | Behavior |
|---|---|
| `auto` (default, or parameter missing) | Sends the first request with the token contract. If the response has `blockData`, restarts with the block contract. If it returns no records, retries with the block contract and uses it if that one returns records. Otherwise continues with the token contract. |
| `token` | Token contract only. |
| `block` | Block contract only. |

The contract used is stored on each synchronization (`dian.sync.dian_protocol`,
shown in the synchronization form) and logged (`protocol=` in the
`DIAN GetDocumentsPageToken` log lines). In `auto`, a range that is really
empty costs one extra request (the block retry).

## How this was verified

- **Block contract (2026-09-23):** authenticated browser session; page
  HTML/JS of `/Document/Received` (kept in `tmp/received.html`), the exact
  `curl` request DIAN's JS sends and its full JSON response (`tmp/`).
- **Token contract:** the `curl` request of the "Buscar" button and its JSON
  response on two tenants: OD. ONE. (2026-10-05, 29 records, one page) and
  FD San Jorge (2026-10-06, first page of 50 with `hasMore: true`). FD San
  Jorge was served the block contract before; both tenants now get the token
  contract. The page JS of this version has not been captured yet.

Both contracts are covered by mocked tests in
`tests/test_dian_api_client.py`. If DIAN changes the endpoint again,
re-capture the request/response the same way and compare with this document;
`dian.sync.unaccounted_count` != 0 is the usual first symptom.
