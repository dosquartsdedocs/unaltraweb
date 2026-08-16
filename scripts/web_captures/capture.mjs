import { readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";

function fail(message) {
  throw new Error(message);
}

function sameOrigin(candidate, origin) {
  try {
    const url = new URL(candidate);
    return url.protocol === "data:" || url.protocol === "blob:" || url.origin === origin;
  } catch {
    return false;
  }
}

async function selectorBox(page, item, label) {
  const selector = item.selector;
  const count = await page.locator(selector).count();
  const strict = item.strict !== false;
  const required = item.required !== false;
  if (!count) {
    if (required) fail(`Missing ${label} selector: ${selector}`);
    return null;
  }
  if (strict && count !== 1) fail(`${label} selector must match exactly one element: ${selector}`);
  const index = strict ? 0 : Number(item.nth || 0);
  if (index < 0 || index >= count) fail(`${label} selector index is out of range: ${selector}`);
  const locator = page.locator(selector).nth(index);
  return locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return {
      x: box.x + window.scrollX,
      y: box.y + window.scrollY,
      width: box.width,
      height: box.height,
    };
  });
}

async function waitForImages(page) {
  await page.waitForFunction(() => Array.from(document.images).every((image) => image.complete && (!image.currentSrc || image.naturalWidth > 0)));
}

async function main() {
  const configPath = process.argv[2];
  if (!configPath) fail("Usage: capture.mjs CONFIG.json");
  const config = JSON.parse(await readFile(configPath, "utf8"));
  const target = new URL(config.url);
  const browser = await chromium.launch({ headless: true });
  try {
    const context = await browser.newContext({
      viewport: { width: config.viewport.width, height: config.viewport.height },
      deviceScaleFactor: config.viewport.device_scale_factor,
      colorScheme: config.theme.color_scheme,
      reducedMotion: "reduce",
      locale: config.locale || "en-US",
      serviceWorkers: "block",
    });
    if (config.theme.setting) {
      await context.addInitScript((setting) => localStorage.setItem("theme", setting), config.theme.setting);
    }
    await context.route("**/*", async (route) => {
      if (sameOrigin(route.request().url(), target.origin)) await route.continue();
      else await route.abort("blockedbyclient");
    });
    await context.routeWebSocket("**/*", (route) => route.close());
    const page = await context.newPage();
    context.on("page", (candidate) => {
      if (candidate !== page) candidate.close().catch(() => {});
    });
    const response = await page.goto(target.href, {
      waitUntil: config.waits.wait_until,
      timeout: config.waits.timeout_ms,
    });
    if (!response) fail(`Navigation returned no response: ${target.href}`);
    if (response.status() < 200 || response.status() >= 400) fail(`Navigation failed with HTTP ${response.status()}: ${target.href}`);
    const finalUrl = new URL(page.url());
    if (finalUrl.origin !== target.origin) fail(`Navigation left the allowed origin: ${finalUrl.href}`);

    for (const wait of config.waits.selectors) {
      await page.locator(wait.selector).waitFor({ state: wait.state, timeout: config.waits.timeout_ms });
    }
    if (config.waits.fonts) await page.evaluate(() => document.fonts.ready);
    if (config.waits.images) await waitForImages(page);
    if (config.waits.delay_ms) await page.waitForTimeout(config.waits.delay_ms);

    if (config.theme.expect) {
      const expected = config.theme.expect;
      const actual = await page.locator(expected.selector).first().getAttribute(expected.attribute);
      if (actual !== expected.equals) fail(`Theme expectation failed for ${expected.selector}[${expected.attribute}]: expected ${expected.equals}, got ${actual}`);
    }

    let origin = { x: 0, y: 0 };
    let fullPage = config.capture.full_page === true;
    let clip;
    const captureSelector = config.capture.selector || config.capture.clip?.selector;
    if (captureSelector) {
      const item = { selector: captureSelector, strict: true, required: true };
      const box = await selectorBox(page, item, "capture");
      const padding = Number(config.capture.clip ? config.capture.clip.padding : config.capture.padding);
      clip = {
        x: Math.max(0, box.x - padding),
        y: Math.max(0, box.y - padding),
        width: box.width + padding * 2,
        height: box.height + padding * 2,
      };
      origin = { x: clip.x, y: clip.y };
      fullPage = false;
    }

    const annotations = [];
    for (const annotation of config.annotations) {
      const box = await selectorBox(page, annotation, `annotation ${annotation.id}`);
      if (box) annotations.push({ ...annotation, box });
    }

    const cssDimensions = fullPage
      ? await page.evaluate(() => ({ width: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight }))
      : clip
        ? { width: clip.width, height: clip.height }
        : { width: config.viewport.width, height: config.viewport.height };
    const pixelWidth = Math.ceil(cssDimensions.width * config.viewport.device_scale_factor);
    const pixelHeight = Math.ceil(cssDimensions.height * config.viewport.device_scale_factor);
    if (pixelWidth > 20000 || pixelHeight > 20000 || pixelWidth * pixelHeight > 80000000) {
      fail(`Capture dimensions exceed safety limits: ${pixelWidth}x${pixelHeight}`);
    }

    await page.screenshot({
      path: config.png_path,
      fullPage,
      clip,
      animations: "disabled",
      caret: "hide",
      scale: "device",
    });
    const result = {
      ok: true,
      browser_version: browser.version(),
      final_url: finalUrl.href,
      status: response.status(),
      origin,
      dimensions: cssDimensions,
      device_scale_factor: config.viewport.device_scale_factor,
      annotations,
    };
    await writeFile(config.result_path, JSON.stringify(result, null, 2) + "\n", "utf8");
    process.stdout.write(JSON.stringify(result) + "\n");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
});
