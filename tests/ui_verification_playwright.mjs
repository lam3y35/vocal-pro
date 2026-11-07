import { chromium } from "playwright";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const ROOT = process.cwd();
const SCREENSHOT_DIR = path.join(ROOT, "docs", "quality", "screenshots");
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

async function waitForServer(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function main() {
  const port = 4173;
  const baseUrl = `http://127.0.0.1:${port}`;
  const server = spawn("npx", ["vite", "preview", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: ROOT,
    stdio: "ignore",
  });

  try {
    await waitForServer(baseUrl);
    const browser = await chromium.launch({
      headless: true,
      executablePath: "/usr/bin/chromium",
      args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
    });
    const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    const page = await context.newPage();

    const t0 = Date.now();
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    const startupInteractiveMs = Date.now() - t0;

    // 1. Open First-Run Onboarding Wizard
    await page.getByRole("button", { name: /Setup Wizard/i }).click();
    await page.waitForSelector('[data-testid="onboarding-modal"]');
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "01_onboarding_first_run_1280x800.png"),
    });
    await page.getByRole("button", { name: /Save & Enter Studio/i }).click();

    // 2. Separation Screen Ready State (Dark, 1280x800)
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "02_separate_ready_dark_1280x800.png"),
    });

    // 3. Separation Screen Empty State
    await page.evaluate(() => {
      window.__VOCALPRO_STORES__.useJobsStore.getState().clearFiles();
    });
    await page.waitForTimeout(100);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "03_separate_empty_state_1280x800.png"),
    });

    // Restore files & start batch -> Running State
    await page.evaluate(() => {
      const store = window.__VOCALPRO_STORES__.useJobsStore.getState();
      store.addFiles([
        "C:\\Users\\Lam3y\\Music\\StudioSession_LeadVocal_44k.wav",
        "C:\\Users\\Lam3y\\Videos\\LiveConcert_4K.mp4",
      ]);
      store.startSeparationBatch();
    });
    await page.waitForSelector('[data-testid="job-queue-bar"]');
    await page.waitForTimeout(350);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "04_separate_running_batch_1280x800.png"),
    });

    // 5. Error State Card (Structured DECODE_FAILED + Retry + Export Diagnostics)
    await page.evaluate(() => {
      window.__VOCALPRO_STORES__.useJobsStore.getState().simulateFailedJob();
    });
    await page.waitForSelector('[data-testid="job-error-card"]');
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "05_separate_error_state_1280x800.png"),
    });

    // 6. Results & Real-Time 6-Stem Mixer Screen
    await page.locator("aside nav button").nth(2).click();
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "06_results_6stem_mixer_1280x800.png"),
    });

    // 7. History Screen
    await page.locator("aside nav button").nth(3).click();
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "07_history_screen_1280x800.png"),
    });

    // 8. Settings Screen (Basic View, Dark, 1280x800)
    await page.locator("aside nav button").nth(4).click();
    await page.waitForSelector('[data-testid="settings-screen"]');
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "08_settings_basic_dark_1280x800.png"),
    });

    // 9. Settings Screen (Advanced View, 1920x1080)
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.getByRole("tab", { name: /Advanced View/i }).click();
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "09_settings_advanced_dark_1920x1080.png"),
    });

    // 10. Light Theme Verification (1280x800)
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.getByRole("button", { name: /Toggle Light or Dark Theme/i }).click();
    await page.waitForTimeout(150);
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "10_settings_light_theme_1280x800.png"),
    });
    // Switch back to Dark theme
    await page.getByRole("button", { name: /Toggle Light or Dark Theme/i }).click();

    // 11. Arabic RTL Layout Verification (dir="rtl")
    await page.evaluate(() => {
      window.__VOCALPRO_STORES__.useSystemStore.getState().setLocale("ar");
    });
    await page.locator("aside nav button").nth(1).click();
    await page.waitForTimeout(150);
    const dirAttr = await page.locator("div[dir]").first().getAttribute("dir");
    await page.screenshot({
      path: path.join(SCREENSHOT_DIR, "11_separate_arabic_rtl_1280x800.png"),
    });

    // Reset locale to English
    await page.evaluate(() => {
      window.__VOCALPRO_STORES__.useSystemStore.getState().setLocale("en");
    });

    // Audit DOM accessibility & layout overflow metrics
    const audit = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll("button"));
      const unlabeledButtons = buttons.filter(
        (b) =>
          !(b.textContent || "").trim() &&
          !b.getAttribute("aria-label") &&
          !b.getAttribute("title")
      ).length;
      const docWidth = document.documentElement.scrollWidth;
      const winWidth = window.innerWidth;
      return {
        totalButtons: buttons.length,
        unlabeledButtons,
        horizontalOverflowPx: Math.max(0, docWidth - winWidth),
      };
    });

    const summary = {
      startup_interactive_ms: startupInteractiveMs,
      rtl_dir_attribute: dirAttr,
      screenshots_captured: fs.readdirSync(SCREENSHOT_DIR).sort(),
      accessibility_audit: audit,
    };
    fs.writeFileSync(
      path.join(ROOT, "benchmarks", "ui_audit_results.json"),
      JSON.stringify(summary, null, 2)
    );
    console.log("UI Audit Summary:", JSON.stringify(summary, null, 2));
    await browser.close();
  } finally {
    server.kill("SIGTERM");
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
