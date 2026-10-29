(() => {
  'use strict';
  const KEY = 'servitas-referencias-salvas-v1';
  const LIMIT = 300;
  const text = (value, max = 1000) => typeof value === 'string' ? value.replace(/\s+/g, ' ').trim().slice(0, max) : '';
  function safeURL(value) {
    try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; } catch { return ''; }
  }
  function normalize(value) {
    if (!value || !['book', 'article', 'image'].includes(value.type) || !text(value.title, 400)) throw Error('Referência inválida');
    const url = new URL(safeURL(value.url));
    url.hash = '';
    let source = '';
    if (value.type === 'book' && url.hostname === 'openlibrary.org' && /^\/works\/OL\d+W$/.test(url.pathname)) source = 'Open Library';
    if (value.type === 'article' && url.hostname === 'doi.org' && /^10\.\d{4,9}\/\S{1,200}$/.test(decodeURIComponent(url.pathname.slice(1)))) {
      source = 'Crossref / DOI'; url.pathname = '/' + encodeURIComponent(decodeURIComponent(url.pathname.slice(1)).toLowerCase());
    }
    if (value.type === 'article' && url.hostname === 'doaj.org' && /^\/article\/[a-f0-9]{32}$/.test(url.pathname)) source = 'DOAJ';
    if (value.type === 'image' && url.hostname === 'commons.wikimedia.org' && url.pathname.startsWith('/wiki/File:')) source = 'Wikimedia Commons';
    if (!source || url.port) throw Error('Fonte inválida');
    url.search = '';
    return { type: value.type, title: text(value.title, 400), authors: text(value.authors), year: text(value.year, 20), publication: text(value.publication, 250), url: url.href, source, fulltext: safeURL(value.fulltext), credit: text(value.credit), license: text(value.license, 150), licenseURL: safeURL(value.licenseURL) };
  }
  function read() {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const data = JSON.parse(raw);
    if (data?.version !== 1 || !Array.isArray(data.items) || data.items.length > LIMIT) throw Error('Lista inválida');
    return data.items.map(item => {
      const normalized = normalize(item);
      if (typeof item.savedAt !== 'string' || !Number.isFinite(Date.parse(item.savedAt))) throw Error('Data inválida');
      return { ...normalized, savedAt: item.savedAt };
    });
  }
  function write(items) {
    localStorage.setItem(KEY, JSON.stringify({ version: 1, items }));
    window.dispatchEvent(new Event('servita-saved-change'));
  }
  function save(value) {
    const item = normalize(value), items = read();
    if (items.some(existing => existing.url === item.url)) return false;
    if (items.length >= LIMIT) throw Error('Limite da lista');
    items.unshift({ ...item, savedAt: new Date().toISOString() });
    write(items);
    return true;
  }
  function remove(url) { const items = read(); write(items.filter(item => item.url !== url)); }
  function refreshButtons() {
    let items;
    try { items = read(); } catch { return; }
    const urls = new Set(items.map(item => item.url));
    document.querySelectorAll('[data-saved-reference]').forEach(button => {
      const saved = urls.has(button.dataset.savedReference);
      button.textContent = saved ? 'Referência salva' : 'Salvar referência';
      button.setAttribute('aria-pressed', String(saved));
    });
  }
  function addButton(host, value) {
    const getValue = typeof value === 'function' ? value : () => value;
    let item;
    try { item = normalize(getValue()); } catch { return; }
    const button = document.createElement('button'), status = document.createElement('p'), group = document.createElement('div');
    button.type = 'button'; button.dataset.savedReference = item.url; button.className = 'save-reference';
    button.style.cssText = 'display:block;margin-top:10px;background:#fff;color:#173b67;font-size:.9rem;min-height:44px';
    button.textContent = 'Salvar referência'; button.setAttribute('aria-pressed', 'false');
    status.className = 'note'; status.setAttribute('role', 'status');
    button.addEventListener('click', () => {
      try {
        const added = save(getValue());
        status.textContent = added ? 'Referência salva neste navegador.' : 'Esta referência já está na sua lista.';
        refreshButtons();
      } catch {
        status.textContent = 'Não foi possível salvar. Verifique se o armazenamento está disponível e se a lista tem menos de 300 referências.';
      }
    });
    group.append(button, status); host.append(group);
    try { const saved = read().some(existing => existing.url === item.url); button.textContent = saved ? 'Referência salva' : 'Salvar referência'; button.setAttribute('aria-pressed', String(saved)); } catch {}
    refreshButtons();
  }
  function link(label, url) { const a = document.createElement('a'); a.textContent = label; a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
  function mount(root, status) {
    function render(focusIndex) {
      let items;
      try { items = read(); } catch { status.textContent = 'Não foi possível ler a lista salva neste navegador. Os dados existentes foram preservados.'; return; }
      root.replaceChildren();
      status.textContent = items.length ? items.length + (items.length === 1 ? ' referência salva.' : ' referências salvas.') : 'Sua lista está vazia. Salve referências nas pesquisas de livros, artigos ou imagens.';
      const types = { book: 'Livro', article: 'Artigo', image: 'Imagem' };
      items.forEach((item, index) => {
        const article = document.createElement('article'), h = document.createElement('h2'), meta = document.createElement('p'), details = document.createElement('p'), actions = document.createElement('div'), button = document.createElement('button');
        article.className = 'result'; h.textContent = item.title;
        meta.textContent = [types[item.type], item.authors, item.publication, item.year, item.source].filter(Boolean).join(' · ');
        details.textContent = [item.credit ? 'Crédito/origem: ' + item.credit : '', item.license ? 'Licença informada: ' + item.license : item.type === 'image' ? 'Confira a licença na página do arquivo.' : ''].filter(Boolean).join(' · ');
        actions.className = 'actions'; actions.append(link('Abrir fonte', item.url));
        if (item.fulltext) actions.append(link('Ler texto na fonte', item.fulltext));
        if (item.licenseURL) actions.append(link('Consultar licença', item.licenseURL));
        button.type = 'button'; button.textContent = 'Remover da lista'; button.setAttribute('aria-label', 'Remover da lista: ' + item.title);
        button.addEventListener('click', () => {
          try { remove(item.url); render(index); } catch { status.textContent = 'Não foi possível remover a referência. A lista foi preservada.'; }
        });
        actions.append(button); article.append(h, meta); if (details.textContent) article.append(details); article.append(actions); root.append(article);
      });
      if (Number.isInteger(focusIndex)) {
        const buttons = root.querySelectorAll('button');
        if (buttons.length) buttons[Math.min(focusIndex, buttons.length - 1)].focus(); else status.focus();
      }
    }
    window.addEventListener('storage', event => { if (event.key === KEY || event.key === null) render(); });
    render();
  }
  window.addEventListener('servita-saved-change', refreshButtons);
  window.addEventListener('storage', event => { if (event.key === KEY || event.key === null) refreshButtons(); });
  window.ServitaSaved = { addButton, mount, read, normalize, save, remove };
})();
