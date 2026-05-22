// Node Playwright scraper for modoo.or.kr 도전 아이디어 list.
//
// Invoked as a subprocess by collectors/modoo.py. Stdin is ignored.
// Reads CLI args: --pages <n> --timeout <ms>
// Writes a JSON array of {category, time, title, page} to stdout.
// All diagnostics go to stderr so the parent can json.loads() stdout cleanly.

import { chromium } from 'playwright';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  if (i === -1) return fallback;
  return process.argv[i + 1] ?? fallback;
}

const PAGES = Math.max(1, Math.min(20, parseInt(arg('--pages', '3'), 10)));
const TIMEOUT_MS = parseInt(arg('--timeout', '60000'), 10);

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  locale: 'ko-KR',
  userAgent:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
});
const page = await ctx.newPage();

const collected = [];
try {
  for (let p = 1; p <= PAGES; p++) {
    const url =
      p === 1
        ? 'https://www.modoo.or.kr/idea/list'
        : `https://www.modoo.or.kr/idea/list?page=${p}`;
    await page.goto(url, { waitUntil: 'networkidle', timeout: TIMEOUT_MS });
    await page.waitForTimeout(2500);

    const cards = await page.evaluate(() => {
      const rows = [];
      const badges = document.querySelectorAll('div.flex.items-center.gap-\\[6px\\]');
      badges.forEach((badge) => {
        const btxt = (badge.textContent || '').trim();
        if (!/(분|시간|일)\s*전/.test(btxt)) return;
        let node = badge;
        for (let i = 0; i < 6; i++) {
          if (node.parentElement) node = node.parentElement;
          else break;
          const txt = (node.innerText || '').trim();
          const lines = txt.split('\n').map((s) => s.trim()).filter(Boolean);
          if (lines.length >= 3) {
            rows.push({
              category: lines[0],
              time: lines[1],
              title: lines.slice(2).find((l) => !/^도전자|^\d+$/.test(l)) || lines[2],
            });
            break;
          }
        }
      });
      return rows;
    });
    process.stderr.write(`[modoo] page ${p}: ${cards.length}\n`);
    cards.forEach((c) => collected.push({ page: p, ...c }));
  }
} finally {
  await browser.close();
}

process.stdout.write(JSON.stringify(collected));
