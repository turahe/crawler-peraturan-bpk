from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import requests
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from playright_peraturan_bpk.main import BPKCrawler
from playright_peraturan_bpk.models import Base, CrawlJob, DocumentFile, DocumentMetadata, Regulation, Subject


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


class FakeResponse:
    headers: dict[str, str] = {
        "Content-Type": "application/pdf; charset=binary",
        "Content-Disposition": 'attachment; filename="original document.pdf"',
    }

    def __init__(self, content: bytes = b"fake-pdf", text: str = "", status_code: int = 200) -> None:
        self.content = content
        self.text = text
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        del chunk_size
        yield self.content[:4]
        yield b""
        yield self.content[4:]

    def close(self) -> None:
        return None


DETAIL_PAGE_HTML = """
<div class="container fs-6">
    <div class="row"><div class="col-lg-3 fw-bold">Tipe Dokumen</div><div class="col-lg-9">Peraturan Perundang-undangan</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Judul</div><div class="col-lg-9">Peraturan Badan Pemeriksa Keuangan Nomor 2 Tahun 2026 tentang Kode Etik</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">T.E.U.</div><div class="col-lg-9">Indonesia, BPK RI</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Nomor</div><div class="col-lg-9">2</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Bentuk</div><div class="col-lg-9">Peraturan Badan Pemeriksa Keuangan</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Bentuk Singkat</div><div class="col-lg-9">Peraturan BPK</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Tahun</div><div class="col-lg-9">2026</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Tempat Penetapan</div><div class="col-lg-9">Jakarta</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Tanggal Penetapan</div><div class="col-lg-9"><span>10 April 2026</span></div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Tanggal Pengundangan</div><div class="col-lg-9"><span>10 April 2026</span></div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Tanggal Berlaku</div><div class="col-lg-9"><span>10 April 2026</span></div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Sumber</div><div class="col-lg-9">LN 2026 (7/BPK) : 22 hlm</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Subjek</div><div class="col-lg-9">KODE ETIK</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Status</div><div class="col-lg-9">Berlaku</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Bahasa</div><div class="col-lg-9">Bahasa Indonesia</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Lokasi</div><div class="col-lg-9">BPK RI</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Bidang</div><div class="col-lg-9">HUKUM ADMINISTRASI NEGARA</div></div>
    <div class="row"><div class="col-lg-3 fw-bold">Alias</div><div class="col-lg-9">Peraturan BPK No. 2 Tahun 2026</div></div>
</div>
<a href="/Download/peraturan-bpk-2-2026.pdf">PDF</a>
"""


def test_crawler_has_expected_defaults():
    crawler = BPKCrawler()
    assert crawler.base_url == "https://peraturan.bpk.go.id"
    assert crawler.target_url == "https://peraturan.bpk.go.id/Subjek"
    assert len(crawler.create_requests_sessions(2)) == 2


def test_get_retries_transient_http_status(monkeypatch, tmp_path, session_factory):
    responses = iter((FakeResponse(status_code=503), FakeResponse(text="ok")))
    requested: list[str] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        requested.append(url)
        return next(responses)

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(
        output_dir=tmp_path,
        session_factory=session_factory,
        request_delay_seconds=0,
        retry_delay_seconds=0,
    )

    response = crawler._get("https://example.com/retry")

    assert response.text == "ok"
    assert requested == ["https://example.com/retry"] * 2
    assert crawler._last_request_attempts == 2


def test_get_does_not_retry_permanent_http_error(monkeypatch, tmp_path, session_factory):
    calls = 0

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        nonlocal calls
        calls += 1
        return FakeResponse(status_code=404)

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(
        output_dir=tmp_path,
        session_factory=session_factory,
        request_delay_seconds=0,
        retry_delay_seconds=0,
    )

    with pytest.raises(requests.HTTPError):
        crawler._get("https://example.com/missing")
    assert calls == 1


