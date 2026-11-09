const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync('app.js','utf8');
function env({canRegister=true,rejectRegister=false,rejectExit=false,native=true,historyLength=1}={}){
 const handlers={},warnings=[],nodes={};let callback,back=0,exit=0;
 for(const id of ['blogFrame','fallback','retryButton','installButton'])nodes[id]={hidden:false,addEventListener(){}};
 const App={async addListener(name,cb){assert.equal(name,'backButton');if(rejectRegister)throw Error('registro');callback=cb;},async exitApp(){exit++;if(rejectExit)throw Error('saída');}};
 const w={Capacitor:{isNativePlatform:()=>native,Plugins:canRegister?{App}:{}},history:{length:historyLength,back(){back++;}},addEventListener(name,fn){handlers[name]=fn;},setTimeout,clearTimeout};
 const c=vm.createContext({window:w,document:{querySelector:s=>nodes[s.slice(1)]},navigator:{onLine:false},console:{warn:(...args)=>warnings.push(args)},AbortController,fetch:async()=>({})});vm.runInContext(source,c);
 return {handlers,warnings,nodes,async boot(){await handlers.DOMContentLoaded?.();},async press(value){assert.ok(callback,'Listener deve ser registrado');await callback({canGoBack:value});},counts:()=>({back,exit})};
}
(async()=>{
 let e=env();await e.boot();await e.press(true);assert.deepEqual(e.counts(),{back:1,exit:0});assert.equal(e.nodes.fallback.hidden,false);
 e=env({historyLength:99});await e.boot();await e.press(false);assert.deepEqual(e.counts(),{back:0,exit:1});
 e=env({historyLength:1});await e.boot();await e.press(true);assert.deepEqual(e.counts(),{back:1,exit:0},'canGoBack do WebView prevalece para o iframe');
 for(const opts of [{canRegister:false},{rejectRegister:true}]){e=env(opts);await e.boot();assert.equal(e.warnings.length,1);assert.equal(e.nodes.fallback.hidden,false);}
 e=env({rejectExit:true});await e.boot();await e.press(false);assert.equal(e.warnings.length,1);
 e=env({native:false});assert.ok(e.handlers.beforeinstallprompt);assert.equal(e.handlers.DOMContentLoaded,undefined);
 assert.ok(!source.includes("import('@capacitor/app')"));
 const html=fs.readFileSync('index.html','utf8'),resources=fs.readFileSync('recursos.html','utf8'),gallery=fs.readFileSync('cartoes/index.html','utf8'),generator=fs.readFileSync('scripts/atualizar-cartoes.py','utf8');
 assert.match(html,/id="resourcesButton" href="\.\/recursos.html"/);assert.match(resources,/href="\.\/index.html"[^>]*>Voltar ao Somos Servos/);
 assert.match(gallery,/href="\.\.\/index.html"[^>]*>Voltar ao Somos Servos/);assert.match(generator,/href="\.\.\/index.html">Voltar ao Somos Servos/);
 for(const repo of ['liturgia-osm','hoje-familia-servita','somos-servos-app'])assert.ok(resources.includes('/'+repo+'/releases/latest'));
 console.log('PASS: registro pela ponte nativa; histórico do WebView; saída na raiz; falhas tratadas; acesso a Recursos; retornos locais e links de versões atuais.');
})().catch(e=>{console.error(e);process.exitCode=1;});
