# Entity relationship diagram

The schema below reflects the ORM declarations in `src/playright_peraturan_bpk/models.py` and the Alembic migrations under `migrations/versions/`, which are the source of truth for deployed schema changes.

```mermaid

erDiagram
    SUBJECTS ||--o{ REGULATION_SUBJECTS : classifies
    REGULATIONS ||--o{ REGULATION_SUBJECTS : categorized_as
    REGULATIONS ||--o{ CRAWL_JOBS : crawled_by
    REGULATIONS ||--o{ DOCUMENT_FILES : has
    DOCUMENT_FILES ||--o{ DOCUMENT_METADATA : described_by
    DOCUMENT_FILES ||--o{ DOCUMENT_PAGES : extracted_into
    DOCUMENT_PAGES ||--o{ DOCUMENT_CHUNKS : split_into
    REGULATIONS ||--o{ REGULATION_RELATIONS : source
    REGULATIONS ||--o{ REGULATION_RELATIONS : target

    SUBJECTS {
        bigint id PK
        uuid uuid
        varchar source_theme_id UK
        varchar name
        text source_url
        timestamp created_at
        timestamp updated_at
    }
    REGULATIONS {
        bigint id PK
        uuid uuid
        varchar source_id UK
        varchar document_number
        varchar title
        int year
        text detail_url UK
        varchar status
        timestamp created_at
        timestamp updated_at
    }
    REGULATION_SUBJECTS {
        bigint id PK
        uuid uuid
        bigint regulation_id FK
        bigint subject_id FK
        timestamp created_at
        timestamp updated_at
    }
    CRAWL_JOBS {
        bigint id PK
        uuid uuid
        bigint regulation_id FK "nullable for subject jobs"
        bigint subject_id FK
        varchar stage
        varchar status
        int attempts
        text error_message
        timestamp completed_at
        timestamp created_at
        timestamp updated_at
    }
    DOCUMENT_FILES {
        bigint id PK
        uuid uuid
        bigint regulation_id FK "nullable until regulation is matched"
        varchar hash
        varchar file_name "UUID v4 plus extension"
        varchar original_file_name
        varchar file_extension
        varchar disk
        varchar mime_type
        bigint size
        text source_url
        text storage_key
        text storage_path
        varchar checksum_sha256
        timestamp downloaded_at
        timestamp created_at
        timestamp updated_at
    }
    DOCUMENT_METADATA {
        bigint id PK
        bigint document_file_id FK
        bigint regulation_id FK
        varchar document_type
        varchar title
        varchar teu
        varchar number
        varchar form
        varchar form_short
        int year
        varchar place_of_enactment
        date enactment_date
        date promulgation_date
        date effective_date
        text source
        varchar subject
        varchar status
        varchar language
        varchar location
        varchar field
        varchar alias
        timestamp created_at
        timestamp updated_at
    }
    DOCUMENT_PAGES {
        bigint id PK
        uuid uuid
        bigint document_file_id FK
        int page_number
        text content
        timestamp created_at
        timestamp updated_at
    }
    DOCUMENT_CHUNKS {
        bigint id PK
        uuid uuid
        bigint document_page_id FK
        text content
        jsonb metadata
        timestamp created_at
        timestamp updated_at
    }
    REGULATION_RELATIONS {
        bigint id PK
        uuid uuid
        bigint source_regulation_id FK
        bigint target_regulation_id FK
        varchar relation_type
        timestamp created_at
        timestamp updated_at
    }
```

## Entity notes

`document_files` records one row per successfully downloaded file, with a canonical UUID v4 filename (`<uuid>.<extension>`) so an original source name cannot overwrite a previously stored file. `file_name` stores the generated filename; `original_file_name` preserves the name from the HTTP `Content-Disposition` header or source URL. `uuid` stores that same UUID as a database UUID value.

`document_metadata` can exist for a regulation that has no downloadable PDF, so the link to `document_file` is nullable. `crawl_jobs` optionally references a subject or a regulation; the `regulation_id` is nullable for subject jobs.

See [Data model](data-model.md) for the entity-by-entity summary and [Downloaded file storage metadata](../README.md#downloaded-file-storage-metadata) for the `document_files` column reference.