def test_extract_subjects_uses_search_links_and_strips_result_counts(monkeypatch, tmp_path, session_factory):
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)
    response = FakeResponse(
        text="""
    <a href="/Search?tema=1">Administrasi dan Tata Usaha Negara [7.953]</a>
    <a href="https://peraturan.bpk.go.id/Search?tema=2">Agraria [4,425]</a>
    <a href="/Details/42/peraturan">Not a subject</a>
    """
    )
    response.headers = {}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    assert crawler.crawl_bpk_subjects() == [
        {
            "source_theme_id": "1",
            "name": "Administrasi dan Tata Usaha Negara",
            "search_url": "https://peraturan.bpk.go.id/Search?tema=1",
        },
        {
            "source_theme_id": "2",
            "name": "Agraria",
            "search_url": "https://peraturan.bpk.go.id/Search?tema=2",
        },
    ]


def test_crawl_search_pages_follows_pagination_and_deduplicates_regulations(monkeypatch, tmp_path, session_factory):
    page_one = """
        <div class="card"><div class="col-lg-10 fs-2 fw-bold pe-4">
            <a href="/Details/101/uu-no-1">Undang-undang No. 1</a>
        </div><a class="text-danger" href="/Details/999/related">Related regulation</a></div>
    <ul class="pagination"><li><a href="/Search?tema=1&amp;p=2">2</a></li></ul>
    """
    page_two = """
    <a href="/Details/101/uu-no-1">Duplicate regulation</a>
    <a href="/Details/102/uu-no-2">Undang-undang No. 2</a>
    <ul class="pagination"><li><a href="/Search?tema=1&amp;p=1">1</a></li></ul>
    """
    responses = {
        "https://peraturan.bpk.go.id/Search?tema=1": page_one,
        "https://peraturan.bpk.go.id/Search?tema=1&p=2": page_two,
    }
    requested: list[str] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        requested.append(url)
        response = FakeResponse(text=responses[url])
        response.headers = {}
        return response

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    results = crawler.crawl_search_pages("https://peraturan.bpk.go.id/Search?tema=1")

    assert [item["source_id"] for item in results] == ["101", "102"]
    assert len(requested) == 2


def test_run_persists_subject_regulations_metadata_files_and_completed_jobs(
    monkeypatch,
    tmp_path,
    session_factory,
):
    subject_html = '<a href="/Search?tema=9">KODE ETIK [2]</a>'
    search_html = '<a href="/Details/347827/peraturan-bpk-no-2-tahun-2026">Peraturan BPK Nomor 2 Tahun 2026</a>'
    detail_url = "https://peraturan.bpk.go.id/Details/347827/peraturan-bpk-no-2-tahun-2026"
    responses = {
        "https://peraturan.bpk.go.id/Subjek": subject_html,
        "https://peraturan.bpk.go.id/Search?tema=9": search_html,
        detail_url: DETAIL_PAGE_HTML,
    }
    requested: list[str] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        requested.append(url)
        response = FakeResponse(b"regulation-pdf", text=responses.get(url, ""))
        response.headers = {
            "Content-Type": "application/pdf",
            "Content-Disposition": 'attachment; filename="signed-copy.pdf"',
        }
        return response

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    summary = crawler.run()

    assert summary.subjects_discovered == 1
    assert summary.subjects_completed == 1
    assert summary.regulations_discovered == 1
    assert summary.regulations_completed == 1
    assert summary.entities_completed == 2
    assert summary.failed_entities == 0
    assert summary.pdfs_downloaded == 1
    assert "https://peraturan.bpk.go.id/Search?tema=9&p=2" not in requested

    with session_factory() as session:
        subject = session.scalar(select(Subject).where(Subject.source_theme_id == "9"))
        regulation = session.scalar(select(Regulation).where(Regulation.source_id == "347827"))
        file_row = session.scalar(select(DocumentFile).where(DocumentFile.regulation_id == regulation.id))
        metadata = session.scalar(select(DocumentMetadata).where(DocumentMetadata.regulation_id == regulation.id))
        job = session.scalar(select(CrawlJob).where(CrawlJob.regulation_id == regulation.id))
        subject_job = session.scalar(select(CrawlJob).where(CrawlJob.subject_id == subject.id))

    assert subject is not None and subject.name == "KODE ETIK"
    assert regulation is not None and regulation.detail_url == detail_url
    assert file_row is not None and Path(file_row.storage_path).read_bytes() == b"regulation-pdf"
    assert metadata is not None
    assert metadata.document_file_id == file_row.id
    assert metadata.title == "Peraturan Badan Pemeriksa Keuangan Nomor 2 Tahun 2026 tentang Kode Etik"
    assert job is not None and job.status == "completed" and job.completed_at is not None
    assert subject_job is not None and subject_job.status == "peraturan_list_extracted"


