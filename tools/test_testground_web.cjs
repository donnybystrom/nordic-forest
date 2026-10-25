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
  const start=Date.now();while(Date.now()-start<timeout){const s=await state();if(s&&predicate(s)){console.log('PASS',label);return s;}await sleep(180);}
  throw Error(label+': '+JSON.stringify(await state()));
}
async function control(name){
  for(let i=0;i<12;i++){
    const s=await state(),p=s.controls[name];
    if(name==='play'||(p[1]>55&&p[1]<650)){await point(p);return;}
    const box=await page.locator('#canvas').boundingBox();
    await page.mouse.move(box.x+180/1100*box.width,box.y+350/850*box.height);
    await page.mouse.wheel(0,p[1]<55?-300:300);await sleep(250);
  }
  throw Error('Menu control remained outside scroll area: '+name);
}
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
  for(let attempt=0;attempt<8;attempt++){
    const s=await state(),target=s.zombies[index].parts[bone].position;
    const dx=target[0]-s.player[0],dy=target[1]-(s.player[1]+1.65),dz=target[2]-s.player[2];
    const yaw=Math.atan2(-dx,-dz),pitch=Math.atan2(dy,Math.hypot(dx,dz));
    const yawError=Math.atan2(Math.sin(yaw-s.yaw),Math.cos(yaw-s.yaw));
    if(Math.abs(yawError)<.004&&Math.abs(pitch-s.pitch)<.004)return;
    mouse.x-=yawError/s.sensitivity;mouse.y-=(pitch-s.pitch)/s.sensitivity;
    await page.mouse.move(mouse.x,mouse.y,{steps:8});
    await until(n=>Math.abs(Math.atan2(Math.sin(n.yaw-yaw),Math.cos(n.yaw-yaw)))<.005&&Math.abs(n.pitch-pitch)<.005,'FPS applies the complete mouse movement');
  }
  const s=await state(),p=s.zombies[index].parts[bone].screen;
  if(Math.hypot(p[0]-550,p[1]-425)<3)return;
  throw Error('FPS mouselook did not converge: '+JSON.stringify({yaw:s.yaw,pitch:s.pitch,point:p}));
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
  const damageOnly=args.includes('--damage-only');
  let hit=null,heavy=null,buckshot=null,generation2=0;const recoveries=[];
  let s=await until(n=>n.zombies.length===4,'FPS arena startup',180000);
  await control('damage');await until(n=>!n.damage_enabled,'Isolate the existing impact/recovery regression');
  assert.equal(new Set(s.zombies.map(z=>z.model)).size,2);assert.equal(new Set(s.zombies.map(z=>z.clip)).size,4);
  await page.screenshot({path:path.join(out,'group-settings.png')});
  if(!damageOnly){
  // The number and animation dropdown are edited through actual Godot UI.
  await control('amount');await until(n=>n.count_focused,'Count field focus');
  await page.keyboard.press(process.platform==='darwin'?'Meta+A':'Control+A');await page.keyboard.type('2');await page.keyboard.press('Enter');
  await until(n=>n.selected_count===2,'Count field commit');
  await control('motions');s=await until(n=>n.motions_open,'Animation dropdown opens');
  const popup=s.motion_popup;await point([popup[0]+popup[2]/2,popup[1]+popup[3]*1.5/s.motion_count]);
  await until(n=>n.selected_motion===1,'Rest pose dropdown');
  const generation=s.generation;await control('spawn');
  s=await until(n=>n.generation>generation&&n.zombies.length===2,'Respawn with UI choices');
  const stationary=s.zombies.map(z=>z.root);
  await sleep(1000);s=await state();s.zombies.forEach((z,i)=>assert(Math.hypot(z.root[0]-stationary[i][0],z.root[2]-stationary[i][2])<.3,'Resting group should not walk away'));
  await control('play');await until(n=>n.captured&&!n.menu,'Pointer capture');
  assert.equal(await page.evaluate(()=>document.pointerLockElement?.id),'canvas');
  const before=s.player;
  await page.keyboard.down('d');await until(n=>n.player[0]>before[0]+.25,'WASD strafe');await page.keyboard.up('d');
  s=await until(n=>n.player_speed<.05,'Player stops after key release');
  await aimAt(0,'Head');
  const shots=s.shots;
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.shots>shots&&n.last_shot.bone==='Head','Actual FPS headshot');
  assert.equal(s.ammo,11);assert.equal(s.zombies[0].hits,1);
  hit=s.last_shot;
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
  // Heavy and buckshot profiles must also work through real keyboard input,
  // aim and shooting, with physical movement observed from the rendered game.
  generation2=s.generation;await control('spawn');
  s=await until(n=>n.generation>generation2&&n.zombies.length===2,'Fresh impact targets');
  await control('play');await until(n=>n.captured,'Recapture for impact profiles');
  await page.keyboard.press('2');await until(n=>n.profile===1&&n.impulse===70,'Heavy impulse profile');
  await aimAt(0,'LeftArm');s=await state();
  const shoulderStart=s.zombies[0].root,heavySequence=s.shots;
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.shots>heavySequence&&n.last_shot.bone,'Heavy shoulder shot');
  heavy=s.last_shot;assert.equal(heavy.budget_ns,70);
  s=await until(n=>n.zombies[0].root[2]<shoulderStart[2]-.2&&['downed','recovering'].includes(n.zombies[0].state),'Physical shoulder knockdown',45000);
  assert.equal(s.zombies[0].muscles,1,'Impact retains muscle motors');
  await page.screenshot({path:path.join(out,'heavy-shoulder-fall.png')});
  await page.keyboard.press('Tab');await until(n=>n.menu&&!n.captured,'Menu for buckshot target');
  generation2=s.generation;await control('spawn');await until(n=>n.generation>generation2,'Fresh buckshot target');
  await control('play');await until(n=>n.captured,'Recapture for buckshot');
  await page.keyboard.press('3');await until(n=>n.profile===2&&n.impulse===100,'Buckshot profile');
  await aimAt(0,'Spine');s=await state();const buckSequence=s.shots;
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.shots>buckSequence&&n.last_shot.body_hits>1,'Actual buckshot body hits');
  buckshot=s.last_shot;assert.equal(buckshot.pellets.length,8);assert(buckshot.delivered_ns<=100);
  assert(buckshot.pellets.filter(p=>p.bone).every(p=>p.impulse_ns===12.5));
  await page.screenshot({path:path.join(out,'buckshot-torso.png')});
  // Select both lying starts through the actual Godot dropdown. Recovery
  // must choose the observed body orientation, run the phases and exit.
  await page.keyboard.press('Tab');await until(n=>n.menu&&!n.captured,'Menu for recovery scenarios');
  for(const [choice,kind] of [[6,'prone'],[7,'supine']]){
    await control('motions');s=await until(n=>n.motions_open,'Recovery scenario dropdown');
    const rect=s.motion_popup;await point([rect[0]+rect[2]/2,rect[1]+rect[3]*(choice+.5)/s.motion_count]);
    await until(n=>n.selected_motion===choice,'Recovery scenario selection');
    generation2=s.generation;await control('spawn');
    await until(n=>n.generation>generation2,'Lying group spawn');
    s=await until(n=>n.zombies.every(z=>z.state==='recovering'&&z.recovery_kind===kind&&z.recovery_time>1),'Animation starts from '+kind,45000);
    await page.screenshot({path:path.join(out,'getup-'+kind+'.png')});
    s=await until(n=>n.zombies.every(z=>z.recovery_completed>0),'Animation blends back to locomotion from '+kind,80000);
    assert(s.zombies.every(z=>z.root[1]>.65));
    recoveries.push({kind,models:s.zombies.map(z=>z.model),completed:s.zombies.map(z=>z.recovery_completed)});
  }
  }
  // Enable destruction and use real pointer-lock input for both the .44
  // head rule and held-trigger automatic fire. No state-mutating test API.
  await control('damage');await until(n=>n.damage_enabled,'Mesh destruction enabled');
  await control('motions');s=await until(n=>n.motions_open,'Rest choice for damage targets');
  {const rect=s.motion_popup;await point([rect[0]+rect[2]/2,rect[1]+rect[3]*1.5/s.motion_count]);}
  await until(n=>n.selected_motion===1,'Rest targets selected');
  generation2=s.generation;await control('spawn');await until(n=>n.generation>generation2,'Fresh damage targets');
  await control('play');await until(n=>n.captured,'Capture for actual mesh destruction');
  await page.keyboard.press('r');await until(n=>n.ammo===12&&!n.reloading,'Reload for destruction test');
  await page.keyboard.press('2');await until(n=>n.profile===1,'Select .44 damage profile');
  await aimAt(0,'Head');s=await state();const damageStart=s.shots;
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.shots>damageStart&&n.zombies[0].damage.fatal&&n.zombies[0].damage.removed_cells>0,'Head geometry removed and brain rule collapses body');
  assert.equal(s.zombies[0].state,'dead');assert(s.debris<=s.debris_limit);
  const headDamage=s.zombies[0].damage;
  await page.screenshot({path:path.join(out,'damage-head-collapse.png')});
  await page.keyboard.press('4');await until(n=>n.profile===3,'Automatic rifle profile');
  // Move to the opening: the right target is correctly occluded by the
  // right wall when the earlier WASD test leaves the player far to the right.
  s=await state();
  if(s.player[0]>.15){await page.keyboard.down('a');await until(n=>n.player[0]<.1,'Move to a clear firing lane');await page.keyboard.up('a');await until(n=>n.player_speed<.05,'Stop at the opening');}
  await aimAt(1,'Spine');s=await state();const autoStart=s.shots;
  await page.mouse.down();await until(n=>n.shots>=autoStart+5,'Held trigger fires several rounds',20000);await page.mouse.up();
  s=await until(n=>n.zombies[1].damage.removed_cells>0,'Automatic fire removes torso mesh cells');
  // The physical head can fall through the held firing line after a torso
  // hit. Chest-only survival is tested with recorded pellets in damage_smoke.
  if(s.zombies[1].damage.fatal)assert(s.zombies[1].death_capacity.best<.08,'A terminal hit needs insufficient remaining movement capacity');
  assert(s.debris<=s.debris_limit);
  const automatic={shots:s.shots-autoStart,damage:s.zombies[1].damage,debris:s.debris,limit:s.debris_limit};
  await page.screenshot({path:path.join(out,'damage-automatic-torso.png')});
  // A killed actor releases live resources, remains shootable, and does not
  // occupy a living spawn slot. Exercise retention/cleanup through real UI.
  s=await state();const corpseId=s.zombies[0].id,deadHits=s.zombies[0].hits,deadRebuilds=s.zombies[0].damage.rebuilds;
  const liveTicks=s.zombies[0].live_ticks,motorTicks=s.zombies[0].motor_ticks;
  assert(s.zombies[0].permanently_dead&&!s.zombies[0].animation_reference&&!s.zombies[0].agent_processing&&!s.zombies[0].motor_processing);
  await page.keyboard.press('2');await until(n=>n.profile===1,'Heavy profile for corpse damage');
  await aimAt(0,'LeftUpLeg');s=await state();
  await page.mouse.down();await page.mouse.up();
  s=await until(n=>n.zombies[0].hits>deadHits&&n.zombies[0].damage.rebuilds>deadRebuilds&&n.zombies[0].damage.pending===0,'Actual FPS bullet damages a passive corpse');
  assert(s.zombies[0].permanently_dead&&s.zombies[0].live_ticks===liveTicks&&s.zombies[0].motor_ticks===motorTicks);
  const corpseDamage=s.zombies[0].damage;
  await page.keyboard.press('Tab');await until(n=>n.menu&&!n.captured,'Corpse spawn controls');
  const livingBefore=s.living,corpsesBefore=s.corpses;
  await control('add');s=await until(n=>n.living===livingBefore+1&&n.corpses===corpsesBefore,'Spawn another living zombie alongside retained corpses');
  const retainedGeneration=s.generation;await control('spawn');
  s=await until(n=>n.generation>retainedGeneration&&n.living===n.selected_count&&n.corpses===corpsesBefore,'Group respawn preserves dead bodies');
  assert(s.zombies.some(z=>z.id===corpseId&&z.permanently_dead));
  await page.screenshot({path:path.join(out,'retained-corpses-new-group.png')});
  await control('clear_corpses');s=await until(n=>n.corpses===0&&n.zombies.length===n.living,'Explicit corpse cleanup');
  assert(!s.zombies.some(z=>z.id===corpseId));
  assert.deepEqual(errors,[],'Browser and GDScript errors');
  const report={corpse_damage:corpseDamage,permanent_passive_death:true,retained_corpses_and_spawn:true,explicit_corpse_cleanup:true,damage_only:damageOnly,head_damage:headDamage,automatic_fire:automatic,status:'pass',url:target,pointer_lock:true,wasd:!damageOnly,mouselook:true,actual_headshot:hit,heavy_shoulder_knockdown:heavy,buckshot,recoveries,ads:!damageOnly,reload:true,group_spawn_and_animation_ui:true,follow_toggle:!damageOnly,console_errors:errors};
  fs.writeFileSync(path.join(out,'validation.json'),JSON.stringify(report,null,2)+'\n');console.log('TESTGROUND_WEB_PASS',JSON.stringify(report));
})().catch(async e=>{
  if(page){await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({state:await state().catch(()=>null),mouse_moves:await page.evaluate(()=>window.__testMouseMoves)},null,2));}
  console.error(e);process.exitCode=1;
}).finally(async()=>{fs.writeFileSync(path.join(out,'console.json'),JSON.stringify(messages,null,2));await browser?.close();if(server)await new Promise(resolve=>server.close(resolve));});
