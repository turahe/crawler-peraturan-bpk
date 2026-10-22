# Data model

The ORM schema is declared in `src/playright_peraturan_bpk/models.py`; Alembic migrations under `migrations/versions/` are the source of truth for deployed schema changes.

| Entity | Purpose | Relationships |
| --- | --- | --- |
| `subjects` | BPK subject/theme index entries | Many-to-many with regulations; may own subject crawl jobs |
| `regulations` | Regulation identity, title, year, status, and detail URL | Many-to-many with subjects; has crawl jobs, files, metadata, and regulation relations |
| `regulation_subjects` | Join table for subject classification | One row per regulation/subject pair |
| `crawl_jobs` | Stage, status, attempts, errors, and completion timestamp | Optionally references a subject or regulation |
| `document_files` | Downloaded file identity, source, checksum, storage, and MIME details | Belongs optionally to a regulation; has pages and associated metadata |
| `document_metadata` | Fields parsed from a regulation detail page | Unique per regulation and optionally linked to a document file |
| `document_pages` | Extracted text by page | Belongs to a document file; has chunks |
| `document_chunks` | Text segments and JSON metadata | Belongs to a document page |
| `regulation_relations` | Typed relation between two regulations | References source and target regulations |

Most entities have an integer primary key, a UUID, and creation/update timestamps. Source IDs and URLs are constrained to prevent duplicate subject/regulation identities. `document_metadata` can exist for a regulation that has no downloadable PDF; the file link is nullable. File names are generated UUIDs while original source names are preserved in `original_file_name`.

The chunk metadata column uses PostgreSQL JSONB in PostgreSQL and a generic JSON type elsewhere. Primary keys use PostgreSQL-friendly `BigInteger` with an SQLite `Integer` variant for lightweight tests.

For a complete ER overview, see the schema diagram in [erd.md](erd.md) and the model declarations in `models.py`.