def test_run_marks_failed_regulation_when_detail_request_fails(monkeypatch, tmp_path, session_factory):
    responses = {
        "https://peraturan.bpk.go.id/Subjek": '<a href="/Search?tema=9">KODE ETIK [2]</a>',
        "https://peraturan.bpk.go.id/Search?tema=9": '<a href="/Details/347827/peraturan">Regulation</a>',
    }
    # One attempt keeps this failure-path test fast while the production default remains three.
    crawler = BPKCrawler(
        output_dir=tmp_path,
        session_factory=session_factory,
        request_delay_seconds=0,
        retry_delay_seconds=0,
        max_attempts=1,
    )
    monkeypatch.setattr(
        "playright_peraturan_bpk.main.BPKCrawler._get",
        lambda self, url, **kwargs: _fake_html_response(responses[url]) if url in responses else _raise_offline(),
    )

    summary = crawler.run()

    assert summary.regulations_completed == 0
    assert summary.failed_entities == 1
    with session_factory() as session:
        job = session.scalar(select(CrawlJob).where(CrawlJob.regulation_id.is_not(None)))
    assert job is not None and job.status == "failed"
    assert "detail page" in job.error_message


def _fake_html_response(html: str) -> FakeResponse:
    response = FakeResponse(text=html)
    response.headers = {}
    return response


def _raise_offline() -> FakeResponse:
    raise requests.ConnectionError("offline")


def test_parse_detail_metadata_extracts_labels_and_indonesian_dates():
    metadata = BPKCrawler.parse_detail_metadata(DETAIL_PAGE_HTML)

    assert metadata is not None
    assert metadata.document_type == "Peraturan Perundang-undangan"
    assert metadata.title == "Peraturan Badan Pemeriksa Keuangan Nomor 2 Tahun 2026 tentang Kode Etik"
    assert metadata.teu == "Indonesia, BPK RI"
    assert metadata.number == "2"
    assert metadata.form == "Peraturan Badan Pemeriksa Keuangan"
    assert metadata.form_short == "Peraturan BPK"
    assert metadata.year == 2026
    assert metadata.place_of_enactment == "Jakarta"
    assert str(metadata.enactment_date) == "2026-04-10"
    assert metadata.promulgation_date == metadata.enactment_date
    assert metadata.effective_date == metadata.enactment_date
    assert metadata.source == "LN 2026 (7/BPK) : 22 hlm"
    assert metadata.subject == "KODE ETIK"
    assert metadata.status == "Berlaku"
    assert metadata.language == "Bahasa Indonesia"
    assert metadata.location == "BPK RI"
    assert metadata.field == "HUKUM ADMINISTRASI NEGARA"
    assert metadata.alias == "Peraturan BPK No. 2 Tahun 2026"


def test_detail_page_metadata_is_saved_with_downloaded_file(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(b"regulation-pdf"))

    pdf_urls = crawler.download_pdfs(
        "https://peraturan.bpk.go.id/Details/347827/regulation",
        page_html=DETAIL_PAGE_HTML,
        regulation_id=_create_test_regulation(session_factory),
    )

    assert pdf_urls == ["https://peraturan.bpk.go.id/Download/peraturan-bpk-2-2026.pdf"]
    with session_factory() as session:
        file_record = session.scalar(select(DocumentFile))
        metadata_record = session.scalar(select(DocumentMetadata))

    assert file_record is not None
    assert metadata_record is not None
    assert metadata_record.document_file_id == file_record.id
    assert metadata_record.title == "Peraturan Badan Pemeriksa Keuangan Nomor 2 Tahun 2026 tentang Kode Etik"
    assert metadata_record.year == 2026
    assert str(metadata_record.enactment_date) == "2026-04-10"
    assert metadata_record.subject == "KODE ETIK"


