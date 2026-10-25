/* Browser acceptance: real pointer lock, WASD, aim, shot, reload and group UI. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const args=process.argv.slice(2);
const option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(__dirname,'..');
const site=path.join(root,'build/character-web/site');
const out=path.resolve(option('--out',path.join(root,'build/character-web/verification/testground')));
fs.mkdirSync(out,{recursive:true});
for(const name of ['validation.json','failure.json','failure.png'])fs.rmSync(path.join(out,name),{force:true});
let server,browser,page;
const messages=[],errors=[];
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function state(){return page.evaluate(()=>window.__testgroundDemo);}
async function until(predicate,label,timeout=30000){
  const start=Date.now();while(Date.now()-start<timeout){const s=await state();if(s&&predicate(s))return s;await sleep(180);}
  throw Error(label+': '+JSON.stringify(await state()));
}
async function control(name){const s=await state();await point(s.controls[name]);}
async function point(p){const box=await page.locator('#canvas').boundingBox();mouse={x:box.x+p[0]/1100*box.width,y:box.y+p[1]/850*box.height};await page.mouse.click(mouse.x,mouse.y);}
async function serve(){
  server=http.createServer((req,res)=>{
    const name=new URL(req.url,'http://localhost').pathname.replace(/^\/nordic-forest\//,'')||'index.html';
    const file=path.resolve(site,name);
    if(!file.startsWith(site+path.sep)||!fs.existsSync(file)){res.writeHead(404).end();return;}
    const types={'.wasm':'application/wasm','.js':'text/javascript','.html':'text/html','.json':'application/json'};
    res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));return `http://127.0.0.1:${server.address().port}/nordic-forest/`;
}
let mouse={x:640,y:500};
async function aimAt(index,bone){
  for(let attempt=0;attempt<4;attempt++){
    const s=await state(),target=s.zombies[index].parts[bone].position;
    const dx=target[0]-s.player[0],dy=target[1]-(s.player[1]+1.65),dz=target[2]-s.player[2];
    const yaw=Math.atan2(-dx,-dz),pitch=Math.atan2(dy,Math.hypot(dx,dz));
    const yawError=Math.atan2(Math.sin(yaw-s.yaw),Math.cos(yaw-s.yaw));
    if(Math.abs(yawError)<.004&&Math.abs(pitch-s.pitch)<.004)return;
    mouse.x-=yawError/s.sensitivity;mouse.y-=(pitch-s.pitch)/s.sensitivity;
    await page.mouse.move(mouse.x,mouse.y,{steps:8});
    await until(n=>Math.abs(n.yaw-s.yaw)+Math.abs(n.pitch-s.pitch)>.0001,'FPS receives mouse movement');
    await sleep(300);
  }
  const s=await state();throw Error('FPS mouselook did not converge: '+JSON.stringify({yaw:s.yaw,pitch:s.pitch}));
}
(async()=>{
  const target=option('--url')||await serve(),url=new URL(target);url.searchParams.set('mode','arena');url.searchParams.set('test','1');
  // Exercise pointer lock with the same headless implementation as real Chrome.
  browser=await chromium.launch({headless:true,channel:option('--channel','chromium'),args:['--enable-webgl','--ignore-gpu-blocklist','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  page=await browser.newPage({viewport:{width:1280,height:1000}});
  page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{messages.push({type:m.type(),text:m.text()});if(m.type()==='error')errors.push(m.text());});
  await page.goto(url.toString(),{waitUntil:'domcontentloaded'});
  await page.evaluate(()=>{
    window.__testMouseMoves=[];
    document.addEventListener('mousemove',event=>{
      if(!document.pointerLockElement)return;
      window.__testMouseMoves.push({x:event.clientX,y:event.clientY,dx:event.movementX,dy:event.movementY,trusted:event.isTrusted,target:event.target.id});
      if(window.__testMouseMoves.length>64)window.__testMouseMoves.shift();
    },true);
  });
  await page.getByRole('button',{name:'Starta FPS-testbanan',exact:true}).click();
  let s=await until(n=>n.zombies.length===4,'FPS arena startup',180000);
  assert.equal(new Set(s.zombies.map(z=>z.model)).size,2);assert.equal(new Set(s.zombies.map(z=>z.clip)).size,4);
  await page.screenshot({path:path.join(out,'group-settings.png')});
  // The number and animation dropdown are edited through actual Godot UI.
  await control('amount');await until(n=>n.count_focused,'Count field focus');
  await page.keyboard.press(process.platform==='darwin'?'Meta+A':'Control+A');await page.keyboard.type('2');await page.keyboard.press('Enter');
  await until(n=>n.selected_count===2,'Count field commit');
  await control('motions');s=await until(n=>n.motions_open,'Animation dropdown opens');
  const popup=s.motion_popup;await point([popup[0]+popup[2]/2,popup[1]+popup[3]*1.5/6]);
  await until(n=>n.selected_motion===1,'Rest pose dropdown');
  const generation=s.generation;await control('spawn');
  s=await until(n=>n.generation>generation&&n.zombies.length===2,'Respawn with UI choices');
  const anchors=s.zombies.map(z=>z.anchor);
  await sleep(1000);s=await state();assert.deepEqual(s.zombies.map(z=>z.anchor),anchors,'Stationary group targets');
  await control('play');await until(n=>n.captured&&!n.menu,'Pointer capture');
  assert.equal(await page.evaluate(()=>document.pointerLockElement?.id),'canvas');
  const before=s.player;
  await page.keyboard.down('d');await sleep(1200);await page.keyboard.up('d');
  s=await until(n=>n.player[0]>before[0]+.1,'WASD strafe');
  await aimAt(0,'Head');
  const shots=s.shots;
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.shots>shots&&n.last_shot.bone==='Head','Actual FPS headshot');
  assert.equal(s.ammo,11);assert.equal(s.zombies[0].hits,1);
  const hit=s.last_shot;
  await page.screenshot({path:path.join(out,'fps-headshot.png')});
  await page.mouse.down({button:'right'});await until(n=>n.fov<60,'Aim down sights');await page.mouse.up({button:'right'});
  await page.keyboard.press('r');await until(n=>n.reloading,'Reload starts');await until(n=>!n.reloading&&n.ammo===12,'Reload completes');
  await page.keyboard.press('Tab');await until(n=>n.menu&&!n.captured,'Tab releases mouse for settings');
  await control('follow');s=await until(n=>n.follow,'Follow checkbox');
  const old=s.zombies[1].root;
  s=await until(n=>Math.hypot(n.zombies[1].root[0]-old[0],n.zombies[1].root[2]-old[2])>.15,'Crowd follower moves toward player',45000);
  assert(Math.hypot(s.zombies[1].root[0]-s.player[0],s.zombies[1].root[2]-s.player[2])<Math.hypot(old[0]-s.player[0],old[2]-s.player[2]));
  await control('follow');await until(n=>!n.follow,'Stationary checkbox');
  await page.screenshot({path:path.join(out,'follow-settings.png')});
  assert.deepEqual(errors,[],'Browser and GDScript errors');
  const report={status:'pass',url:target,pointer_lock:true,wasd:true,mouselook:true,actual_headshot:hit,ads:true,reload:true,group_spawn_and_animation_ui:true,follow_toggle:true,console_errors:errors};
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(report,null,2)+'\n');console.log('TESTGROUND_WEB_PASS',JSON.stringify(report));
})().catch(async e=>{
  if(page){await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({state:await state().catch(()=>null),mouse_moves:await page.evaluate(()=>window.__testMouseMoves)},null,2));}
  console.error(e);process.exitCode=1;
}).finally(async()=>{fs.writeFileSync(path.join(out,'console.json'),JSON.stringify(messages,null,2));await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));});
