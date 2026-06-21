"""Host-backed transcript artifacts for QR verification."""

from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
import secrets
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TypedDict, cast

from django.conf import settings
from django.core import signing
from django.core.exceptions import SuspiciousFileOperation
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from app.website.services.transcript_document import build_transcript_document
from app.website.services.transcript_rendering import render_transcript_document_pdf
from app.website.services.transcript_types import (
    TranscriptDocumentT,
    TranscriptLayoutKeyT,
)

ARTIFACT_ROOT = "transcripts"
MANIFEST_DIR = "manifests"
PDF_DIR = "pdfs"
SIGNING_SALT = "tusis.transcript_artifacts.v1"


class TranscriptArtifactT(TypedDict):
    """Signed metadata stored next to a generated official transcript PDF."""

    token: str
    layout: str
    student_pk: int
    student_id: str
    student_name: str
    program_code: str
    major_program: str
    college: str
    issued_at: str
    issued_by: str
    verification_url: str
    pdf_relative_path: str
    pdf_sha256: str
    pdf_size: int
    revoked: bool
    revoked_reason: str


@dataclass(frozen=True)
class IssuedTranscriptArtifact:
    """Generated transcript PDF plus the signed metadata written to disk."""

    artifact: TranscriptArtifactT
    filename: str
    pdf_bytes: bytes
    pdf_path: Path


def _artifact_root() -> Path:
    """Return the media-backed transcript artifact root."""
    return Path(settings.MEDIA_ROOT) / ARTIFACT_ROOT


def _token_is_safe(token: str) -> bool:
    """Return whether a token can be safely mapped to a manifest filename."""
    return bool(token) and all(char.isalnum() or char in "-_" for char in token)


def _manifest_path(token: str) -> Path:
    """Return the manifest path for a token."""
    if not _token_is_safe(token):
        raise ValueError("Transcript verification token is not valid.")
    return _artifact_root() / MANIFEST_DIR / f"{token}.json"


def _safe_filename_part(value: str) -> str:
    """Return a conservative filename component."""
    clean_value = "".join(
        char if char.isalnum() or char in "-_" else "_" for char in value
    )
    return clean_value.strip("_") or "student"


def _new_token() -> str:
    """Return a unique URL-safe artifact token."""
    for _attempt in range(8):
        token = secrets.token_urlsafe(24)
        if not _manifest_path(token).exists():
            return token
    raise RuntimeError("Could not allocate a transcript verification token.")


def _signer() -> signing.Signer:
    """Return the stable signer used for manifest integrity checks."""
    return signing.Signer(salt=SIGNING_SALT)