def test_detail_metadata_persists_when_no_pdf_link_exists(tmp_path, session_factory):
    regulation_id = _create_test_regulation(session_factory)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)
    detail_without_pdf = DETAIL_PAGE_HTML.split('<a href="/Download/', 1)[0]

    assert (
        crawler.download_pdfs(
            "https://peraturan.bpk.go.id/Details/347827/regulation",
            page_html=detail_without_pdf,
            regulation_id=regulation_id,
        )
        == []
    )

    with session_factory() as session:
        metadata = session.scalar(select(DocumentMetadata).where(DocumentMetadata.regulation_id == regulation_id))
    assert metadata is not None
    assert metadata.document_file_id is None
    assert metadata.title == "Peraturan Badan Pemeriksa Keuangan Nomor 2 Tahun 2026 tentang Kode Etik"


def _create_test_regulation(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as session, session.begin():
        regulation = Regulation(source_id="347827", title="Regulation", detail_url="https://example.com/detail")
        session.add(regulation)
        session.flush()
        return regulation.id


def test_download_persists_uuid_file_and_comprehensive_metadata(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    content = b"fake-pdf-content"
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(content))

    payload = crawler.download_pdf("https://peraturan.bpk.go.id/Download/regulation.pdf")

    assert payload == content
    with session_factory() as session:
        record = session.scalar(select(DocumentFile))

    assert record is not None
    file_uuid = uuid.UUID(record.file_name.removesuffix(record.file_extension))
    assert file_uuid.version == 4
    assert record.uuid == file_uuid
    assert record.file_name == f"{file_uuid}.pdf"
    assert record.original_file_name == "original document.pdf"
    assert record.file_extension == ".pdf"
    assert record.mime_type == "application/pdf"
    assert record.size == len(content)
    assert record.checksum_sha256 == hashlib.sha256(content).hexdigest()
    assert record.hash == record.checksum_sha256
    assert record.source_url == "https://peraturan.bpk.go.id/Download/regulation.pdf"
    assert record.downloaded_at is not None
    assert record.disk == "local"
    assert record.storage_path == str((tmp_path / "pdf" / record.file_name).resolve())
    assert Path(record.storage_path).read_bytes() == content
    assert list((tmp_path / "pdf").glob("*.part")) == []


def test_download_uses_url_name_when_content_disposition_missing(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    response = FakeResponse()
    response.headers = {"Content-Type": "application/pdf"}
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)

    assert crawler.download_pdf("https://example.com/files/Salinan%20Peraturan.pdf") == b"fake-pdf"
    with session_factory() as session:
        record = session.scalar(select(DocumentFile))

    assert record is not None
    assert record.original_file_name == "Salinan Peraturan.pdf"
    assert record.file_name == f"{record.uuid}.pdf"


@pytest.mark.parametrize(
    ("download_href", "expected_url"),
    [
        (
            "/Download/46688/Perbup%20Bantul%20No.%2041%20Tahun%202011%20ttg%20Perubahan%20Atas%20Peraturan%20Bupati%20Bantul%20No.%2011%20Tahun%202011%20ttg%20Pelimpahan%20Sebagian%20Wewenang%20Bupati%20Kepada%20Camat.pdf",
            "https://peraturan.bpk.go.id/Download/46688/Perbup%20Bantul%20No.%2041%20Tahun%202011%20ttg%20Perubahan%20Atas%20Peraturan%20Bupati%20Bantul%20No.%2011%20Tahun%202011%20ttg%20Pelimpahan%20Sebagian%20Wewenang%20Bupati%20Kepada%20Camat.pdf",
        ),
        (
            "https://cdn.example.test/Download/46688/Perbup%20Bantul.pdf",
            "https://cdn.example.test/Download/46688/Perbup%20Bantul.pdf",
        ),
    ],
)
def test_download_follows_read_link_for_html_response(
    monkeypatch,
    tmp_path,
    session_factory,
    download_href,
    expected_url,
):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    detail_url = "https://peraturan.bpk.go.id/Read/46688/source-page"
    html = f'<a class="read-btn-download" href="{download_href}">Unduh PDF</a>'
    html_response = FakeResponse(text=html)
    html_response.headers = {"Content-Type": "text/html; charset=UTF-8"}
    pdf_response = FakeResponse(content=b"actual-pdf")
    pdf_response.headers = {
        "Content-Type": "application/pdf",
        "Content-Disposition": 'attachment; filename="bantul.pdf"',
    }
    requested_urls: list[str] = []

    def fake_get(requested_url: str, **kwargs: object) -> FakeResponse:
        requested_urls.append(requested_url)
        return html_response if requested_url == detail_url else pdf_response

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    result = crawler.download_pdf(detail_url)

    assert result == b"actual-pdf"
    assert requested_urls == [detail_url, expected_url]
    with session_factory() as session:
        record = session.scalar(select(DocumentFile))
    assert record is not None
    assert record.source_url == expected_url
    assert Path(record.storage_path).read_bytes() == b"actual-pdf"


@pytest.mark.parametrize("mime_type", ["application/pdf", "application/xhtml+xml"])
def test_download_does_not_follow_link_for_non_html_mime_type(monkeypatch, tmp_path, session_factory, mime_type):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    response = FakeResponse(content=b"pdf-bytes")
    response.headers = {"Content-Type": mime_type}
    requested_urls: list[str] = []

    def fake_get(url, **kwargs):
        requested_urls.append(url)
        return response

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    assert crawler.download_pdf("https://example.test/download") == b"pdf-bytes"
    assert requested_urls == ["https://example.test/download"]


def test_download_rejects_html_response_after_following_download_link(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    detail_url = "https://example.test/Read/1"
    download_url = "https://example.test/Download/1/file.pdf"
    html_response = FakeResponse(text='<a class="read-btn-download" href="/Download/1/file.pdf">Unduh PDF</a>')
    html_response.headers = {"Content-Type": "text/html"}
    destination_response = FakeResponse(text="still HTML")
    destination_response.headers = {"Content-Type": "text/html"}
    requested_urls: list[str] = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        requested_urls.append(url)
        return html_response if url == detail_url else destination_response

    monkeypatch.setattr(requests, "get", fake_get)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    assert crawler.download_pdf(detail_url) is None
    assert requested_urls == [detail_url, download_url]
    with session_factory() as session:
        assert session.scalar(select(DocumentFile.id)) is None
    assert list((tmp_path / "pdf").iterdir()) == []


@pytest.mark.parametrize(
    "html",
    [
        "<html><body>No download button</body></html>",
        '<a class="read-btn-download" href="javascript:alert(1)">Unduh PDF</a>',
    ],
)
def test_download_rejects_missing_or_invalid_html_download_url(monkeypatch, tmp_path, session_factory, html):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    response = FakeResponse(text=html)
    response.headers = {"Content-Type": "text/html"}
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: response)
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory, request_delay_seconds=0)

    assert crawler.download_pdf("https://example.test/Read/1") is None
    with session_factory() as session:
        assert session.scalar(select(DocumentFile.id)) is None
    assert list((tmp_path / "pdf").iterdir()) == []


