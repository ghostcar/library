const { chromium } = require("playwright");
const { pathToFileURL } = require("node:url");
const path = require("node:path");

async function checkViewport(page, width, height, expected) {
  await page.setViewportSize({ width, height });
  await page.goto(pathToFileURL(path.join(__dirname, "shell_fixture.html")).href);

  const state = await page.evaluate(() => ({
    sidebar: getComputedStyle(document.querySelector(".sidebar")).display,
    bottomNav: getComputedStyle(document.querySelector(".bottom-nav")).display,
    overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
    iconWidth: document.querySelector(".icon").getBoundingClientRect().width,
  }));
  if (state.sidebar !== expected.sidebar || state.bottomNav !== expected.bottomNav) {
    throw new Error(`${width}px: unexpected navigation state ${JSON.stringify(state)}`);
  }
  if (state.overflow) throw new Error(`${width}px: horizontal overflow`);
  if (state.iconWidth < 18 || state.iconWidth > 22) {
    throw new Error(`${width}px: icon width ${state.iconWidth}px`);
  }
}

(async () => {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;
  const browser = await chromium.launch({
    headless: true,
    ...(executablePath ? { executablePath } : {}),
  });
  try {
    const page = await browser.newPage();
    await checkViewport(page, 1280, 800, { sidebar: "flex", bottomNav: "none" });
    await checkViewport(page, 390, 844, { sidebar: "none", bottomNav: "grid" });
    console.log("browser shell checks passed: desktop 1280x800, mobile 390x844");
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
