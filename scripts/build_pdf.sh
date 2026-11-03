#!/usr/bin/env bash
# Render report markdown to PDF: pandoc (md -> html, MathML) + headless Chromium (html -> pdf).
set -euo pipefail
cd "$(dirname "$0")/../report"
for doc in trade_pitch rates_note; do
  pandoc "$doc.md" -s --mathml --css style.css --resource-path=.:.. -o "$doc.html"
  node ../scripts/html_to_pdf.js "$doc.html" "$doc.pdf"
  python3 -c "import re,sys; print('$doc.pdf pages:', len(re.findall(rb'/Type\s*/Page[^s]', open('$doc.pdf','rb').read())))"
done
