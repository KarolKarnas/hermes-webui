const fs = require('fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const output = path.resolve(process.argv[2] || '/tmp/hermes-clarify-layout');
fs.mkdirSync(output, {recursive:true});
const baseCss = execFileSync('git', ['show', 'e33da25c6cfde3ea337e1b6d7701161d02e995cf:static/style.css'], {cwd:root, encoding:'utf8'});
(async () => {
  const browser = await chromium.launch({...(process.env.CHROME_PATH ? {executablePath:process.env.CHROME_PATH} : {}), headless:true});
  try {
    for (const version of ['before','after']) {
      const css = version === 'before' ? baseCss : fs.readFileSync(`${root}/static/style.css`,'utf8');
      const index = fs.readFileSync(`${root}/static/index.html`,'utf8');
      const start = index.indexOf('<div class="clarify-card"');
      const end = index.indexOf('<div class="composer-terminal-panel"',start);
      const card = index.slice(start,end).replace('class="clarify-card"','class="clarify-card visible"')
          .replace('hidden aria-hidden="true" inert','aria-hidden="false"');
      for (const [width,height] of [[1280,800],[720,800],[390,844],[390,440]]) {
        const page = await browser.newPage({viewport:{width,height},isMobile:width<640,hasTouch:width<640});
        await page.setContent(`<html class="dark"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style>
          <style>.test-shell{position:fixed;bottom:0;left:0;right:0} .test-composer{height:110px;padding:16px;box-sizing:border-box}</style></head>
          <body><div class="test-shell"><div class="composer-wrap"><div class="composer-flyout">${card}</div>
          <div class="composer-box test-composer">Clarification needed<br><br>Attach　Microphone　Send</div></div></div></body></html>`);
        await page.locator('#clarifyQuestion').evaluate(el=>el.textContent='Which database should we use? Postgres or SQLite?');
        await page.waitForTimeout(500);
        const box = await page.locator('.clarify-inner').boundingBox();
        const composer = await page.locator('.composer-box').boundingBox();
        const gap = composer.y-(box.y+box.height);
        console.log(`${version} ${width}x${height}: panel/composer gap=${gap}`);
        if(version==='before') assert.ok(gap<0,'Must reproduce overlapping panel');
        else {
          assert.ok(gap>=8,'Panel must stay above composer');
          assert.ok(box.y>=0,'Question must stay within viewport');
          await page.locator('#clarifyInput').click();
          await page.locator('#clarifyInput').fill('Please use Postgres');
          assert.equal(await page.locator('#clarifyInput').inputValue(),'Please use Postgres');
          await page.locator('#clarifyQuestion').evaluate(el=>el.textContent='Long question details. '.repeat(90));
          assert.ok(await page.locator('.clarify-inner').evaluate(el=>el.scrollHeight>el.clientHeight));
          await page.locator('.clarify-inner').evaluate(el=>el.scrollTop=el.scrollHeight);
          const send = await page.locator('#clarifySubmit').boundingBox();
          assert.ok(send.y>=0 && send.y+send.height<=composer.y,'Send must be scrollable into view');
          await page.locator('.clarify-inner').evaluate(el=>el.scrollTop=0);
          assert.ok(await page.locator('#clarifyQuestion').evaluate(el=>el.getBoundingClientRect().top>=0));
        }
        await page.locator('#clarifyQuestion').evaluate(el=>el.textContent='Which database should we use? Postgres or SQLite?');
        await page.screenshot({path:`${output}/${version}-${width}x${height}.png`});
        await page.close();
      }
    }
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exit(1)});