def _payload_json(payload: TranscriptArtifactT) -> str:
    """Return canonical JSON for signing and verification."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _signed_manifest(payload: TranscriptArtifactT) -> dict[str, object]:
    """Return readable signed manifest content."""
    payload_json = _payload_json(payload)
    return {
        "payload": payload,
        "signature": _signer().signature(payload_json),
    }


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    """Write JSON by replacing a temporary file in the target directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _write_bytes_atomic(path: Path, payload: bytes) -> None:
    """Write bytes by replacing a temporary file in the target directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("wb", dir=path.parent, delete=False) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def _required_str(data: dict[str, object], key: str) -> str:
    """Return a required manifest string field."""
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Transcript artifact field {key!r} is invalid.")
    return value


def _required_int(data: dict[str, object], key: str) -> int:
    """Return a required manifest integer field."""
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Transcript artifact field {key!r} is invalid.")
    return value


def _required_bool(data: dict[str, object], key: str) -> bool:
    """Return a required manifest boolean field."""
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Transcript artifact field {key!r} is invalid.")
    return value


def _coerce_artifact(payload: object) -> TranscriptArtifactT:
    """Validate untyped JSON and return a typed artifact payload."""
    if not isinstance(payload, dict):
        raise ValueError("Transcript artifact manifest payload is invalid.")
    data = cast(dict[str, object], payload)
    return {
        "token": _required_str(data, "token"),
        "layout": _required_str(data, "layout"),
        "student_pk": _required_int(data, "student_pk"),
        "student_id": _required_str(data, "student_id"),
        "student_name": _required_str(data, "student_name"),
        "program_code": _required_str(data, "program_code"),
        "major_program": _required_str(data, "major_program"),
        "college": _required_str(data, "college"),
        "issued_at": _required_str(data, "issued_at"),
        "issued_by": _required_str(data, "issued_by"),
        "verification_url": _required_str(data, "verification_url"),
        "pdf_relative_path": _required_str(data, "pdf_relative_path"),
        "pdf_sha256": _required_str(data, "pdf_sha256"),
        "pdf_size": _required_int(data, "pdf_size"),
        "revoked": _required_bool(data, "revoked"),
        "revoked_reason": str(data.get("revoked_reason", "")),
    }


def _verified_manifest(raw_manifest: object) -> TranscriptArtifactT:
    """Validate a manifest wrapper and its signature."""
    if not isinstance(raw_manifest, dict):
        raise ValueError("Transcript artifact manifest is invalid.")
    manifest = cast(dict[str, object], raw_manifest)
    signature = _required_str(manifest, "signature")
    artifact = _coerce_artifact(manifest.get("payload"))
    payload_json = _payload_json(artifact)
    signed_value = f"{payload_json}{_signer().sep}{signature}"
    _signer().unsign(signed_value)
    return artifact


def load_transcript_artifact(token: str) -> TranscriptArtifactT:
    """Load and verify a signed transcript artifact manifest."""
    manifest_path = _manifest_path(token)
    raw_manifest: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    return _verified_manifest(raw_manifest)


def transcript_artifact_pdf_path(artifact: TranscriptArtifactT) -> Path:
    """Return the artifact PDF path after validating it stays under MEDIA_ROOT."""
    media_root = Path(settings.MEDIA_ROOT).resolve()
    pdf_path = (media_root / artifact["pdf_relative_path"]).resolve()
    if media_root != pdf_path and media_root not in pdf_path.parents:
        raise SuspiciousFileOperation("Transcript artifact PDF escapes MEDIA_ROOT.")
    return pdf_path


def transcript_artifact_filename(artifact: TranscriptArtifactT) -> str:
    """Return the official download filename for a transcript artifact."""
    student_part = _safe_filename_part(artifact["student_id"])
    return f"transcript_{student_part}_{artifact['layout']}_{artifact['token'][:8]}.pdf"


def _qr_png_bytes_from_python(value: str) -> bytes | None:
    """Return QR PNG bytes from the optional Python qrcode package."""
    try:
        import qrcode
    except ImportError:
        return None
    buffer = BytesIO()
    image = qrcode.make(value)
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _qr_png_bytes_from_qrencode(value: str) -> bytes:
    """Return QR PNG bytes using the system qrencode fallback."""
    try:
        completed = subprocess.run(
            ["qrencode", "-o", "-", "-t", "PNG", "-s", "4", "--", value],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("qrencode is required for transcript QR generation.") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Transcript QR generation failed: {detail}") from exc
    return completed.stdout


def qr_code_data_uri(value: str) -> str:
    """Render a QR code PNG data URI for embedding in the transcript PDF."""
    # Prefer the Python dependency in Docker; keep qrencode for local resilience.
    png_bytes = _qr_png_bytes_from_python(value)
    if png_bytes is None:
        png_bytes = _qr_png_bytes_from_qrencode(value)
    encoded = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def transcript_document_with_verification(
    document: TranscriptDocumentT,
    *,
    qr_code_uri: str,
    token: str,
    verification_url: str,
) -> TranscriptDocumentT:
    """Return a transcript document annotated with verification metadata."""
    return {
        **document,
        "qr_code_uri": qr_code_uri,
        "verification_token": token,
        "verification_url": verification_url,
    }


def _artifact_payload(
    *,
    document: TranscriptDocumentT,
    issued_by: str,
    layout: TranscriptLayoutKeyT,
    pdf_bytes: bytes,
    pdf_relative_path: str,
    student_id: int,
    token: str,
    verification_url: str,
) -> TranscriptArtifactT:
    """Return signed metadata for a generated transcript artifact."""
    return {
        "token": token,
        "layout": layout,
        "student_pk": student_id,
        "student_id": document["student_id"],
        "student_name": document["student_name"],
        "program_code": document["program_code"],
        "major_program": document["major_program"],
        "college": document["college"],
        "issued_at": timezone.now().isoformat(),
        "issued_by": issued_by,
        "verification_url": verification_url,
        "pdf_relative_path": pdf_relative_path,
        "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "pdf_size": len(pdf_bytes),
        "revoked": False,
        "revoked_reason": "",
    }


def issue_transcript_artifact(
    request: HttpRequest,
    *,
    layout: TranscriptLayoutKeyT,
    student_id: int,
) -> IssuedTranscriptArtifact:
    """Generate, sign, store, and return an official transcript artifact."""
    document = build_transcript_document(student_id)
    token = _new_token()
    verification_url = request.build_absolute_uri(
        reverse("transcript_verify", args=[token])
    )
    document = transcript_document_with_verification(
        document,
        qr_code_uri=qr_code_data_uri(verification_url),
        token=token,
        verification_url=verification_url,
    )
    pdf_bytes = render_transcript_document_pdf(document, layout=layout)
    student_part = _safe_filename_part(document["student_id"])
    pdf_relative_path = f"{ARTIFACT_ROOT}/{PDF_DIR}/{student_part}/{token}_{layout}.pdf"
    pdf_path = Path(settings.MEDIA_ROOT) / pdf_relative_path
    issued_by = getattr(request.user, "username", "") or "system"
    artifact = _artifact_payload(
        document=document,
        issued_by=issued_by,
        layout=layout,
        pdf_bytes=pdf_bytes,
        pdf_relative_path=pdf_relative_path,
        student_id=student_id,
        token=token,
        verification_url=verification_url,
    )
    _write_bytes_atomic(pdf_path, pdf_bytes)
    _write_json_atomic(_manifest_path(token), _signed_manifest(artifact))
    return IssuedTranscriptArtifact(
        artifact=artifact,
        filename=transcript_artifact_filename(artifact),
        pdf_bytes=pdf_bytes,
        pdf_path=pdf_path,
    )


__all__ = [
    "IssuedTranscriptArtifact",
    "TranscriptArtifactT",
    "issue_transcript_artifact",
    "load_transcript_artifact",
    "qr_code_data_uri",
    "transcript_artifact_filename",
    "transcript_artifact_pdf_path",
    "transcript_document_with_verification",
]
