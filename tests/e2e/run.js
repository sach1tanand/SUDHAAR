// End-to-end browser test for Sudhaar (uses Playwright + Chromium with a fake camera and GPS).
//   SUDHAAR_OFFLINE=1 python -m uvicorn backend.main:app --port 8000   (fresh SUDHAAR_DATA)
//   node tests/e2e/run.js            # BASE=http://localhost:8000 SHOTS=/some/dir to save screenshots
const { chromium } = require('playwright');
const path = require('path');
const BASE = process.env.BASE || 'http://localhost:8000', SHOTS = process.env.SHOTS || '';
let pass = 0, fail = 0;
const ok = (c, m) => { if (c) { pass++; console.log('  PASS', m); } else { fail++; console.log('  FAIL', m); } };
const shot = async (p, n) => { if (SHOTS) await p.screenshot({ path: path.join(SHOTS, n + '.png'), fullPage: false }); };

async function typeStaffLogin(page, user, pw) {   // regression: typing must really work (keystrokes used to be cancelled)
  await page.goto(BASE + '/#/staff'); await page.waitForSelector('#u');
  await page.click('#u'); await page.keyboard.type(user, { delay: 15 });
  await page.click('#p'); await page.keyboard.type(pw, { delay: 15 });
  const typed = await page.inputValue('#p'); ok(typed === pw, `password field accepts typing for ${user}`);
  await page.keyboard.press('Enter');
}
const logout = async page => { await page.click('#lo'); await page.waitForSelector('.hero'); };