def test_download_retries_uuid_when_filename_already_exists(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    first_uuid = uuid.UUID("12345678-1234-4234-8234-123456789abc")
    second_uuid = uuid.UUID("87654321-4321-4321-8321-cba987654321")
    (tmp_path / "pdf").mkdir(parents=True)
    existing_path = tmp_path / "pdf" / f"{first_uuid}.pdf"
    existing_path.write_bytes(b"existing file")
    generated = iter((first_uuid, second_uuid))
    monkeypatch.setattr("playright_peraturan_bpk.main.uuid.uuid4", lambda: next(generated))
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)

    assert crawler.download_pdf("https://example.com/file.pdf") == b"fake-pdf"

    with session_factory() as session:
        record = session.scalar(select(DocumentFile))
    assert record is not None
    assert record.uuid == second_uuid
    assert existing_path.read_bytes() == b"existing file"
    assert (tmp_path / "pdf" / record.file_name).read_bytes() == b"fake-pdf"


def test_download_retries_uuid_when_uuid_already_exists_in_database(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    first_uuid = uuid.UUID("12345678-1234-4234-8234-123456789abc")
    second_uuid = uuid.UUID("87654321-4321-4321-8321-cba987654321")
    with session_factory() as session, session.begin():
        session.add(DocumentFile(uuid=first_uuid, file_name=f"{first_uuid}.pdf"))

    generated = iter((first_uuid, second_uuid))
    monkeypatch.setattr("playright_peraturan_bpk.main.uuid.uuid4", lambda: next(generated))
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)

    assert crawler.download_pdf("https://example.com/file.pdf") == b"fake-pdf"
    with session_factory() as session:
        records = session.scalars(select(DocumentFile).order_by(DocumentFile.id)).all()

    assert [record.uuid for record in records] == [first_uuid, second_uuid]
    assert (tmp_path / "pdf" / f"{second_uuid}.pdf").read_bytes() == b"fake-pdf"


