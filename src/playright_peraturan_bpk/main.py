import hashlib
import mimetypes
import os
import re
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from email.message import Message
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import CrawlJob, DocumentFile, DocumentMetadata, Regulation, Subject
from .tasks import crawl_regulation

try:
    import boto3
except ImportError:  # pragma: no cover - optional dependency for RustFS uploads
    boto3 = None

BASE_URL = "https://peraturan.bpk.go.id"
TARGET_URL = f"{BASE_URL}/Subjek"
OUTPUT_DIR = Path("data")
PDF_DIR = OUTPUT_DIR / "pdf"
PDF_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DownloadedFileMetadata:
    checksum_sha256: str
    downloaded_at: datetime
    file_extension: str
    mime_type: str
    original_file_name: str
    size: int
    source_url: str


@dataclass(frozen=True)
class RegulationPageMetadata:
    document_type: str | None = None
    title: str | None = None
    teu: str | None = None
    number: str | None = None
    form: str | None = None
    form_short: str | None = None
    year: int | None = None
    place_of_enactment: str | None = None
    enactment_date: date | None = None
    promulgation_date: date | None = None
    effective_date: date | None = None
    source: str | None = None
    subject: str | None = None
    status: str | None = None
    language: str | None = None
    location: str | None = None
    field: str | None = None
    alias: str | None = None


@dataclass(frozen=True)
class CrawlSummary:
    subjects_discovered: int = 0
    subjects_completed: int = 0
    regulations_discovered: int = 0
    regulations_completed: int = 0
    failed_entities: int = 0
    pdfs_downloaded: int = 0

    @property
    def entities_completed(self) -> int:
        return self.subjects_completed + self.regulations_completed


class _RequestRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_request_at = 0.0

    def wait(self, interval_seconds: float) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next_request_at - now)
            if delay:
                time.sleep(delay)
            self._next_request_at = time.monotonic() + interval_seconds


