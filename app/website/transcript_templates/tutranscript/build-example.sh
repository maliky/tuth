#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
org_home="/home/mlk/.emacs.d/elpa/org-9.7.5"
emacs_args=(--batch --quick)

if [[ -d "$org_home" ]]; then
  emacs_args+=(-L "$org_home")
fi

refresh_orgtbl() {
  emacs "${emacs_args[@]}" -l "$root/tutranscript.el" \
    --eval "(setq make-backup-files nil auto-save-default nil create-lockfiles nil)" \
    "$root/example.org" \
    --eval "(progn
              (setq buffer-read-only nil)
              (goto-char (point-min))
              (while (re-search-forward \"^#\\\\+ORGTBL: SEND\" nil t)
                (unless (re-search-forward \"^[ \t]*|\" nil t)
                  (error \"No Org table found after ORGTBL line\"))
                (beginning-of-line)
                (orgtbl-send-table t)
                (forward-line 1))
              (write-region (point-min) (point-max) buffer-file-name nil 'silent))"
}

build_layout() {
  local options="$1"
  local output="${2:-$1}"
  local profile="${3:-}"
  local tmpdir
  tmpdir="$(mktemp -d)"
  cp "$root/example.org" "$tmpdir/example.org"
  cp "$root/tutranscript.cls" "$tmpdir/tutranscript.cls"
  cp "$root/tutranscript.sty" "$tmpdir/tutranscript.sty"
  cp "$root/tutranscript.el" "$tmpdir/tutranscript.el"
  if [[ -f "$root/logo120pi.png" ]]; then
    cp "$root/logo120pi.png" "$tmpdir/logo120pi.png"
  fi

  perl -0pi -e "s/#\\+LATEX_CLASS_OPTIONS: \\[[^\\n]+\\]/#+LATEX_CLASS_OPTIONS: [10pt,a4paper,$options]/;
                s/#\\+EXPORT_FILE_NAME: [^\\n]+/#+EXPORT_FILE_NAME: example_$output/;" \
    "$tmpdir/example.org"

  if [[ "$profile" == "portrait_two" ]]; then
    python3 - "$tmpdir/example.org" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
replacements = {
    r"#+LATEX_HEADER: \setlength{\TUTRBlockColumnSep}{3cm}":
        r"#+LATEX_HEADER: \setlength{\TUTRBlockColumnSep}{0.35cm}",
    r"#+LATEX_HEADER: \setlength{\TUTRTermGap}{2ex}":
        r"#+LATEX_HEADER: \setlength{\TUTRTermGap}{0.75ex}",
    r"#+LATEX_HEADER: \setlength{\TUTRTermHeaderGap}{0.45ex}":
        r"#+LATEX_HEADER: \setlength{\TUTRTermHeaderGap}{0.18ex}",
}
for old, new in replacements.items():
    text = text.replace(old, new, 1)
insert_after = r"#+LATEX_HEADER: \TUTranscriptShowQRfalse" + "\n"
extra = "".join([
    r"#+LATEX_HEADER: \setlength{\TUTRDetailColSep}{0.06cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTRCodeW}{1.65cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTRGradeW}{0.48cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTRAttemptedW}{0.72cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTREarnedW}{0.72cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTRPointsW}{0.80cm}" + "\n",
    r"#+LATEX_HEADER: \setlength{\TUTRTermTotalGap}{0.22ex}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTRDetailFont}{\fontsize{9pt}{9.4pt}\selectfont}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTRDetailStretch}{0.86}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTRGradeLabel}{Gr.}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTRAttemptedLabel}{Att}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTREarnedLabel}{Ern}" + "\n",
    r"#+LATEX_HEADER: \renewcommand{\TUTRPointsLabel}{Pts}" + "\n",
])
if extra not in text:
    text = text.replace(insert_after, insert_after + extra, 1)
text = text.replace("<T6.1cm>", "<T2.8cm>")
text = text.replace("<T6.2cm>", "<T2.8cm>")
text = text.replace("[6.1cm]", "[2.8cm]")
text = text.replace("[6.2cm]", "[2.8cm]")
path.write_text(text)
PY
  fi

  (
    cd "$tmpdir"
    TEXMFVAR=/tmp/texmf-var TEXMFCACHE=/tmp/texmf-cache \
      emacs "${emacs_args[@]}" -l ./tutranscript.el example.org \
      --eval "(org-latex-export-to-pdf)"
    TEXMFVAR=/tmp/texmf-var TEXMFCACHE=/tmp/texmf-cache \
      lualatex -interaction=nonstopmode -halt-on-error "example_$output.tex" >/dev/null
    TEXMFVAR=/tmp/texmf-var TEXMFCACHE=/tmp/texmf-cache \
      lualatex -interaction=nonstopmode -halt-on-error "example_$output.tex" >/dev/null
  )

  cp "$tmpdir/example_$output.pdf" "$root/example_$output.pdf"
  cp "$tmpdir/example_$output.tex" "$root/example_$output.tex"
  rm -rf "$tmpdir"
}

refresh_orgtbl
case "${1:-all}" in
  all)
    build_layout portrait portrait
    build_layout landscape landscape
    build_layout "portrait,detailtwocolumns" portrait_two portrait_two
    ;;
  portrait)
    build_layout portrait portrait
    ;;
  landscape)
    build_layout landscape landscape
    ;;
  portrait_two)
    build_layout "portrait,detailtwocolumns" portrait_two portrait_two
    ;;
  *)
    echo "usage: $0 [all|portrait|landscape|portrait_two]" >&2
    exit 2
    ;;
esac