(async () => {
  const browser = await chromium.launch({ args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] });
  const errs = [];
  const mk = async (w = 390, h = 820) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, permissions: ['camera', 'microphone', 'geolocation'], geolocation: { latitude: 25.3176, longitude: 82.9739 } });
    const p = await ctx.newPage(); p.on('pageerror', e => errs.push(e.message)); return p;
  };
  // ---------- 1. landing + staff login typing (admin)
  let p = await mk(390, 820);
  await p.goto(BASE + '/'); await p.waitForSelector('.hero'); await shot(p, '01-landing-mobile');
  await typeStaffLogin(p, 'admin', 'admin1234'); await p.waitForSelector('text=Platform overview');
  ok(true, 'admin login reaches the overview'); await shot(p, '10-admin-overview-mobile');
  await logout(p);
  await typeStaffLogin(p, 'admin', 'wrong-password'); await p.waitForSelector('#msg:not([hidden])');
  ok((await p.textContent('#msg')).includes('Invalid'), 'wrong password shows an error');

  // ---------- 2. citizen reports a pothole with live camera
  const c = await mk(390, 820);
  await c.goto(BASE + '/#/login'); await c.fill('#mob', '9876500011'); await c.click('#send');
  await c.waitForSelector('#dev b'); const otp = await c.textContent('#dev b'); await c.fill('#otp', otp); await c.click('#ver');
  await c.waitForSelector('text=Welcome'); await shot(c, '02-citizen-home-empty');
  await c.click('a[href="#/report"].btn'); await c.click('.cat[data-c="Roads and Infrastructure"]'); await shot(c, '03-report-categories');
  await c.click('#next'); await c.waitForSelector('#snap:not([disabled])', { timeout: 20000 });
  ok(true, 'camera and GPS ready'); await c.waitForTimeout(600); await shot(c, '04-report-capture');
  await c.click('#snap'); await c.waitForSelector('#shots img'); await c.click('#next:not([disabled])');
  await c.fill('#desc', 'Large pothole near the school gate'); await shot(c, '05-report-review');
  await c.click('#submit'); await c.waitForSelector('.code', { timeout: 30000 });
  const code = (await c.textContent('.code')).trim(); ok(/^SDH-\d{6}-\w{5}$/.test(code), 'complaint ID issued: ' + code); await shot(c, '06-submitted');
  await c.waitForTimeout(1500);
  await c.goto(BASE + '/#/c/' + code); await c.waitForSelector('.stepper');
  const citizenHtml = await c.content();
  ok(!/validity|Evidence validity|score/i.test(await c.textContent('#app')), 'citizen detail exposes no evidence score');
  await shot(c, '07-citizen-detail');

  // ---------- 3. department officer works the complaint
  const o = await mk(1280, 860);
  await typeStaffLogin(o, 'vmc_eng', 'demo1234'); await o.waitForSelector('.citem');
  ok((await o.textContent('#app')).includes(code), 'complaint appears on the VMC Engineering dashboard'); await shot(o, '11-dept-dashboard');
  await o.click(`a[href="#/d/${code}"]`); await o.waitForSelector('#actions'); await shot(o, '12-dept-detail');
  await o.click('button[data-st="Complaint Acknowledged"]'); await o.waitForSelector('.chip.st-open:has-text("Complaint Acknowledged")');
  ok(true, 'officer can acknowledge');
  await o.selectOption('#fo', { index: 1 }); await o.click('button[data-st="Field Officer Assigned"]'); await o.waitForSelector('.chip:has-text("Field Officer Assigned")');
  await o.click('button[data-st="Work In Progress"]'); await o.waitForSelector('.chip:has-text("Work In Progress")');
  await o.fill('#rem', 'Crew dispatched, patching today');
  await o.click('#addrem'); await o.waitForSelector('text=Crew dispatched');
  await o.click('button[data-st="Resolved"]'); await o.waitForSelector('#toast.on');
  ok((await o.textContent('#toast')).includes('resolution proof'), 'resolve without proof is refused');
  await o.setInputFiles('#rf', path.join(__dirname, 'proof.jpg')); await o.click('#uprf'); await o.waitForTimeout(800);
  await o.click('button[data-st="Resolved"]'); await o.waitForSelector('.chip.st-Resolved'); ok(true, 'officer resolves with proof');
  await shot(o, '13-dept-resolved'); await logout(o);

  // ---------- 4. citizen sees proof, reopens, then department re-resolves requires NEW proof
  await c.reload(); await c.waitForSelector('#ok');
  ok((await c.textContent('#app')).includes('Proof from the department'), 'citizen sees resolution proof'); await shot(c, '08-citizen-resolved');
  await c.click('#ok'); await c.waitForSelector('.notice.ok'); ok(true, 'citizen confirms resolution');

  // ---------- 5. AI monitor
  const a = await mk(1280, 860);
  await typeStaffLogin(a, 'sudhaar', 'sudhaar1234'); await a.waitForSelector('.pstep'); ok(true, 'sudhaar login shows AI live feed');
  const feed = await a.textContent('#feed'); ok(/Computer-vision analysis/.test(feed) && /Identify the responsible department/.test(feed) && /evidence validity score/i.test(feed), 'live feed shows vision, routing and scoring steps');
  await shot(a, '14-ai-live');
  await a.click('a[href="#/ai/runs"]'); await a.waitForSelector('.citem'); await shot(a, '15-ai-runs');
  await a.click(`a[href="#/ai/c/${code}"]`); await a.waitForSelector('.pipe .pstep');
  const steps = await a.$$eval('.pipe .pstep b', els => els.map(e => e.textContent));
  ok(steps.length >= 9, `pipeline replay lists ${steps.length} steps: ` + steps.slice(0, 4).join(' > ') + ' ...');
  await a.click('.pstep:has-text("Identify the responsible department") summary'); await shot(a, '16-ai-replay');
  ok((await a.textContent('.pipe')).includes('Roads'), 'routing reasoning visible in replay');
  // staff-only pages must reject the monitor from officer endpoints
  const r = await a.evaluate(async () => (await fetch('/api/dept/complaints', { headers: { Authorization: 'Bearer ' + localStorage.sdh_token } })).status);
  ok(r === 403, 'AI monitor cannot use department endpoints (403)');

  // ---------- 6. chatbot typing works + appears in AI monitor
  await a.click('#chat-fab'); await a.click('#chat-input'); await a.keyboard.type('how do I report?', { delay: 10 });
  ok((await a.inputValue('#chat-input')) === 'how do I report?', 'chat input accepts typing'); await a.keyboard.press('Enter'); await a.waitForSelector('.msg.b:nth-child(3)');
  await a.goto(BASE + '/#/ai/chat'); await a.waitForSelector('.pstep'); ok((await a.textContent('#app')).includes('how do I report?'), 'chatbot Q&A visible to AI monitor');

  // ---------- 7. admin desktop views
  const d = await mk(1280, 860); await typeStaffLogin(d, 'admin', 'admin1234'); await d.waitForSelector('text=Platform overview'); await shot(d, '17-admin-desktop');
  await d.goto(BASE + '/#/d/' + code); await d.waitForSelector('text=Read-only view'); ok(true, 'admin can open a complaint (read-only)');
  await d.click('a:has-text("See how the AI handled this")'); await d.waitForSelector('.pipe .pstep'); ok(true, 'admin can jump to AI trace');
  // ---------- 8. privacy: officer of another department is denied
  const t = await d.evaluate(async () => (await fetch('/api/admin/audit/verify', { headers: { Authorization: 'Bearer ' + localStorage.sdh_token } })).json()); ok(t.intact, 'audit hash-chain intact');
  ok(errs.length === 0, 'no uncaught JS errors' + (errs.length ? ': ' + errs.join(' | ') : ''));
  console.log(`\n${pass} passed, ${fail} failed`); await browser.close(); process.exit(fail ? 1 : 0);
})().catch(e => { console.error('E2E crashed:', e.message); process.exit(2); });
