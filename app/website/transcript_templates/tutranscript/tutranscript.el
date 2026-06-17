;;; tutranscript.el --- Org export helpers for TU transcripts -*- lexical-binding: t; -*-

;;; Commentary:
;; Load this file before exporting transcript Org sources with the local
;; tutranscript.cls and tutranscript.sty files.

;;; Code:

(require 'org)
(require 'org-table)
(require 'ox-latex)
(require 'seq)

(add-to-list
 'org-latex-classes
 '("tutranscript"
   "\\documentclass[10pt,a4paper]{tutranscript}"
   ("\\section{%s}" . "\\section*{%s}")
   ("\\subsection{%s}" . "\\subsection*{%s}")
   ("\\subsubsection{%s}" . "\\subsubsection*{%s}")))

(defconst tutranscript-latex-specials
  '(("\\" . "\\textbackslash{}")
    ("&" . "\\&")
    ("%" . "\\%")
    ("$" . "\\$")
    ("#" . "\\#")
    ("_" . "\\_")
    ("{" . "\\{")
    ("}" . "\\}")
    ("~" . "\\textasciitilde{}")
    ("^" . "\\textasciicircum{}"))
  "Characters escaped by `tutranscript-latex-escape'.")

(defun tutranscript-latex-escape (value)
  "Escape VALUE for simple LaTeX macro arguments."
  (let ((text (or value "")))
    (dolist (pair tutranscript-latex-specials text)
      (setq text
            (replace-regexp-in-string
             (regexp-quote (car pair))
             (cdr pair)
             text
             t
             t)))))

(defun tutranscript-course-row-to-macro (row)
  "Convert one ROW to a `\\TUTranscriptCourse' macro.
ROW must contain code, title, start date, end date, grade, attempted credit,
earned credit, and quality points."
  (format "\\TUTranscriptCourse{%s}{%s}{%s}{%s}{%s}{%s}{%s}{%s}"
          (tutranscript-latex-escape (or (nth 0 row) ""))
          (tutranscript-latex-escape (or (nth 1 row) ""))
          (tutranscript-latex-escape (or (nth 2 row) ""))
          (tutranscript-latex-escape (or (nth 3 row) ""))
          (tutranscript-latex-escape (or (nth 4 row) ""))
          (tutranscript-latex-escape (or (nth 5 row) ""))
          (tutranscript-latex-escape (or (nth 6 row) ""))
          (tutranscript-latex-escape (or (nth 7 row) ""))))

(defun tutranscript-org-course-table-to-macros ()
  "Copy transcript course macros generated from the Org table at point.
The table must have columns: code, title, start, end, grade, attempted,
earned, quality. Header and hline rows are ignored."
  (interactive)
  (unless (org-at-table-p)
    (user-error "Point is not inside an Org table"))
  (let* ((rows (org-table-to-lisp))
         (body (seq-filter (lambda (row) (and (listp row) (>= (length row) 8))) rows))
         (without-header (if (string= (downcase (or (caar body) "")) "code")
                             (cdr body)
                           body))
         (macros (mapconcat #'tutranscript-course-row-to-macro without-header "\n")))
    (kill-new macros)
    (message "Copied %d transcript course macros" (length without-header))))

(provide 'tutranscript)
;;; tutranscript.el ends here
