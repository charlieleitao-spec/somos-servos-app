const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const base='https://example.test/somos-servos-app/',handlers={},stores=new Map(),deleted=[];
let network=async()=>new Response('nova página'),networkCalls=0,added=[],timeoutNow=false;
const key=request=>typeof request==='string'?new URL(request,base).href:request.url;
function cacheFor(name){if(!stores.has(name))stores.set(name,new Map());const store=stores.get(name);return {async match(request){return store.get(key(request))?.clone()},async put(request,response){store.set(key(request),response.clone())},async addAll(requests){added=requests}}}
const context={URL,Response,AbortController,Request:class extends Request{constructor(path,options){super(new URL(path,base),options)}},caches:{async open(name){return cacheFor(name)},async keys(){return [...stores.keys()]},async delete(name){deleted.push(name);return stores.delete(name)}},self:{location:{origin:new URL(base).origin},clients:{claim(){}},skipWaiting(){},addEventListener(name,handler){handlers[name]=handler}},setTimeout(fn,ms){return timeoutNow?setTimeout(fn,0):setTimeout(fn,ms)},clearTimeout,fetch:async(...args)=>{networkCalls++;return network(...args)}};
vm.runInNewContext(fs.readFileSync('service-worker.js','utf8'),context);
const cacheName=vm.runInNewContext('CACHE',context),request={url:base+'pesquisa-bibliografica.html',method:'GET',mode:'navigate'};
async function dispatch(req){let response;handlers.fetch({request:req,respondWith(p){response=p}});return response}
(async()=>{
 let installing;handlers.install({waitUntil(p){installing=p}});await installing;assert.ok(added.some(r=>r.url.endsWith('/pesquisa-historica.html')));assert.ok(added.every(r=>r.cache==='reload'));
 stores.set('familia-servita-v1',new Map());stores.set('somos-servos-shell-v53',new Map());let activating;handlers.activate({waitUntil(p){activating=p}});await activating;assert.ok(deleted.includes('somos-servos-shell-v53'));assert.ok(stores.has('familia-servita-v1'));assert.ok(stores.has(cacheName));
 const cache=cacheFor(cacheName);await cache.put(request,new Response('página antiga'));let response=await dispatch(request);assert.equal(await response.text(),'nova página');assert.equal(await (await cache.match(request)).text(),'nova página');
 network=async()=>{throw Error('offline')};response=await dispatch(request);assert.equal(await response.text(),'nova página');
 network=async()=>new Response('indisponível',{status:503});response=await dispatch(request);assert.equal(await response.text(),'nova página');assert.equal(await (await cache.match(request)).text(),'nova página');
 network=async()=>new Response('removida',{status:404});response=await dispatch(request);assert.equal(response.status,404);assert.equal(await (await cache.match(request)).text(),'nova página');
 timeoutNow=true;network=async(_request,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(Error('timeout')),{once:true}));response=await dispatch(request);assert.equal(await response.text(),'nova página');timeoutNow=false;
 const asset={url:base+'styles.css?v=5',method:'GET',mode:'cors'};await cache.put(asset,new Response('estilo salvo'));const before=networkCalls;response=await dispatch(asset);assert.equal(await response.text(),'estilo salvo');assert.equal(networkCalls,before);
 network=async()=>new Response('erro',{status:500});const missing={url:base+'ausente.js',method:'GET',mode:'cors'};response=await dispatch(missing);assert.equal(response.status,500);assert.equal(await cache.match(missing),undefined);
 assert.equal(await dispatch({url:'https://api.unpaywall.org/v2/test',method:'GET',mode:'cors'}),undefined);assert.equal(await dispatch({...request,method:'POST'}),undefined);
 console.log('PASS: páginas atualizadas online; fallback offline e timeout; instalação sem cache HTTP antigo; erros não sobrescrevem conteúdo; arquivos locais preservados; caches de outros projetos protegidos; APIs externas intactas.');
})().catch(e=>{console.error(e);process.exit(1)});
