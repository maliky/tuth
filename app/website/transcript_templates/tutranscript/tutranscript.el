;;; tutranscript.el --- Org export helpers for TU transcripts -*- lexical-binding: t; -*-

;;; Commentary:
;; Load this file before exporting transcript Org sources with the local
;; tutranscript.cls and tutranscript.sty files.

;;; Code:

(require 'org)
(require 'org-table)
(require 'ox-latex)
(require 'cl-lib)
(require 'subr-x)
(require 'seq)

(add-to-list
 'org-latex-classes
 '("tutranscript"
   "\\documentclass[10pt,a4paper]{tutranscript}"
   ("\\section{%s}" . "\\section*{%s}")
   ("\\subsection{%s}" . "\\subsection*{%s}")
   ("\\subsubsection{%s}" . "\\subsubsection*{%s}")))

(defconst tutranscript-latex-specials
  '((?\\ . "\\textbackslash{}")
    (?& . "\\&")
    (?% . "\\%")
    (?$ . "\\$")
    (?# . "\\#")
    (?_ . "\\_")
    (?{ . "\\{")
    (?} . "\\}")
    (?~ . "\\textasciitilde{}")
    (?^ . "\\textasciicircum{}"))
  "Characters escaped by `tutranscript-latex-escape'.")

(defun tutranscript-latex-escape (value)
  "Escape VALUE for simple LaTeX macro arguments."
  (mapconcat
   (lambda (char)
     (or (alist-get char tutranscript-latex-specials)
         (char-to-string char)))
   (or value "")
   ""))

(defun tutranscript--blank-p (value)
  "Return non-nil when VALUE is nil or whitespace-only."
  (or (null value)
      (and (stringp value)
           (not (string-match-p "[^[:space:]]" value)))))

(defun tutranscript--separator-row-p (row)
  "Return non-nil when ROW is an Org table separator."
  (or (eq row 'hline)
      (equal row '(hline))))

(defun tutranscript--colhint-cell-p (value)
  "Return non-nil when VALUE is an Org column width hint like <10>."
  (string-match-p "\\`<[0-9]+>\\'" (string-trim (or value ""))))

(defun tutranscript--colhint-row-p (row)
  "Return non-nil when ROW contains only Org width hints and blanks."
  (and (listp row)
       (seq-some #'tutranscript--colhint-cell-p row)
       (seq-every-p
        (lambda (cell)
          (or (tutranscript--blank-p cell)
              (tutranscript--colhint-cell-p cell)))
        row)))

(defun tutranscript--data-row-p (row)
  "Return non-nil when ROW is real transcript table data."
  (and (listp row)
       (not (tutranscript--separator-row-p row))
       (not (tutranscript--colhint-row-p row))))

(defun tutranscript--header-row-p (row)
  "Return non-nil when ROW is the transcript source header row."
  (and (listp row)
       (string= (downcase (string-trim (or (car row) ""))) "kind")))

(defun tutranscript--parse-cell (value)
  "Parse the small transcript cell marker language from VALUE.
Supported leading markers are <Tlen> for a title truncation override.
The marker is removed from the visible text and LEN is passed through as a
LaTeX width, adding cm when LEN is a bare number."
  (let ((text (string-trim-left (or value "")))
        truncate marker raw-truncate)
    (while (string-match "\\`<T\\([^>]+\\)>" text)
      (setq marker (match-string 0 text)
            raw-truncate (string-trim (match-string 1 text))
            text (string-trim-left (substring text (length marker))))
      (when (string-empty-p raw-truncate)
        (error "Empty truncate marker in transcript cell: %s" value))
      (setq truncate
            (if (string-match-p "\\`[0-9]+\\(?:\\.[0-9]+\\)?\\'" raw-truncate)
                (concat raw-truncate "cm")
              raw-truncate)))
    (list :text (string-trim text) :truncate truncate)))

(defun tutranscript--cell-text (value)
  "Return VALUE with transcript cell markers removed."
  (plist-get (tutranscript--parse-cell value) :text))

(defun tutranscript--cell-tex (value)
  "Return VALUE marker-stripped and escaped for LaTeX."
  (tutranscript-latex-escape (tutranscript--cell-text value)))

(defun tutranscript--course-row-to-macro (row)
  "Convert a transcript source ROW into a `\\TUTranscriptCourse' macro."
  (let* ((title-cell (tutranscript--parse-cell (or (nth 3 row) "")))
         (truncate (plist-get title-cell :truncate))
         (title (tutranscript-latex-escape (plist-get title-cell :text)))
         (prefix (if truncate (format "[%s]" truncate) "")))
    (format "\\TUTranscriptCourse%s{%s}{%s}{%s}{%s}{%s}{%s}"
            prefix
            (tutranscript--cell-tex (nth 2 row))
            title
            (tutranscript--cell-tex (nth 4 row))
            (tutranscript--cell-tex (nth 5 row))
            (tutranscript--cell-tex (nth 6 row))
            (tutranscript--cell-tex (nth 7 row)))))

(defun tutranscript--totals-row-to-macro (row default-label &optional macro)
  "Convert a transcript total ROW using DEFAULT-LABEL when title is blank."
  (format "\\%s{%s}{%s}{%s}{%s}{%s}"
          (or macro "TUTranscriptTotals")
          (let ((label (tutranscript--cell-text (nth 3 row))))
            (tutranscript-latex-escape
             (if (string-empty-p label) default-label label)))
          (tutranscript--cell-tex (nth 8 row))
          (tutranscript--cell-tex (nth 5 row))
          (tutranscript--cell-tex (nth 6 row))
          (tutranscript--cell-tex (nth 7 row))))

(defun tutranscript--source-rows (table)
  "Return transcript data rows from TABLE."
  (seq-remove
   (lambda (row)
     (or (not (tutranscript--data-row-p row))
         (tutranscript--header-row-p row)))
   table))

(defun tutranscript-detail (table _params)
  "Emit semantic transcript detail macros from an Org TABLE.
The table columns are kind, term, code, title, grade, attempted, earned,
quality, and gpa. Supported kinds are program, term, course, term-total,
program-total, and column-break. Course-title cells may start with <Twidth>
to override the default title truncation width for that one row."
  (let ((rows (tutranscript--source-rows table))
        (out '("\\TUTranscriptUseBlockstrue"
               "\\renewcommand{\\TUTranscriptDetailRows}{%"))
        current-term
        current-lines)
    (cl-labels
        ((flush-term
          ()
          (when current-term
            (setq out
                  (append out
                          (list (format "  \\TUTranscriptTermBlock{%s}{%%"
                                        (tutranscript-latex-escape current-term)))
                          (mapcar (lambda (line) (concat "    " line))
                                  (nreverse current-lines))
                          (list "  }"))))
          (setq current-term nil
                current-lines nil)))
      (dolist (row rows)
        (let ((kind (downcase (string-trim (or (car row) "")))))
          (pcase kind
            ("program"
             (flush-term)
             (setq out
                   (append
                    out
                    (list
                     (format "  \\TUTranscriptProgramBlock{%s}{%s}"
                             (tutranscript--cell-tex (nth 2 row))
                             (tutranscript--cell-tex (nth 3 row)))))))
            ("column-break"
             (flush-term)
             (setq out (append out '("  \\TUTranscriptColumnBreak"))))
            ("term"
             (flush-term)
             (setq current-term (tutranscript--cell-text (nth 1 row))))
            ("course"
             (unless current-term
               (error "Transcript course row appears before a term: %S" row))
             (push (tutranscript--course-row-to-macro row) current-lines))
            ("term-total"
             (unless current-term
               (error "Transcript term-total row appears before a term: %S" row))
             (push (tutranscript--totals-row-to-macro
                    row "Term Totals" "TUTranscriptTermTotals")
                   current-lines))
            ("program-total"
             (unless current-term
               (error "Transcript program-total row appears before a term: %S" row))
             (push (tutranscript--totals-row-to-macro row "Program Totals")
                   current-lines))
            (""
             nil)
            (_
             (error "Unsupported transcript row kind %S in row %S" kind row)))))
      (flush-term))
    (unless (> (length rows) 0)
      (setq out (append out '("  \\TUTranscriptEmptyBlock{No grades recorded.}"))))
    (setq out (append out '("}")))
    (mapconcat #'identity out "\n")))

(defun tutranscript-course-row-to-macro (row)
  "Convert one ROW to a `\\TUTranscriptCourse' macro.
ROW must contain code, title, grade, attempted credit, earned credit, and
quality points."
  (format "\\TUTranscriptCourse{%s}{%s}{%s}{%s}{%s}{%s}"
          (tutranscript-latex-escape (or (nth 0 row) ""))
          (tutranscript-latex-escape (or (nth 1 row) ""))
          (tutranscript-latex-escape (or (nth 2 row) ""))
          (tutranscript-latex-escape (or (nth 3 row) ""))
          (tutranscript-latex-escape (or (nth 4 row) ""))
          (tutranscript-latex-escape (or (nth 5 row) ""))))

(defun tutranscript-org-course-table-to-macros ()
  "Copy transcript course macros generated from the Org table at point.
The table must have columns: code, title, grade, attempted, earned, quality.
Header and hline rows are ignored."
  (interactive)
  (unless (org-at-table-p)
    (user-error "Point is not inside an Org table"))
  (let* ((rows (org-table-to-lisp))
         (body (seq-filter (lambda (row) (and (listp row) (>= (length row) 6))) rows))
         (without-header (if (string= (downcase (or (caar body) "")) "code")
                             (cdr body)
                           body))
         (macros (mapconcat #'tutranscript-course-row-to-macro without-header "\n")))
    (kill-new macros)
    (message "Copied %d transcript course macros" (length without-header))))

(provide 'tutranscript)
;;; tutranscript.el ends here
