import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {pathToFileURL} from 'node:url';
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_PATH).href);
const output='validation-navigation';await fs.mkdir(output,{recursive:true});
const server=spawn('python3',['-m','http.server','18777','--bind','127.0.0.1'],{stdio:'ignore'});
let browser;const results=[];
try{
 for(let n=0;n<80;n++){try{if((await fetch('http://127.0.0.1:18777/')).ok)break;}catch{}await new Promise(r=>setTimeout(r,50));}
 browser=await chromium.launch({executablePath:process.env.CHROME_BIN,headless:true,args:['--no-sandbox']});
 for(const width of [320,390,768]){
  const c=await browser.newContext({viewport:{width,height:844},hasTouch:true,isMobile:true});
  await c.route('https://somosservos.blogspot.com/**',r=>r.fulfill({contentType:'text/html',body:'<h1>Blog de teste</h1><p>Conteúdo simulado para conferir a interface do aplicativo.</p>'}));
  const page=await c.newPage();await page.goto('http://127.0.0.1:18777/');
  await page.waitForFunction(()=>!document.getElementById('blogFrame').hidden&&document.getElementById('fallback').hidden);
  await page.evaluate(()=>navigator.serviceWorker.ready);await page.reload();
  const geometry=await page.locator('#resourcesButton').evaluate(el=>{const r=el.getBoundingClientRect();return {height:r.height,left:r.left,right:r.right,bottom:r.bottom,hit:document.elementFromPoint(r.x+r.width/2,r.y+r.height/2)?.closest('a')===el};});
  assert.ok(geometry.height>=44&&geometry.left>=0&&geometry.right<=width&&geometry.hit);
  await page.screenshot({path:output+'/'+width+'-online.png',animations:'disabled'});
  await c.setOffline(true);await page.reload();await page.waitForFunction(()=>!document.getElementById('fallback').hidden);
  await page.screenshot({path:output+'/'+width+'-offline.png',animations:'disabled'});
  await page.getByRole('link',{name:'Abrir recursos da família servita'}).tap();await page.getByRole('heading',{name:'Recursos da Família Servita',exact:true}).waitFor();
  await page.getByRole('link',{name:'Abrir os 32 cartões do Santoral',exact:true}).tap();assert.equal(await page.locator('article').count(),32);
  await page.getByRole('link',{name:'Voltar ao Somos Servos',exact:true}).tap();await page.waitForFunction(()=>!document.getElementById('fallback').hidden);
  await page.getByRole('link',{name:'Abrir recursos da família servita'}).tap();await page.getByRole('link',{name:'Começar o percurso formativo',exact:true}).tap();await page.waitForURL('**/percurso-servita.html');
  results.push({width,...geometry,offlineResources:true,offlineGallery:true,offlineReturn:true,offlinePercurso:true});await c.close();
 }
 await fs.writeFile(output+'/results.json',JSON.stringify({browser:browser.version(),results},null,2));console.log('PASS: Recursos online/offline, galeria com 32 entradas, retornos e percurso HTML em três larguras; blog simulado.');
}catch(error){await fs.writeFile(output+'/failure.txt',String(error.stack||error));throw error;}
finally{await browser?.close();server.kill();}
