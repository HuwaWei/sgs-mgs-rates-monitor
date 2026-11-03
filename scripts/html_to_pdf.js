// Usage: node scripts/html_to_pdf.js in.html out.pdf  -> prints page count
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [inp, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + path.resolve(inp), { waitUntil: 'networkidle' });
  await page.pdf({ path: out, format: 'A4', preferCSSPageSize: true, printBackground: true });
  await browser.close();
})();
