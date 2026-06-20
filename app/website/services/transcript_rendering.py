"""HTML and PDF rendering helpers for transcript documents."""

from __future__ import annotations

from django.conf import settings
from django.template.loader import render_to_string

from app.website.services.transcript_org import render_transcript_document_org
from app.website.services.transcript_types import (
    DEFAULT_TRANSCRIPT_LAYOUT,
    TranscriptDocumentT,
    TranscriptLayoutKeyT,
    normalize_transcript_layout,
    transcript_layout_config,
)


def render_transcript_document_html(
    document: TranscriptDocumentT,
    *,
    layout: TranscriptLayoutKeyT = DEFAULT_TRANSCRIPT_LAYOUT,
    template_name: str = "website/registrar_transcript_pdf.html",
) -> str:
    """Render the transcript PDF HTML document."""
    layout_key = normalize_transcript_layout(layout)
    return render_to_string(
        template_name,
        {
            "transcript": document,
            "layout": transcript_layout_config(layout_key),
        },
    )


def render_transcript_document_pdf(
    document: TranscriptDocumentT,
    *,
    layout: TranscriptLayoutKeyT = DEFAULT_TRANSCRIPT_LAYOUT,
) -> bytes:
    """Render the transcript payload into a PDF document."""
    try:
        from weasyprint import HTML
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("WeasyPrint is required to render transcript PDFs.") from exc

    html = render_transcript_document_html(document, layout=layout)
    base_url = getattr(settings, "WEASYPRINT_BASE_URL", None)
    if base_url is None:
        base_url = getattr(settings, "STATIC_ROOT", None) or settings.BASE_DIR
    pdf_bytes = HTML(string=html, base_url=str(base_url)).write_pdf()
    return bytes(pdf_bytes)


__all__ = [
    "render_transcript_document_html",
    "render_transcript_document_org",
    "render_transcript_document_pdf",
]
