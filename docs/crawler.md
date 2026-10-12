# Crawler workflow

The crawler targets `https://peraturan.bpk.go.id/Subjek` and runs from `BPKCrawler.run()` in `src/playright_peraturan_bpk/main.py`.

## Collection stages

1. Fetch the subject index and extract each subject's theme ID, name, and search URL.
2. Upsert subjects and track their crawl state.
3. Visit each subject search and follow pagination links. Extract regulation IDs, titles, document numbers, years, statuses, and detail URLs; associate regulations with subjects.
4. Visit regulation detail pages and parse the labeled metadata fields, including Indonesian dates.
5. Find PDF links, download files, persist file metadata, and optionally upload the file to RustFS.
6. Record completed or failed jobs and print a summary of subjects, regulations, failures, and PDFs.

## Requests and failures

Requests use a browser-like user agent and a 30-second default timeout. The crawler retries transient HTTP failures up to three attempts, with exponential retry delay. `CRAWLER_REQUEST_DELAY_SECONDS` controls the minimum interval between requests and defaults to `0.5` seconds. Non-retryable HTTP errors are surfaced to the relevant crawl stage, which records failure state where possible.

## PDF naming and durability

Each successful download is published under a generated UUID v4 filename with its lowercase extension. The original source filename is retained separately. The crawler computes SHA-256, byte size, MIME type, source URL, and download time. It writes to a temporary file before publishing the final path; metadata is persisted transactionally, and a newly published local file is removed if its database write fails. UUID conflicts are retried.

PDFs are stored under `data/pdf` by default. If RustFS credentials and endpoint are configured, the crawler uploads the file and records its object key. RustFS is an optional secondary storage target; its use is controlled by the `RUSTFS_*` environment variables.

## Crawl state

`crawl_jobs` records subject and regulation stages, status, attempts, error text, and completion time. The implementation persists progress as it processes records, so a failure is visible without losing all prior crawl work. On a later run, existing subjects and regulations are updated or reused by their source identifiers.
