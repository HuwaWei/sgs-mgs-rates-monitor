.PHONY: all analysis test pdf clean

all: analysis test        ## one command: analytics, tables, charts, tests

analysis:
	python3 -m src.main

test:
	python3 -m pytest -q

pdf:                      ## optional: render report PDFs (needs pandoc + Node Playwright/Chromium)
	bash scripts/build_pdf.sh

clean:
	rm -rf output/*.png output/tables output/summary.json
