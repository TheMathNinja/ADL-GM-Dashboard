const fs = require('node:fs');
const assert = require('node:assert/strict');
const source = fs.readFileSync('www/pr-rank-popovers.js', 'utf8');
const start = source.indexOf('  function computePlacement(');
const end = source.indexOf('  function position()', start);
assert(start >= 0 && end > start);
const compute = Function(`return (${source.slice(start, end).trim()});`)();
for (const [vw, vh] of [[360,640],[1280,720],[768,1024],[1920,1080]]) {
  const width = Math.min(500,vw-16), height = Math.min(420,vh-16);
  for (const x of [8, (vw-52)/2, vw-60]) {
    for (const y of [8, (vh-18)/2, vh-26]) {
      const box = {left:x, right:x+52, top:y, bottom:y+18};
      const p = compute(box,width,height,vw,vh);
      const h = Math.min(height,p.maxHeight);
      assert(p.left >= 8 && p.left+width <= vw-8);
      assert(p.top >= 8 && p.top+h <= vh-8);
      assert(p.left >= box.right+12 || p.left+width <= box.left-12 ||
        p.top >= box.bottom+12 || p.top+h <= box.top-12,
        `Popover overlaps its trigger at ${vw}x${vh}: ${JSON.stringify(p)}`);
    }
  }
}
console.log('PASS: desktop/tablet/mobile popovers stay inside viewport and never cover the originating rank.');
const css = fs.readFileSync('www/pr-rank-popovers.css', 'utf8');
assert.match(css, /td:nth-child\(2\)[^{]+\{[^}]*white-space:\s*nowrap/);
assert.match(css, /min-width:\s*max-content/);
console.log('PASS: player labels never wrap; narrow viewports retain horizontal scrolling.');
