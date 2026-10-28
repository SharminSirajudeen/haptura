// How each page looks, measured: every band keeps the gutter on both edges, and every piece of text meets WCAG AA
// contrast in both colour schemes.
const { test, expect, ready } = require('./site');

const gutter = (width) => Math.min(96, Math.max(16, width / 20)); // style.css --gutter: clamp(16px, 5vw, 96px)
// The two pages, by the fixture that holds each URL, and what each must finish drawing before it is measured.
const PAGES = { site: ['the landing page', () => {}], viewer: ['the arena viewer', ready] };

// Runs in the page. Each element that holds text: its colour over the backgrounds under it, against those backgrounds.
// A canvas reads any CSS colour syntax back as RGBA.
function contrast() {
  const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
  const rgba = (css) => {
    ctx.clearRect(0, 0, 1, 1);
    ctx.fillStyle = css;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  };
  const over = (top, base) => [0, 1, 2].map((i) => top[i] * top[3] + base[i] * (1 - top[3])).concat(1);
  const under = (el) => {
    const layers = [];
    for (let e = el; e && (layers.at(-1)?.[3] ?? 0) < 1; e = e.parentElement) layers.push(rgba(getComputedStyle(e).backgroundColor));
    return layers.reverse().reduce((base, top) => over(top, base), [255, 255, 255, 1]);
  };
  const linear = (v) => (v / 255 <= 0.04045 ? v / 255 / 12.92 : ((v / 255 + 0.055) / 1.055) ** 2.4);
  const lum = ([r, g, b]) => 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b);
  const holdsText = (el) => [...el.childNodes].some((n) => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
  const texts = [...document.body.querySelectorAll('*')].filter((el) => holdsText(el) && el.checkVisibility());
  const low = texts.flatMap((el) => {
    const style = getComputedStyle(el);
    const bg = under(el);
    const [hi, lo] = [lum(over(rgba(style.color), bg)), lum(bg)].sort((x, y) => y - x);
    const ratio = (hi + 0.05) / (lo + 0.05);
    const size = parseFloat(style.fontSize);
    const large = size >= 24 || (size >= 18.66 && Number(style.fontWeight) >= 700);
    return ratio < (large ? 3 : 4.5) ? [`${el.tagName} "${el.textContent.trim().slice(0, 40)}" ${ratio.toFixed(2)}`] : [];
  });
  return { checked: texts.length, low };
}

// Runs in the page. Each band's content box: where its own gutter leaves its content on the left and on the right.
const contentEdges = (bands) =>
  bands.map((band) => {
    const box = band.getBoundingClientRect();
    const style = getComputedStyle(band);
    return { band: band.id || band.className, left: box.left + parseFloat(style.paddingLeft), right: box.right - parseFloat(style.paddingRight) };
  });

for (const [fixture, [name, drawn]] of Object.entries(PAGES)) {
  for (const width of [390, 1440, 1920, 2560]) {
    test(`every band on ${name} keeps the gutter on both edges at ${width} px`, async ({ page, site, viewer }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto({ site, viewer }[fixture]);
      await drawn(page);
      const bands = await page.locator('.topnav, .band').evaluateAll(contentEdges);
      expect(bands.length).toBeGreaterThan(1);
      const off = bands.filter(({ left, right }) => Math.abs(left - gutter(width)) > 0.5 || Math.abs(right - width + gutter(width)) > 0.5);
      expect(off).toEqual([]);
    });
  }
  for (const scheme of ['light', 'dark']) {
    test(`every piece of text on ${name} meets WCAG AA contrast in the ${scheme} scheme`, async ({ page, site, viewer }) => {
      await page.emulateMedia({ colorScheme: scheme });
      await page.goto({ site, viewer }[fixture]);
      await drawn(page);
      const { checked, low } = await page.evaluate(contrast);
      expect(checked).toBeGreaterThan(0);
      expect(low).toEqual([]);
    });
  }
}
