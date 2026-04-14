const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  
  // Set viewport to a nice desktop size
  await page.setViewportSize({ width: 1280, height: 1080 });
  
  // Geopolitical
  await page.goto('http://localhost:3000/geopolitical', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/Users/gio/.gemini/antigravity/brain/0c935f67-1eb9-4b6f-8536-68ca7fadfe5b/geo_screen.png' });
  
  // Asset
  await page.goto('http://localhost:3000/asset/NVDA', { waitUntil: 'networkidle' });
  await page.screenshot({ path: '/Users/gio/.gemini/antigravity/brain/0c935f67-1eb9-4b6f-8536-68ca7fadfe5b/asset_screen.png' });
  
  await browser.close();
})();
