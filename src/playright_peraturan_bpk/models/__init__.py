from __future__ import annotations

import sys

from .base import Base
from .crawl_job import CrawlJob
from .document_chunk import DocumentChunk
from .document_file import DocumentFile
from .document_metadata import DocumentMetadata
from .document_page import DocumentPage
from .regulation import Regulation
from .regulation_relation import RegulationRelation
from .regulation_subject import RegulationSubject
from .subject import Subject


def _bind_related_models() -> None:
    """Expose related classes in each module so SQLAlchemy can resolve annotations."""
    bindings: dict[str, dict[str, type[Base]]] = {
        "subject": {"Regulation": Regulation, "CrawlJob": CrawlJob},
        "regulation": {
            "Subject": Subject,
            "CrawlJob": CrawlJob,
            "DocumentFile": DocumentFile,
            "DocumentMetadata": DocumentMetadata,
            "RegulationRelation": RegulationRelation,
        },
        "crawl_job": {"Regulation": Regulation, "Subject": Subject},
        "document_file": {
            "Regulation": Regulation,
            "DocumentMetadata": DocumentMetadata,
            "DocumentPage": DocumentPage,
        },
        "document_metadata": {"DocumentFile": DocumentFile, "Regulation": Regulation},
        "document_page": {"DocumentFile": DocumentFile, "DocumentChunk": DocumentChunk},
        "document_chunk": {"DocumentPage": DocumentPage},
        "regulation_relation": {"Regulation": Regulation},
    }
    for module_name, names in bindings.items():
        module = sys.modules[f"{__name__}.{module_name}"]
        for name, model in names.items():
            setattr(module, name, model)


_bind_related_models()

__all__ = [
    "Base",
    "CrawlJob",
    "DocumentChunk",
    "DocumentFile",
    "DocumentMetadata",
    "DocumentPage",
    "Regulation",
    "RegulationRelation",
    "RegulationSubject",
    "Subject",
]
