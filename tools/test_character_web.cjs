/* Actual browser events against the exported WebGL canvas, including collisions.
 * Optional --url verifies the deployed Pages site with the same acceptance test.
 */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('playwright');
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name)+1] : fallback;
const root = path.resolve(__dirname, '..');
const site = path.join(root, 'build/character-web/site');
const output = path.resolve(option('--out', path.join(root, 'build/character-web/verification')));
fs.mkdirSync(output, {recursive:true});
const errors = [], messages = [], results = [];
let server, browser, page, target;
const sleep = ms => new Promise(resolve=>setTimeout(resolve, ms));

async function serve(){
  server = http.createServer((req,res)=>{
    try{
      const pathname = decodeURIComponent(new URL(req.url,'http://localhost').pathname);
      const relative = pathname.replace(/^\/nordic-forest\//,'').replace(/^\//,'') || 'index.html';
      const file = path.resolve(site, relative);
      if(!file.startsWith(site+path.sep)){res.writeHead(403).end();return;}
      const types={'.html':'text/html; charset=utf-8','.js':'text/javascript','.wasm':'application/wasm','.json':'application/json','.png':'image/png','.pck':'application/octet-stream'};
      if(!fs.statSync(file).isFile())throw Error('not a file');
      res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});
      fs.createReadStream(file).pipe(res);
    }catch{res.writeHead(404).end('Not found');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  return `http://127.0.0.1:${server.address().port}/nordic-forest/`;
}
async function state(){return page.evaluate(()=>window.__ragdollDemo);}
async function until(predicate, label, timeout=15000){
  const started=Date.now();
  while(Date.now()-started<timeout){
    const value=await state();
    if(value&&predicate(value))return value;
    await sleep(150);
  }
  throw Error(`${label}: ${JSON.stringify(await state())}`);
}
async function screen(point){
  const current=await state(), bounds=await page.locator('#canvas').boundingBox();
  return {x:bounds.x+point[0]/current.viewport[0]*bounds.width,y:bounds.y+point[1]/current.viewport[1]*bounds.height};
}
async function clickControl(name){const s=await state(),p=await screen(s.controls[name]);await page.mouse.click(p.x,p.y);}
async function setSlider(name,fraction){
  const s=await state(),r=s.slider_rects[name],p=await screen([r[0]+r[2]*fraction,r[1]+r[3]/2]);
  await page.mouse.click(p.x,p.y);
}
async function rest(){
  for(let index=0;index<14;index++){
    const s=await state();if(s.clip==='')return;
    await page.keyboard.press('ArrowLeft');await until(n=>n.clip!==s.clip,'Previous clip');
  }
  throw Error('Could not select rest pose');
}
function distance(a,b){return Math.hypot(...a.map((n,i)=>n-b[i]));}

(async()=>{
  target=option('--url')||await serve();
  const url=new URL(target);url.searchParams.set('test','1');
  browser=await chromium.launch({headless:true,channel:option('--channel',undefined),args:['--enable-webgl','--ignore-gpu-blocklist','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  page=await browser.newPage({viewport:{width:1280,height:1000}});
  page.on('pageerror',error=>errors.push(String(error)));
  page.on('console',message=>{messages.push({type:message.type(),text:message.text()});if(message.type()==='error')errors.push(message.text());});
  await page.goto(url.toString(),{waitUntil:'domcontentloaded',timeout:60000});
  await page.getByRole('button',{name:'Starta fysiklabbet',exact:true}).click();
  await until(s=>s.mode===1&&s.bodies===17,'WebAssembly app startup',180000);
  assert.equal(await page.evaluate(()=>window.crossOriginIsolated),false,'Single-thread export must work without isolation headers');
  assert.equal((await state()).models,2);
  const seen=new Set();
  for(let model=0;model<2;model++){
    await rest();await sleep(2600);
    let s=await state();seen.add(s.model);
    assert.equal(s.clips,13);assert.equal(s.joints,16);assert(s.hips[1]>.5&&s.hips[1]<1.6);
    assert(s.skin_samples>0&&s.skin_error<0.005,'Rendered skeleton must follow physical bodies');
    const before=s.hips,contacts=s.ball_contacts;
    await clickControl('push');
    let maxDisplacement=0;
    for(let sample=0;sample<20;sample++){await sleep(150);s=await state();maxDisplacement=Math.max(maxDisplacement,distance(before,s.hips));}
    assert(s.ball_contacts>contacts,'The launched ball must collide with a body');
    assert(maxDisplacement>0.008,'Ball contact must physically displace the character');
    await page.screenshot({path:path.join(output,`${s.model}-web-hit.png`)});
    await page.keyboard.press('b');
    s=await until(n=>Math.abs(n.ball_position[1]-.17)<.025,'Ball settles before mouse pick',20000);
    const initialBall=s.ball_position,p=await screen(s.ball_screen);
    await page.mouse.move(p.x,p.y);await page.mouse.down();
    await until(n=>n.dragging,'Mouse raycast picks ball');
    await page.mouse.move(p.x+70,p.y-65,{steps:12});await sleep(700);
    s=await state();const dragDistance=distance(initialBall,s.ball_position);
    assert(dragDistance>.05,'Spring drag must move the real ball');
    await page.mouse.up();await until(n=>!n.dragging,'Mouse release ends drag');
    await page.keyboard.press('3');
    s=await until(n=>n.mode===2&&n.hips[1]<.5,'Passive body falls to floor',20000);
    assert(s.hips.every(Number.isFinite));assert(s.support_force<0.001);
    await page.screenshot({path:path.join(output,`${s.model}-web-passive.png`)});
    const fallenHeight=s.hips[1];
    await page.keyboard.press('2');await page.keyboard.press('r');
    await until(n=>n.mode===1&&n.hips[1]>.5,'Active mode and reset');
    const clips=new Set();
    for(let index=0;index<13;index++){
      const previous=(await state()).clip;
      await page.keyboard.press('ArrowRight');
      s=await until(n=>n.clip!==previous,'Next animation');
      assert(s.clip&&s.playing);clips.add(s.clip);
    }
    assert.equal(clips.size,13);
    await page.keyboard.press('Space');await until(n=>!n.playing,'Pause animation');
    await page.keyboard.press('Space');await until(n=>n.playing,'Resume animation');
    results.push({model:s.model,clips:clips.size,ball_contacts:s.ball_contacts,max_hit_displacement_m:maxDisplacement,dragged_ball_distance_m:dragDistance,passive_hips_height_m:fallenHeight});
    await page.keyboard.press('e');
    await until(n=>n.model!==s.model,'Next character');
  }
  assert.equal(seen.size,2);
  await setSlider('ball_mass',.65);await until(s=>s.mass>10&&s.mass<=20,'Ball mass slider');
  await setSlider('muscles',.5);await until(s=>s.muscles>.5&&s.muscles<1,'Muscle strength slider');
  await setSlider('balance',.5);await until(s=>s.balance>.3&&s.balance<.7,'Pelvis support slider');
  assert.deepEqual(errors,[],'Browser or GDScript errors');
  const report={status:'pass',url:target,renderer:'Chromium WebGL2/SwiftShader',cross_origin_isolated:false,characters:results,actual_mouse_drag:true,actual_canvas_buttons_and_keyboard:true,sliders:true,console_errors:errors};
  fs.writeFileSync(path.join(output,'web-validation.json'),JSON.stringify(report,null,2)+'\n');
  console.log('CHARACTER_WEB_SMOKE_PASS',JSON.stringify(report));
})().catch(async error=>{
  if(page){await page.screenshot({path:path.join(output,'failure.png')}).catch(()=>{});fs.writeFileSync(path.join(output,'failure-state.json'),JSON.stringify(await state().catch(()=>null),null,2)+'\n');}
  console.error(error);process.exitCode=1;
}).finally(async()=>{
  fs.writeFileSync(path.join(output,'browser-console.json'),JSON.stringify(messages,null,2)+'\n');
  await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));
});
