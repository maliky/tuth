"""Public transcript artifact verification views."""

from __future__ import annotations

import json
from pathlib import Path

from django.core import signing
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import render
from django.urls import reverse

from app.website.services.transcript_artifacts import (
    TranscriptArtifactT,
    load_transcript_artifact,
    transcript_artifact_filename,
    transcript_artifact_pdf_path,
)


def _artifact_or_404(token: str) -> TranscriptArtifactT:
    """Return a verified artifact manifest or raise a public 404."""
    try:
        return load_transcript_artifact(token)
    except (
        FileNotFoundError,
        ValueError,
        json.JSONDecodeError,
        signing.BadSignature,
    ) as exc:
        raise Http404("Transcript verification record not found.") from exc


def transcript_verify(request: HttpRequest, token: str) -> HttpResponse:
    """Render the public verification page for a stored transcript."""
    artifact = _artifact_or_404(token)
    status_code = 410 if artifact["revoked"] else 200
    context = {
        "artifact": artifact,
        "pdf_url": reverse("transcript_verify_pdf", args=[token]),
    }
    return render(
        request,
        "website/transcript_verify.html",
        context,
        status=status_code,
    )


def transcript_verify_pdf(request: HttpRequest, token: str) -> HttpResponseBase:
    """Stream the stored transcript PDF for a verified artifact token."""
    artifact = _artifact_or_404(token)
    if artifact["revoked"]:
        return HttpResponse("Transcript verification record revoked.", status=410)
    try:
        pdf_path = transcript_artifact_pdf_path(artifact)
    except SuspiciousFileOperation as exc:
        raise Http404("Transcript verification record not found.") from exc
    if not Path(pdf_path).exists():
        raise Http404("Transcript PDF not found.")
    return FileResponse(
        open(pdf_path, "rb"),
        as_attachment=True,
        content_type="application/pdf",
        filename=transcript_artifact_filename(artifact),
    )


__all__ = [
    "transcript_verify",
    "transcript_verify_pdf",
]
