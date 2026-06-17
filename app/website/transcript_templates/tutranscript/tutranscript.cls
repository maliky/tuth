\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{tutranscript}[2026/06/15 TU transcript class]

\DeclareOption{9pt}{\PassOptionsToClass{9pt}{article}}
\DeclareOption{10pt}{\PassOptionsToClass{10pt}{article}}
\DeclareOption{11pt}{\PassOptionsToClass{11pt}{article}}
\DeclareOption{12pt}{\PassOptionsToClass{12pt}{article}}
\DeclareOption{a4paper}{\PassOptionsToClass{a4paper}{article}}
\DeclareOption{letterpaper}{\PassOptionsToClass{letterpaper}{article}}
\ExecuteOptions{10pt,a4paper}
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass{article}
\RequirePackage{tutranscript}
\endinput