class BPKCrawler:
    def __init__(
        self,
        base_url: str = BASE_URL,
        target_url: str | None = None,
        output_dir: str | Path = OUTPUT_DIR,
        session_factory: Callable[[], Session] | None = None,
        request_delay_seconds: float | None = None,
        retry_delay_seconds: float = 1.0,
        max_attempts: int = 3,
        request_rate_limiter: _RequestRateLimiter | None = None,
    ) -> None:
        self.base_url = base_url
        self.target_url = target_url or f"{self.base_url}/Subjek"
        self.output_dir = Path(output_dir)
        self.pdf_dir = self.output_dir / "pdf"
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.session_factory = session_factory or SessionLocal
        self.rustfs_endpoint = os.getenv("RUSTFS_ENDPOINT")
        self.rustfs_access_key = os.getenv("RUSTFS_ACCESS_KEY")
        self.rustfs_secret_key = os.getenv("RUSTFS_SECRET_KEY")
        self.rustfs_bucket = os.getenv("RUSTFS_BUCKET", "documents")
        self.rustfs_prefix = os.getenv("RUSTFS_PREFIX", "pdf")
        self.request_delay_seconds = (
            max(0.0, float(os.getenv("CRAWLER_REQUEST_DELAY_SECONDS", "0.5")))
            if request_delay_seconds is None
            else max(0.0, request_delay_seconds)
        )
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.max_attempts = min(3, max(1, max_attempts))
        self.crawler_mode = os.getenv("CRAWLER_MODE", "inline").lower()
        self.thread_count = max(1, int(os.getenv("CRAWLER_THREADS", "4")))
        self._request_rate_limiter = request_rate_limiter or _RequestRateLimiter()
        self._last_request_attempts = 0
        self._last_request_error: str | None = None
        self._pdfs_downloaded = 0

    @staticmethod
    def user_agent() -> str:
        return (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

    def create_requests_sessions(self, n: int = 4) -> list[requests.Session]:
        sessions: list[requests.Session] = []
        for _ in range(n):
            session = requests.Session()
            session.headers.update({"User-Agent": self.user_agent()})
            sessions.append(session)
        return sessions

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def _get(self, url: str, timeout: int = 30, stream: bool = False) -> requests.Response:
        last_error: requests.RequestException | None = None
        retryable_statuses = {429, 500, 502, 503, 504}
        for attempt in range(1, self.max_attempts + 1):
            self._last_request_attempts = attempt
            self._request_rate_limiter.wait(self.request_delay_seconds)
            response: requests.Response | None = None
            try:
                response = requests.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": self.user_agent()},
                    stream=stream,
                )
                if response.status_code in retryable_statuses and attempt < self.max_attempts:
                    response.close()
                    time.sleep(self.retry_delay_seconds * (2 ** (attempt - 1)))
                    continue
                if response.status_code >= 400 and response.status_code not in retryable_statuses:
                    response.raise_for_status()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                if response is not None:
                    response.close()
                    if response.status_code >= 400 and response.status_code not in retryable_statuses:
                        raise
                last_error = exc
                if attempt == self.max_attempts:
                    break
                time.sleep(self.retry_delay_seconds * (2 ** (attempt - 1)))

        assert last_error is not None
        raise last_error

    def crawl_bpk_subjects(self) -> list[dict[str, str]]:
        response = self._get(self.target_url)
        try:
            soup = BeautifulSoup(response.text, "html.parser")
        finally:
            response.close()

        subjects_by_id: dict[str, dict[str, str]] = {}
        for anchor in soup.select('a[href*="/Search?tema="]'):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            search_url = urljoin(self.base_url, href)
            theme_id = parse_qs(urlsplit(search_url).query).get("tema", [""])[0]
            if not theme_id:
                continue
            name = re.sub(r"\s*\[\s*[\d.,]+\s*\]\s*$", "", anchor.get_text(" ", strip=True)).strip()
            if not name:
                continue
            subjects_by_id[theme_id] = {
                "source_theme_id": theme_id,
                "name": name,
                "search_url": search_url,
            }
        if not subjects_by_id:
            raise ValueError(f"No subjects found on {self.target_url}")
        return list(subjects_by_id.values())

    def crawl_bpk_details(self, url: str) -> str:
        self._last_request_error = None
        try:
            response = self._get(url)
        except requests.RequestException as exc:
            self._last_request_error = str(exc)
            print(f"Failed to fetch page: {url}. Error: {exc}")
            return ""
        try:
            return response.text
        finally:
            response.close()

    @staticmethod
    def extract_regulations(html: str, base_url: str = BASE_URL) -> list[dict[str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        regulations: dict[str, dict[str, str]] = {}
        anchors = list(soup.select(".card .col-lg-10.fs-2.fw-bold a[href*='/Details/']"))
        if not anchors:
            anchors = [
                anchor
                for anchor in soup.select("a[href*='/Details/']")
                if "text-danger" not in anchor.get_attribute_list("class")
            ]
        for anchor in anchors:
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            detail_url = urljoin(base_url, href)
            match = re.search(r"/Details/(\d+)(?:/[^/?#]*)?", urlsplit(detail_url).path, re.IGNORECASE)
            if match is None:
                continue
            source_id = match.group(1)
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if title and source_id not in regulations:
                regulations[source_id] = {
                    "source_id": source_id,
                    "title": title,
                    "detail_url": detail_url,
                }
        return list(regulations.values())

    @staticmethod
    def _search_page_urls(html: str, current_url: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        page_urls = [current_url]
        for anchor in soup.select(".pagination a[href], ul.pagination a[href]"):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            candidate = urljoin(current_url, href)
            if urlsplit(candidate).path.rstrip("/").lower().endswith("/search"):
                page_urls.append(candidate)
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if isinstance(href, str) and "tema" in parse_qs(urlsplit(href).query):
                candidate = urljoin(current_url, href)
                if urlsplit(candidate).path.rstrip("/").lower().endswith("/search"):
                    page_urls.append(candidate)
        return list(dict.fromkeys(page_urls))

    def crawl_search_pages(self, search_url: str) -> list[dict[str, str]]:
        regulations: dict[str, dict[str, str]] = {}
        pending_urls = [search_url]
        visited_urls: set[str] = set()
        while pending_urls:
            page_url = pending_urls.pop(0)
            page_key = self._canonical_search_url(page_url)
            if page_key in visited_urls:
                continue
            visited_urls.add(page_key)
            response = self._get(page_url)
            try:
                html = response.text
            finally:
                response.close()

            for regulation in self.extract_regulations(html, self.base_url):
                regulations.setdefault(regulation["source_id"], regulation)

            for candidate in self._search_page_urls(html, page_url):
                candidate_key = self._canonical_search_url(candidate)
                if candidate_key not in visited_urls and all(
                    self._canonical_search_url(pending) != candidate_key for pending in pending_urls
                ):
                    pending_urls.append(candidate)

        return list(regulations.values())

    @staticmethod
    def _canonical_search_url(url: str) -> str:
        parsed = urlsplit(url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if not (key == "p" and value == "1")
        ]
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))

    def _save_subject(self, item: dict[str, str]) -> int:
        with self.session_factory() as session, session.begin():
            subject = session.scalar(select(Subject).where(Subject.source_theme_id == item["source_theme_id"]))
            if subject is None:
                subject = Subject(
                    source_theme_id=item["source_theme_id"],
                    name=item["name"],
                    source_url=item["search_url"],
                )
                session.add(subject)
                session.flush()
            else:
                subject.name = item["name"]
                subject.source_url = item["search_url"]
            self._set_crawl_status(
                session,
                subject_id=subject.id,
                stage="subject",
                status="subjek_extracted",
            )
            return subject.id

    @staticmethod
    def _set_crawl_status(
        session: Session,
        *,
        stage: str,
        status: str,
        subject_id: int | None = None,
        regulation_id: int | None = None,
        error_message: str | None = None,
        attempts: int | None = None,
    ) -> CrawlJob:
        filters = [CrawlJob.subject_id == subject_id, CrawlJob.regulation_id == regulation_id]
        job = session.scalar(select(CrawlJob).where(*filters).order_by(CrawlJob.id.desc()).limit(1))
        if job is None:
            job = CrawlJob(subject_id=subject_id, regulation_id=regulation_id, attempts=0)
            session.add(job)
        job.stage = stage
        job.status = status
        job.error_message = error_message
        if attempts is not None:
            job.attempts = attempts
        job.completed_at = datetime.now(UTC) if status in {"completed", "failed"} else None
        return job

    def _save_regulations(
        self,
        subject_id: int,
        items: list[dict[str, str]],
    ) -> list[int]:
        regulation_ids: list[int] = []
        with self.session_factory() as session, session.begin():
            subject = session.get(Subject, subject_id)
            if subject is None:
                raise LookupError(f"Subject {subject_id} disappeared while saving regulations")
            for item in items:
                regulation = session.scalar(select(Regulation).where(Regulation.source_id == item["source_id"]))
                if regulation is None:
                    regulation = Regulation(
                        source_id=item["source_id"],
                        title=item["title"],
                        detail_url=item["detail_url"],
                    )
                    session.add(regulation)
                    session.flush()
                else:
                    regulation.title = item["title"]
                    regulation.detail_url = item["detail_url"]
                if subject not in regulation.subjects:
                    regulation.subjects.append(subject)
                self._set_crawl_status(
                    session,
                    regulation_id=regulation.id,
                    stage="regulation_list",
                    status="peraturan_list_extracted",
                )
                regulation_ids.append(regulation.id)
            self._set_crawl_status(
                session,
                subject_id=subject_id,
                stage="subject",
                status="peraturan_list_extracted",
            )
        return regulation_ids

    @staticmethod
    def _parse_indonesian_date(value: str) -> date | None:
        normalized = " ".join(value.strip().replace(",", " ").split()).casefold()
        if not normalized:
            return None

        months = {
            "januari": 1,
            "februari": 2,
            "maret": 3,
            "april": 4,
            "mei": 5,
            "juni": 6,
            "juli": 7,
            "agustus": 8,
            "september": 9,
            "oktober": 10,
            "november": 11,
            "desember": 12,
        }
        parts = normalized.split()
        if len(parts) == 3 and parts[1] in months:
            try:
                return date(int(parts[2]), months[parts[1]], int(parts[0]))
            except ValueError:
                return None

        for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(normalized, date_format).date()
            except ValueError:
                continue
        return None

    @classmethod
    def parse_detail_metadata(cls, html: str) -> RegulationPageMetadata | None:
        label_fields = {
            "tipe dokumen": "document_type",
            "judul": "title",
            "t.e.u.": "teu",
            "teu": "teu",
            "nomor": "number",
            "bentuk": "form",
            "bentuk singkat": "form_short",
            "tahun": "year",
            "tempat penetapan": "place_of_enactment",
            "tanggal penetapan": "enactment_date",
            "tanggal pengundangan": "promulgation_date",
            "tanggal berlaku": "effective_date",
            "sumber": "source",
            "subjek": "subject",
            "status": "status",
            "bahasa": "language",
            "lokasi": "location",
            "bidang": "field",
            "alias": "alias",
        }
        soup = BeautifulSoup(html, "html.parser")
        values: dict[str, str] = {}
        date_values: dict[str, date | None] = {}
        year: int | None = None
        for label in soup.select(".row .col-lg-3.fw-bold"):
            normalized_label = " ".join(label.get_text(" ", strip=True).split()).casefold()
            field_name = label_fields.get(normalized_label)
            row = label.find_parent(class_="row")
            value_node = row.select_one(".col-lg-9") if row else None
            if field_name is None or value_node is None:
                continue

            value = " ".join(value_node.get_text(" ", strip=True).split())
            if not value:
                continue
            if field_name == "year":
                try:
                    year = int(value)
                except ValueError:
                    continue
            elif field_name in {"enactment_date", "promulgation_date", "effective_date"}:
                date_values[field_name] = cls._parse_indonesian_date(value)
            else:
                values[field_name] = value

        if not values and year is None and not date_values:
            return None
        return RegulationPageMetadata(
            document_type=values.get("document_type"),
            title=values.get("title"),
            teu=values.get("teu"),
            number=values.get("number"),
            form=values.get("form"),
            form_short=values.get("form_short"),
            year=year,
            place_of_enactment=values.get("place_of_enactment"),
            enactment_date=date_values.get("enactment_date"),
            promulgation_date=date_values.get("promulgation_date"),
            effective_date=date_values.get("effective_date"),
            source=values.get("source"),
            subject=values.get("subject"),
            status=values.get("status"),
            language=values.get("language"),
            location=values.get("location"),
            field=values.get("field"),
            alias=values.get("alias"),
        )

    def _persist_regulation_metadata(
        self,
        regulation_id: int,
        metadata: RegulationPageMetadata,
    ) -> None:
        with self.session_factory() as session, session.begin():
            regulation = session.get(Regulation, regulation_id)
            if regulation is None:
                raise LookupError(f"Regulation {regulation_id} disappeared before metadata persistence")
            metadata_row = session.scalar(
                select(DocumentMetadata).where(DocumentMetadata.regulation_id == regulation_id)
            )
            if metadata_row is None:
                metadata_row = DocumentMetadata(regulation_id=regulation_id, **asdict(metadata))
                session.add(metadata_row)
            else:
                for name, value in asdict(metadata).items():
                    setattr(metadata_row, name, value)

            first_file = session.scalar(
                select(DocumentFile).where(DocumentFile.regulation_id == regulation_id).order_by(DocumentFile.id)
            )
            if first_file is not None:
                metadata_row.document_file_id = first_file.id
            regulation.document_number = metadata.number or regulation.document_number
            regulation.title = metadata.title or regulation.title
            regulation.year = metadata.year or regulation.year
            regulation.status = metadata.status or regulation.status

    def _persist_storage_key(self, file_path: Path, storage_key: str) -> None:
        with self.session_factory() as session, session.begin():
            file_row = session.scalar(select(DocumentFile).where(DocumentFile.storage_path == str(file_path.resolve())))
            if file_row is None:
                raise LookupError(f"No document file row for {file_path}")
            file_row.storage_key = storage_key

    def download_pdfs(
        self,
        url: str,
        page_html: str | None = None,
        regulation_id: int | None = None,
        detail_metadata: RegulationPageMetadata | None = None,
    ) -> list[str]:
        if page_html is None:
            try:
                response = self._get(url)
                try:
                    page_html = response.text
                finally:
                    response.close()
            except requests.RequestException as exc:
                print(f"Failed to fetch page: {url}. Error: {exc}")
                return []

        if detail_metadata is None:
            detail_metadata = self.parse_detail_metadata(page_html)
        if detail_metadata is not None and regulation_id is not None:
            self._persist_regulation_metadata(regulation_id, detail_metadata)
        soup = BeautifulSoup(page_html, "html.parser")
        pdfs: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href")
            if isinstance(href, str) and urlsplit(href).path.lower().endswith(".pdf"):
                pdfs.append(urljoin(url, href))

        print(pdfs)
        successful_downloads: list[str] = []
        failed_downloads: list[str] = []
        for pdf in pdfs:
            if (
                self.download_pdf(
                    pdf,
                    regulation_id=regulation_id,
                    include_payload=False,
                )
                is None
            ):
                failed_downloads.append(pdf)
            else:
                successful_downloads.append(pdf)
                self._pdfs_downloaded += 1

        # A second persistence links metadata to the first file now that it exists.
        if detail_metadata is not None and regulation_id is not None:
            self._persist_regulation_metadata(regulation_id, detail_metadata)

        if failed_downloads:
            raise RuntimeError(f"Failed to download {len(failed_downloads)} of {len(pdfs)} PDFs for {url}")

        return successful_downloads

    @staticmethod
    def find_next_page(soup: BeautifulSoup) -> str | None:
        next_page = soup.find("a", class_="next")
        if next_page:
            href = next_page.get("href")
            return href if isinstance(href, str) else None
        return None

    def _upload_to_rustfs(self, file_path: Path) -> str | None:
        if not self.rustfs_endpoint or boto3 is None:
            return None

        if not all((self.rustfs_access_key, self.rustfs_secret_key)):
            return None

        remote_key = str(Path(self.rustfs_prefix.strip("/")) / file_path.name)
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=self.rustfs_endpoint,
                aws_access_key_id=self.rustfs_access_key,
                aws_secret_access_key=self.rustfs_secret_key,
                region_name="us-east-1",
                verify=False,
            )
            try:
                s3.head_bucket(Bucket=self.rustfs_bucket)
            except Exception as exc:
                error_response = getattr(exc, "response", None) or {}
                error_code = error_response.get("Error", {}).get("Code")
                if error_code not in {"404", "NoSuchBucket", "NotFound"}:
                    raise
                s3.create_bucket(Bucket=self.rustfs_bucket)

            s3.upload_file(str(file_path), self.rustfs_bucket, remote_key)
            return remote_key
        except Exception as exc:  # pragma: no cover - depends on external S3-compatible storage
            print(f"Failed to upload PDF to RustFS: {exc}")
            return None

    @staticmethod
    def _original_filename(url: str, headers: Mapping[str, str]) -> str:
        disposition = Message()
        disposition["content-disposition"] = headers.get("Content-Disposition", "")
        filename = disposition.get_filename()
        if not filename:
            filename = Path(unquote(urlsplit(url).path)).name
        return Path(unquote(filename).replace("\\", "/")).name or "download"

    @staticmethod
    def _is_uuid_collision(exc: IntegrityError) -> bool:
        original = exc.orig
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", "")
        message = str(original).lower()
        return constraint_name == "uq_document_files_uuid" or "document_files.uuid" in message

    @staticmethod
    def _is_checksum_collision(exc: IntegrityError) -> bool:
        original = exc.orig
        constraint_name = getattr(getattr(original, "diag", None), "constraint_name", "")
        message = str(original).lower()
        return (
            constraint_name == "uq_document_files_checksum_sha256"
            or "uq_document_files_checksum_sha256" in message
            or "unique constraint failed: document_files.checksum_sha256" in message
        )

    def _persist_file(
        self,
        temporary_path: Path,
        metadata: DownloadedFileMetadata,
        regulation_id: int | None = None,
    ) -> Path:
        for _ in range(5):
            file_uuid = uuid.uuid4()
            extension = metadata.file_extension
            file_name = f"{file_uuid}{extension}"
            file_path = self.pdf_dir / file_name

            if file_path.exists():
                continue

            linked_file = False
            try:
                with self.session_factory() as session, session.begin():
                    # A same-directory hard link atomically publishes the complete file without overwriting.
                    os.link(temporary_path, file_path)
                    linked_file = True
                    file_row = DocumentFile(
                        uuid=file_uuid,
                        regulation_id=regulation_id,
                        hash=metadata.checksum_sha256,
                        file_name=file_name,
                        original_file_name=metadata.original_file_name,
                        file_extension=extension,
                        disk="local",
                        mime_type=metadata.mime_type,
                        size=metadata.size,
                        source_url=metadata.source_url,
                        storage_key=None,
                        storage_path=str(file_path.resolve()),
                        checksum_sha256=metadata.checksum_sha256,
                        downloaded_at=metadata.downloaded_at,
                    )
                    session.add(file_row)
                    session.flush()
                return file_path
            except FileExistsError:
                continue
            except IntegrityError as exc:
                if linked_file:
                    file_path.unlink(missing_ok=True)
                if self._is_uuid_collision(exc):
                    continue
                if self._is_checksum_collision(exc):
                    with self.session_factory() as session:
                        existing = session.scalar(
                            select(DocumentFile).where(DocumentFile.checksum_sha256 == metadata.checksum_sha256)
                        )
                        if existing is not None:
                            existing_path = (
                                Path(existing.storage_path)
                                if existing.storage_path
                                else self.pdf_dir / (existing.file_name or "")
                            )
                            if not existing_path.is_file() and existing.file_name:
                                with suppress(FileExistsError):
                                    os.link(temporary_path, existing_path)
                            if existing_path.is_file():
                                print(
                                    "PDF with SHA-256 "
                                    f"{metadata.checksum_sha256} already exists; reusing {existing_path}"
                                )
                                return existing_path
                    raise RuntimeError(
                        "A duplicate PDF checksum was detected, but its existing file could not be reused"
                    ) from exc
                raise
            except Exception:
                if linked_file:
                    file_path.unlink(missing_ok=True)
                raise

        raise RuntimeError("Unable to allocate a unique UUID filename after 5 attempts")

    @staticmethod
    def _resolve_download_url(base_url: str, href: str) -> str:
        resolved_url = urljoin(base_url, href.strip())
        parsed_url = urlsplit(resolved_url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
        ):
            raise ValueError(f"Invalid PDF download URL: {href!r}")
        try:
            _port = parsed_url.port
        except ValueError as exc:
            raise ValueError(f"Invalid port in PDF download URL: {resolved_url!r}") from exc
        return resolved_url

    @staticmethod
    def _requires_pdf_validation(mime_type: str, extension: str) -> bool:
        return extension == ".pdf" or mime_type in {"application/pdf", "application/x-pdf"}

    @staticmethod
    def _validate_pdf(path: Path) -> None:
        try:
            with PdfReader(path) as reader:
                if not reader.is_encrypted and len(reader.pages) < 1:
                    raise ValueError("PDF has no pages")
        except PdfReadError as exc:
            raise ValueError(f"Downloaded file is not a valid PDF: {exc}") from exc

    def download_pdf(
        self,
        url: str,
        regulation_id: int | None = None,
        *,
        include_payload: bool = True,
    ) -> bytes | bool | None:
        temporary_path: Path | None = None
        file_path: Path | None = None
        response: requests.Response | None = None
        try:
            response = self._get(url, timeout=60, stream=True)

            headers = response.headers
            mime_type = headers.get("Content-Type", "").split(";", 1)[0].strip()

            if mime_type == "text/html":
                html = response.text
                response_url = getattr(response, "url", None) or url
                response.close()
                response = None

                soup = BeautifulSoup(html, "html.parser")
                download_anchor = soup.select_one("a.read-btn-download[href]")
                href = download_anchor.get("href") if download_anchor else None
                if not isinstance(href, str) or not href.strip():
                    raise ValueError(f"HTML response for {url} has no read-btn-download link")

                target_url = self._resolve_download_url(response_url, href)
                response = self._get(target_url, timeout=60, stream=True)
                headers = response.headers
                mime_type = headers.get("Content-Type", "").split(";", 1)[0].strip()
                if mime_type == "text/html":
                    raise ValueError(f"Following read-btn-download from {url} returned HTML, not a file")
                url = target_url

            original_filename = self._original_filename(url, headers)
            mime_type = mime_type or mimetypes.guess_type(original_filename)[0] or "application/octet-stream"
            extension = Path(original_filename).suffix.lower()
            if not re.fullmatch(r"\.[a-z0-9]{1,16}", extension):
                extension = mimetypes.guess_extension(mime_type) or ""

            self.pdf_dir.mkdir(parents=True, exist_ok=True)
            checksum = hashlib.sha256()
            payload = bytearray() if include_payload else None
            payload_size = 0
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=self.pdf_dir,
                prefix=".download-",
                suffix=".part",
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                chunks = response.iter_content(chunk_size=64 * 1024)
                for chunk in chunks:
                    if not chunk:
                        continue
                    temporary_file.write(chunk)
                    checksum.update(chunk)
                    payload_size += len(chunk)
                    if payload is not None:
                        payload.extend(chunk)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            if temporary_path is None:
                raise RuntimeError("PDF download did not create a temporary file")
            if self._requires_pdf_validation(mime_type, extension):
                self._validate_pdf(temporary_path)

            downloaded_at = datetime.now(UTC)
            checksum_sha256 = checksum.hexdigest()
            file_path = self._persist_file(
                temporary_path,
                DownloadedFileMetadata(
                    checksum_sha256=checksum_sha256,
                    downloaded_at=downloaded_at,
                    file_extension=extension,
                    mime_type=mime_type[:100],
                    original_file_name=original_filename,
                    size=payload_size,
                    source_url=url,
                ),
                regulation_id=regulation_id,
            )
            print(f"PDF saved as: {file_path}")

            rustfs_key = self._upload_to_rustfs(file_path)
            if rustfs_key:
                try:
                    self._persist_storage_key(file_path, rustfs_key)
                except SQLAlchemyError as exc:
                    print(f"Failed to persist RustFS object key for {file_path}: {exc}")
                print(f"PDF uploaded to RustFS as: {rustfs_key}")

            return bytes(payload) if payload is not None else True
        except requests.RequestException as exc:
            print(f"Exception while downloading PDF: {url} -> {exc}")
            return None
        except ValueError as exc:
            print(f"Invalid PDF download response for {url}: {exc}")
            return None
        except (OSError, SQLAlchemyError, RuntimeError) as exc:
            if file_path is not None:
                file_path.unlink(missing_ok=True)
            print(f"Failed to save PDF metadata or file: {url} -> {exc}")
            return None
        finally:
            if response is not None:
                response.close()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    def run(self) -> CrawlSummary:
        self._pdfs_downloaded = 0
        failed_entities = 0
        subjects_completed = 0
        regulations_completed = 0
        regulations_discovered = 0
        try:
            with self.session_factory() as session:
                session.execute(select(1))
        except SQLAlchemyError as exc:
            print(f"Database initialization failed: {exc}")
            summary = CrawlSummary(failed_entities=1)
            self._print_summary(summary)
            return summary

        try:
            subjects = self.crawl_bpk_subjects()
        except (requests.RequestException, SQLAlchemyError, ValueError) as exc:
            print(f"Subject retrieval failed: {exc}")
            summary = CrawlSummary(failed_entities=1)
            self._print_summary(summary)
            return summary

        for subject_item in subjects:
            subject_id: int | None = None
            try:
                subject_id = self._save_subject(subject_item)
                regulations = self.crawl_search_pages(subject_item["search_url"])
                regulation_ids = self._save_regulations(subject_id, regulations)
                regulations_discovered += len(regulation_ids)
                subjects_completed += 1
            except (requests.RequestException, SQLAlchemyError, LookupError) as exc:
                failed_entities += 1
                print(f"Subject {subject_item['source_theme_id']} failed: {exc}")
                if subject_id is not None:
                    try:
                        with self.session_factory() as session, session.begin():
                            self._set_crawl_status(
                                session,
                                subject_id=subject_id,
                                stage="regulation_list",
                                status="failed",
                                error_message=str(exc),
                                attempts=self._last_request_attempts,
                            )
                    except SQLAlchemyError as status_error:
                        print(f"Could not persist subject failure status: {status_error}")
                continue

            for regulation_id in regulation_ids:
                if self.crawler_mode == "producer":
                    try:
                        crawl_regulation.delay(regulation_id)
                    except Exception as exc:
                        failed_entities += 1
                        print(f"Could not enqueue regulation {regulation_id}: {exc}")
            if self.crawler_mode != "producer":
                completed, failed, downloaded = self._process_regulations_threaded(regulation_ids)
                regulations_completed += completed
                failed_entities += failed
                self._pdfs_downloaded += downloaded

        summary = CrawlSummary(
            subjects_discovered=len(subjects),
            subjects_completed=subjects_completed,
            regulations_discovered=regulations_discovered,
            regulations_completed=regulations_completed,
            failed_entities=failed_entities,
            pdfs_downloaded=self._pdfs_downloaded,
        )
        self._print_summary(summary)
        return summary

    def _process_regulations_threaded(self, regulation_ids: list[int]) -> tuple[int, int, int]:
        if not regulation_ids:
            return 0, 0, 0

        completed = failed = downloaded = 0
        with ThreadPoolExecutor(max_workers=min(self.thread_count, len(regulation_ids))) as executor:
            futures = {
                executor.submit(self._process_regulation_in_worker, regulation_id): regulation_id
                for regulation_id in regulation_ids
            }
            for future in as_completed(futures):
                regulation_id = futures[future]
                try:
                    succeeded, pdfs_downloaded = future.result()
                except Exception as exc:
                    failed += 1
                    print(f"Regulation {regulation_id} worker failed unexpectedly: {exc}")
                    continue
                if succeeded:
                    completed += 1
                else:
                    failed += 1
                downloaded += pdfs_downloaded
        return completed, failed, downloaded

    def _process_regulation_in_worker(self, regulation_id: int) -> tuple[bool, int]:
        crawler = BPKCrawler(
            base_url=self.base_url,
            target_url=self.target_url,
            output_dir=self.output_dir,
            session_factory=self.session_factory,
            request_delay_seconds=self.request_delay_seconds,
            retry_delay_seconds=self.retry_delay_seconds,
            max_attempts=self.max_attempts,
            request_rate_limiter=self._request_rate_limiter,
        )
        succeeded = crawler.process_regulation(regulation_id)
        return succeeded, crawler._pdfs_downloaded

    def process_regulation(self, regulation_id: int) -> bool:
        """Fetch and persist one regulation; return whether the queue item completed."""
        try:
            with self.session_factory() as session, session.begin():
                regulation = session.get(Regulation, regulation_id)
                if regulation is None:
                    raise LookupError(f"Regulation {regulation_id} does not exist")
                detail_url = regulation.detail_url
                self._set_crawl_status(session, regulation_id=regulation_id, stage="detail", status="detail_processing")

            detail_html = self.crawl_bpk_details(detail_url)
            if not detail_html:
                raise RuntimeError(
                    f"Could not retrieve detail page {detail_url}: {self._last_request_error or 'request failed'}"
                )
            metadata = self.parse_detail_metadata(detail_html)
            if metadata is None:
                raise ValueError(f"No regulation metadata found on detail page: {detail_url}")
            if not self.download_pdfs(
                detail_url, page_html=detail_html, regulation_id=regulation_id, detail_metadata=metadata
            ):
                raise RuntimeError(f"No PDF was downloaded for regulation: {detail_url}")
            with self.session_factory() as session, session.begin():
                self._set_crawl_status(
                    session,
                    regulation_id=regulation_id,
                    stage="completed",
                    status="completed",
                    attempts=self._last_request_attempts,
                )
            return True
        except (requests.RequestException, SQLAlchemyError, LookupError, RuntimeError, ValueError, OSError) as exc:
            print(f"Regulation {regulation_id} failed: {exc}")
            try:
                with self.session_factory() as session, session.begin():
                    self._set_crawl_status(
                        session,
                        regulation_id=regulation_id,
                        stage="failed",
                        status="failed",
                        error_message=str(exc),
                        attempts=self._last_request_attempts,
                    )
            except SQLAlchemyError as status_error:
                print(f"Could not persist regulation failure status: {status_error}")
            return False

    @staticmethod
    def _print_summary(summary: CrawlSummary) -> None:
        print(
            "Crawl summary: "
            f"subjects={summary.subjects_discovered}, "
            f"subjects_completed={summary.subjects_completed}, "
            f"regulations={summary.regulations_discovered}, "
            f"completed={summary.regulations_completed}, "
            f"entities_completed={summary.entities_completed}, "
            f"failures={summary.failed_entities}, "
            f"PDFs={summary.pdfs_downloaded}"
        )


def main() -> None:
    crawler = BPKCrawler()
    crawler.run()


if __name__ == "__main__":
    main()