def test_disk_write_failure_does_not_create_metadata(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(
        "playright_peraturan_bpk.main.os.link",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)

    assert crawler.download_pdf("https://example.com/file.pdf") is None
    with session_factory() as session:
        assert session.scalar(select(DocumentFile.id)) is None
    assert list((tmp_path / "pdf").iterdir()) == []


def test_database_flush_failure_rolls_back_metadata_and_published_file(monkeypatch, tmp_path, session_factory):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    class FailingSession(Session):
        def flush(self, objects=None) -> None:
            raise SQLAlchemyError("database write failed")

    failing_factory = sessionmaker(
        bind=session_factory.kw["bind"],
        class_=FailingSession,
    )
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=failing_factory)

    assert crawler.download_pdf("https://example.com/file.pdf") is None
    with session_factory() as session:
        assert session.scalar(select(DocumentFile.id)) is None
    assert list((tmp_path / "pdf").iterdir()) == []


def test_database_connection_failure_removes_written_file(monkeypatch, tmp_path):
    monkeypatch.delenv("RUSTFS_ENDPOINT", raising=False)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

    def fail_to_connect() -> Session:
        raise SQLAlchemyError("database unavailable")

    crawler = BPKCrawler(output_dir=tmp_path, session_factory=fail_to_connect)

    assert crawler.download_pdf("https://example.com/file.pdf") is None
    assert list((tmp_path / "pdf").iterdir()) == []


def test_download_uploads_uuid_filename_to_rustfs(monkeypatch, tmp_path, session_factory):
    monkeypatch.setenv("RUSTFS_ENDPOINT", "http://localhost:8080")
    monkeypatch.setenv("RUSTFS_ACCESS_KEY", "admin")
    monkeypatch.setenv("RUSTFS_SECRET_KEY", "password")
    monkeypatch.setenv("RUSTFS_BUCKET", "documents")
    crawler = BPKCrawler(output_dir=tmp_path, session_factory=session_factory)

    class MissingBucketError(Exception):
        response = {"Error": {"Code": "404"}}

    class FakeS3Client:
        def __init__(self) -> None:
            self.created_buckets: list[str] = []
            self.uploaded: list[tuple[str, str, str]] = []

        def head_bucket(self, **kwargs: str) -> None:
            raise MissingBucketError()

        def create_bucket(self, **kwargs: str) -> None:
            self.created_buckets.append(kwargs["Bucket"])

        def upload_file(self, path: str, bucket: str, key: str) -> None:
            self.uploaded.append((path, bucket, key))

    s3_client = FakeS3Client()
    captured: dict[str, object] = {}

    def fake_client(service_name: str, **kwargs: object) -> FakeS3Client:
        captured["service_name"] = service_name
        captured["endpoint_url"] = kwargs["endpoint_url"]
        return s3_client

    monkeypatch.setattr(
        "playright_peraturan_bpk.main.boto3",
        type("B", (), {"client": staticmethod(fake_client)}),
    )
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(b"rustfs-pdf"))

    assert crawler.download_pdf("https://example.com/other.pdf") == b"rustfs-pdf"

    with session_factory() as session:
        record = session.scalar(select(DocumentFile))
    assert record is not None
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "http://localhost:8080"
    assert s3_client.created_buckets == ["documents"]
    assert s3_client.uploaded[0][1:] == ("documents", f"pdf/{record.file_name}")
    assert record.storage_key == f"pdf/{record.file_name}"
