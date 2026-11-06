/* ==========================================================
   烽火南境 · 写作台
   界面沿用炼笔智作（解包所得）的布局与设计令牌，
   数据与 AI 能力由本地 FastAPI 后端提供。
   ========================================================== */
(() => {
'use strict';

/* ---------------- 基础工具 ---------------- */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n) => (n || 0).toLocaleString('en-US');
const todayKey = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const autoGrow = (el, max) => {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, max || 200) + 'px';
};

const store = {
  get(k, d = null) { try { const v = localStorage.getItem(k); return v == null ? d : v; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  json(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
  setJson(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
  del(k) { try { localStorage.removeItem(k); } catch {} },
};

/* ---------------- 账号（服务器模式） ---------------- */
const AUTH_KEY = 'fj:auth:token';
const AUTH = { token: store.get(AUTH_KEY, ''), enabled: false, user: null };
const authHeaders = (extra) => ({ ...(extra || {}), ...(AUTH.token ? { Authorization: 'Bearer ' + AUTH.token } : {}) });

async function ensureAuth() {
  let st = { enabled: false };
  try {
    const r = await fetch('/api/auth/state', { cache: 'no-store' });
    if (r.ok) st = await r.json();
  } catch (e) { /* 后端没起来时交给后面的提示 */ }
  AUTH.enabled = !!st.enabled;
  if (!AUTH.enabled) return true;
  if (AUTH.token) {
    try {
      const me = await fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + AUTH.token }, cache: 'no-store' });
      if (me.ok) { AUTH.user = (await me.json()).user; return true; }
    } catch (e) { /* 网络问题，走登录页 */ }
    store.del(AUTH_KEY);
    AUTH.token = '';
  }
  showAuthGate(!!st.need_setup);
  return false;
}

function showAuthGate(needSetup) {
  const old = document.getElementById('authGate');
  if (old) old.remove();
  const el = document.createElement('div');
  el.id = 'authGate';
  el.innerHTML = `
    <div class="auth-card">
      <div class="auth-brand">烽火南境<span>·</span>写作台</div>
      <p class="auth-sub">${needSetup ? '首次使用，请创建管理员账号，书稿会存进服务器数据库' : '登录后，任何设备的同一账号都能打开你的书稿'}</p>
      <label class="auth-field"><span>账号</span><input id="authUser" autocomplete="username" placeholder="给账号起个名字"></label>
      <label class="auth-field"><span>密码</span><input id="authPass" type="password" autocomplete="current-password" placeholder="至少 6 位"></label>
      <div class="auth-err" id="authErr"></div>
      <button class="auth-btn" id="authGo">${needSetup ? '创建并进入' : '登录'}</button>
      <p class="auth-tip">数据存在服务器上，换手机、换电脑都能接着写。</p>
    </div>`;
  document.body.appendChild(el);
  const user = document.getElementById('authUser');
  const pass = document.getElementById('authPass');
  const err = document.getElementById('authErr');
  const btn = document.getElementById('authGo');
  const submit = async () => {
    const u = (user.value || '').trim();
    const p = pass.value || '';
    if (!u || !p) { err.textContent = '账号和密码都要填'; return; }
    btn.disabled = true;
    const label = btn.textContent;
    btn.textContent = '请稍候…';
    try {
      const r = await fetch('/api/auth/' + (needSetup ? 'register' : 'login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: u, password: p }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(d.detail || '登录失败');
      store.set(AUTH_KEY, d.token);
      AUTH.token = d.token;
      location.reload();
    } catch (e2) {
      err.textContent = e2.message || '登录失败';
      btn.disabled = false;
      btn.textContent = label;
    }
  };
  btn.onclick = submit;
  pass.addEventListener('keydown', (e3) => { if (e3.key === 'Enter') submit(); });
  setTimeout(() => user.focus(), 300);
}

/* ---------------- API ---------------- */
let offlineTimer = null;
function showOffline() {
  if (!document.getElementById('offlineBar')) {
    const bar = document.createElement('div');
    bar.id = 'offlineBar';
    bar.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;padding:8px 14px;background:#a5382e;color:#f7f3ea;'
      + 'font-size:13px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.25);letter-spacing:.02em';
    bar.textContent = '后端连接断开，正在自动重连…（保存会失败，请确认「启动写作台.bat」或桌面端在运行）';
    document.body.appendChild(bar);
  }
  if (offlineTimer) return;
  offlineTimer = setInterval(async () => {
    try {
      const r = await fetch('/api/health', { cache: 'no-store' });
      if (!r.ok) return;
      clearInterval(offlineTimer);
      offlineTimer = null;
      const bar = document.getElementById('offlineBar');
      if (bar) bar.remove();
      toast('已重新连上后端');
      try {
        await loadBooks();
        if (S.book) await openBook(S.book.name);
      } catch (e) { /* 忽略 */ }
    } catch (e) { /* 继续等 */ }
  }, 5000);
}

async function api(path, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase();
  const init = {
    ...opts,
    headers: {
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
      ...(AUTH.token ? { Authorization: 'Bearer ' + AUTH.token } : {}),
    },
    body: opts.body && typeof opts.body !== 'string' ? JSON.stringify(opts.body) : opts.body,
  };
  let res;
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch('/api' + path, init);
      break;
    } catch (e) {
      /* 读接口遇到断连（比如服务刚重启）自动重试一次 */
      if (attempt === 0 && method === 'GET') {
        await new Promise((r) => setTimeout(r, 800));
        continue;
      }
      showOffline();
      throw new Error('后端没在运行（请双击「启动写作台.bat」或打开桌面端），当前改动没能保存');
    }
  }
  let data = null;
  try { data = await res.json(); } catch {}
  if (res.status === 401 && AUTH.enabled) {
    store.del(AUTH_KEY);
    AUTH.token = '';
    showAuthGate(false);
    throw new Error('登录已过期，请重新登录');
  }
  if (!res.ok) throw new Error((data && (data.detail || data.message)) || `HTTP ${res.status}`);
  return data;
}

/* ---------------- 状态 ---------------- */
const S = {
  books: [],
  book: null,          // 项目对象
  files: [],           // FileNode[]
  chapterId: null,
  settings: { api_key: '', base_url: '', model: '' },
  goal: 3000,
  lock: { on: false, goal: 500, startWords: 0 },
  pomo: { on: false, left: 25 * 60, timer: null },
  find: { term: '', hits: [], idx: -1 },
  sensitives: [],
  flash: null,
  findVisible: false,
  searchTouched: false,
  lastAi: { text: '', kind: '' },
  chat: [],
  saveTimer: null,
  snapTimer: null,
  lockedWhileSaving: false,
};

const KEY = {
  lastBook: 'fj:lastBook',
  daily: 'fj:daily',
  goal: (b) => `fj:goal:${b}`,
  collapsed: (b) => `fj:collapsed:${b}`,
  foreshadow: (b) => `fj:foreshadow:${b}`,
  scratch: (b) => `fj:scratch:${b}`,
  chat: (b) => `fj:chat:${b}`,
  convs: (b) => `fj:convs:${b}`,
  snaps: (id) => `fj:snap:${id}`,
  trash: (b) => `fj:trash:${b}`,
  lex: 'fj:lex:custom',
  ui: 'fj:ui',
};

const DEFAULT_LEX = ['赌博', '毒品', '嫖', '自杀', '爆炸', '恐怖袭击', '枪支', '色情', '裸露', '血腥', '强奸', '拐卖', '邪教', '传销', '洗钱', '诈骗', '偷渡', '走私', '虐待', '尸块', '分尸', '自残'];

/* ---------------- 路由 / 分栏 ---------------- */
function setRightTab(tab) {
  $$('.rtab').forEach((b) => b.classList.toggle('on', b.dataset.tab === tab));
  $$('[data-pane]').forEach((p) => { p.hidden = p.dataset.pane !== tab; });
  if (tab === 'companion') { setTimeout(scrollChat, 30); updateChatCtx(); }
}

/* ---------------- 手机端布局 ---------------- */
const MOBILE_MQ = window.matchMedia('(max-width: 768px)');
const isMobileView = () => MOBILE_MQ.matches;

function updateMobileTitle() {
  const b = $('#mBookName');
  const c = $('#mChapterName');
  if (!b || !c) return;
  b.textContent = (S.book && S.book.name) || '未命名';
  const f = currentFile();
  c.textContent = f ? f.name : '未选择章节';
}

function setMobileTab(name) {
  const tabs = $('#mTabs');
  if (!tabs) return;
  Array.from(tabs.querySelectorAll('.m-tab')).forEach((b) => b.classList.toggle('on', b.dataset.mtab === name));
}

function closeMobileSheets(silent) {
  const left = $('#left');
  const right = $('#right');
  if (left) left.classList.remove('mobile-open');
  if (right) right.classList.remove('mobile-open');
  const sheet = $('#mMoreSheet');
  if (sheet) sheet.hidden = true;
  if (right) right.classList.remove('ai-float-mode');
  if (!silent) setMobileTab('write');
}

function setLeftTab(name) {
  const tab = name === 'book' ? 'book' : 'toc';
  document.body.classList.toggle('m-ltab-book', tab === 'book');
  document.body.classList.toggle('m-ltab-toc', tab === 'toc');
  $$('#mLeftTabs button').forEach((b) => b.classList.toggle('on', b.dataset.ltab === tab));
}

function openMobileToc() {
  closeMobileSheets(true);
  setLeftTab('toc');
  $('#left').classList.add('mobile-open');
  setMobileTab('toc');
  updateMobileTitle();
}

function openMobilePane(tab, mtab) {
  closeMobileSheets(true);
  setRightTab(tab);
  $('#right').classList.add('mobile-open');
  setMobileTab(mtab);
}

/* 写作台底栏的 AI：打开搭子。窄屏/手机端浮成一张卡片，宽屏切右栏 */
function openAiCompanion() {
  const right = $('#right');
  if (!right) return;
  const floating = isMobileView() || window.innerWidth <= 1240;
  closeMobileSheets(true);
  setRightTab('companion');
  if (floating) {
    right.classList.add('mobile-open');
    right.classList.add('ai-float-mode');
    setMobileTab('companion');
    setTimeout(() => { const box = $('#chatInput'); if (box) box.focus(); }, 150);
  }
  updateChatCtx();
  setTimeout(scrollChat, 60);
}

/* 侧栏抽屉的关闭按钮：任何宽度下都先建好，靠 CSS 决定什么时候显示，
   避免窄屏收起目录 / 侧栏时找不到关闭入口 */
function ensureSheetClose() {
  [['#left', '收起目录'], ['#right', '收起']].forEach((pair) => {
    const el = $(pair[0]);
    if (!el || el.querySelector('.m-sheet-close')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'm-sheet-close';
    btn.textContent = pair[1];
    btn.addEventListener('click', (e) => { e.stopPropagation(); closeMobileSheets(); });
    el.appendChild(btn);
  });
}

function applyMobileChrome() {
  const on = isMobileView();
  ensureSheetClose();
  const bar = $('#mBar');
  const tabs = $('#mTabs');
  if (bar) bar.hidden = !on;
  if (tabs) tabs.hidden = !on;
  if (!on) {
    document.body.classList.remove('m-mode');
    closeMobileSheets(true);
    return;
  }
  document.body.classList.add('m-mode');
  if (!document.body.classList.contains('m-ltab-book')) setLeftTab('toc');
  updateMobileTitle();
}

/* ---------------- Windows 桌面版外壳 ---------------- */
const IS_DESKTOP_SHELL = new URLSearchParams(location.search).get('shell') === 'desktop';

function initDesktopShell() {
  if (!IS_DESKTOP_SHELL) return;
  document.body.dataset.shell = 'desktop';
  const bar = $('#dBar');
  if (bar) bar.hidden = false;

  const model = $('#dModel');
  const chip = $('#modelChip');
  if (model && chip) model.textContent = chip.textContent || 'deepseek-flash';

  $$('#dMenu button').forEach((b) => b.addEventListener('click', () => {
    $$('#dMenu button').forEach((x) => x.classList.toggle('on', x === b));
    const link = document.querySelector(`.ml-nav a[data-nav="${b.dataset.dnav}"]`);
    if (link) link.click();
    if (b.dataset.dnav !== 'writer') setTimeout(() => { b.classList.remove('on'); }, 600);
  }));

  const api = () => (window.pywebview && window.pywebview.api) || null;
  const callWin = (name, ...args) => {
    const a = api();
    if (!a || typeof a[name] !== 'function') return;
    try {
      const p = a[name](...args);
      if (p && typeof p.catch === 'function') p.catch(() => {});
    } catch (e) { /* 浏览器里没有窗口 API，忽略 */ }
  };
  const min = $('#dMin');
  const max = $('#dMax');
  const close = $('#dClose');
  if (min) min.addEventListener('click', () => callWin('minimize'));
  if (max) max.addEventListener('click', () => callWin('toggle_max'));
  if (close) close.addEventListener('click', () => callWin('close'));

  /* 自绘标题栏拖动 */
  let drag = null;
  let dragRaf = 0;
  let dragTo = null;
  if (bar) {
    bar.addEventListener('mousedown', (e) => {
      if (e.target.closest('button')) return;
      if (!api()) return;
      drag = { sx: e.screenX, sy: e.screenY, wx: window.screenX, wy: window.screenY };
    });
    window.addEventListener('mousemove', (e) => {
      if (!drag) return;
      dragTo = { x: drag.wx + e.screenX - drag.sx, y: drag.wy + e.screenY - drag.sy };
      if (dragRaf) return;
      dragRaf = requestAnimationFrame(() => {
        dragRaf = 0;
        if (dragTo) callWin('move', Math.round(dragTo.x), Math.round(dragTo.y));
      });
    });
    window.addEventListener('mouseup', () => { drag = null; dragTo = null; });
  }
}

/* ---------------- 顶部书名 / 卡片 ---------------- */
function chapterFiles() { return S.files.filter((f) => f.type === 'FILE'); }
function volumeFolders() { return S.files.filter((f) => f.type === 'FOLDER' && f.id !== 'root' && f.parentId === 'root'); }
function childFolders(volId) { return S.files.filter((f) => f.type === 'FOLDER' && f.parentId === volId); }
function filesInFolder(id) { return S.files.filter((f) => f.type === 'FILE' && f.parentId === id); }
function filesInVolume(v) {
  const own = filesInFolder(v.id);
  childFolders(v.id).forEach((c) => own.push(...filesInFolder(c.id)));
  return own;
}
function fileById(id) { return S.files.find((f) => f.id === id) || null; }
function wordCount(text) { return (text || '').replace(/\s/g, '').length; }
function bookWords() { return chapterFiles().reduce((n, f) => n + wordCount(f.content), 0); }
function chapterNo(file) {
  const vol = file.parentId;
  const list = S.files.filter((f) => f.type === 'FILE' && f.parentId === vol);
  return list.findIndex((f) => f.id === file.id) + 1;
}
function currentFile() { return fileById(S.chapterId); }

function setCover(el, book, fallbackChar) {
  if (!el) return;
  if (book && book.cover) {
    el.style.backgroundImage = `url("${book.cover}")`;
    el.textContent = '';
    el.classList.add('has-image');
  } else {
    el.style.backgroundImage = '';
    el.textContent = fallbackChar || '书';
  }
}

function renderBookHead() {
  if (!S.book) {
    $('#bookName').textContent = '未命名';
    $('#bookMeta').textContent = '暂无书籍';
    $('#bookCoverChar').textContent = '书';
    $('#lcName').textContent = '未命名';
    $('#lcTag').textContent = '未设置题材';
    $('#lcCover').textContent = '书';
    $('#bookWords').textContent = '0';
    $('#crumbBook').textContent = '未命名';
    $('#signalGenre').textContent = '—';
    return;
  }
  const name = S.book.name || '未命名';
  const byline = S.book.author ? ' · ' + S.book.author : '';
  const meta = ([S.book.genre, S.book.style].filter(Boolean).join(' · ') || '未设置题材') + byline;
  $('#bookName').textContent = name;
  $('#bookMeta').textContent = meta;
  $('#bookCoverChar').textContent = name.slice(0, 1);
  $('#lcName').textContent = name;
  $('#lcTag').textContent = meta;
  $('#lcCover').textContent = name.slice(0, 1);
  setCover($('#bookCoverChar'), S.book, name.slice(0, 1));
  setCover($('#lcCover'), S.book, name.slice(0, 1));
  $('#bookWords').textContent = fmt(bookWords());
  $('#crumbBook').textContent = name;
  $('#signalGenre').textContent = S.book.genre || '—';
  if (typeof updateMobileTitle === 'function') updateMobileTitle();
}

/* ---------------- 目录 ---------------- */
function collapsedMap() { return store.json(KEY.collapsed(S.book ? S.book.name : '_'), {}); }
function saveCollapsed(map) { store.setJson(KEY.collapsed(S.book ? S.book.name : '_'), map); }

function renderToc() {
  const tree = $('#tocTree');
  const query = ($('#tocSearch').value || '').trim();
  if (!S.book) {
    tree.innerHTML = `<div class="toc-empty"><b>还没有书</b>点上方书名 → 新建书籍，<br>或先建一本再开写。</div>`;
    return;
  }
  const vols = volumeFolders();
  const rootFiles = S.files.filter((f) => f.type === 'FILE' && f.parentId === 'root');
  if (!vols.length && !rootFiles.length) {
    tree.innerHTML = `<div class="toc-empty"><b>目录还是空的</b>点下方「新建章节」开始。</div>`;
    return;
  }
  if (query) { renderTocSearch(tree, query); return; }

  const collapsed = collapsedMap();
  const html = [];

  const renderItems = (files) => files.map((f) => {
    const no = chapterNo(f);
    const wc = wordCount(f.content);
    const active = f.id === S.chapterId ? ' active' : '';
    return `<div class="ch-item${active}" data-id="${f.id}" draggable="true">
      <span class="no">${String(no).padStart(3, '0')}</span>
      <span class="ti">${esc(f.name)}</span>
      <span class="wc">${wc ? fmt(wc) : '0'}</span>
      <div class="ops">
        <button class="icon-btn" data-act="rename" title="重命名"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button>
        <button class="icon-btn" data-act="more" title="更多"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg></button>
      </div>
    </div>`;
  }).join('');

  if (rootFiles.length) {
    html.push(`<div class="vol" data-vol="root">${renderItems(rootFiles)}</div>`);
  }

  vols.forEach((v) => {
    const own = filesInFolder(v.id);
    const kids = childFolders(v.id);
    const all = filesInVolume(v);
    const words = all.reduce((n, f) => n + wordCount(f.content), 0);
    const isCollapsed = !!collapsed[v.id];
    const kidHtml = kids.map((k) => {
      const kf = filesInFolder(k.id);
      const kw = kf.reduce((n, f) => n + wordCount(f.content), 0);
      const kc = !!collapsed[k.id];
      return `<div class="vol sub${kc ? ' collapsed' : ''}" data-vol="${k.id}">
        <div class="vol-row">
          <span class="caret"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg></span>
          <div class="vn"><b>${esc(k.name)}</b><span>${kf.length} 章 · ${fmt(kw)} 字</span></div>
        </div>
        <div class="ch-list">${renderItems(kf)}</div>
      </div>`;
    }).join('');
    html.push(`<div class="vol${isCollapsed ? ' collapsed' : ''}" data-vol="${v.id}">
      <div class="vol-row">
        <span class="caret"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 9l6 6 6-6"/></svg></span>
        <div class="vn"><b>${esc(v.name)}</b><span>${all.length} 章 · ${fmt(words)} 字</span></div>
        <div class="ops">
          <button class="icon-btn" data-act="add-to" title="在此新建章节"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg></button>
          <button class="icon-btn" data-act="vol-more" title="分卷操作"><svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg></button>
        </div>
      </div>
      <div class="ch-list">${renderItems(own)}${kidHtml}</div>
    </div>`);
  });

  tree.innerHTML = html.join('') || `<div class="toc-empty"><b>目录还是空的</b>点下方「新建章节」开始。</div>`;
}

/* 目录搜索：标题命中 + 正文命中 */
function renderTocSearch(tree, query) {
  const hits = [];
  S.files.filter((f) => f.type === 'FILE').forEach((f) => {
    const inTitle = f.name.includes(query);
    const inBody = (f.content || '').includes(query);
    if (!inTitle && !inBody) return;
    let snippet = '';
    if (inBody) {
      const idx = f.content.indexOf(query);
      snippet = f.content.slice(Math.max(0, idx - 24), idx + query.length + 30).replace(/\n/g, ' ');
    }
    hits.push({ f, inTitle, snippet });
  });
  if (!hits.length) {
    tree.innerHTML = `<div class="toc-empty"><b>没有命中</b>换个关键词试试（标题和正文都会搜）。</div>`;
    return;
  }
  hits.sort((a, b) => Number(b.inTitle) - Number(a.inTitle));
  const mark = (s) => esc(s).replace(new RegExp(esc(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), (m) => `<mark>${m}</mark>`);
  tree.innerHTML = `
    <div class="toc-head" style="margin:2px 2px 6px"><span class="tt" style="font-size:12.5px">搜索「${esc(query)}」· ${hits.length} 条</span></div>
    ${hits.map(({ f, inTitle, snippet }) => `<div class="toc-hit" data-hit="${f.id}">
      <div class="h1">${inTitle ? mark(f.name) : esc(f.name)}</div>
      <div class="h2">${snippet ? '正文 · ' + mark(snippet) : '标题命中'}</div>
    </div>`).join('')}`;
}


/* ---------------- 编辑器 ---------------- */
const input = () => $('#input');

function renderBackdrop() {
  const el = input();
  const text = el.value;
  const bd = $('#backdrop');
  if (!text) { bd.innerHTML = ''; return; }

  const flags = new Uint8Array(text.length); // 0 none, 1 sensitive, 2 find
  S.sensitives.forEach((w) => {
    if (!w) return;
    let i = text.indexOf(w);
    while (i >= 0) { for (let k = i; k < i + w.length; k++) if (!flags[k]) flags[k] = 1; i = text.indexOf(w, i + w.length); }
  });
  const term = S.find.term;
  let currentStart = -1;
  if (term) {
    const hits = [];
    let i = text.indexOf(term);
    while (i >= 0) { hits.push(i); i = text.indexOf(term, i + term.length); }
    S.find.hits = hits;
    if (S.find.idx >= hits.length) S.find.idx = hits.length ? 0 : -1;
    S.find.hits.forEach((h, n) => {
      const cls = n === S.find.idx ? 2 : 2;
      for (let k = h; k < h + term.length; k++) flags[k] = cls;
      if (n === S.find.idx) currentStart = h;
    });
  } else { S.find.hits = []; S.find.idx = -1; }

  if (S.flash && S.flash.until > Date.now()) {
    const a = Math.max(0, S.flash.start);
    const b = Math.min(text.length, S.flash.start + S.flash.len);
    for (let k = a; k < b; k++) if (!flags[k]) flags[k] = 3;
  }

  let out = '';
  let i = 0;
  while (i < text.length) {
    const f = flags[i];
    let j = i;
    while (j < text.length && flags[j] === f) j++;
    const chunk = esc(text.slice(i, j));
    if (f === 1) out += `<mk>${chunk}</mk>`;
    else if (f === 2) out += `<mk class="find${i === currentStart ? ' cur' : ''}">${chunk}</mk>`;
    else if (f === 3) out += `<mk class="flash">${chunk}</mk>`;
    else out += chunk;
    i = j;
  }
  bd.innerHTML = out;
  bd.scrollTop = el.scrollTop;
  updateFindCount();
}

function updateFindCount() {
  const c = $('#findCnt');
  if (!S.find.term) { c.textContent = '0/0'; return; }
  c.textContent = `${S.find.idx >= 0 ? S.find.idx + 1 : 0}/${S.find.hits.length}`;
}

function updateEditorChrome() {
  const f = currentFile();
  const title = $('#chTitle');
  const empty = $('#edEmpty');
  if (!f) {
    title.value = '';
    autoGrow(title, 220);
    input().value = '';
    lastLen = 0;
    S.sensitives = [];
    renderBackdrop();
    empty.classList.remove('show');
    $('#crumbCh').textContent = '未选择章节';
    $('#crumbVol').textContent = '—';
    updateStats();
    return;
  }
  title.value = f.name;
  autoGrow(title, 220);
  input().value = f.content || '';
  lastLen = input().value.length;
  histReset();
  empty.classList.toggle('show', !(f.content || '').trim());
  const vol = fileById(f.parentId);
  $('#crumbVol').textContent = vol ? vol.name : '未分卷';
  $('#crumbCh').textContent = `第 ${String(chapterNo(f)).padStart(3, '0')} 章 · ${f.name}`;
  updateStats();
  applySensitivity();
}

function updateStats() {
  const f = currentFile();
  const words = f ? wordCount(f.content) : 0;
  const today = todayWords();
  const rate = currentRate();
  const pct = S.goal ? Math.min(100, Math.round((today / S.goal) * 100)) : 0;

  const setT = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };
  setT('#stChWords', fmt(words));
  setT('#stToday', fmt(today));
  setT('#stRate', rate);
  setT('#todayWords', fmt(today));
  setT('#dailyGoalValue', fmt(S.goal));
  setT('#ringPct', pct + '%');
  const ringFg = $('#ringFg');
  if (ringFg) ringFg.style.strokeDashoffset = String(194.8 * (1 - pct / 100));
  setT('#rateWords', rate);
  const sbGoalBar = $('#sbGoalBar');
  if (sbGoalBar) sbGoalBar.style.width = pct + '%';
  setT('#sbGoalPct', pct + '%');
  setT('#fsCh', fmt(words));
  setT('#fsToday', fmt(today));
  setT('#fsRate', rate);
  setT('#bookWords', fmt(bookWords()));
  renderWeekDots();
  renderLock();
  renderStats();
  if (!$('#phoneDrawer').classList.contains('show')) return;
  renderPhonePreview();
}

function updateTocCounts() {
  const f = currentFile();
  if (!f) return;
  const item = document.querySelector(`.ch-item[data-id="${f.id}"] .wc`);
  if (item) item.textContent = fmt(wordCount(f.content));
  const vol = document.querySelector(`.vol[data-vol="${f.parentId}"] .vn span`);
  if (vol) {
    const files = S.files.filter((x) => x.type === 'FILE' && x.parentId === f.parentId);
    vol.textContent = `${files.length} 章 · ${fmt(files.reduce((n, x) => n + wordCount(x.content), 0))} 字`;
  }
}

function renderWeekDots() {
  const box = $('#weekDots');
  if (!box) return;
  const names = ['一', '二', '三', '四', '五', '六', '日'];
  const daily = store.json(KEY.daily, {});
  const day = new Date().getDay() || 7;
  box.innerHTML = names.map((n, i) => {
    const idx = i + 1;
    const d = new Date(); d.setDate(d.getDate() - (day - idx));
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    const hit = (daily[key] || 0) > 0 ? ' hit' : '';
    const today = idx === day ? ' today' : '';
    return `<span class="wd${hit}${today}">${n}</span>`;
  }).join('');
}

/* ---- 今日字数 / 速率 ---- */
function todayWords() {
  const daily = store.json(KEY.daily, {});
  return daily[todayKey()] || 0;
}
function addTodayWords(n) {
  if (!n) return;
  const daily = store.json(KEY.daily, {});
  const k = todayKey();
  daily[k] = Math.max(0, (daily[k] || 0) + n);
  const keys = Object.keys(daily).sort();
  while (keys.length > 120) delete daily[keys.shift()];
  store.setJson(KEY.daily, daily);
  updateStats();
}
/* 速率按整分钟结算：一分钟到点才统计这一分钟手打了多少字，没到点不变 */
let rateWindowStart = 0;
let rateTyped = 0;
let rateLast = 0;

function markKeystroke(chars) {
  const now = Date.now();
  if (!rateWindowStart) rateWindowStart = now;
  rateTyped += chars;
}

/* 返回刚结算的速率；还没到一分钟返回 undefined */
function tickRate() {
  if (!rateWindowStart) return undefined;
  const now = Date.now();
  if (now - rateWindowStart < 60000) return undefined;
  rateLast = rateTyped;
  rateWindowStart = now;
  rateTyped = 0;
  return rateLast;
}

function currentRate() { return rateLast; }

/* 只算手打的字：输入法提交算；复制粘贴、拖拽、撤销重做、程序写入都不算 */
let imeComposing = false;
let imeCommit = 0;

function typedCharsFromEvent(e, delta) {
  if (!e) return 0;
  if (imeComposing) return 0;
  if (imeCommit) { imeCommit = 0; return 0; }
  if (typeof e.inputType === 'string' && e.inputType) {
    if (e.inputType === 'insertText' || e.inputType === 'insertReplacementText') {
      return String(e.data || '').length;
    }
    return 0;
  }
  /* 老环境拿不到 inputType：用长度差兜底，一次涨 20 字以上按粘贴处理 */
  const d = Number(delta) || 0;
  return d > 0 && d < 20 ? d : 0;
}

function recordTyped(n) {
  if (!n || n < 1) return;
  addTodayWords(n);
  markKeystroke(n);
  sfxOn();
  if (window.Ambient) window.Ambient.pulse();
}

/* ---- 打字音效（手打才响，粘贴 / AI 写入不响） ---- */
const SFX_SETS = {
  none: { name: '关闭', keys: [] },
  mechanical: { name: '机械键盘', keys: ['down1', 'down2', 'down3', 'down4', 'down5'].map((n) => `assets/sfx/clicketyclack/${n}.wav`) },
  typewriter: { name: '打字机', keys: ['assets/sfx/daktilo/keystroke.mp3', 'assets/sfx/daktilo/keystroke.mp3', 'assets/sfx/daktilo/ding.mp3'] },
  waveclick: { name: '电子点击', keys: ['waveclick-1', 'waveclick-2', 'waveclick-3'].map((n) => `assets/sfx/video-v1/${n}.wav`) },
  pencil: { name: '铅笔沙沙', keys: ['pencil-1', 'pencil-2', 'pencil-3'].map((n) => `assets/sfx/video-v1/${n}.wav`) },
  ballpoint: { name: '圆珠笔', keys: ['ballpoint-1', 'ballpoint-2', 'ballpoint-3'].map((n) => `assets/sfx/video-v1/${n}.wav`) },
  scifi: { name: '编程短音', keys: ['scifi-1', 'scifi-2', 'scifi-3'].map((n) => `assets/sfx/video-v1/${n}.wav`) },
  drop: { name: '水滴', keys: ['assets/sfx/ai-v1/drop-normal.wav'] },
  mahjong: { name: '麻将', keys: ['mahjong-1', 'mahjong-2', 'mahjong-3'].map((n) => `assets/sfx/ai-v1/${n}.wav`) },
  muyu: { name: '木鱼', keys: ['muyu-1', 'muyu-2', 'muyu-3'].map((n) => `assets/sfx/muyu/${n}.wav`) },
  black: { name: '黑轴', keys: ['assets/sfx/keyboard-v2/black-normal.wav'] },
  red: { name: '红轴', keys: ['assets/sfx/keyboard-v2/red-normal.wav'] },
  cute: { name: '动森', keys: ['505-key-1', '505-key-2', '505-key-3'].map((n) => `assets/sfx/cute/${n}.wav`) },
  dog: { name: '犬吠', keys: ['assets/ew/audio/dragon-studio-dog-bark-382732.mp3'] },
  ak: { name: '枪响', keys: ['assets/ew/audio/microsammy-ak-47-firing-8760.mp3'] },
};
const sfxPool = new Map();
let sfxLast = 0;

function sfxOn() {
  const ui = store.json(KEY.ui, {});
  const key = ui.sfx === 'clicketyclack' ? 'mechanical' : (ui.sfx || 'none');
  const set = SFX_SETS[key];
  if (!set || !set.keys.length) return;
  const now = Date.now();
  if (now - sfxLast < 28) return;
  sfxLast = now;
  const src = set.keys[Math.floor(Math.random() * set.keys.length)];
  let pool = sfxPool.get(src);
  if (!pool) { pool = []; sfxPool.set(src, pool); }
  try {
    let a = pool.find((x) => x.paused || x.ended);
    if (!a) {
      a = new Audio(src);
      pool.push(a);
      if (pool.length > 6) pool.shift();
    }
    a.volume = Math.max(0, Math.min(1, (ui.sfxVol == null ? 60 : ui.sfxVol) / 100));
    a.currentTime = 0;
    a.play().catch(() => {});
  } catch (e) { /* ignore */ }
}

function syncSfxUi() {
  const ui = store.json(KEY.ui, {});
  const key = ui.sfx === 'clicketyclack' ? 'mechanical' : (ui.sfx || 'none');
  $$('#sfxSeg button').forEach((b) => b.classList.toggle('on', b.dataset.sfx === key));
  const vol = ui.sfxVol == null ? 60 : ui.sfxVol;
  const r = $('#sfxVol');
  if (r) r.value = vol;
  const v = $('#sfxVolVal');
  if (v) v.textContent = vol + '%';
  applyTypography();
}

/* ---- 听写：录音 → 后端转写；不支持录音时退回浏览器语音识别 ---- */
let dictRec = null;
let dictating = false;
let dictStream = null;
let dictChunks = [];

function setDictateBtn(on, label) {
  const b = $('#dictateBtn');
  if (!b) return;
  if (!b.dataset.orig) b.dataset.orig = b.innerHTML;
  b.classList.toggle('on', on);
  b.title = on ? '结束听写' : '听写（语音输入）';
  b.innerHTML = on ? '<b style="color:var(--seal)">●</b> 录音中' : b.dataset.orig;
  if (label) toast(label);
}

function stopDictate() {
  if (!dictating) return;
  dictating = false;
  setDictateBtn(false);
  if (dictRec && dictRec.state !== 'inactive') { try { dictRec.stop(); } catch (e) { /* ignore */ } }
  if (dictStream) { dictStream.getTracks().forEach((t) => t.stop()); dictStream = null; }
}

/* 录音转 16k 单声道 WAV：本地模型和云端接口都能直接吃 */
async function blobToWav16k(blob) {
  const AC = window.AudioContext || window.webkitAudioContext;
  const ctx = new AC();
  let audio;
  try {
    audio = await ctx.decodeAudioData(await blob.arrayBuffer());
  } finally {
    try { ctx.close(); } catch (e) { /* ignore */ }
  }
  const rate = 16000;
  const frames = Math.max(1, Math.ceil(audio.duration * rate));
  const off = new OfflineAudioContext(1, frames, rate);
  const src = off.createBufferSource();
  src.buffer = audio;
  src.connect(off.destination);
  src.start();
  const rendered = await off.startRendering();
  const pcm = rendered.getChannelData(0);
  const buf = new ArrayBuffer(44 + pcm.length * 2);
  const view = new DataView(buf);
  const writeStr = (o, s) => { for (let i = 0; i < s.length; i++) view.setUint8(o + i, s.charCodeAt(i)); };
  writeStr(0, 'RIFF'); view.setUint32(4, 36 + pcm.length * 2, true);
  writeStr(8, 'WAVE'); writeStr(12, 'fmt ');
  view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  writeStr(36, 'data'); view.setUint32(40, pcm.length * 2, true);
  let o = 44;
  for (let i = 0; i < pcm.length; i++, o += 2) {
    const v = Math.max(-1, Math.min(1, pcm[i]));
    view.setInt16(o, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }
  return new Blob([buf], { type: 'audio/wav' });
}

async function transcribeBlob(blob) {
  const wav = await blobToWav16k(blob);
  const fd = new FormData();
  fd.append('file', wav, 'audio.wav');
  fd.append('language', 'zh');
  const r = await fetch('/api/ai/transcribe', { method: 'POST', headers: authHeaders(), body: fd });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || ('HTTP ' + r.status));
  return String(data.text || '').trim();
}

let dictModelState = null;
let dictPollTimer = null;

function paintDictStatus(st) {
  const lab = $('#dictModelStatus');
  const btn = $('#dictModelBtn');
  if (!lab) return;
  if (st && st.downloading) {
    const pct = st.total ? Math.min(100, Math.round((st.received || 0) / st.total * 100)) : 0;
    lab.textContent = '下载中 ' + pct + '% · ' + ((st.received || 0) / 1048576).toFixed(1) + ' MB';
    if (btn) { btn.disabled = true; btn.textContent = '下载中…'; }
  } else if (st && st.installed) {
    lab.textContent = '已就绪（离线可用）';
    if (btn) { btn.disabled = true; btn.textContent = '离线模型已安装'; }
  } else {
    const lack = st && st.has_sherpa === false;
    lab.textContent = lack ? '当前环境未安装 sherpa-onnx，无法离线听写' : (st && st.error ? '下载失败：' + st.error : '未安装 · 约 228MB');
    if (btn) { btn.disabled = !!lack; btn.textContent = '下载离线听写模型'; }
  }
}

async function refreshDictStatus() {
  try { dictModelState = await api('/dictation/status'); } catch (e) { dictModelState = null; }
  paintDictStatus(dictModelState);
  return dictModelState;
}

async function downloadDictModel() {
  const btn = $('#dictModelBtn');
  if (btn) btn.disabled = true;
  try {
    dictModelState = await api('/dictation/download', { method: 'POST', body: {} });
  } catch (e) {
    toast('下载失败：' + e.message);
    if (btn) btn.disabled = false;
    return;
  }
  paintDictStatus(dictModelState);
  clearInterval(dictPollTimer);
  dictPollTimer = setInterval(async () => {
    const st = await refreshDictStatus();
    if (!st || !st.downloading) {
      clearInterval(dictPollTimer);
      if (st && st.installed) toast('离线听写模型已就绪');
      else if (st && st.error) toast('下载失败：' + st.error);
    }
  }, 1500);
}

function startSpeechDictate() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { toast('当前环境不支持听写：请在 设置 → 接口 配置听写接口'); return; }
  dictRec = new SR();
  dictRec.lang = 'zh-CN';
  dictRec.continuous = true;
  dictRec.interimResults = false;
  dictRec.onresult = (e) => {
    let out = '';
    for (let i = e.resultIndex; i < e.results.length; i++) {
      if (e.results[i].isFinal) out += e.results[i][0].transcript;
    }
    if (out) insertAtCursor(out);
  };
  dictRec.onerror = (e) => { toast('听写出错：' + (e.error || '未知')); stopDictate(); };
  dictRec.onend = () => { if (dictating) { try { dictRec.start(); } catch (e) { stopDictate(); } } };
  try {
    dictRec.start();
    dictating = true;
    setDictateBtn(true, '听写中，说话就会写进正文');
  } catch (e) { toast('听写启动失败：' + e.message); }
}

async function toggleDictate() {
  if (dictating) { stopDictate(); return; }
  const st = S.settings || {};
  const cloudReady = !!(st.asr_base || st.has_asr_key || String(st.base_url || '').includes('siliconflow'));
  if (!cloudReady) {
    const ds = await refreshDictStatus();
    if (!ds || !ds.installed) { startSpeechDictate(); return; }
  }
  if (!navigator.mediaDevices || !window.MediaRecorder) { startSpeechDictate(); return; }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (e) {
    toast('没有拿到麦克风权限，改用浏览器语音识别');
    startSpeechDictate();
    return;
  }
  dictStream = stream;
  dictChunks = [];
  const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus'
    : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';
  dictRec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  dictRec.ondataavailable = (e) => { if (e.data && e.data.size) dictChunks.push(e.data); };
  dictRec.onstop = async () => {
    const type = (dictRec && dictRec.mimeType) || 'audio/webm';
    const blob = new Blob(dictChunks, { type });
    dictChunks = [];
    if (!blob.size) return;
    toast('正在转写…');
    try {
      const text = await transcribeBlob(blob);
      if (text) insertAtCursor(text);
      else toast('没听清，再说一次试试');
    } catch (e) {
      toast('听写失败：' + e.message);
    }
  };
  try {
    dictRec.start();
    dictating = true;
    setDictateBtn(true, '录音中，说完再点一次「听写」结束');
  } catch (e) {
    toast('录音启动失败：' + e.message);
    stream.getTracks().forEach((t) => t.stop());
    dictStream = null;
  }
}

/* ---- 写作画布（自由卡片 / 连线 / 手绘） ---- */
function openCanvas() {
  const frame = $('#canvasFrame');
  if (frame && (!frame.getAttribute('src') || frame.getAttribute('src') === 'about:blank')) {
    frame.setAttribute('src', 'free-canvas/index.html');
  }
  openModal('canvasModal');
}

/* ---- 保存 ---- */
function setSave(state, text) {
  $('#saveText').textContent = text;
  const dot = $('#saveDot');
  dot.classList.toggle('saving', state === 'saving');
}
function scheduleSave() {
  setSave('saving', '正在落存…');
  clearTimeout(S.saveTimer);
  const ui = store.json(KEY.ui, {});
  S.saveTimer = setTimeout(saveNow, Number(ui.autosaveMs) || 900);
  scheduleSnapshot();
}
async function saveNow(silent) {
  const f = currentFile();
  if (!f || !S.book) { setSave('idle', '尚未落存'); return; }
  clearTimeout(S.saveTimer);
  f.lastModified = Date.now();
  try {
    await api(`/files/${encodeURIComponent(S.book.name)}/${encodeURIComponent(f.id)}`, {
      method: 'PUT', body: { content: f.content || '', name: f.name, metadata: f.metadata || {} },
    });
    setSave('idle', '已落存');
    scanChapterCharacters(false);
    if (!silent) toast('已保存');
  } catch (e) {
    setSave('idle', '保存失败');
    toast('保存失败：' + e.message);
  }
}

function scheduleSnapshot() {
  clearTimeout(S.snapTimer);
  S.snapTimer = setTimeout(() => takeSnapshot(true), 5 * 60 * 1000);
}
function takeSnapshot(auto) {
  const f = currentFile();
  if (!f || !S.book) return;
  const key = KEY.snaps(f.id);
  const list = store.json(key, []);
  const content = f.content || '';
  if (list.length && list[0].content === content) { if (!auto) toast('内容没有变化'); return; }
  list.unshift({ t: Date.now(), title: f.name, content });
  store.setJson(key, list.slice(0, 20));
  if (!auto) toast('已存稿');
}

/* ---- 排版变量 ---- */
function applyTypography() {
  const t = store.json(KEY.ui, {});
  const size = t.size || 17, leading = t.leading || 16, indent = t.indent == null ? 2 : t.indent, family = t.family || 'sans';
  const side = t.side == null ? 58 : t.side;
  const fontName = t.fontName || '';
  const ink = t.ink || '';
  document.body.style.setProperty('--ed-size', size + 'px');
  document.body.style.setProperty('--ed-leading', (leading / 10).toFixed(1));
  document.body.style.setProperty('--ed-indent', indent + 'em');
  document.body.style.setProperty('--ed-side', side + 'px');
  if (fontName) document.body.style.setProperty('--ed-family', `"${String(fontName).replace(/"/g, '')}",${family === 'serif' ? 'var(--serif)' : 'var(--sans)'}`);
  else document.body.style.setProperty('--ed-family', family === 'serif' ? 'var(--serif)' : 'var(--sans)');
  const si = $('#typoSize'), sl = $('#typoLeading'), sn = $('#typoIndent');
  if (si) { si.value = size; $('#typoSizeVal').textContent = size + 'px'; }
  if (sl) { sl.value = leading; $('#typoLeadingVal').textContent = (leading / 10).toFixed(1); }
  if (sn) { sn.value = indent; $('#typoIndentVal').textContent = indent + 'em'; }
  $$('#typoFamily button').forEach((b) => b.classList.toggle('on', b.dataset.family === family));
  $$('#wsFamily button').forEach((b) => b.classList.toggle('on', !fontName && b.dataset.family === family));
  const ws = { wsSize: [size, size + 'px'], wsLeading: [leading, (leading / 10).toFixed(1)], wsIndent: [indent, indent + 'em'], wsSide: [side, side + 'px'] };
  Object.entries(ws).forEach(([id, [v, txt]]) => {
    const el = $('#' + id); if (el) el.value = v;
    const lab = $('#' + id + 'Val'); if (lab) lab.textContent = txt;
  });
  const fn = $('#wsFontName'); if (fn && document.activeElement !== fn) fn.value = fontName;
  $$('#wsInkSeg button').forEach((b) => b.classList.toggle('on', (b.dataset.ink === 'custom') === !!ink));
  const ic = $('#wsInkColor'); if (ic && ink) ic.value = ink;
  const irow = $('#wsInkRow'); if (irow) irow.hidden = !ink;
}

/* ---------------- 主题 / 纸面 / 场景 ---------------- */
const SCENES = [
  { id: 'none', name: '无' },
  { id: 'starfield', name: '星野' },
  { id: 'island', name: '窗岛' },
  { id: 'night-train', name: '夜车' },
  { id: 'pond', name: '池塘' },
  { id: 'dunes', name: '沙丘' },
  { id: 'ocean', name: '远海' },
  { id: 'monet', name: '莫奈花园' },
  { id: 'ink', name: '水墨' },
  { id: 'dream', name: '梦境' },
  { id: 'bamboo', name: '竹林雨' },
  { id: 'ink-wash', name: '水墨留白', img: 'assets/scenes/ink-wash.jpg' },
  { id: 'paper-bamboo', name: '宣纸竹影', img: 'assets/scenes/paper-bamboo.jpg' },
  { id: 'green-mountain', name: '青绿山水', img: 'assets/scenes/green-mountain.jpg' },
  { id: 'ink-dragon', name: '水墨双龙', img: 'assets/scenes/ink-dragon.jpg' },
  { id: 'green-dragon', name: '青绿青龙', img: 'assets/scenes/green-dragon.jpg' },
  { id: 'sakura-blade', name: '樱雨刀光', img: 'assets/scenes/sakura-blade.jpg' },
  { id: 'ne-zha', name: '哪吒闹海', img: 'assets/scenes/ne-zha.jpg' },
  { id: 'tokusatsu', name: '都市巨兽', img: 'assets/scenes/tokusatsu.jpg' },
  { id: 'custom', name: '自定义' },
];

function sceneFileUrl(scene) {
  const s = SCENES.find((x) => x.id === scene);
  if (s && s.img) return s.img;
  return `assets/scenes/${scene}.webp`;
}

function sceneImageUrl(ui) {
  if (ui.scene === 'custom') return ui.customImage ? `url("${ui.customImage}")` : 'none';
  if (!ui.scene || ui.scene === 'none') return 'none';
  return `url("${sceneFileUrl(ui.scene)}")`;
}

function sceneScrimColor(ui, theme) {
  const a = (ui.scrim == null ? 40 : ui.scrim) / 100;
  return theme === 'night' ? `rgba(6,8,10,${a})` : `rgba(250,247,240,${a})`;
}

/* ---------- 字色自适应：主题 / 纸张透明度 / 氛围场景 ---------- */
const SCENE_TONE = new Map();
const THEME_BASE = {
  paper: { editor: '#faf8f1', card: '#fdfbf6', card2: '#f3efe5', deep: '#e9e6dd' },
  eye: { editor: '#f8f1de', card: '#faf4e4', card2: '#f3ecd8', deep: '#ece2cc' },
  night: { editor: '#1b1c1f', card: '#1f2124', card2: '#26282c', deep: '#131416' },
};
const SURF_LIGHT = { editor: '#faf8f1', card: '#fdfbf6', card2: '#f3efe5', deep: '#e9e6dd' };
const SURF_DARK = { editor: '#1b1c1f', card: '#1f2124', card2: '#26282c', deep: '#131416' };
/* 透明度硬底线：再低也要留一层薄底。否则深色氛围图会直接透上来把整页压成黑色，任何字色都读不出来 */
const PAPER_ALPHA_FLOOR = 34;
const SIDE_ALPHA_FLOOR = 26;

function _rgbOf(hex) {
  const s = String(hex || '').trim();
  let m = s.match(/^#([0-9a-f]{3})$/i);
  if (m) return [parseInt(m[1][0] + m[1][0], 16), parseInt(m[1][1] + m[1][1], 16), parseInt(m[1][2] + m[1][2], 16)];
  m = s.match(/^#([0-9a-f]{6})$/i);
  if (m) return [parseInt(m[1].slice(0, 2), 16), parseInt(m[1].slice(2, 4), 16), parseInt(m[1].slice(4, 6), 16)];
  m = s.match(/^rgba?\(([^)]+)\)/i);
  if (m) {
    const p = m[1].split(',').map((x) => parseFloat(x));
    return [p[0] || 0, p[1] || 0, p[2] || 0];
  }
  return [250, 248, 241];
}

function _lumOf(rgb) {
  const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  return 0.2126 * f(rgb[0]) + 0.7152 * f(rgb[1]) + 0.0722 * f(rgb[2]);
}

function _contrastOf(l1, l2) {
  const a = Math.max(l1, l2);
  const b = Math.min(l1, l2);
  return (a + 0.05) / (b + 0.05);
}

function _mixRgb(a, b, t) {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function _cssRgb(rgb, alpha) {
  const r = Math.round(rgb[0]); const g = Math.round(rgb[1]); const b = Math.round(rgb[2]);
  return alpha == null ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${alpha})`;
}

/* 让字色在给定背景亮度下达到 target 对比度；达不到就取黑/白里更清楚的那个 */
function _fitInk(base, bgLum, target) {
  const baseC = _contrastOf(_lumOf(base), bgLum);
  if (baseC >= target) return base.slice();
  let best = base.slice();
  let bestC = baseC;
  for (const toward of [[0, 0, 0], [255, 255, 255]]) {
    let lo = 0;
    let hi = 1;
    let hit = -1;
    for (let i = 0; i < 18; i++) {
      const mid = (lo + hi) / 2;
      if (_contrastOf(_lumOf(_mixRgb(base, toward, mid)), bgLum) >= target) { hit = mid; hi = mid; } else { lo = mid; }
    }
    const t = hit >= 0 ? hit : 1;
    const rgb = _mixRgb(base, toward, t);
    const c = _contrastOf(_lumOf(rgb), bgLum);
    if (c > bestC) { best = rgb; bestC = c; }
  }
  return best;
}

/* 采样场景图平均亮度（同源 canvas，一次即可） */
function loadSceneTone(cssUrl, done) {
  if (!cssUrl || cssUrl === 'none' || SCENE_TONE.has(cssUrl)) { done(); return; }
  const m = cssUrl.match(/url\(["']?(.*?)["']?\)/);
  if (!m) { done(); return; }
  const img = new Image();
  img.onload = () => {
    try {
      const c = document.createElement('canvas');
      c.width = 16; c.height = 16;
      const ctx = c.getContext('2d');
      ctx.drawImage(img, 0, 0, 16, 16);
      const d = ctx.getImageData(0, 0, 16, 16).data;
      let r = 0; let g = 0; let b = 0; let n = 0;
      for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; n++; }
      SCENE_TONE.set(cssUrl, _lumOf([r / n, g / n, b / n]));
    } catch (e) {
      SCENE_TONE.set(cssUrl, null);
    }
    done();
  };
  img.onerror = () => { SCENE_TONE.set(cssUrl, null); done(); };
  img.src = m[1];
}

function syncInkReadable(ui, theme, paperA, sideA) {
  const scene = ui.scene || 'none';
  const cssUrl = sceneImageUrl(ui);
  if (cssUrl !== 'none' && !SCENE_TONE.has(cssUrl)) {
    loadSceneTone(cssUrl, () => { applyUi(); });
    return;
  }
  const base = THEME_BASE[theme] || THEME_BASE.paper;
  const paperLum = _lumOf(_rgbOf(base.editor));
  const pageLum = _lumOf(_rgbOf(base.deep));
  const scrimT = (ui.scrim == null ? 40 : ui.scrim) / 100;
  const scrimLum = _lumOf(_rgbOf(sceneScrimColor(ui, theme)));
  const scope = ui.sceneScope || 'global';
  const op = (ui.opacity == null ? 50 : ui.opacity) / 100;
  const rawTone = cssUrl === 'none' ? null : SCENE_TONE.get(cssUrl);
  const imgLum = rawTone == null ? scrimLum : rawTone;
  /* 纸面下面铺的是「场景层」：浓度(opacity)只作用在这一层，必须按实际浓度折算。
     之前把场景当满强度算，深色图会被判成亮底/暗底，字色跟着选错，透明一拉低就整页发黑 */
  let underLum = pageLum;
  if (scene !== 'none') {
    if (scope === 'page') underLum = (pageLum * (1 - op) + imgLum * op) * (1 - scrimT) + scrimLum * scrimT;
    else underLum = pageLum * (1 - op) + (imgLum * (1 - scrimT) + scrimLum * scrimT) * op;
  }
  /* 正文纸面与左右栏各算一次，取更吃力的那个。
     专注模式下左右栏现在是保留的（只是收起了顶栏等干扰元素），所以照样要把侧栏算进去 */
  const a = Math.max(0, Math.min(100, paperA == null ? 100 : paperA)) / 100;
  const sa = Math.max(0, Math.min(100, sideA == null ? 100 : sideA)) / 100;
  const paperBg = paperLum * a + underLum * (1 - a);
  const sideBg = paperLum * sa + underLum * (1 - sa);
  const bgLum = Math.min(paperBg, sideBg);

  const nativeDark = theme === 'night';
  const wantDark = bgLum < 0.36;
  const inkBase = wantDark ? [246, 243, 235] : [29, 30, 32];
  const ink = _fitInk(inkBase, bgLum, 9);
  const ink2 = _fitInk(wantDark ? [214, 210, 199] : [75, 74, 69], bgLum, 6);
  const muted = _fitInk(wantDark ? [170, 165, 152] : [110, 108, 99], bgLum, 4.2);

  document.body.style.setProperty('--ink', _cssRgb(ink));
  document.body.style.setProperty('--ink-2', _cssRgb(ink2));
  document.body.style.setProperty('--muted', _cssRgb(muted));
  document.body.style.setProperty('--faint', _cssRgb(_mixRgb(ink, wantDark ? [255, 255, 255] : [0, 0, 0], 0.45)));
  document.body.style.setProperty('--line', _cssRgb(ink, wantDark ? 0.2 : 0.14));
  document.body.style.setProperty('--line-strong', _cssRgb(ink, wantDark ? 0.38 : 0.3));

  /* 正文字色：默认跟随主题/场景；自定义色也按背景亮度校正，保证在深色氛围里不糊成一片 */
  const wantInk = ui.ink ? _fitInk(_rgbOf(ui.ink), bgLum, 7) : ink;
  document.body.style.setProperty('--ed-ink', _cssRgb(wantInk));
  /* 光标颜色同样跟着背景走，深色场景下不至于消失 */
  const sealRaw = getComputedStyle(document.body).getPropertyValue('--seal').trim();
  if (sealRaw) {
    document.body.style.setProperty('--ed-caret', _cssRgb(_fitInk(_rgbOf(sealRaw), bgLum, 4.5)));
  }

  /* 只有背景与主题明暗相反时才翻转表面，避免白天主题被场景硬拽成黑夜 */
  if (wantDark !== nativeDark) {
    const surf = wantDark ? SURF_DARK : SURF_LIGHT;
    document.body.style.setProperty('--editor', surf.editor);
    document.body.style.setProperty('--card', surf.card);
    document.body.style.setProperty('--card-2', surf.card2);
    document.body.style.setProperty('--paper-deep', surf.deep);
    document.body.style.setProperty('--paper', surf.deep);
  } else {
    document.body.style.removeProperty('--editor');
    document.body.style.removeProperty('--card');
    document.body.style.removeProperty('--card-2');
    document.body.style.removeProperty('--paper-deep');
    document.body.style.removeProperty('--paper');
  }
  document.body.dataset.inkMode = wantDark ? 'dark' : 'light';
}

function applyUi() {
  const ui = store.json(KEY.ui, {});
  const theme = ui.theme || 'paper';
  const paper = ui.paper || 'plain';
  const scene = ui.scene || 'none';
  const scope = ui.sceneScope || 'global';
  const opacity = ui.opacity == null ? 50 : ui.opacity;
  const blur = ui.blur == null ? 0 : ui.blur;
  const scrim = ui.scrim == null ? 40 : ui.scrim;
  const paperAlpha = ui.paperAlpha == null ? 100 : ui.paperAlpha;
  const autoAlpha = ui.autoAlpha !== false;
  const effAlpha = (autoAlpha && scene !== 'none') ? Math.min(paperAlpha, 84) : paperAlpha;
  /* 透明度再低也要留一层薄底，配合上面的字色计算，避免深色场景把整页压成黑色 */
  const paperCss = Math.max(PAPER_ALPHA_FLOOR, effAlpha);
  const sideCss = Math.max(SIDE_ALPHA_FLOOR, paperCss - 14);

  document.body.dataset.theme = theme;
  document.body.dataset.paper = paper;
  document.body.dataset.scene = scene;
  if (window.Ambient) window.Ambient.set(scope === 'page' ? 'none' : scene);
  document.body.dataset.sceneScope = scope;
  document.documentElement.dataset.colorMode = theme === 'night' ? 'night' : 'day';
  document.body.style.setProperty('--paper-alpha', String(paperCss));
  document.body.style.setProperty('--side-alpha', String(sideCss));
  document.body.style.setProperty('--scene-image', sceneImageUrl(ui));
  document.body.style.setProperty('--scene-opacity', String(opacity / 100));
  document.body.style.setProperty('--scene-blur', blur + 'px');
  document.body.style.setProperty('--scene-scrim', sceneScrimColor(ui, theme));

  renderSceneChoices();
  $$('#themeSeg button, #setThemeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.themeBtn === theme));
  $$('#paperSeg button, #setPaperSeg button').forEach((b) => b.classList.toggle('on', b.dataset.paperBtn === paper));
  $$('#sceneScopeSeg button, #setScopeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.scope === scope));
  $$('#sceneChoices .background-choice').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.scene === scene)));
  $$('#setSceneSeg button').forEach((b) => b.classList.toggle('on', b.dataset.scene === scene));

  const setSlider = (id, valId, value, text) => {
    const el = $('#' + id);
    if (el) el.value = value;
    const lab = $('#' + valId);
    if (lab) lab.textContent = text;
  };
  setSlider('sceneOpacity', 'sceneOpacityVal', opacity, opacity + '%');
  setSlider('sceneBlur', 'sceneBlurVal', blur, blur + 'px');
  setSlider('sceneScrim', 'sceneScrimVal', scrim, scrim + '%');
  setSlider('setSceneOpacity', 'setSceneOpacityVal', opacity, opacity + '%');
  setSlider('setSceneBlur', 'setSceneBlurVal', blur, blur + 'px');
  setSlider('setSceneScrim', 'setSceneScrimVal', scrim, scrim + '%');
  setSlider('paperAlpha', 'paperAlphaVal', paperAlpha, paperAlpha + '%');
  $$('#autoAlphaSeg button').forEach((b) => b.classList.toggle('on', (b.dataset.autoAlpha === '1') === autoAlpha));

  const customBtns = [$('#bgClearCustom'), $('#setLookClear')];
  customBtns.forEach((b) => { if (b) b.hidden = !ui.customImage; });
  const nameEl = $('#bgCustomName');
  if (nameEl) nameEl.textContent = ui.customImage ? ui.customImage.split('/').pop() : '';

  $('#themeLabel').textContent = theme === 'night' ? '夜间' : theme === 'eye' ? '护眼' : '背景';
  document.body.classList.toggle('typewriter-on', !!ui.typewriter);
  $('#twBtn').classList.toggle('on', !!ui.typewriter);
  const wsTw = $('#wsTypewriter');
  if (wsTw) {
    wsTw.setAttribute('aria-checked', String(!!ui.typewriter));
    wsTw.textContent = '光标居中 · ' + (ui.typewriter ? '已开启' : '已关闭');
    wsTw.classList.toggle('primary', !!ui.typewriter);
  }
  syncInkReadable(ui, theme, paperCss, sideCss);
  applyTypography();

  /* 底部工具栏：整条收起 / 展开（工具栏 + 状态栏一起收，编辑区自动变高） */
  document.body.classList.toggle('tools-collapsed', !!ui.ftMin);
  const ftBtn = $('#ftToggle');
  if (ftBtn) {
    ftBtn.setAttribute('aria-expanded', String(!ui.ftMin));
    ftBtn.title = ui.ftMin ? '展开工具栏' : '收起工具栏';
  }
  if (ui.ftMin) closeFtDrawer();

  /* 左右侧栏：桌面端整栏收起 / 展开（手机端走抽屉逻辑，不受影响） */
  document.body.classList.toggle('left-hidden', !!ui.leftHidden);
  document.body.classList.toggle('right-hidden', !!ui.rightHidden);
  const ltBtn = $('#leftToggle'), rtBtn = $('#rightToggle');
  if (ltBtn) {
    ltBtn.setAttribute('aria-pressed', String(!!ui.leftHidden));
    ltBtn.title = ui.leftHidden ? '展开目录' : '收起目录';
  }
  if (rtBtn) {
    rtBtn.setAttribute('aria-pressed', String(!!ui.rightHidden));
    rtBtn.title = ui.rightHidden ? '展开侧栏' : '收起侧栏';
  }
}

function setUi(patch) {
  const ui = store.json(KEY.ui, {});
  Object.assign(ui, patch);
  store.setJson(KEY.ui, ui);
  applyUi();
}

function renderSceneChoices() {
  const box = $('#sceneChoices');
  if (!box) return;
  const ui = store.json(KEY.ui, {});
  box.innerHTML = SCENES.map((s) => {
    let thumb = '';
    if (s.id === 'custom') thumb = ui.customImage ? `background-image:url('${ui.customImage}')` : '';
    else if (s.id !== 'none') thumb = `background-image:url('${sceneFileUrl(s.id)}')`;
    return `<button class="background-choice" data-scene="${s.id}" aria-pressed="${s.id === (ui.scene || 'none')}">
      <i style="${thumb}"></i><span>${s.name}</span>
    </button>`;
  }).join('');

  const segBox = $('#setSceneSeg');
  if (segBox) {
    segBox.innerHTML = SCENES.map((s) => `<button data-scene="${s.id}" class="${s.id === (ui.scene || 'none') ? 'on' : ''}" style="flex:none;padding:0 10px">${s.name}</button>`).join('');
  }
}

async function handleBackgroundFile(file) {
  if (!file) return;
  if (file.size > 8 * 1024 * 1024) { toast('图片超过 8MB，请先压缩'); return; }
  const dataUrl = await new Promise((res) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.readAsDataURL(file);
  });
  try {
    const r = await api('/appearance/background', { method: 'POST', body: { data: dataUrl } });
    setUi({ customImage: r.url, scene: 'custom' });
    toast('自定义背景已应用');
  } catch (e) { toast('上传失败：' + e.message); }
}

function pickBackgroundImage() {
  const inp = $('#bgFileInput');
  if (inp) { inp.value = ''; inp.click(); }
}

/* ---------------- 敏感词 / 自检 ---------------- */
const RISK_DICT = [
  { cat: '色情', level: 3, words: ['色情', '裸体', '裸身', '情欲', '呻吟', '抚摸', '亲吻', '床笫', '肉体', '淫', '荡妇', '勾引', '发情', '媚药', '春药'] },
  { cat: '暴力', level: 2, words: ['血腥', '溅血', '割喉', '斩首', '碎尸', '鞭打', '酷刑', '残肢', '断臂', '血肉模糊', '杀人', '屠杀', '尸首', '屠戮'] },
  { cat: '违法', level: 3, words: ['毒品', '吸毒', '海洛因', '冰毒', '枪支', '炸弹', '走私', '洗钱', '赌博', '诈骗', '绑架', '拐卖', '贿赂', '贪腐'] },
  { cat: '迷信', level: 1, words: ['邪教', '诅咒', '附身', '妖术', '蛊毒', '血祭', '招魂', '鬼上身'] },
  { cat: '网络', level: 1, words: ['微信', 'QQ', '支付宝', '淘宝', '抖音', '二维码', '加群', '代理', '返利', '刷单'] },
];
const RISK_NAME = { 1: '低', 2: '中', 3: '高' };
let SELF_SC_T = 0;

function lexList() {
  const custom = store.json(KEY.lex, []);
  return Array.from(new Set([...DEFAULT_LEX, ...custom]));
}
function normForScan(s) {
  return String(s || '').replace(/[\s\u200b-\u200f·.,，。!！?？;；:："'"'‘’“”()（）\[\]【】<>《》\-_/\\|*#~`…—]/g, '');
}
function countIn(s, w) {
  if (!s || !w) return 0;
  let n = 0, i = 0;
  while ((i = s.indexOf(w, i)) >= 0) { n++; i += w.length; }
  return n;
}
function countWord(raw, norm, w) {
  const c1 = countIn(raw, w);
  const nw = normForScan(w);
  const c2 = (nw && nw !== w) ? countIn(norm, nw) : 0;
  return Math.max(c1, c2);
}
function scanRisk(text) {
  const norm = normForScan(text);
  const map = new Map();
  const add = (w, cat, level) => {
    if (!w) return;
    const n = countWord(text, norm, w);
    if (!n) return;
    const old = map.get(w);
    if (old) { old.count = Math.max(old.count, n); old.level = Math.max(old.level, level); return; }
    map.set(w, { word: w, cat, level, count: n });
  };
  RISK_DICT.forEach((g) => g.words.forEach((w) => add(w, g.cat, g.level)));
  lexList().forEach((w) => add(w, '自定义', 2));
  return Array.from(map.values()).sort((a, b) => b.level * b.count - a.level * a.count);
}
function applySensitivity() {
  const text = input().value || '';
  const hits = scanRisk(text);
  S.sensitives = hits.map((h) => h.word);
  renderBackdrop();
  renderSelfCheck(hits);
}
function renderSelfCheck(hits) {
  const text = input().value || '';
  hits = hits || scanRisk(text);
  const total = hits.reduce((s, h) => s + h.count, 0);
  const risk = Math.min(100, Math.round(hits.reduce((s, h) => s + h.level * h.count * 6, 0)));
  const band = risk >= 60 ? 'high' : risk >= 25 ? 'mid' : 'low';
  $('#senCount').textContent = total;
  $('#senScanned').textContent = fmt(wordCount(text));
  $('#senLex').textContent = RISK_DICT.reduce((n, g) => n + g.words.length, 0) + lexList().length;
  $('#senList').innerHTML = hits.length
    ? `<div class="risk-bar"><i class="${band}" style="width:${Math.max(5, risk)}%"></i></div>
       <div class="hint" style="margin:5px 0 3px">风险 ${risk} · ${band === 'high' ? '高' : band === 'mid' ? '中' : '低'} · 共 ${total} 处</div>
       <div class="hint" style="margin-bottom:8px">${Object.entries(hits.reduce((m, h) => { m[h.cat] = (m[h.cat] || 0) + h.count; return m; }, {})).map(([k, v]) => `${esc(k)} ${v}`).join(' · ')}</div>`
      + hits.slice(0, 10).map((h) => `<div class="outline-li" data-jump="${esc(h.word)}" style="cursor:pointer" title="定位到正文">
          <span class="oi">${RISK_NAME[h.level]}</span><span>「${esc(h.word)}」×${h.count} <span class="hint">${esc(h.cat)}</span></span>
        </div>`).join('')
    : '<div class="hint">未发现风险词</div>';
  const chip = $('#stSensitive');
  if (chip) chip.innerHTML = total ? `<span class="bad">敏感 ${total}</span>` : '';
  clearTimeout(SELF_SC_T);
  SELF_SC_T = setTimeout(() => { renderRepeat(text); renderRhythm(text); }, 240);
}

function renderRepeat(text) {
  const clean = String(text || '').replace(/[^\u4e00-\u9fa5]/g, '');
  const box = $('#repeatList');
  if (!box) return;
  if (clean.length < 80) {
    box.innerHTML = '<span class="sub" style="font-size:11.5px;color:var(--muted)">正文太短，先写 80 字以上</span>';
    return;
  }
  const stop = new Set('的了着过是在我你他她它不都也就很又还这那有和与说着来去上下没有把被给让对从到地得只而但并'.split(''));
  // 按标点切成小句，只在句内统计，避免跨标点拼出假词
  const clauses = String(text || '').split(/[^\u4e00-\u9fa5]+/).filter((c) => c.length >= 2);
  const freq = new Map();
  clauses.forEach((c) => {
    for (let n = 2; n <= 5; n++) {
      for (let i = 0; i + n <= c.length; i++) {
        const g = c.slice(i, i + n);
        if (stop.has(g[0]) || stop.has(g[g.length - 1])) continue;
        if (n === 2 && (stop.has(g[1]) || /[的了着过是在]/.test(g))) continue;
        freq.set(g, (freq.get(g) || 0) + 1);
      }
    }
  });
  const overlap = (a, b) => {
    const k = Math.min(a.length, b.length) - 1;
    if (k < 2) return false;
    for (let i = 0; i + k <= a.length; i++) if (b.includes(a.slice(i, i + k))) return true;
    return false;
  };
  const rows = [];
  Array.from(freq.entries())
    .filter(([w, c]) => c >= (w.length >= 3 ? 2 : 3))
    .sort((a, b) => (b[1] * (b[0].length - 1)) - (a[1] * (a[0].length - 1)))
    .forEach(([w, c]) => {
      if (rows.some((r) => r[0].includes(w) || w.includes(r[0]) || overlap(r[0], w))) return;
      rows.push([w, c]);
    });
  const tics = ['仿佛', '忽然', '瞬间', '微微', '缓缓', '淡淡', '猛地', '似乎', '不禁', '竟然', '顿时', '目光', '嘴角', '心里', '脸色', '一丝', '一抹', '一声', '有些'];
  tics.forEach((w) => {
    const n = countIn(text, w);
    if (n >= 2 && !rows.some((r) => r[0].includes(w) || w.includes(r[0]))) rows.push([w, n]);
  });
  rows.sort((a, b) => b[1] - a[1]);
  const top = rows.slice(0, 12);
  const redundant = rows.reduce((s, r) => s + (r[1] - 1) * r[0].length, 0);
  const ratio = Math.min(99, Math.round((redundant / clean.length) * 100));
  box.innerHTML = top.length
    ? `<div class="rhythm-meta">重复片段 ${rows.length} 组 · 冗余约 ${ratio}% · 点词定位</div>`
      + top.map(([w, n]) => `<span class="lex" data-jump="${esc(w)}" style="cursor:pointer" title="出现 ${n} 次 · 点此定位">${esc(w)} ×${n}</span>`).join('')
    : '<span class="sub" style="font-size:11.5px;color:var(--muted)">没有明显重复片段</span>';
}

function renderRhythm(text) {
  const box = $('#rhythmList');
  if (!box) return;
  const paras = judgeParaSplit(text);
  if (!paras.length) {
    box.innerHTML = '<div class="outline-li"><span class="oi">—</span><span>还没有正文</span></div>';
    return;
  }
  const lens = paras.map((p) => p.replace(/\s/g, '').length);
  const avg = Math.round(lens.reduce((a, b) => a + b, 0) / lens.length);
  const sd = Math.sqrt(lens.reduce((a, l) => a + (l - avg) * (l - avg), 0) / lens.length);
  const cv = avg ? sd / avg : 0;
  const longN = lens.filter((l) => l > 220).length;
  const shortN = lens.filter((l) => l < 15).length;
  const dialogN = paras.filter((p) => /[“「"]/.test(p)).length;
  const max = Math.max(...lens, 1);
  const bars = paras.slice(0, 80).map((p, i) => {
    const l = lens[i];
    const h = Math.max(5, Math.round((l / max) * 44));
    const cls = l > 220 ? 'high' : l < 15 ? 'low' : '';
    return `<i class="${cls}" data-jpara="${i + 1}" style="height:${h}px" title="第 ${i + 1} 段 · ${l} 字"></i>`;
  }).join('');
  const verdict = cv > 0.75 ? '长短错落，节奏自然' : cv > 0.45 ? '节奏偏匀，可再加点短句' : '节奏很平，几乎每段一样长';
  const maxI = lens.indexOf(max);
  const minI = lens.indexOf(Math.min(...lens));
  box.innerHTML = `
    <div class="rhythm-bars">${bars}</div>
    <div class="rhythm-meta">平均段长 ${avg} 字 · 波动 ${cv.toFixed(2)} · 长段 ${longN} · 短段 ${shortN} · 对话段 ${dialogN}/${paras.length}</div>
    <div class="outline-li"><span class="oi">${cv > 0.75 ? '佳' : '注'}</span><span>${verdict}</span></div>
    <div class="outline-li" data-jpara="${maxI + 1}" style="cursor:pointer;border-bottom:none"><span class="oi">长</span><span>最长第 ${maxI + 1} 段 · ${max} 字（点此定位）</span></div>
    <div class="outline-li" data-jpara="${minI + 1}" style="cursor:pointer;border-bottom:none"><span class="oi">短</span><span>最短第 ${minI + 1} 段 · ${Math.min(...lens)} 字（点此定位）</span></div>
    ${longN ? `<div class="outline-li"><span class="oi">注</span><span>${longN} 段超过 220 字，手机阅读建议拆段</span></div>` : ''}`;
}

/* ---------------- 查找 ---------------- */
/* 段落切分：与后端 _para_split 同规则，带精确字符区间 */
function paraSpans(text) {
  const s = String(text || '');
  const hasBlank = /\n[ \t\r]*\n/.test(s);
  const sep = hasBlank ? /\n[ \t\r]*\n/g : /\n/g;
  const cuts = [];
  let last = 0, m;
  while ((m = sep.exec(s))) {
    cuts.push([last, m.index]);
    last = m.index + m[0].length;
  }
  cuts.push([last, s.length]);
  const out = [];
  cuts.forEach(([a, b]) => {
    let st = a, en = b;
    while (st < en && /\s/.test(s[st])) st++;
    while (en > st && /\s/.test(s[en - 1])) en--;
    if (en > st) out.push({ start: st, end: en, text: s.slice(st, en) });
  });
  return out;
}

/* 用高亮层当尺子，量出某个字符在稿纸里的真实纵坐标（含自动换行） */
function yOfOffset(pos) {
  const el = input();
  const bd = $('#backdrop');
  const wrap = $('#paperWrap');
  if (!el || !bd || !wrap) return null;
  const text = el.value || '';
  const p = Math.max(0, Math.min(text.length, pos));
  const html = bd.innerHTML;
  bd.innerHTML = esc(text.slice(0, p)) + '<span data-mk></span>' + esc(text.slice(p));
  const mk = bd.querySelector('[data-mk]');
  let y = null;
  if (mk) {
    const wr = wrap.getBoundingClientRect();
    const mr = mk.getBoundingClientRect();
    y = wrap.scrollTop + (mr.top - wr.top);
  }
  bd.innerHTML = html;
  return y;
}

function scrollToOffset(pos, smooth) {
  const wrap = $('#paperWrap');
  if (!wrap) return;
  const y = yOfOffset(pos);
  if (y == null) return;
  const top = Math.max(0, y - wrap.clientHeight * 0.36);
  if (smooth === false) wrap.scrollTop = top;
  else wrap.scrollTo({ top, behavior: 'smooth' });
}

let FLASH_T = 0;
function flashRange(start, len) {
  S.flash = { start, len, until: Date.now() + 1600 };
  renderBackdrop();
  clearTimeout(FLASH_T);
  FLASH_T = setTimeout(() => { S.flash = null; renderBackdrop(); }, 1700);
}

/* 跳到正文某段：关掉侧栏抽屉、选中、滚到视野中间、闪一下 */
function jumpToRange(start, end) {
  const el = input();
  if (!el) return;
  closeMobileSheets();
  el.focus();
  el.setSelectionRange(start, end);
  S.cursor = { id: S.chapterId, start: end, end };
  flashRange(start, Math.max(1, Math.min(end - start, 600)));
  requestAnimationFrame(() => scrollToOffset(start));
  setTimeout(() => scrollToOffset(start), 300);
}

function findWordPos(text, word) {
  const p = text.indexOf(word);
  if (p >= 0) return { pos: p, len: word.length };
  const nw = normForScan(word);
  if (!nw) return null;
  let norm = '';
  const map = [];
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (normForScan(ch)) { norm += ch; map.push(i); }
  }
  const idx = norm.indexOf(nw);
  if (idx < 0) return null;
  const start = map[idx];
  const last = map[idx + nw.length - 1];
  return { pos: start, len: (last == null ? start : last) - start + 1 };
}
function jumpToWord(word) {
  if (!word) return;
  const el = input();
  const hit = findWordPos(el.value || '', String(word));
  if (!hit) { toast('正文里没找到「' + word + '」'); return; }
  jumpToRange(hit.pos, hit.pos + hit.len);
}
function openFind() {
  $('#findBar').classList.add('show');
  S.findVisible = true;
  const i = $('#findInput');
  i.focus(); i.select();
}
function closeFind() {
  $('#findBar').classList.remove('show');
  S.findVisible = false;
  S.find = { term: '', hits: [], idx: -1 };
  renderBackdrop();
}
function doFind(term) {
  S.find.term = term;
  S.find.idx = term ? 0 : -1;
  renderBackdrop();
  jumpToFind();
}
function jumpToFind() {
  const hits = S.find.hits;
  if (!hits.length || S.find.idx < 0) return;
  const pos = hits[S.find.idx];
  const el = input();
  el.focus();
  el.setSelectionRange(pos, pos + S.find.term.length);
  scrollToOffset(pos);
}
function scrollCaretToCenter(pos) {
  const el = input();
  const before = el.value.slice(0, pos);
  const lines = before.split('\n').length;
  const lh = parseFloat(getComputedStyle(el).lineHeight) || 26;
  const wrap = $('#paperWrap');
  const paperTop = $('#paperWrap .paper').offsetTop;
  const target = paperTop + 120 + (lines - 1) * lh - wrap.clientHeight / 2;
  wrap.scrollTo({ top: Math.max(0, target), behavior: 'smooth' });
}

/* ---------------- 目录操作 ---------------- */
async function pushFiles(force) {
  if (!S.book) return;
  const url = `/files/${encodeURIComponent(S.book.name)}`;
  try {
    await api(url, { method: 'POST', body: { files: S.files, force: !!force } });
  } catch (e) {
    if (!force && /章节数量|force/.test(e.message || '')) {
      const ok = await askConfirm('章节数量骤减', e.message + ' 确认要覆盖服务器上的目录吗？', '仍然保存');
      if (ok) { await pushFiles(true); return; }
      const fresh = await api(`/projects/${encodeURIComponent(S.book.name)}`);
      S.files = fresh._files || S.files;
      renderToc();
      return;
    }
    throw e;
  }
}

function newId(prefix) {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

async function newVolume() {
  if (!S.book) { openBookModal(); return; }
  const n = volumeFolders().length + 1;
  const name = await askText('新建分卷', '给这一卷起个名字，例如「第二卷 · 山门」', `第${n}卷`);
  if (!name) return;
  const vol = { id: newId('vol_'), parentId: 'root', name, type: 'FOLDER', lastModified: Date.now() };
  S.files.push(vol);
  await pushFiles();
  const map = collapsedMap();
  delete map[vol.id];
  saveCollapsed(map);
  renderToc();
  toast('分卷已建立');
}

async function renameVolume(id) {
  const v = fileById(id);
  if (!v) return;
  const name = await askText('重命名分卷', '', v.name);
  if (!name || name === v.name) return;
  v.name = name;
  await pushFiles();
  renderToc();
  updateEditorChrome();
  toast('已改名');
}

async function deleteVolume(id) {
  const v = fileById(id);
  if (!v) return;
  const kids = childFolders(id);
  const list = [...filesInFolder(id)];
  kids.forEach((k) => list.push(...filesInFolder(k.id)));
  const ok = await askConfirm('删除分卷', `「${v.name}」中的 ${list.length} 章会一起移入回收站，可以再恢复。`, '删除');
  if (!ok) return;
  const trash = store.json(KEY.trash(S.book.name), []);
  list.forEach((f) => trash.unshift({ t: Date.now(), file: f }));
  store.setJson(KEY.trash(S.book.name), trash.slice(0, 200));
  const dropIds = new Set([id, ...kids.map((k) => k.id)]);
  S.files = S.files.filter((f) => !dropIds.has(f.id) && !dropIds.has(f.parentId));
  await pushFiles();
  if (list.some((f) => f.id === S.chapterId)) { S.chapterId = null; updateEditorChrome(); }
  renderToc(); renderTrashCount();
  toast('分卷已删除');
}

function volumeMenu(id, anchor) {
  const v = fileById(id);
  if (!v) return;
  showMenu(anchor, [
    { label: '重命名分卷', icon: '编', action: () => renameVolume(id) },
    { label: '在此新建章节', icon: '＋', action: () => newChapter(id) },
    { label: '导出本卷', icon: '存', action: () => exportVolume(id) },
    { sep: true },
    { label: '删除分卷', icon: '删', danger: true, action: () => deleteVolume(id) },
  ]);
}

function chapterMenu(id, anchor) {
  const f = fileById(id);
  if (!f) return;
  const vols = volumeFolders();
  const items = [
    { label: '重命名', icon: '编', action: () => renameChapter(id) },
    { label: '创建副本', icon: '复', action: () => duplicateChapter(id) },
    { label: '导出本章', icon: '存', action: () => exportChapter(id) },
  ];
  if (vols.length > 1) {
    items.push({ sep: true });
    vols.forEach((v) => {
      if (v.id === f.parentId) return;
      items.push({
        label: `移到「${v.name}」`,
        icon: '移',
        action: async () => {
          f.parentId = v.id;
          await pushFiles();
          renderToc();
          toast('已移动');
        },
      });
    });
  }
  items.push({ sep: true });
  items.push({ label: '移到回收站', icon: '删', danger: true, action: () => deleteChapter(id) });
  showMenu(anchor, items);
}

async function duplicateChapter(id) {
  const f = fileById(id);
  if (!f) return;
  const copy = {
    ...JSON.parse(JSON.stringify(f)),
    id: newId('ch_'),
    name: f.name.replace(/(（副本\d*）)$/, '') + '（副本）',
    lastModified: Date.now(),
  };
  const idx = S.files.findIndex((x) => x.id === id);
  S.files.splice(idx + 1, 0, copy);
  await pushFiles();
  renderToc();
  toast('已创建副本');
}

async function newChapter(volId) {
  if (!S.book) { openBookModal(); return; }
  let vol = volId || (volumeFolders()[0] && volumeFolders()[0].id);
  if (!vol) {
    const folder = { id: newId('vol_'), parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() };
    S.files.push(folder);
    vol = folder.id;
  }
  const n = S.files.filter((f) => f.type === 'FILE' && f.parentId === vol).length + 1;
  const file = {
    id: newId('ch_'), parentId: vol, name: `第${n}章`, type: 'FILE',
    content: '', lastModified: Date.now(), metadata: {},
  };
  S.files.push(file);
  await pushFiles();
  renderToc();
  await openChapter(file.id);
  $('#chTitle').focus();
  $('#chTitle').select();
}

async function openChapter(id) {
  if (S.chapterId === id) return;
  if (S.lock.on && S.chapterId) {
    const left = Math.max(0, S.lock.goal - (wordCount(currentFile() && currentFile().content) - S.lock.startWords));
    if (left > 0 && !await askConfirm('码字锁还差 ' + left + ' 字', '现在换章会打断节奏，确定要换吗？', '换章')) return;
  }
  await saveNow(true);
  S.chapterId = id;
  const f = fileById(id);
  if (f) store.set(KEY.lastBook + ':chapter', f.id);
  renderToc();
  updateEditorChrome();
  loadChapterNotes(f);
  $('#edEmpty').classList.toggle('show', !(f && (f.content || '').trim()));
  $('#paperWrap').scrollTop = 0;
  $('#left').classList.remove('mobile-open');
  if (!$('#phoneDrawer').classList.contains('show')) $('#drawerMask').classList.remove('show');
  setSave('idle', '已同步');
  S.cursor = { id: f ? f.id : '', start: 0, end: 0 };
  if (typeof updateChatCtx === 'function') updateChatCtx();
  if (typeof updateMobileTitle === 'function') { updateMobileTitle(); setMobileTab('write'); }
}

async function renameChapter(id) {
  const f = fileById(id);
  if (!f) return;
  const name = await askText('重命名章节', '', f.name);
  if (!name || name === f.name) return;
  f.name = name;
  f.lastModified = Date.now();
  await saveNow(true);
  renderToc();
  if (id === S.chapterId) updateEditorChrome();
  toast('已改名');
}

async function deleteChapter(id) {
  const f = fileById(id);
  if (!f) return;
  const ok = await askConfirm('移到回收站', `「${f.name}」会放进回收站，随时可以恢复。`, '移到回收站');
  if (!ok) return;
  const trash = store.json(KEY.trash(S.book.name), []);
  trash.unshift({ t: Date.now(), file: f });
  store.setJson(KEY.trash(S.book.name), trash.slice(0, 200));
  S.files = S.files.filter((x) => x.id !== id);
  await pushFiles();
  if (S.chapterId === id) { S.chapterId = null; updateEditorChrome(); }
  renderToc(); renderTrashCount();
  toast('已移到回收站');
}

async function restoreFromTrash(idx) {
  const trash = store.json(KEY.trash(S.book.name), []);
  const item = trash[idx];
  if (!item) return;
  trash.splice(idx, 1);
  store.setJson(KEY.trash(S.book.name), trash);
  if (!fileById(item.file.parentId)) {
    let vol = volumeFolders()[0];
    if (!vol) {
      vol = { id: newId('vol_'), parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() };
      S.files.push(vol);
    }
    item.file.parentId = vol.id;
  }
  S.files.push(item.file);
  await pushFiles();
  renderToc(); renderTrashCount(); renderTrashList();
  toast('已恢复');
}

async function purgeTrash(idx) {
  const trash = store.json(KEY.trash(S.book.name), []);
  const item = trash[idx];
  if (!item) return;
  const ok = await askConfirm('彻底删除', `「${item.file.name}」将被永久删除，无法恢复。`, '永久删除');
  if (!ok) return;
  trash.splice(idx, 1);
  store.setJson(KEY.trash(S.book.name), trash);
  renderTrashCount(); renderTrashList();
  toast('已彻底删除');
}

async function clearTrash() {
  const list = store.json(KEY.trash(S.book ? S.book.name : '_'), []);
  if (!list.length) { toast('回收站是空的'); return; }
  const ok = await askConfirm('清空回收站', `${list.length} 项会被永久删除，无法恢复。`, '清空');
  if (!ok) return;
  store.setJson(KEY.trash(S.book ? S.book.name : '_'), []);
  renderTrashCount(); renderTrashList();
  toast('回收站已清空');
}

function renderTrashCount() {
  const n = (store.json(KEY.trash(S.book ? S.book.name : '_'), []) || []).length;
  $('#trashCnt').textContent = n;
}

/* ---------------- 目录拖拽排序 ---------------- */
const drag = { id: null, overEl: null };
function clearDropMarks() {
  $$('.ch-item').forEach((el) => el.classList.remove('drop-before', 'drop-after'));
  $$('.vol').forEach((el) => el.classList.remove('drop-into'));
}
function bindDrag() {
  const tree = $('#tocTree');
  tree.addEventListener('dragstart', (e) => {
    const item = e.target.closest('.ch-item');
    if (!item) return;
    drag.id = item.dataset.id;
    item.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    try { e.dataTransfer.setData('text/plain', drag.id); } catch {}
  });
  tree.addEventListener('dragend', () => {
    drag.id = null;
    $$('.ch-item').forEach((el) => el.classList.remove('dragging'));
    clearDropMarks();
  });
  tree.addEventListener('dragover', (e) => {
    if (!drag.id) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    clearDropMarks();
    const item = e.target.closest('.ch-item');
    if (item) {
      const r = item.getBoundingClientRect();
      item.classList.add(e.clientY < r.top + r.height / 2 ? 'drop-before' : 'drop-after');
      return;
    }
    const vol = e.target.closest('.vol');
    if (vol) vol.classList.add('drop-into');
  });
  tree.addEventListener('drop', async (e) => {
    if (!drag.id) return;
    e.preventDefault();
    const source = fileById(drag.id);
    if (!source) return;
    const item = e.target.closest('.ch-item');
    const volEl = e.target.closest('.vol');
    let targetVol = volEl ? volEl.dataset.vol : null;
    let index = -1;
    if (item) {
      const target = fileById(item.dataset.id);
      if (!target || target.id === source.id) { clearDropMarks(); return; }
      targetVol = target.parentId;
      const r = item.getBoundingClientRect();
      const after = e.clientY >= r.top + r.height / 2;
      index = S.files.findIndex((x) => x.id === target.id) + (after ? 1 : 0);
    }
    if (!targetVol) { clearDropMarks(); return; }
    const from = S.files.findIndex((x) => x.id === source.id);
    S.files.splice(from, 1);
    source.parentId = targetVol;
    if (index < 0) {
      const sameVol = S.files.filter((x) => x.type === 'FILE' && x.parentId === targetVol);
      const last = sameVol[sameVol.length - 1];
      index = last ? S.files.findIndex((x) => x.id === last.id) + 1 : S.files.length;
    } else if (index > from) {
      index -= 1;
    }
    S.files.splice(index, 0, source);
    clearDropMarks();
    await pushFiles();
    renderToc();
    toast('已调整顺序');
  });
}

/* ---------------- 便签 / 设定 ---------------- */
function loadChapterNotes(f) {
  const scratch = store.get(KEY.scratch(S.book ? S.book.name : '_'), '');
  $('#scratchNote').value = scratch || '';
  autoGrow($('#scratchNote'), 260);
  const outline = (f && f.metadata && f.metadata.outline) || '';
  $('#outlineNote').value = outline;
  autoGrow($('#outlineNote'), 260);
  renderForeshadow();
}

function foreshadowItems() {
  if (!S.book) return [];
  if (!S.book.outline || typeof S.book.outline !== 'object') S.book.outline = {};
  if (!Array.isArray(S.book.outline.foreshadows)) S.book.outline.foreshadows = [];
  return S.book.outline.foreshadows;
}

async function saveForeshadows() {
  if (!S.book) return;
  await saveProjectFields({ outline: S.book.outline || {} });
  renderForeshadow();
}

function renderForeshadow() {
  if (!S.book) {
    $('#foreshadowList').innerHTML = '<div class="outline-li"><span class="oi">空</span><span>还没有伏笔记录</span></div>';
    $('#foreshadowSub').textContent = '0 待回收';
    return;
  }
  /* 把旧版本存在本地的伏笔并进项目，之后两边共用一份 */
  const migKey = KEY.foreshadow(S.book.name) + ':migrated';
  if (!store.get(migKey)) {
    const legacy = store.json(KEY.foreshadow(S.book.name), []);
    const items = foreshadowItems();
    if (Array.isArray(legacy) && legacy.length) {
      legacy.forEach((it) => { if (it && it.text) items.push({ text: String(it.text), done: !!it.done }); });
      saveProjectFields({ outline: S.book.outline || {} });
    }
    store.set(migKey, '1');
  }
  const list = foreshadowItems();
  $('#foreshadowList').innerHTML = list.length ? list.map((it, i) => `<div class="check-li${it.done ? ' done' : ''}" style="display:flex;gap:8px;align-items:flex-start">
      <input type="checkbox" data-fs="${i}" ${it.done ? 'checked' : ''}>
      <span data-fs-edit="${i}" title="点击编辑（支持换行）" style="flex:1;white-space:pre-wrap;cursor:pointer">${esc(it.text)}</span>
      <button class="icon-btn" data-fs-del="${i}" title="删除"><svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
    </div>`).join('') : '<div class="outline-li"><span class="oi">空</span><span>还没有伏笔记录</span></div>';
  $('#foreshadowSub').textContent = `${list.filter((x) => !x.done).length} 待回收`;
}

function charMeta(c) {
  if (typeof c === 'string') return { name: c, role: '', purpose: [], desc: '' };
  const raw = (c && (c.purpose || c['用途'])) || [];
  const purpose = Array.isArray(raw) ? raw : String(raw).split(/[、,，;；\s]+/).filter(Boolean);
  return {
    name: String((c && (c.name || c['姓名'])) || ''),
    role: String((c && (c.role || c['定位'])) || ''),
    purpose,
    desc: String((c && (c.desc || c.description || c.profile)) || ''),
  };
}

function charList() {
  const chars = (S.book && S.book.characters) || {};
  const out = [];
  ['主角', '配角', '反派'].forEach((group) => {
    (Array.isArray(chars[group]) ? chars[group] : []).forEach((c, i) => {
      const m = charMeta(c);
      if (!m.name) return;
      out.push(Object.assign({ group, index: i }, m));
    });
  });
  Object.entries(chars).forEach(([group, arr]) => {
    if (['主角', '配角', '反派'].includes(group) || !Array.isArray(arr)) return;
    arr.forEach((c, i) => {
      const m = charMeta(c);
      if (m.name) out.push(Object.assign({ group, index: i }, m));
    });
  });
  return out;
}

function renderWorld() {
  const box = $('#worldList');
  if (!S.book) {
    box.innerHTML = '<div class="outline-li"><span class="oi">—</span><span>先选一本书</span></div>';
    $('#worldText').value = '';
    $('#conceptBox').textContent = '尚未生成核心概念';
    return;
  }
  const items = charList();
  box.innerHTML = items.length ? items.map((it, n) => {
    const sub = [it.group, it.role, it.purpose.slice(0, 2).join(' / ')].filter(Boolean).join(' · ');
    return `<div class="setting-item">
      <span class="s-badge person">${esc(it.name.slice(0, 1))}</span>
      <span class="si" data-char-open="${n}" style="cursor:pointer" title="打开角色档案（介绍 / 关系图 / 出场章节）"><b>${esc(it.name)}</b><span>${esc(sub || it.desc || it.group)}</span></span>
      <button class="mini-btn" data-insert="${esc(it.name)}">插入</button>
      <button class="icon-btn" data-char-del="${n}" title="删除"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg></button>
    </div>`;
  }).join('')
    : '<div class="outline-li"><span class="oi">空</span><span>还没有人物，点右上「＋人物」加一个。</span></div>';

  const world = S.book.world || {};
  const text = typeof world === 'string' ? world : (world.content || world.macro || '');
  $('#worldText').value = text;
  autoGrow($('#worldText'), 260);

  const concept = S.book.concept || {};
  const parts = [
    concept.core && `核心故事：${concept.core}`,
    concept.theme && `主题内核：${concept.theme}`,
    concept.positioning && `市场定位：${concept.positioning}`,
  ].filter(Boolean);
  $('#conceptBox').textContent = parts.join('\n\n') || '尚未生成核心概念';
  $('#conceptSub').textContent = parts.length ? '已保存' : '项目设定';
}

function textSig(t) {
  const s = String(t || '');
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return s.length + ':' + h;
}

/* 正文里出现的新人物，自动补进人物表（设定面板与搭子共用同一份） */
let charScanBusy = false;
async function scanChapterCharacters(force) {
  const f = currentFile();
  if (!f || !S.book || charScanBusy) return;
  const text = f.content || '';
  const plain = text.replace(/\s/g, '');
  if (plain.length < 60) return;
  const key = 'fj:charScan:' + f.id;
  const last = store.json(key, null) || {};
  const sig = textSig(text);
  const now = Date.now();
  if (!force) {
    if (last.sig === sig) return;
    if (last.ts && now - last.ts < 90000) return;
    if (last.len && plain.length - last.len < 150) return;
  }
  store.setJson(key, { sig, len: plain.length, ts: now });
  charScanBusy = true;
  try {
    const r = await api(`/projects/${encodeURIComponent(S.book.name)}/ai-scan-characters`, {
      method: 'POST',
      body: { text: text.slice(0, 12000), chapter_id: f.id },
    });
    if (r && ((r.added && r.added.length) || (r.enriched && r.enriched.length))) {
      S.book.characters = r.characters || S.book.characters;
      renderWorld();
      const studio = $('#studio');
      if (studio && !studio.hidden && window.Studio) {
        const on = document.querySelector('.studio-nav button.on');
        if (on && on.dataset.mod === 'characters') window.Studio.setModule('characters');
      }
      const bits = [];
      if (r.added && r.added.length) bits.push('新人物：' + r.added.join('、'));
      if (r.enriched && r.enriched.length) bits.push('补全档案：' + r.enriched.join('、'));
      toast(bits.join('；'));
    }
  } catch (e) { /* 静默失败，不打断写作 */ }
  charScanBusy = false;
}

async function saveProjectFields(patch) {
  if (!S.book) return;
  Object.assign(S.book, patch);
  try {
    await api(`/projects/${encodeURIComponent(S.book.name)}`, { method: 'PUT', body: patch });
  } catch (e) { toast('保存失败：' + e.message); }
}

function deepSetPath(obj, parts, value) {
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const k = parts[i];
    if (cur[k] == null || typeof cur[k] !== 'object') cur[k] = {};
    cur = cur[k];
  }
  cur[parts[parts.length - 1]] = value;
}

function getPath(obj, parts) {
  let cur = obj;
  for (const p of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = cur[p];
  }
  return cur;
}

/* 撤回提问时，把这条问答复产生的改动一并退回去：融入的正文、搭子改过的设置 */
async function undoChatEffects(msgs) {
  if (!S.book || !Array.isArray(msgs)) return null;
  const items = [];
  msgs.forEach((m) => { if (m && Array.isArray(m.undo)) items.push(...m.undo); });
  if (!items.length) return null;
  let chapterN = 0, projectN = 0, skipped = 0;
  const tops = new Set();
  for (let idx = items.length - 1; idx >= 0; idx--) {
    const u = items[idx];
    if (!u) continue;
    if (u.t === 'chapter') {
      const f = fileById(u.id);
      if (!f || String(f.content || '') !== String(u.after || '')) { skipped++; continue; }
      f.content = String(u.before || '');
      try {
        await api(`/files/${encodeURIComponent(S.book.name)}/${encodeURIComponent(f.id)}`, {
          method: 'PUT', body: { content: f.content, name: f.name, metadata: f.metadata || {} },
        });
        chapterN++;
      } catch (e) { skipped++; }
      if (S.chapterId === f.id) { updateEditorChrome(); renderToc(); }
    } else if (u.t === 'project') {
      const parts = String(u.path || '').split('.').filter(Boolean);
      if (!parts.length) continue;
      const cur = getPath(S.book, parts);
      if (JSON.stringify(cur) !== JSON.stringify(u.after)) { skipped++; continue; }
      deepSetPath(S.book, parts, u.before);
      tops.add(parts[0]);
      projectN++;
    }
  }
  for (const top of tops) {
    try {
      await api(`/projects/${encodeURIComponent(S.book.name)}`, { method: 'PUT', body: { [top]: S.book[top] } });
    } catch (e) { /* 单个字段失败不影响其它 */ }
  }
  if (projectN) { renderWorld(); renderBookHead(); }
  if (chapterN) { renderToc(); updateStats(); }
  return { chapterN, projectN, skipped };
}

/* 搭子已经在后端改了项目数据，这里把本地这份同步过来并刷新界面 */
async function applyProjectUpdates(updates) {
  if (!S.book || !Array.isArray(updates) || !updates.length) return;
  const tops = new Set(updates.map((u) => String(u.path || '').split('.')[0]).filter(Boolean));
  try {
    const fresh = await api(`/projects/${encodeURIComponent(S.book.name)}`);
    tops.forEach((k) => { if (fresh[k] !== undefined) S.book[k] = fresh[k]; });
  } catch (e) {
    updates.forEach((u) => {
      const parts = String(u.path || '').split('.').filter(Boolean);
      if (parts.length) deepSetPath(S.book, parts, u.value);
    });
  }
  renderBookHead();
  renderWorld();
  const studio = $('#studio');
  if (studio && !studio.hidden && window.Studio) {
    const on = document.querySelector('.studio-nav button.on');
    window.Studio.setModule(on ? on.dataset.mod : 'project');
  }
}

function resetCharForm() {
  ['charName', 'charAlias', 'charRole', 'charDesc', 'charTagline', 'charIntro'].forEach((id) => {
    const el = $('#' + id);
    if (el) el.value = '';
  });
  $$('#charPurpose .ch-chip').forEach((b) => b.classList.remove('on'));
  $$('#charGroup button').forEach((b) => b.classList.toggle('on', b.dataset.group === '主角'));
}

async function addCharacter() {
  if (!S.book) { toast('先选一本书'); return; }
  const name = $('#charName').value.trim();
  if (!name) { toast('姓名不能为空'); return; }
  const group = ($('#charGroup .on') && $('#charGroup .on').dataset.group) || '主角';
  const chars = S.book.characters || {};
  if (!Array.isArray(chars[group])) chars[group] = [];
  if (chars[group].some((c) => (typeof c === 'string' ? c : c && c.name) === name)) {
    toast('「' + group + '」里已有同名人物');
    return;
  }
  const alias = $('#charAlias').value.trim();
  const role = $('#charRole').value.trim();
  const identity = $('#charDesc').value.trim();
  const tagline = $('#charTagline').value.trim();
  const intro = $('#charIntro').value.trim();
  const purpose = $$('#charPurpose .ch-chip.on').map((b) => b.dataset.p);
  chars[group].push({
    name,
    aliases: alias.split(/[、,，;；\s]+/).filter(Boolean),
    role,
    identity,
    tagline,
    intro,
    purpose,
    desc: tagline || identity || role,
    relations: [],
  });
  await saveProjectFields({ characters: chars });
  closeModal($('#charModal'));
  resetCharForm();
  renderWorld();
  toast('人物已添加，可到工坊「人物」补关系图');
}

async function deleteCharacter(n) {
  const it = charList()[n];
  if (!it) return;
  const chars = S.book.characters || {};
  if (!Array.isArray(chars[it.group])) return;
  chars[it.group].splice(it.index, 1);
  await saveProjectFields({ characters: chars });
  renderWorld();
  toast('已删除');
}

async function saveWorldText() {
  if (!S.book) return;
  const text = $('#worldText').value;
  const world = (typeof S.book.world === 'object' && S.book.world) ? { ...S.book.world, content: text } : { content: text };
  await saveProjectFields({ world });
  toast('世界观已保存');
}


/* ---------------- 插入文本 ---------------- */
function chatChapterByName(name) {
  const s = String(name || '').trim();
  if (!s) return null;
  const list = S.files.filter((x) => x.type === 'FILE');
  return list.find((x) => x.name === s)
    || list.find((x) => x.name.includes(s))
    || list.find((x) => s.includes(x.name))
    || null;
}

/* 先确定这条回复改的是哪一章：搭子标了章就照它，其次按后端的内容比对，拿不准就让用户选 */
async function resolveApplyChapter(msg) {
  const chapters = S.files.filter((x) => x.type === 'FILE');
  if (!chapters.length) return null;
  const act = (msg.actions || []).find((a) => String(a.do || a.type || '').toLowerCase() === 'apply');
  if (act) {
    const hit = chatChapterByName(act.chapter || act.title);
    if (hit) return hit;
  }
  const t = msg.target || null;
  if (t && t.confident) {
    const hit = fileById(t.id);
    if (hit) return hit;
  }
  const guess = t && t.id ? fileById(t.id) : null;
  const hint = (t && t.name)
    ? `从对话看像是「${t.name}」${t.reason ? '（' + t.reason + '）' : ''}，不对就换一章。`
    : '这条回复没写明是哪一章，选一章再融。';
  const pick = await askPick('融入正文', hint,
    chapters.map((f) => ({ id: f.id, label: f.name, note: (wordCount(f.content) || 0) + ' 字' })),
    guess ? guess.id : (S.chapterId || ''));
  return pick ? fileById(pick) : null;
}

async function applyChatToText(btn, msg) {
  if (!S.book) { toast('先打开一本书'); return; }
  const label = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '定位章节…'; }
  try {
    const target = await resolveApplyChapter(msg);
    if (!target) return;
    if (target.id !== S.chapterId) {
      await openChapter(target.id);
      toast('已切到「' + target.name + '」');
    }
    const f = currentFile();
    if (!f) { toast('先选一个章节'); return; }
    if (!(f.content || '').trim()) { toast('「' + f.name + '」还没有正文，没法融合'); return; }
    const el = input();
    const beforeContent = f.content || '';
    /* 只有回复是在这一章问的，才沿用当时的光标与选中段 */
    const sameCh = !!(msg.ch && msg.ch === f.id);
    const cur = sameCh
      ? ((msg.cur && msg.cur.id === f.id) ? msg.cur.start
        : ((S.cursor && S.cursor.id === f.id) ? S.cursor.start : 0))
      : 0;
    if (btn) btn.textContent = '融合中…';
    const r = await api('/ai/apply', {
      method: 'POST',
      body: {
        project_name: S.book ? S.book.name : '',
        chapter_id: f.id,
        text: f.content || '',
        reply: msg.text || '',
        selection: sameCh ? (msg.sel || '') : '',
        cursor: cur,
      },
    });
    if (!r.changed) { toast('内容与正文一致，没有改动'); return; }
    takeSnapshot(true);
    histCommit();
    el.value = r.text;
    f.content = r.text;
    onEditorInput();
    histCommit();
    renderBackdrop();
    const a = Math.max(0, Math.min(Number(r.pos) || 0, el.value.length));
    const b = Math.min(el.value.length, a + (Number(r.length) || 0));
    el.focus();
    el.setSelectionRange(a, b);
    S.cursor = { id: f.id, start: b, end: b };
    const wrap = $('#paperWrap');
    if (wrap && el.value.length) {
      wrap.scrollTop = Math.max(0, (a / el.value.length) * wrap.scrollHeight - wrap.clientHeight / 2);
    }
    toast('已' + (r.mode || '写入') + '「' + f.name + '」');
    /* 记下这次融入，撤回提问时按 before 退回去 */
    if (beforeContent.length <= 60000 && String(r.text || '').length <= 60000) {
      if (!Array.isArray(msg.undo)) msg.undo = [];
      msg.undo.push({ t: 'chapter', id: f.id, before: beforeContent, after: r.text });
      saveConvs();
    }
  } catch (e) {
    toast('融入正文失败：' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = label; }
  }
}

/* ---------------- 搭子直接改正文：像真人一样在编辑框里逐字敲 ---------------- */
let editAnim = null;
let _editRefreshAt = 0;

document.addEventListener('pointerdown', () => { if (editAnim) editAnim.fast = true; }, true);
document.addEventListener('keydown', () => { if (editAnim) editAnim.fast = true; }, true);

function editSleep(ms) { return new Promise((r) => setTimeout(r, Math.max(0, ms))); }
function setCaret(el, pos) { try { el.setSelectionRange(pos, pos); } catch (e) {} }

function editRefresh(el, pos) {
  const now = Date.now();
  if (now - _editRefreshAt < 150) return;
  _editRefreshAt = now;
  try { renderBackdrop(); } catch (e) {}
  try { scrollToOffset(pos, false); } catch (e) {}
}

function editDelay(chunk, per) {
  let d = 13 + Math.random() * 18;
  if (per === 1) d *= 1.35;
  const last = chunk.slice(-1);
  if ('，。！？；：、'.includes(last)) d += 70 + Math.random() * 120;
  else if (last === '\n') d += 120;
  else if (',.!?;:'.includes(last)) d += 40;
  return d;
}

async function typeIntoEditor(el, pos, text) {
  const total = text.length;
  const per = total > 1500 ? 10 : total > 400 ? 3 : total > 80 ? 2 : 1;
  let i = 0;
  while (i < total) {
    if (editAnim && editAnim.fast) {
      const rest = text.slice(i);
      el.value = el.value.slice(0, pos) + rest + el.value.slice(pos);
      pos += rest.length;
      setCaret(el, pos);
      editRefresh(el, pos);
      break;
    }
    const chunk = text.slice(i, i + per);
    i += chunk.length;
    el.value = el.value.slice(0, pos) + chunk + el.value.slice(pos);
    pos += chunk.length;
    setCaret(el, pos);
    if (per > 1 || Math.random() < 0.8) sfxOn();
    if (i % 24 === 0) editRefresh(el, pos);
    await editSleep(editDelay(chunk, per));
  }
  return pos;
}

async function eraseInEditor(el, start, end) {
  const tail = el.value.slice(end);
  const span = end - start;
  const step = span > 120 ? 3 : span > 30 ? 2 : 1;
  let e = end;
  while (e > start) {
    if (editAnim && editAnim.fast) {
      el.value = el.value.slice(0, start) + tail;
      setCaret(el, start);
      editRefresh(el, start);
      return start;
    }
    e = Math.max(start, e - step);
    el.value = el.value.slice(0, e) + tail;
    setCaret(el, e);
    sfxOn();
    if (e % 40 === 0) editRefresh(el, e);
    await editSleep(9 + Math.random() * 13);
  }
  return start;
}

/* 演一条动作：返回 {pos,len}，没对上原文返回 null */
async function playEditOp(el, op) {
  const kind = String(op.op || 'replace').toLowerCase();
  const find = String(op.find || '');
  const withText = String(op.with || '');
  if (kind === 'append') {
    const cut = el.value.replace(/\s+$/, '').length;
    let prefix = '';
    if (cut > 0 && !el.value.slice(0, cut).endsWith('\n')) prefix = '\n\n';
    const pos = cut + prefix.length;
    el.value = el.value.slice(0, cut) + prefix + el.value.slice(cut);
    setCaret(el, pos);
    editRefresh(el, pos);
    await editSleep(180);
    const end = await typeIntoEditor(el, pos, withText);
    return { pos, len: end - pos };
  }
  if (kind === 'rewrite') {
    /* 整章重写：只重演不一样的那一段，别把整章从头敲一遍 */
    const old = el.value;
    let a = 0;
    let b = 0;
    while (a < old.length && a < withText.length && old[a] === withText[a]) a++;
    while (b < old.length - a && b < withText.length - a
           && old[old.length - 1 - b] === withText[withText.length - 1 - b]) b++;
    const oldMid = old.slice(a, old.length - b);
    const newMid = withText.slice(a, withText.length - b);
    if (!oldMid && !newMid) return null;
    if (!oldMid) {
      const end = await typeIntoEditor(el, a, newMid);
      return { pos: a, len: end - a };
    }
    return playEditOp(el, { op: 'replace', find: oldMid, with: newMid });
  }
  if (!find) return null;
  const at = el.value.indexOf(find);
  if (at < 0) return null;
  if (kind === 'delete' || (!withText && (kind === 'replace' || kind === 'change'))) {
    el.setSelectionRange(at, at + find.length);
    await editSleep(140);
    await eraseInEditor(el, at, at + find.length);
    return { pos: at, len: 0 };
  }
  if (kind === 'insert') {
    const pos = String(op.where || '').toLowerCase() === 'before' ? at : at + find.length;
    setCaret(el, pos);
    editRefresh(el, pos);
    await editSleep(110);
    const end = await typeIntoEditor(el, pos, withText);
    return { pos, len: end - pos };
  }
  el.setSelectionRange(at, at + find.length);
  await editSleep(140);
  const pos = await eraseInEditor(el, at, at + find.length);
  if (!withText) return { pos, len: 0 };
  await editSleep(70);
  const end = await typeIntoEditor(el, pos, withText);
  return { pos, len: end - pos };
}

async function runChapterEdits(msg, r) {
  const ops = Array.isArray(r && r.edits) ? r.edits : [];
  if (!ops.length || editAnim) return;
  const tgt = (r && r.edit_chapter) || {};
  let f = tgt.id ? fileById(tgt.id) : currentFile();
  if (!f) { toast('要改的那章不在了'); return; }
  chatNav('writer');
  if (f.id !== S.chapterId) {
    if (S.lock && S.lock.on) { toast('码字锁开着，先没切章改'); return; }
    try { await openChapter(f.id); } catch (e) {}
    f = currentFile();
  }
  const el = input();
  if (!el || !f) { toast('正文没打开，这次没动'); return; }

  editAnim = { fast: false };
  const before = el.value;
  const wasRO = el.readOnly;
  el.readOnly = true;
  const touch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches;
  if (!touch) { try { el.focus({ preventScroll: true }); } catch (e) {} }
  takeSnapshot(true);
  histCommit();
  const bands = [];
  try {
    for (const op of ops) {
      const res = await playEditOp(el, op);
      if (res) bands.push(res);
      await editSleep(200);
    }
    renderBackdrop();
  } catch (e) {
    console.warn('搭子改正文出错', e);
  } finally {
    el.readOnly = wasRO;
    editAnim = null;
  }

  const after = el.value;
  if (after === before) {
    renderBackdrop();
    toast('这次没对上原文，正文没动');
    return;
  }
  f.content = after;
  lastLen = after.length;
  onEditorInput();
  histCommit();
  S.cursor = { id: f.id, start: el.selectionEnd || 0, end: el.selectionEnd || 0 };
  if (msg && before.length <= 60000 && after.length <= 60000) {
    if (!Array.isArray(msg.undo)) msg.undo = [];
    msg.undo.push({ t: 'chapter', id: f.id, before, after });
    saveConvs();
  }
  if (bands.length) {
    const last = bands[bands.length - 1];
    flashRange(Math.max(0, last.pos), Math.max(1, Math.min(last.len || 1, 900)));
    scrollToOffset(Math.max(0, last.pos - 80), false);
  }
  const miss = ops.length - bands.length;
  toast('搭子改好 ' + bands.length + ' 处' + (miss > 0 ? '，' + miss + ' 处没对上原文' : ''));
}

function insertAtCursor(text) {
  const el = input();
  const f = currentFile();
  if (!f) { toast('先选一个章节'); return; }
  /* 焦点不在正文时（比如在聊天框点“用到正文”），回到上次记住的光标位置 */
  const focused = document.activeElement === el;
  let start = el.selectionStart || 0;
  let end = el.selectionEnd || 0;
  if (!focused && S.cursor && S.cursor.id === f.id) {
    start = S.cursor.start;
    end = S.cursor.end;
  }
  start = Math.max(0, Math.min(start, el.value.length));
  end = Math.max(start, Math.min(end, el.value.length));
  const before = el.value.slice(0, start);
  const after = el.value.slice(end);
  histCommit();
  el.value = before + text + after;
  f.content = el.value;
  const pos = start + text.length;
  el.focus();
  el.setSelectionRange(pos, pos);
  S.cursor = { id: f.id, start: pos, end: pos };
  onEditorInput();
  histCommit();
  renderBackdrop();
  /* 滚到插入点 */
  const wrap = $('#paperWrap');
  if (wrap) {
    const ratio = el.value.length ? pos / el.value.length : 1;
    wrap.scrollTop = Math.max(0, ratio * wrap.scrollHeight - wrap.clientHeight / 2);
  }
}

/* ---------------- 撤销 / 重做（自建历史，接管 Ctrl+Z / Ctrl+Y） ---------------- */
const HIST = { stack: [], idx: -1, timer: null, applying: false, chapterId: null, limit: 150 };

function histReset() {
  const el = input();
  HIST.stack = el ? [{ text: el.value, start: el.selectionStart || 0, end: el.selectionEnd || 0 }] : [];
  HIST.idx = HIST.stack.length - 1;
  HIST.chapterId = S.chapterId;
  if (HIST.timer) { clearTimeout(HIST.timer); HIST.timer = null; }
}

function histCommit() {
  const el = input();
  if (!el || HIST.applying) return;
  if (HIST.chapterId !== S.chapterId || !HIST.stack.length) { histReset(); return; }
  const text = el.value;
  const cur = HIST.stack[HIST.idx];
  if (cur && cur.text === text) return;
  HIST.stack = HIST.stack.slice(0, HIST.idx + 1);
  HIST.stack.push({ text, start: el.selectionStart || 0, end: el.selectionEnd || 0 });
  if (HIST.stack.length > HIST.limit) HIST.stack.shift();
  HIST.idx = HIST.stack.length - 1;
}

function histSchedule() {
  if (HIST.applying) return;
  if (HIST.timer) clearTimeout(HIST.timer);
  HIST.timer = setTimeout(() => { HIST.timer = null; histCommit(); }, 450);
}

function histApply(entry) {
  const el = input();
  const f = currentFile();
  if (!el || !f || !entry) return;
  HIST.applying = true;
  el.value = entry.text;
  f.content = entry.text;
  lastLen = entry.text.length;   /* 撤销/重做不计入今日码字 */
  onEditorInput();
  const pos = Math.min(entry.end == null ? entry.text.length : entry.end, el.value.length);
  el.focus();
  el.setSelectionRange(pos, pos);
  S.cursor = { id: f.id, start: pos, end: pos };
  HIST.applying = false;
  const wrap = $('#paperWrap');
  if (wrap && el.value.length) {
    wrap.scrollTop = Math.max(0, (pos / el.value.length) * wrap.scrollHeight - wrap.clientHeight / 2);
  }
}

function histUndo() {
  if (HIST.timer) { clearTimeout(HIST.timer); HIST.timer = null; histCommit(); }
  if (HIST.idx <= 0) { toast('没有可撤销的修改了'); return; }
  HIST.idx -= 1;
  histApply(HIST.stack[HIST.idx]);
  toast('已撤销');
}

function histRedo() {
  if (HIST.idx >= HIST.stack.length - 1) { toast('没有可重做的修改'); return; }
  HIST.idx += 1;
  histApply(HIST.stack[HIST.idx]);
  toast('已重做');
}

/* ---------------- 编辑器事件 ---------------- */
let lastLen = 0;
function onEditorInput(e) {
  const f = currentFile();
  if (!f) return;
  const el = input();
  f.content = el.value;
  $('#edEmpty').classList.toggle('show', !el.value.trim());
  const delta = el.value.length - lastLen;
  lastLen = el.value.length;
  const typed = typedCharsFromEvent(e, delta);
  if (typed > 0) recordTyped(typed);
  applySensitivity();
  updateStats();
  updateTocCounts();
  checkLock();
  if (document.body.classList.contains('typewriter-on')) {
    scrollCaretToCenter(el.selectionStart || 0);
  }
  if (S.find.term) { S.find.idx = -1; }
  scheduleSave();
  histSchedule();
}

async function onTitleChange() {
  const f = currentFile();
  if (!f) return;
  const el = $('#chTitle');
  const v = el.value.replace(/\s+/g, ' ').trim();
  if (el.value !== v) { el.value = v; autoGrow(el, 220); }
  if (!v || v === f.name) return;
  f.name = v;
  f.lastModified = Date.now();
  renderToc();
  $('#crumbCh').textContent = `第 ${String(chapterNo(f)).padStart(3, '0')} 章 · ${f.name}`;
  scheduleSave();
}

/* ---------------- 码字锁 ---------------- */
function renderLock() {
  const on = S.lock.on;
  const banner = $('#lockBanner');
  const chip = $('#lockChip');
  if (banner) banner.classList.toggle('show', on);
  if (chip) chip.innerHTML = on ? '<span class="seal-t">已上锁</span>' : '';
  if (!on) return;
  const written = Math.max(0, wordCount(currentFile() && currentFile().content) - S.lock.startWords);
  const left = Math.max(0, S.lock.goal - written);
  const goalT = $('#lockGoalT');
  const leftT = $('#lockLeftT');
  if (goalT) goalT.textContent = fmt(S.lock.goal);
  if (leftT) leftT.textContent = fmt(left);
}
function checkLock() {
  if (!S.lock.on) return;
  const written = Math.max(0, wordCount(currentFile() && currentFile().content) - S.lock.startWords);
  if (written >= S.lock.goal) {
    S.lock.on = false;
    renderLock();
    toast('码字锁已解锁，出去走两步吧');
  }
}

/* ---------------- 番茄钟 ---------------- */
function pomoDurations() {
  const ui = store.json(KEY.ui, {});
  return {
    focus: Math.max(1, Number(ui.pomoFocus) || 25) * 60,
    rest: Math.max(1, Number(ui.pomoRest) || 5) * 60,
  };
}

function togglePomodoro() {
  if (S.pomo.on) {
    if (S.pomo.mode === 'rest') { startPomo('focus'); return; }
    stopPomodoro();
    return;
  }
  startPomo('focus');
}

function startPomo(mode) {
  clearInterval(S.pomo.timer);
  S.pomo.on = true;
  S.pomo.mode = mode;
  const durations = pomoDurations();
  S.pomo.left = mode === 'rest' ? durations.rest : durations.focus;
  S.pomo.timer = setInterval(() => {
    S.pomo.left--;
    renderPomodoro();
    if (S.pomo.left <= 0) {
      clearInterval(S.pomo.timer);
      if (mode === 'focus') {
        S.pomo.rounds = (S.pomo.rounds || 0) + 1;
        beep(2);
        toast('番茄钟结束，休息 ' + Math.round(durations.rest / 60) + ' 分钟');
        startPomo('rest');
      } else {
        beep(1);
        toast('休息结束，开始下一个番茄');
        startPomo('focus');
      }
    }
  }, 1000);
  renderPomodoro();
}

function stopPomodoro() {
  clearInterval(S.pomo.timer);
  S.pomo.on = false;
  S.pomo.mode = 'focus';
  $('#pomoLabel').textContent = '番茄钟';
  $('#pomoChip').classList.remove('on');
  const d = pomoDurations();
  $('#pomoChip').title = `番茄钟：${Math.round(d.focus / 60)} 分钟专注 + ${Math.round(d.rest / 60)} 分钟休息`;
}

function renderPomodoro() {
  const m = Math.floor(S.pomo.left / 60), s = S.pomo.left % 60;
  const clock = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  $('#pomoLabel').textContent = S.pomo.mode === 'rest' ? `休息 ${clock}` : clock;
  $('#pomoChip').classList.add('on');
  $('#pomoChip').title = S.pomo.mode === 'rest' ? '休息中 · 点击开始下一个番茄' : '专注中 · 点击暂停';
}

/* ---------------- 自动排版 / 手机排版 ---------------- */
function zhPunct(s) {
  let open = true;
  return s
    .replace(/,/g, '，').replace(/;/g, '；').replace(/:/g, '：')
    .replace(/\?/g, '？').replace(/!/g, '！')
    .replace(/\.{3,}/g, '……')
    .replace(/([\u4e00-\u9fa5”』」）])\s*\.\s*(?=[\u4e00-\u9fa5“『「（"']|$)/g, '$1。')
    .replace(/"/g, () => { const ch = open ? '“' : '”'; open = !open; return ch; })
    .replace(/\(/g, '（').replace(/\)/g, '）');
}

function looksHeading(line) {
  const s = (line || '').trim();
  if (!s || s.length > 40) return false;
  return /^(第\s*[0-9零〇一二三四五六七八九十百千两]{1,8}\s*[章节回卷]|(Chapter|CHAPTER)\s+\d+|\d{1,4}\s*[、.．])/.test(s);
}

function looksDialog(line) {
  const s = (line || '').trim();
  return /^[“"「『]/.test(s) || /[：:]\s*[“"「]/.test(s);
}

function autoFormat(text, opts) {
  const o = Object.assign({ punct: true, merge: true, blank: true, indent: true, dialog: true }, opts || {});
  const lines = (text || '').replace(/\r\n?/g, '\n').split('\n')
    .map((l) => l.replace(/[\t\u00a0]/g, ' ').replace(/[ \u3000]+$/g, '').replace(/^[ \u3000]+/g, '').trim());

  const paras = [];
  lines.forEach((line) => {
    if (!line) return;
    const prev = paras[paras.length - 1];
    const canMerge = prev && o.merge
      && !looksHeading(line) && !looksHeading(prev)
      && !looksDialog(line) && !looksDialog(prev)
      && !/[。！？…；”』」）\.\!\?]$/.test(prev);
    if (canMerge) paras[paras.length - 1] = prev + line;
    else paras.push(line);
  });

  let out = [];
  paras.forEach((p) => {
    let s = o.punct ? zhPunct(p) : p;
    if (o.dialog) {
      // 一段里塞了多句对话时，把每句对话拆成独立段落；过短的旁白并回上一句
      const parts = s.split(/(?=[“「])/).filter((x) => x.trim());
      if (parts.length > 1 && s.length > 40) {
        const merged = [];
        parts.forEach((part) => {
          const t = part.trim();
          if (t.length <= 12 && merged.length) merged[merged.length - 1] += t;
          else merged.push(t);
        });
        out.push(...merged);
      } else out.push(s);
    } else out.push(s);
  });

  if (o.indent) out = out.map((p) => (looksHeading(p) ? p : '　　' + p));
  return out.join(o.blank ? '\n\n' : '\n').trim();
}

function mobileFormat(text, maxChars) {
  const max = Math.max(30, Number(maxChars) || 70);
  const base = autoFormat(text, { punct: true, merge: true, blank: true, indent: false, dialog: true });
  const paras = base.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean);
  const out = [];
  paras.forEach((p) => {
    if (p.length <= max) { out.push(p); return; }
    const sentences = p.match(/[^。！？…]*[。！？…]+|[^。！？…]+$/g) || [p];
    let buf = '';
    sentences.forEach((sen) => {
      if (buf && (buf + sen).length > max) { out.push(buf); buf = sen; }
      else buf += sen;
    });
    if (buf) out.push(buf);
  });
  return out.join('\n');
}

function applyFormattedText(text, label) {
  const f = currentFile();
  if (!f) { toast('先打开一章'); return false; }
  if (!text || !text.trim()) { toast('没有可排版的内容'); return false; }
  if (text === (f.content || '')) { toast('排版后没有变化'); return false; }
  takeSnapshot(true);
  histCommit();
  input().value = text;
  f.content = text;
  onEditorInput();
  histCommit();
  toast(label + '已应用（Ctrl+Z 可撤销）');
  return true;
}

/* ---------------- 手机预览 ---------------- */
function renderPhonePreview() {
  const f = currentFile();
  if (!f) {
    $('#phTitle').textContent = '—';
    $('#phMeta').textContent = '—';
    $('#phBody').textContent = '';
    $('#phInfo').textContent = '';
    return;
  }
  const width = Number(($('#phWidth') && $('#phWidth').value) || 70);
  const mobile = mobileFormat(f.content || '', width);
  const paras = mobile ? mobile.split('\n').filter(Boolean).length : 0;
  $('#phTitle').textContent = f.name;
  $('#phMeta').textContent = `${S.book ? S.book.name : ''} · ${fmt(wordCount(f.content))} 字`;
  $('#phBody').textContent = mobile;
  $('#phInfo').textContent = mobile
    ? `已按手机阅读重排：${paras} 段，每段 ≤ ${width} 字（点「应用到正文」写回稿件）`
    : '这一章还没有正文';
}

/* ---------------- Toast ---------------- */
function toast(msg) {
  const box = $('#toasts');
  const el = document.createElement('div');
  el.className = 'toast';
  el.textContent = msg;
  box.appendChild(el);
  setTimeout(() => el.remove(), 2600);
}

/* ---------------- 弹窗 ---------------- */
function openModal(id) {
  $('#' + id).classList.add('show');
  if (id === 'bgModal') syncSfxUi();
}
function closeModal(el) {
  el.classList.remove('show');
  if (el.id === 'inputModal' && inputResolve) { const h = inputResolve; inputResolve = null; h.resolve(null); }
  if (el.id === 'confirmModal' && confirmResolve) { const r = confirmResolve; confirmResolve = null; r(false); }
  if (el.id === 'pickModal' && pickResolve) { const r = pickResolve; pickResolve = null; r(null); }
}

/* 页内输入框 / 确认框（替代原生 prompt / confirm） */
let inputResolve = null;
let confirmResolve = null;
let pickResolve = null;

function askText(title, hint, value, opts) {
  const multi = opts === 'multiline' || !!(opts && opts.multiline);
  return new Promise((resolve) => {
    $('#inputTitle').textContent = title;
    $('#inputHint').textContent = hint || '';
    const line = $('#inputValue');
    const area = $('#inputArea');
    $('#inputAreaWrap').hidden = !multi;
    line.hidden = multi;
    line.value = multi ? '' : (value || '');
    area.value = multi ? (value || '') : '';
    if (multi) autoGrow(area, 320);
    inputResolve = { resolve, multi };
    openModal('inputModal');
    setTimeout(() => {
      const el = multi ? area : line;
      el.focus();
      if (multi) el.setSelectionRange(el.value.length, el.value.length);
      else el.select();
    }, 40);
  });
}
function settleInput(ok) {
  const holder = inputResolve;
  inputResolve = null;
  const el = (holder && holder.multi) ? $('#inputArea') : $('#inputValue');
  const v = el.value.trim();
  closeModal($('#inputModal'));
  if (holder) holder.resolve(ok ? v : null);
}
function askConfirm(title, text, okLabel) {
  return new Promise((resolve) => {
    $('#confirmTitle').textContent = title;
    $('#confirmText').textContent = text;
    $('#confirmOk').textContent = okLabel || '确定';
    confirmResolve = resolve;
    openModal('confirmModal');
  });
}
function settleConfirm(ok) {
  const r = confirmResolve;
  confirmResolve = null;
  closeModal($('#confirmModal'));
  if (r) r(ok);
}
function askPick(title, hint, options, current) {
  return new Promise((resolve) => {
    $('#pickTitle').textContent = title;
    $('#pickHint').textContent = hint || '';
    $('#pickList').innerHTML = (options || []).map((o) => `<button class="pick-item${o.id === current ? ' on' : ''}" data-pk="${esc(o.id)}">
        <span>${esc(o.label)}</span>${o.note ? `<span class="pk-note">${esc(o.note)}</span>` : ''}</button>`).join('');
    pickResolve = resolve;
    openModal('pickModal');
  });
}
function settlePick(id) {
  const r = pickResolve;
  pickResolve = null;
  closeModal($('#pickModal'));
  if (r) r(id);
}

/* ---------------- 菜单 ---------------- */
let menuAnchorEl = null;

function showMenu(anchor, items) {
  const menu = $('#ctxMenu');
  menu.innerHTML = items.map((it, i) => it.sep ? '<hr class="menu-sep">' :
    `<button data-mi="${i}" class="${it.current ? 'current' : ''}${it.danger ? ' danger' : ''}">
       <span class="mi">${it.icon || '·'}</span><span class="mi-line">${esc(it.label)}${it.note ? `<span style="color:var(--muted);font-size:11px">${esc(it.note)}</span>` : ''}</span>
     </button>`).join('');
  menu.hidden = false;
  menuAnchorEl = anchor;
  const r = anchor.getBoundingClientRect();
  const w = 220;
  let left = Math.min(r.left, window.innerWidth - w - 12);
  let top = r.bottom + 6;
  menu.style.width = w + 'px';
  if (top + menu.offsetHeight > window.innerHeight - 12) top = Math.max(12, r.top - menu.offsetHeight - 6);
  menu.style.left = left + 'px';
  menu.style.top = top + 'px';
  menu.onclick = (e) => {
    const b = e.target.closest('button[data-mi]');
    if (!b) return;
    hideMenu();
    const it = items[Number(b.dataset.mi)];
    if (it && it.action) it.action();
  };
}

function hideMenu() {
  const m = $('#ctxMenu');
  if (m) m.hidden = true;
  menuAnchorEl = null;
}

/* ---------------- 底部工具栏：分类抽屉 ---------------- */
let ftCatOpen = '';

function closeFtDrawer() {
  const d = $('#ftDrawer');
  if (!d || d.hidden) return;
  d.classList.remove('on');
  document.querySelectorAll('.ft-cat').forEach((b) => b.setAttribute('aria-expanded', 'false'));
  ftCatOpen = '';
  setTimeout(() => { if (!d.classList.contains('on')) d.hidden = true; }, 260);
}

function openFtDrawer(cat) {
  const d = $('#ftDrawer');
  if (!d) return;
  if (ftCatOpen === cat) { closeFtDrawer(); return; }
  ftCatOpen = cat;
  d.querySelectorAll('.ft-panel').forEach((p) => { p.hidden = p.dataset.cat !== cat; });
  document.querySelectorAll('.ft-cat').forEach((b) => b.setAttribute('aria-expanded', String(b.dataset.cat === cat)));
  d.hidden = false;
  /* 双帧再挂 .on：先让浏览器算出 display:flex 的初始态，再触发过渡，否则首帧会被合并且看起来是“瞬间弹出” */
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (d.hidden) return;
    d.classList.add('on');
  }));
}

/* 收起状态下抽屉不该留在屏幕上 */
function syncFloatTools() {
  if (document.body.classList.contains('tools-collapsed')) closeFtDrawer();
}

/* 同一个锚点再次点击时收起，而不是重新弹出 */
function toggleMenu(anchor, opener) {
  if (!$('#ctxMenu').hidden && menuAnchorEl === anchor) { hideMenu(); return; }
  opener(anchor);
}

/* ---------------- 书籍 ---------------- */
async function loadBooks() {
  const r = await api('/projects');
  S.books = (r.projects || []).slice().sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  return S.books;
}

function firstReadableChapter() {
  const list = chapterFiles();
  if (!list.length) return null;
  const isScaffold = (f) => /\.(md|json|txt|markdown)$/i.test(f.name || '');
  const hasText = (f) => String(f.content || '').trim().length > 0;
  const looksChapter = (f) => /第\s*[0-9一二三四五六七八九十百千]+\s*[章节回卷]|chapter\s*\d+/i.test(f.name || '');
  return list.find((f) => looksChapter(f) && hasText(f))
    || list.find(looksChapter)
    || list.find((f) => !isScaffold(f) && hasText(f))
    || list.find((f) => !isScaffold(f))
    || list[0];
}

async function openBook(name) {
  const project = await api(`/projects/${encodeURIComponent(name)}`);
  let files = project._files;
  if (!Array.isArray(files) || !files.length) {
    files = [
      { id: 'root', parentId: null, name: 'Root', type: 'FOLDER', lastModified: Date.now() },
      { id: 'vol_' + Date.now(), parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() },
    ];
  }
  if (!files.find((f) => f.id === 'root')) files.unshift({ id: 'root', parentId: null, name: 'Root', type: 'FOLDER', lastModified: Date.now() });
  S.book = project;
  S.files = files;
  store.set(KEY.lastBook, name);
  S.goal = Number(store.get(KEY.goal(name), project.daily_goal || 3000)) || 3000;
  loadConversations(name);
  S.chapterId = null;
  S.lock.on = false;
  S.lock.startWords = 0;
  $('#lockBanner').classList.remove('show');
  renderBookHead();
  renderWorld();
  renderToc();
  renderTrashCount();
  renderChat();
  const last = store.get(KEY.lastBook + ':chapter', '');
  const first = firstReadableChapter();
  const target = fileById(last) || first;
  if (target) { await openChapter(target.id); } else { updateEditorChrome(); }
}

async function createBook() {
  const name = $('#newBookName').value.trim();
  if (!name) { toast('书名不能为空'); return; }
  const tpl = ewTpl ? EW_TEMPLATES.find((t) => t.id === ewTpl) : null;
  try {
    await api('/projects', { method: 'POST', body: { name, genre: $('#newBookGenre').value.trim(), style: $('#newBookStyle').value.trim(), author: $('#newBookAuthor').value.trim() } });
    const volId = newId('vol_');
    const files = [
      { id: 'root', parentId: null, name: 'Root', type: 'FOLDER', lastModified: Date.now() },
      { id: volId, parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() },
    ];
    const seedChapters = tpl && tpl.chapters && tpl.chapters.length ? tpl.chapters : ['第1章'];
    seedChapters.forEach((cn) => {
      files.push({ id: newId('ch_'), parentId: volId, name: cn, type: 'FILE', content: '', lastModified: Date.now(), metadata: {} });
    });
    await api(`/files/${encodeURIComponent(name)}`, { method: 'POST', body: { files } });
    $$('.modal-mask').forEach((m) => m.classList.remove('show'));
    $('#newBookName').value = '';
    await loadBooks();
    await openBook(name);
    if (tpl) {
      await saveProjectFields({ description: tpl.desc });
      toast(`已按「${tpl.name}」模板开书：预置 ${seedChapters.length} 章骨架`);
    } else {
      toast('书籍已建立，直接开写吧');
    }
    ewTpl = null;
  } catch (e) { toast('建立失败：' + e.message); }
}

function openBookModal() {
  $('#newBookName').value = '';
  $('#newBookAuthor').value = '';
  $('#newBookGenre').value = '';
  $('#newBookStyle').value = '';
  ewTpl = null;
  ewRenderTemplates();
  openModal('bookModal');
  setTimeout(() => $('#newBookName').focus(), 60);
}

function switchBookMenu(anchor) {
  const items = S.books.map((b) => ({
    label: b.name,
    note: (b.words ? fmt(b.words) + ' 字' : '') + (b.genre ? ' · ' + b.genre : ''),
    icon: '书',
    current: S.book && b.name === S.book.name,
    action: () => openBook(b.name).catch((e) => toast(e.message)),
  }));
  if (!items.length) items.push({ label: '还没有书', icon: '·', action: openBookModal });
  items.push({ sep: true });
  items.push({ label: '书架', icon: '架', action: openShelf });
  items.push({ label: '新建书籍', icon: '＋', action: openBookModal });
  if (S.book) {
    items.push({ label: '书籍设置', icon: '设', action: () => openBookSettings() });
  }
  items.push({ sep: true });
  items.push({ label: '设置 API Key', icon: '钥', action: openSettings });
  showMenu(anchor, items);
}

async function deleteBook(skipConfirm) {
  if (!S.book) return;
  if (!skipConfirm) {
    const typed = await askText('删除书籍', `此操作会移除《${S.book.name}》，请输入书名确认：`, '');
    if (typed !== S.book.name) {
      if (typed !== null) toast('书名不一致，已取消');
      return;
    }
  }
  try {
    await api(`/projects/${encodeURIComponent(S.book.name)}`, { method: 'DELETE' });
    S.book = null; S.files = []; S.chapterId = null;
    await loadBooks();
    renderBookHead(); renderToc(); updateEditorChrome(); renderShelf();
    toast('已删除');
  } catch (e) { toast('删除失败：' + e.message); }
}

/* ---------------- 设置 ---------------- */
async function loadSettings() {
  try {
    S.settings = await api('/settings');
    $('#modelChip').textContent = S.settings.model || 'deepseek-flash';
  } catch {}
}
async function renderDeviceInfo() {
  const box = $('#setDeviceInfo');
  if (!box) return;
  try {
    const r = await api('/system/info');
    const lan = r.lan || [];
    box.innerHTML = `
      <div class="st-item"><div class="t">本机网页版</div><div class="d">http://127.0.0.1:${r.port}/</div></div>
      ${lan.length
        ? lan.map((u) => `<div class="st-item"><div class="t">手机 / 平板访问</div><div class="d">${esc(u)}　（同一个 Wi-Fi 下打开）</div></div>`).join('')
        : '<div class="st-item"><div class="t">手机访问未开启</div><div class="d">用「启动网页版(手机可访问).bat」启动，这里会显示局域网地址</div></div>'}
      <div class="st-item"><div class="t">运行模式</div><div class="d">${r.frozen ? 'Windows 桌面版' : '源码 / 网页版'} · ${esc(r.data_dir)}</div></div>`;
  } catch (e) {
    box.innerHTML = '<div class="st-empty">读取失败：' + esc(e.message) + '</div>';
  }
}

function switchSettingsTab(tab) {
  $$('#setTabs button').forEach((b) => b.classList.toggle('on', b.dataset.setTab === tab));
  $$('[data-set-pane]').forEach((p) => { p.hidden = p.dataset.setPane !== tab; });
  if (tab === 'data') loadProjectTrash();
  if (tab === 'sync') loadSyncPanel();
  if (tab === 'about') renderDeviceInfo();
}

function openSettings(tab) {
  const ui = store.json(KEY.ui, {});
  if (typeof tab !== 'string') tab = 'api';
  $('#setKey').value = '';
  $('#setKey').placeholder = S.settings.api_key ? '已配置（留空保持不变）' : 'sk-…';
  $('#setBase').value = S.settings.base_url || '';
  $('#setModel').value = S.settings.model || 'deepseek-flash';
  const imgKeyEl = $('#setImgKey');
  if (imgKeyEl) {
    imgKeyEl.value = '';
    imgKeyEl.placeholder = S.settings.has_image_key ? '已配置（留空保持不变）' : 'sk-…（可留空）';
    $('#setImgBase').value = S.settings.image_base || '';
    $('#setImgModel').value = S.settings.image_model || '';
  }
  const asrKeyEl = $('#setAsrKey');
  if (asrKeyEl) {
    asrKeyEl.value = '';
    asrKeyEl.placeholder = S.settings.has_asr_key ? '已配置（留空保持不变）' : 'sk-…（可留空）';
    $('#setAsrBase').value = S.settings.asr_base || '';
    $('#setAsrModel').value = S.settings.asr_model || '';
  }
  const ttsProvEl = $('#setTtsProvider');
  if (ttsProvEl) {
    const label = { minimax: 'MiniMax 海螺', volc: '火山豆包', azure: 'Azure 情感', edge: 'Edge 基础（机械感强）' };
    ttsProvEl.value = S.settings.tts_provider || 'auto';
    $('#setTtsActive').value = label[S.settings.tts_active] || S.settings.tts_active || '';
    $('#setMinimaxKey').value = '';
    $('#setMinimaxKey').placeholder = S.settings.has_minimax_key ? '已配置（留空保持不变）' : 'MiniMax API Key';
    $('#setMinimaxModel').value = S.settings.minimax_model || 'speech-2.8-hd';
    $('#setVolcAppid').value = S.settings.volc_appid || '';
    $('#setVolcToken').value = '';
    $('#setVolcToken').placeholder = S.settings.has_volc ? '已配置（留空保持不变）' : 'Access Token';
    $('#setAzureKey').value = '';
    $('#setAzureKey').placeholder = S.settings.has_azure_key ? '已配置（留空保持不变）' : 'Azure Speech Key';
    $('#setAzureRegion').value = S.settings.azure_region || 'eastasia';
    $('#ttsStatus').textContent = S.settings.tts_active === 'edge'
      ? '当前用 Edge 基础音色，填入任意一家 Key 即升级为真人音色'
      : '当前引擎：' + (label[S.settings.tts_active] || S.settings.tts_active);
  }
  $('#setStatus').textContent = '';
  refreshDictStatus();

  // 外观
  applyUi();
  // 写作
  $('#setGoal').value = S.goal || 3000;
  $('#setAutosave').value = String(ui.autosaveMs || 900);
  $('#setPomoFocus').value = Math.round((ui.pomoFocus || 25));
  $('#setPomoRest').value = Math.round((ui.pomoRest || 5));
  $('#setLockGoal').value = ui.lockGoal || 500;
  $('#setEditorFont').value = ui.family || 'sans';
  if ($('#setHumanFlaws')) $('#setHumanFlaws').checked = ui.humanFlaws !== false;
  $('#setWriteStatus').textContent = '';
  $('#setDataStatus').textContent = '';
  switchSettingsTab(tab || 'api');
  openModal('settingsModal');
}

async function saveSettings() {
  const body = { base_url: $('#setBase').value.trim(), model: $('#setModel').value.trim() };
  const key = $('#setKey').value.trim();
  if (key) body.api_key = key;
  const imgKey = $('#setImgKey') ? $('#setImgKey').value.trim() : '';
  if (imgKey) body.image_api_key = imgKey;
  if ($('#setImgBase')) body.image_base = $('#setImgBase').value.trim();
  if ($('#setImgModel')) body.image_model = $('#setImgModel').value.trim();
  const asrKey = $('#setAsrKey') ? $('#setAsrKey').value.trim() : '';
  if (asrKey) body.asr_key = asrKey;
  if ($('#setAsrBase')) body.asr_base = $('#setAsrBase').value.trim();
  if ($('#setAsrModel')) body.asr_model = $('#setAsrModel').value.trim();
  if ($('#setTtsProvider')) {
    body.tts_provider = $('#setTtsProvider').value;
    body.minimax_model = $('#setMinimaxModel').value;
    const mk = $('#setMinimaxKey').value.trim();
    if (mk) body.minimax_key = mk;
    body.volc_appid = $('#setVolcAppid').value.trim();
    const vt = $('#setVolcToken').value.trim();
    if (vt) body.volc_token = vt;
    const azk = $('#setAzureKey').value.trim();
    if (azk) body.azure_key = azk;
    body.azure_region = $('#setAzureRegion').value.trim() || 'eastasia';
  }
  try {
    await api('/settings', { method: 'PUT', body });
    await loadSettings();
    $('#setStatus').textContent = '已保存';
    toast('接口设置已保存');
  } catch (e) { $('#setStatus').textContent = '保存失败：' + e.message; }
}

/* ---------------- 同步（自建同步中心，零成本） ---------------- */
let syncInfo = null;
let syncStamp = 0;
let syncReloadPending = false;

function syncRoleOf() {
  const on = $('#setSyncRole .on');
  return on ? on.dataset.syncRole : 'off';
}

function renderSyncRole(role) {
  $$('#setSyncRole button').forEach((b) => b.classList.toggle('on', b.dataset.syncRole === role));
  $('#syncHubBox').hidden = role !== 'hub';
  $('#syncClientBox').hidden = role !== 'client';
}

function renderSyncStatus(st) {
  if (!st) return;
  const roleTxt = { off: '不同步', hub: '同步中心', client: '客户端' }[st.role] || st.role;
  let line = `状态：${st.enabled ? roleTxt : '不同步'} · 设备 ${st.device || '-'} · 已同步 ${st.projects || 0} 本`;
  if (st.last_sync) line += ` · 上次 ${st.last_sync}`;
  if (st.note) line += ` · ${st.note}`;
  $('#setSyncStatus').textContent = line;
  $('#setSyncHint').textContent = st.last_error
    ? '错误：' + st.last_error
    : st.role === 'hub'
      ? '把上面的地址和令牌填到手机「设置 → 同步 → 连到同步中心」，手机改的内容几秒内就会到电脑。手机连不上时：确认同一个 WiFi，并在 Windows 防火墙里放行专用网络（或直接开公网隧道）。'
      : st.role === 'client'
        ? '每 6 秒自动拉取 / 推送一次，也可以点「立即同步」。'
        : '三端互通靠一台电脑当中心：桌面端或网页版选「本机当同步中心」，手机选「连到同步中心」。';
}

async function loadSyncPanel() {
  try {
    const st = await api('/sync/status');
    syncInfo = st;
    syncStamp = st.pulled_stamp || 0;
    renderSyncRole(st.enabled ? st.role : 'off');
    $('#setSyncLan').value = (st.lan_urls || [])[0] || '';
    $('#setSyncToken').value = st.token || '';
    $('#setSyncTunnel').checked = !!st.tunnel;
    $('#setSyncPublic').value = st.public_url || '';
    $('#setSyncPublic').placeholder = st.tunnel_alive || (st.note || '').indexOf('下载') >= 0
      ? (st.note || '隧道建立中…') : '开启后自动生成 https://xxx.trycloudflare.com';
    $('#setSyncHub').value = st.hub_url || '';
    $('#setSyncToken2').value = st.token || '';
    renderSyncStatus(st);
  } catch (e) {
    $('#setSyncStatus').textContent = '同步不可用：' + e.message;
  }
}

async function saveSyncConfig(extra) {
  const role = syncRoleOf();
  const body = Object.assign({ enabled: role !== 'off', role, tunnel: $('#setSyncTunnel').checked }, extra || {});
  if (role === 'client') {
    body.hub_url = $('#setSyncHub').value.trim().replace(/\/+$/, '');
    const tk = $('#setSyncToken2').value.trim();
    if (tk) body.token = tk;
    if (!body.hub_url) { toast('先填写同步中心地址'); return; }
  }
  try {
    const st = await api('/sync/config', { method: 'POST', body });
    syncInfo = st;
    $('#setSyncLan').value = (st.lan_urls || [])[0] || '';
    $('#setSyncToken').value = st.token || '';
    $('#setSyncPublic').value = st.public_url || '';
    renderSyncStatus(st);
    toast('同步设置已保存');
  } catch (e) {
    $('#setSyncStatus').textContent = '保存失败：' + e.message;
  }
}

async function testSyncHub() {
  const url = $('#setSyncHub').value.trim().replace(/\/+$/, '');
  if (!url) { toast('先填写同步中心地址'); return; }
  $('#setSyncStatus').textContent = '测试中…';
  try {
    const r = await fetch(url + '/api/sync/ping', { cache: 'no-store' });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const js = await r.json();
    const tk = $('#setSyncToken2').value.trim();
    const m = await fetch(url + '/api/sync/manifest', { headers: { 'X-Sync-Token': tk }, cache: 'no-store' });
    if (m.status === 401) throw new Error('令牌不正确');
    if (!m.ok) throw new Error('HTTP ' + m.status);
    const mm = await m.json();
    $('#setSyncStatus').textContent = `已连上 ${js.device || url} · 中心共 ${mm.count || 0} 本`;
  } catch (e) {
    $('#setSyncStatus').textContent = '连接失败：' + e.message + '（检查地址、同一 WiFi、令牌）';
  }
}

/* 后台轮询：远端有更新时自动刷新当前这本书 */
function startSyncWatch() {
  setInterval(async () => {
    try {
      const st = await api('/sync/status');
      if (!syncInfo) { syncInfo = st; syncStamp = st.pulled_stamp || 0; return; }
      const stamp = st.pulled_stamp || 0;
      if (!stamp || stamp <= syncStamp) { syncStamp = Math.max(syncStamp, stamp); return; }
      syncStamp = stamp;
      if (!S.book) {
        await loadBooks();
        toast('已同步其他设备的更新');
        return;
      }
      if (S.saveTimer) {            // 正在打字，等自动保存落盘后再刷
        syncReloadPending = true;
        toast('其他设备有更新，写完这一小段就自动刷新');
        setTimeout(() => { if (syncReloadPending && !S.saveTimer) doSyncReload(); }, 2500);
        return;
      }
      doSyncReload();
    } catch (_) {}
  }, 6000);
}

async function doSyncReload() {
  if (!S.book || S.saveTimer) return;
  syncReloadPending = false;
  const name = S.book.name;
  try {
    await loadBooks();
    await openBook(name);
    toast('已同步其他设备的更新');
  } catch (_) {}
}

function saveWritingPrefs() {
  const goal = Number($('#setGoal').value) || 3000;
  S.goal = goal;
  store.set(KEY.goal(S.book ? S.book.name : '_'), String(goal));
  setUi({
    autosaveMs: Number($('#setAutosave').value) || 900,
    pomoFocus: Math.max(1, Number($('#setPomoFocus').value) || 25),
    pomoRest: Math.max(1, Number($('#setPomoRest').value) || 5),
    lockGoal: Number($('#setLockGoal').value) || 500,
    family: $('#setEditorFont').value,
    humanFlaws: $('#setHumanFlaws') ? $('#setHumanFlaws').checked : true,
  });
  S.pomo.left = Math.round((store.json(KEY.ui, {}).pomoFocus || 25) * 60);
  updateStats();
  $('#setWriteStatus').textContent = '已保存';
  toast('写作设置已保存');
}

async function exportAllProjects() {
  try {
    const list = (await api('/projects')).projects || [];
    const bundle = { exported_at: new Date().toISOString(), projects: [] };
    for (const p of list) {
      try { bundle.projects.push(await api('/projects/' + encodeURIComponent(p.name))); } catch {}
    }
    downloadText(`烽火南境_全部项目_${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(bundle, null, 2));
    $('#setDataStatus').textContent = `已导出 ${bundle.projects.length} 个项目`;
  } catch (e) { toast('导出失败：' + e.message); }
}

async function loadProjectTrash() {
  try {
    const r = await api('/trash');
    const box = $('#setTrashBox');
    box.hidden = false;
    $('#setTrashList').innerHTML = (r.items || []).length
      ? r.items.map((it) => `<div class="st-item">
          <div class="t">${esc(it.name)} <span class="st-badge">${(it.size / 1024).toFixed(0)} KB</span></div>
          <div class="d">${esc(it.ts)}</div>
          <div class="st-row" style="margin-top:6px"><button class="mini-btn" data-trash-file="${esc(it.file)}">恢复到书架</button></div>
        </div>`).join('')
      : '<div class="st-empty">回收站是空的</div>';
  } catch (e) { $('#setDataStatus').textContent = '读取回收站失败：' + e.message; }
}

async function clearLocalCache() {
  const ok = await askConfirm('清空本地缓存', '会清掉本地偏好（主题、排版、聊天、伏笔、快照、回收站等），服务端项目不受影响。', '清空');
  if (!ok) return;
  try {
    Object.keys(localStorage).filter((k) => k.startsWith('fj:')).forEach((k) => localStorage.removeItem(k));
    toast('本地缓存已清空，即将重新加载');
    setTimeout(() => location.reload(), 600);
  } catch (e) { toast('清空失败：' + e.message); }
}

function ensureApi() {
  if (S.settings.api_key) return true;
  toast('先配置 API Key');
  openSettings();
  return false;
}

/* ---------------- AI ---------------- */
function clearHumanizeDiff() {
  const card = $('#aiDiffCard');
  const box = $('#aiDiff');
  if (box) box.innerHTML = '';
  if (card) card.hidden = true;
  const meta = $('#aiDiffMeta');
  if (meta) meta.textContent = '';
  const all = $('#aiDiffFoldAll');
  if (all) all.textContent = '收起全文';
}

function _fallbackOps(d) {
  const ops = [];
  (d.removed || []).forEach((s) => ops.push({ op: 'del', o: s, n: '' }));
  (d.added || []).forEach((s) => ops.push({ op: 'add', o: '', n: s }));
  return ops;
}

function renderHumanizeDiff(r) {
  const card = $('#aiDiffCard');
  const box = $('#aiDiff');
  if (!card || !box) return;
  const diffs = Array.isArray(r.diffs) ? r.diffs : [];
  if (!diffs.length) { clearHumanizeDiff(); return; }

  const sm = r.summary || {};
  const bits = [];
  if ((r.baseline === 'genre' || r.baseline === 'author') && r.profile) bits.push(`基准《${r.profile}》`);
  if (r.quality) bits.push(`文笔 ${r.quality[0]} → ${r.quality[1]}`);
  if (sm.changed != null) bits.push(`共 ${sm.changed} 处改动`);
  if (sm.rewritten != null) bits.push(`改写 ${sm.rewritten} · 删除 ${sm.deleted || 0}`);
  if (sm.failed) bits.push(`退回 ${sm.failed} 段`);
  if (sm.rounds && sm.changed != null && sm.rounds > sm.changed) bits.push(`迭代 ${sm.rounds} 轮`);
  if (sm.aigc && sm.aigc.score != null) {
    bits.push(`AIGC 终检 ${sm.aigc.score}（${sm.aigc.pass ? '通过' : '未通过'}）`
      + (r.aigc_rounds ? ` · 补改 ${r.aigc_rounds} 轮` : ''));
  }
  if (sm.flaws) bits.push(`人味笔误 ${sm.flaws} 处`);
  if (sm.paras) bits.push(`段落 ${sm.paras[0]} → ${sm.paras[1]}`);
  if (sm.chars) {
    const d = sm.chars[1] - sm.chars[0];
    bits.push(`字数 ${sm.chars[0]} → ${sm.chars[1]}（${d >= 0 ? '+' : ''}${d}）`);
  }
  if (sm.sents) bits.push(`句 ${sm.sents[0]} → ${sm.sents[1]}`);
  if (r.detect != null) bits.push(`检测 ${r.detect} 分`);
  $('#aiDiffMeta').textContent = bits.join(' · ');

  box.innerHTML = diffs.map((d) => {
    const reasons = (d.reason || []).map((x) => `<i>${esc(x)}</i>`).join('');
    const ops = (Array.isArray(d.ops) && d.ops.length) ? d.ops : _fallbackOps(d);
    const rows = ops.map((o) => {
      if (o.op === 'same') {
        return `<div class="dl same"><span class="k same">留</span><span class="tx">${esc(o.o)}</span></div>`;
      }
      if (o.op === 'del') {
        return `<div class="dl del"><span class="k del">删</span><span class="tx">${esc(o.o)}</span></div>`;
      }
      if (o.op === 'add') {
        return `<div class="dl add"><span class="k add">增</span><span class="tx">${esc(o.n)}</span></div>`;
      }
      return `<div class="dl mod old"><span class="k del">原</span><span class="tx">${esc(o.o)}</span></div>`
        + `<div class="dl mod new"><span class="k add">改</span><span class="tx">${esc(o.n)}</span></div>`;
    }).join('');
    const chg = [];
    if (d.chars) chg.push(`${d.chars[0]} → ${d.chars[1]} 字`);
    if (d.sents) chg.push(`${d.sents[0]} → ${d.sents[1]} 句`);
    const isDel = d.type === 'delete';
    return `<div class="ai-diff-item${isDel ? ' is-del' : ''}">`
      + `<div class="hd"><b>第 ${d.index} 段</b><span class="kind">${isDel ? '整段删除' : '改写'}</span>`
      + reasons + `<span class="chg">${chg.join(' · ')}</span></div>`
      + `<div class="body">${rows || '<div class="dl"><span class="tx">（这一处没有可对照的句子）</span></div>'}</div>`
      + `</div>`;
  }).join('');

  box.onclick = (e) => {
    const hd = e.target.closest('.ai-diff-item .hd');
    if (hd) hd.parentElement.classList.toggle('folded');
  };
  const all = $('#aiDiffFoldAll');
  if (all) {
    all.textContent = '收起全文';
    all.onclick = () => {
      const items = Array.from(box.querySelectorAll('.ai-diff-item'));
      const anyOpen = items.some((it) => !it.classList.contains('folded'));
      items.forEach((it) => it.classList.toggle('folded', anyOpen));
      all.textContent = anyOpen ? '展开全文' : '收起全文';
    };
  }
  card.hidden = false;
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setAiResult(text, meta, kind) {
  if (kind !== 'humanize') clearHumanizeDiff();
  S.lastAi = { text, kind };
  $('#aiResultCard').hidden = false;
  $('#aiResult').classList.remove('loading');
  $('#aiResult').textContent = text || '（没有返回内容）';
  $('#aiResultMeta').textContent = meta || '';
  $('#aiOutlineSaveBtn').hidden = kind !== 'outline';
  $('#aiReplaceBtn').hidden = kind === 'outline' || kind === 'concept';
  $('#aiInsertBtn').hidden = kind === 'outline' || kind === 'concept';
  setRightTab('ai');
  $('#aiResultCard').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function setAiLoading(meta) {
  $('#aiResultCard').hidden = false;
  $('#aiResult').classList.add('loading');
  $('#aiResult').textContent = '正在生成，请稍候…';
  $('#aiResultMeta').textContent = meta || '';
  setRightTab('ai');
}

function bookContext() {
  const b = S.book || {};
  return {
    project_name: b.name || '',
    genre: b.genre || '东方玄幻',
    style: b.style || '热血励志',
    concept: b.concept || {},
    world: b.world || {},
    characters: b.characters || {},
    outline: b.outline || {},
  };
}

async function aiGenerateChapter() {
  if (!ensureApi() || !S.book) return;
  const f = currentFile();
  const outline = $('#outlineNote').value.trim() || (S.book.outline && S.book.outline.macro) || '';
  setAiLoading('生成本章初稿');
  try {
    const ctx = bookContext();
    const prev = chapterFiles().filter((c) => c.id !== (f && f.id)).slice(-1)[0];
    const r = await api('/generate/chapter', {
      method: 'POST',
      body: {
        ...ctx,
        chapter_num: f ? chapterNo(f) : 1,
        chapter_title: f ? f.name : '第1章',
        words_target: S.book.words_per_chapter || 2500,
        reference_author: S.book.ref_author || '',
        outline: { macro: outline },
        prev_chapter: prev ? (prev.content || '').slice(-800) : '',
        style_ref: S.book.style_ref || '',
        extra: [$('#scratchNote').value.trim(), S.book.prompt_template || ''].filter(Boolean).join('\n').slice(0, 600),
      },
    });
    setAiResult(r.chapter.content || '', '本章初稿 · AI', 'chapter');
  } catch (e) { setAiResult('生成失败：' + e.message, '错误', ''); }
}

async function aiContinue() {
  if (!ensureApi() || !S.book) return;
  const f = currentFile();
  if (!f || !f.content.trim()) { toast('正文还是空的'); return; }
  setAiLoading('续写中');
  try {
    const r = await api('/ai/continue', {
      method: 'POST',
      body: { ...bookContext(), content: f.content.slice(-1600), outline: $('#outlineNote').value.trim() },
    });
    setAiResult(r.text || '', '续写 · AI', 'continue');
  } catch (e) { setAiResult('续写失败：' + e.message, '错误', ''); }
}

async function aiRewrite() {
  if (!ensureApi() || !S.book) return;
  const el = input();
  const selected = el.value.slice(el.selectionStart, el.selectionEnd);
  const content = selected || el.value;
  if (!content.trim()) { toast('没有可改写的正文'); return; }
  setAiLoading(selected ? '改写选中片段' : '改写整章');
  try {
    const r = await api('/ai/rewrite', {
      method: 'POST',
      body: { ...bookContext(), content, direction: '文学润色', requirements: '' },
    });
    setAiResult(r.text || '', selected ? '改写选中 · AI' : '改写整章 · AI', 'rewrite');
  } catch (e) { setAiResult('改写失败：' + e.message, '错误', ''); }
}

async function aiHumanize() {
  if (!S.book) return;
  const el = input();
  const selected = el.value.slice(el.selectionStart, el.selectionEnd);
  const content = selected || el.value;
  if (!content.trim()) { toast('没有可处理的正文'); return; }
  setAiLoading('去 AI 味');
  clearHumanizeDiff();
  try {
    const r = await api('/ai/humanize', {
      method: 'POST',
      body: {
        text: content, intensity: 8,
        project_name: S.book ? S.book.name : '',
        genre: (S.book && S.book.genre) || '',
        style: (S.book && S.book.style) || '',
        human_flaws: store.json(KEY.ui, {}).humanFlaws !== false,
      },
    });
    const bits = [];
    if (r.engine === 'ai-struct') {
      if (r.baseline === 'author') bits.push(r.author ? `作家基准·${r.author}` : '题材基准');
      else if (r.baseline === 'genre') bits.push('题材基准');
      if (r.changed) bits.push(`改写 ${r.changed} 段`);
      if (r.reviewed) bits.push(`复核 ${r.reviewed} 段`);
    } else if (r.engine === 'struct' && r.removed) bits.push(`删了 ${r.removed} 句总结`);
    else if (r.changed) bits.push(`改 ${r.changed} 段`);
    const label = r.engine === 'local' ? '去 AI 味 · 本地清理'
      : r.engine === 'ai-scan' ? '去 AI 味 · 没扫到 AI 结构'
      : r.engine === 'ai-struct' ? `去 AI 味 · 改写+复核${bits.length ? ' · ' + bits.join(' · ') : ''}`
      : r.engine === 'struct' ? `去 AI 味 · 结构清理${bits.length ? ' · ' + bits.join(' · ') : ''}`
      : `去 AI 味 · 保文笔${bits.length ? ' · ' + bits.join(' · ') : ''}`;
    setAiResult(r.text || '', label, 'humanize');
    renderHumanizeDiff(r);
    if (r.warn) toast(r.warn);
  } catch (e) { setAiResult('处理失败：' + e.message, '错误', ''); }
}

/* ---------------- 随机取名（先选类别，再按细分生成） ---------------- */
const NAME_CATS = ['人物', '地名', '势力', '功法', '装备', '丹药', '妖兽', '招式', '称号', '杂项'];
const NAME_SCHEMA = {
  人物: [
    { key: 'gender', label: '性别', opts: ['随机', '男', '女'] },
    { key: 'style', label: '风格', opts: ['古风', '现代', '西幻', '日式'] },
    { key: 'surnameCount', label: '姓数', opts: ['随机', '单姓', '复姓'] },
    { key: 'surname', label: '指定姓氏', input: true, ph: '留空则随机' },
  ],
  地名: [{ key: 'subtype', label: '类型', opts: ['随机', '城池', '山川', '村落', '秘境', '关隘', '海域'] }],
  势力: [{ key: 'subtype', label: '类型', opts: ['随机', '宗门', '王朝', '帮派', '商会', '军队', '教会'] }],
  功法: [{ key: 'subtype', label: '类型', opts: ['随机', '内功心法', '剑诀', '剑意', '刀法', '拳经', '身法', '掌法', '丹经', '阵图', '神通'] }],
  装备: [{ key: 'subtype', label: '类型', opts: ['随机', '剑', '刀', '枪', '弓', '甲', '珠', '镜', '印', '钟', '幡', '琴', '冠'] }],
  丹药: [{ key: 'subtype', label: '类型', opts: ['随机'] }],
  妖兽: [{ key: 'subtype', label: '类型', opts: ['随机'] }],
  招式: [{ key: 'subtype', label: '类型', opts: ['随机'] }],
  称号: [{ key: 'subtype', label: '类型', opts: ['随机'] }],
  杂项: [{ key: 'subtype', label: '子类', opts: ['随机', '灵植', '阵法', '秘宝', '货币', '典籍', '器物', '任务'] }],
};
let NG = null;

function ngState() {
  if (!NG) NG = { cat: '人物', vals: {}, count: 14, names: [], engine: '', req: '' };
  NAME_CATS.forEach((c) => { if (!NG.vals[c]) NG.vals[c] = {}; });
  (NAME_SCHEMA[NG.cat] || []).forEach((f) => {
    const v = NG.vals[NG.cat];
    if (v[f.key] == null) v[f.key] = f.input ? '' : f.opts[0];
  });
  return NG;
}

function openNameGen() {
  const st = ngState();
  st.names = [];
  st.engine = '';
  renderNameGen();
  openModal('nameModal');
}

function renderNameGen() {
  const st = ngState();
  $('#ngCats').innerHTML = NAME_CATS.map((c) => `<button class="ng-cat${st.cat === c ? ' on' : ''}" data-ngcat="${c}">${c}</button>`).join('');
  const vals = st.vals[st.cat];
  const fields = (NAME_SCHEMA[st.cat] || []).filter((f) => f.input || f.opts.length > 1);
  $('#ngOpts').innerHTML = fields.map((f) => {
    if (f.input) {
      return `<div class="ng-row"><label>${esc(f.label)}</label><input class="ng-input" data-nginput="${f.key}" value="${esc(vals[f.key] || '')}" placeholder="${esc(f.ph || '')}"></div>`;
    }
    return `<div class="ng-row"><label>${esc(f.label)}</label><div class="ng-chips">${f.opts.map((o) => `<button class="ng-chip${vals[f.key] === o ? ' on' : ''}" data-ngopt="${f.key}" data-ngval="${esc(o)}">${esc(o)}</button>`).join('')}</div></div>`;
  }).join('');
  $('#ngCount').value = st.count;
  $('#ngCountVal').textContent = st.count;
  $('#ngReq').value = st.req || '';
  $('#ngEng').textContent = st.engine === 'ai' ? '本批由 AI 生成' : (st.engine === 'local' ? '本批由内置词库生成' : '');
  $('#ngResults').innerHTML = st.names.length
    ? st.names.map((n) => `<button class="ng-name" data-ngname="${esc(n)}">${esc(n)}</button>`).join('')
    : '<div class="ng-empty">先选类别，再点「生成」</div>';
}

async function runNameGen() {
  const st = ngState();
  const vals = st.vals[st.cat];
  const btn = $('#ngRun');
  if (btn) { btn.disabled = true; btn.textContent = '生成中…'; }
  try {
    const r = await api('/ai/names', {
      method: 'POST',
      body: {
        category: st.cat,
        subtype: vals.subtype || '随机',
        count: Number($('#ngCount').value) || 14,
        genre: (S.book && S.book.genre) || '',
        requirements: ($('#ngReq').value || '').trim(),
        exclude: st.names.slice(-40),
        gender: vals.gender || '随机',
        style: vals.style || '古风',
        surnameCount: vals.surnameCount || '随机',
        surname: vals.surname || '',
      },
    });
    st.engine = r.engine || '';
    const add = (r.names || []).filter((n) => !st.names.includes(n));
    st.names = st.names.concat(add).slice(0, 60);
    renderNameGen();
    if (!add.length) toast('没有新名字，可再点一次生成');
  } catch (e) {
    toast('生成失败：' + e.message);
  }
  if (btn) { btn.disabled = false; btn.textContent = '生成'; }
}

function aiNames() { openNameGen(); }

async function aiIdea() {
  if (!ensureApi() || !S.book) return;
  const f = currentFile();
  setAiLoading('卡文急救');
  try {
    const r = await api('/ai/idea', {
      method: 'POST',
      body: { ...bookContext(), title: f ? f.name : '', last: f ? (f.content || '').slice(-800) : '', outline: $('#outlineNote').value.trim() },
    });
    setAiResult(r.text || '', '三个「如果」 · AI', 'idea');
  } catch (e) { setAiResult('生成失败：' + e.message, '错误', ''); }
}

async function aiOutline() {
  if (!ensureApi() || !S.book) return;
  setAiLoading('生成全书大纲');
  try {
    const r = await api('/generate/outline', {
      method: 'POST',
      body: {
        ...bookContext(),
        chapter_count: S.book.chapter_count || 400,
        extra: $('#scratchNote').value.trim().slice(0, 200),
      },
    });
    setAiResult((r.outline && r.outline.macro) || '', '全书大纲 · AI', 'outline');
  } catch (e) { setAiResult('生成失败：' + e.message, '错误', ''); }
}

async function saveAiOutline() {
  if (!S.book || !S.lastAi.text) return;
  const outline = (typeof S.book.outline === 'object' && S.book.outline) ? { ...S.book.outline } : {};
  outline.macro = S.lastAi.text;
  await saveProjectFields({ outline });
  toast('已存为全书大纲');
}

async function aiConcept() {
  if (!ensureApi() || !S.book) return;
  setRightTab('world');
  $('#conceptSub').textContent = '生成中…';
  try {
    const r = await api('/generate/concept', {
      method: 'POST',
      body: {
        ...bookContext(),
        subgenre: S.book.subgenre || '',
        ref_author: S.book.ref_author || '',
        strategy: S.book.strategy || '',
        lang: S.book.lang || '',
        audience: S.book.audience || '',
        ending: S.book.ending || '',
        chapter_count: S.book.chapter_count || 400,
        words_per_chapter: S.book.words_per_chapter || 2500,
      },
    });
    await saveProjectFields({ concept: r.concept || {} });
    renderWorld();
    toast('核心概念已生成并保存');
  } catch (e) {
    $('#conceptSub').textContent = '生成失败';
    toast('生成失败：' + e.message);
  }
}


async function aiWorld() {
  if (!ensureApi() || !S.book) return;
  setAiLoading('生成世界观');
  try {
    const r = await api('/generate/world', { method: 'POST', body: { ...bookContext(), extra: '' } });
    await saveProjectFields({ world: r.world || {} });
    setAiResult((r.world && r.world.content) || '', '世界观 · AI', 'world');
    renderWorld();
  } catch (e) { setAiResult('生成失败：' + e.message, '错误', ''); }
}

function judgeParaSplit(t) {
  return paraSpans(t).map((p) => p.text);
}

function judgeJumpParagraph(idx) {
  const el = input();
  if (!el || !idx) return;
  const p = paraSpans(el.value || '')[idx - 1];
  if (!p) return;
  jumpToRange(p.start, p.end);
}

function judgeBand(v) {
  return v >= 68 ? 'high' : v >= 45 ? 'mid' : 'low';
}

function renderJudge(r) {
  const dims = (r.dimensions || []).map((d) => `<div class="jd-dim">
      <span class="jd-dim-name">${esc(d.name)}</span>
      <span class="jd-bar"><i class="${judgeBand(d.score)}" style="width:${Math.max(3, d.score)}%"></i></span>
      <b>${d.score}</b>
    </div>`).join('');
  const heat = (r.paragraphs || []).map((p) => `<button class="jd-cell ${judgeBand(p.score)}" data-jpara="${p.index}" title="第 ${p.index} 段 · ${p.score} 分 · ${esc(p.preview)}"></button>`).join('');
  const hot = (r.hot_paragraphs || []).map((p) => `<div class="jd-hot" data-jpara="${p.index}">
      <b>第 ${p.index} 段 · ${p.score}</b>
      <span>${esc(p.problem || p.preview)}</span>
    </div>`).join('');
  const reasons = (r.reasons || []).slice(0, 4).map((a) => `<li>${esc(a)}</li>`).join('');
  const advice = (r.advice || []).slice(0, 5).map((a) => `<li>${esc(a)}</li>`).join('');
  const sents = (r.sentences || []).filter((x) => x.score >= 30).slice(0, 5)
    .map((x) => `<div class="jd-hot" style="cursor:default"><b>${x.score} 分</b><span>${esc(x.text)}</span></div>`).join('');
  const s = r.stats || {};
  $('#judgeDetail').innerHTML = `
    ${r.verdict ? `<div class="jd-verdict">${esc(r.verdict)}</div>` : ''}
    <div class="jd-dims">${dims}</div>
    ${heat ? '<div class="jd-heat-label">段落热度 <span class="hint">点色块跳到那一段</span></div>' : ''}
    ${heat ? `<div class="jd-heat">${heat}</div>` : ''}
    ${hot ? `<div class="jd-sec"><h5>最像 AI 的段落</h5>${hot}</div>` : ''}
    ${sents ? `<div class="jd-sec"><h5>最像 AI 的句子</h5>${sents}</div>` : ''}
    ${reasons ? `<div class="jd-sec"><h5>问题</h5><ul>${reasons}</ul></div>` : ''}
    ${advice ? `<div class="jd-sec"><h5>怎么改</h5><ul>${advice}</ul></div>` : ''}
    <div class="jd-stats">${s.chars || 0} 字 · ${s.paragraphs || 0} 段 · 平均句长 ${s.avg_sentence || 0} · 句长波动 ${s.sentence_cv || 0} · 对话 ${s.dialogue_per_1000 || 0}/千字${r.model ? ` · 外部模型 ${esc(r.model.name)} ${r.model.score}%（最像 ${r.model.max}%）` : ''}</div>`;
  const eng = $('#judgeEngine');
  if (eng) eng.textContent = (r.engine === 'local+ai' ? '本地统计 + 模型复核'
    : r.engine === 'local+ai+model' ? '本地统计 + 模型复核 + AIGC模型'
      : r.engine === 'local+model' ? '本地统计 + AIGC模型' : '本地统计') + (r.cached ? ' · 已固定' : '');
}

async function judgeAi() {
  const text = input().value.trim();
  if (!text) { toast('正文还是空的'); return; }
  const btn = $('#judgeBtn');
  const label = btn ? btn.textContent : '';
  if (btn) { btn.disabled = true; btn.textContent = '检测中…'; }
  $('#judgeSeal').textContent = '…';
  $('#judgeTitle').textContent = '检测中';
  $('#judgeDesc').textContent = '五个维度统计 + 模型复核，约 10–30 秒…';
  try {
    const modeBtn = $('#judgeModeSeg .on');
    const r = await api('/ai/detect', {
      method: 'POST',
      body: { text, mode: modeBtn ? modeBtn.dataset.jmode : 'wen' },
    });
    $('#judgeSeal').textContent = String(r.ai_probability) + '%';
    $('#judgeTitle').textContent = r.grade || '—';
    $('#judgeDesc').textContent = r.recommendation || '';
    renderJudge(r);
  } catch (e) {
    $('#judgeSeal').textContent = '—';
    $('#judgeTitle').textContent = '检测失败';
    $('#judgeDesc').textContent = e.message;
    $('#judgeDetail').innerHTML = '';
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = label || '检测本章 AI 味'; }
  }
}

/* ---------------- 搭子聊天 ---------------- */
/* ---------------- 成人向模式（口令解锁一次，之后短语切换） ---------------- */
const ADULT_KEY = 'fj:adult';
const ADULT_CODE_HASH = 0x5354e7c0;

function fnv1a(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function adultState() {
  const st = store.json(ADULT_KEY, { unlocked: false, on: false });
  return { unlocked: !!st.unlocked, on: !!st.unlocked && !!st.on };
}

function saveAdult(st) {
  store.setJson(ADULT_KEY, st);
  renderChatMode();
}

function renderChatMode() {
  const on = adultState().on;
  document.body.classList.toggle('adult-mode', on);
  const badge = $('#chatMode');
  if (badge) badge.hidden = !on;
  const sub = $('#chatSub');
  if (sub) sub.textContent = on ? '成人向模式 · 仅限成年角色' : '已读全书设定、人物与章节，能替你跳转和开面板';
}

function handleAdultCommand(text) {
  const t = String(text || '').trim();
  if (!t) return false;
  const st = adultState();

  /* 1) 解锁口令：支持直接输入，或 “解锁 口令” / “/unlock 口令” */
  const raw = t.replace(/^[#/]?\s*(unlock|解锁)[:：\s]*/i, '');
  if (fnv1a(raw) === ADULT_CODE_HASH) {
    saveAdult({ unlocked: true, on: true });
    S.chat.push({ role: 'system', text: '口令正确，已进入成人向模式。硬性限制：涉及性描写的角色必须为成年人，禁止未成年、真实人物与非自愿情节。发送「退出色情模式」可退出。' });
    renderChat();
    saveChat();
    return true;
  }

  /* 2) 进入 */
  if (/进入(色情|成人)模式|开启(色情|成人)模式/.test(t)) {
    if (!st.unlocked) {
      S.chat.push({ role: 'system', text: '还没解锁：首次需要发送一次解锁口令，之后发「进入色情模式 / 退出色情模式」即可切换。' });
      renderChat();
      saveChat();
      return true;
    }
    saveAdult({ unlocked: true, on: true });
    S.chat.push({ role: 'system', text: '已切换到成人向模式。' });
    renderChat();
    saveChat();
    return true;
  }

  /* 3) 退出 */
  if (/退出(色情|成人)模式|关闭(色情|成人)模式/.test(t)) {
    saveAdult({ unlocked: st.unlocked, on: false });
    S.chat.push({ role: 'system', text: '已退出成人向模式，恢复常规写作。' });
    renderChat();
    saveChat();
    return true;
  }
  return false;
}

function chatSelection() {
  const el = input();
  if (!el) return '';
  return String(el.value.slice(el.selectionStart || 0, el.selectionEnd || 0) || '').trim();
}

function updateChatCtx() {
  const box = $('#chatCtx');
  if (!box) return;
  const f = currentFile();
  const bits = [];
  if (f) bits.push(`本章《${f.name}》${fmt(wordCount(f.content || ''))} 字`);
  const sel = chatSelection();
  if (sel) bits.push(`选中 ${fmt(wordCount(sel))} 字`);
  const o = (S.book && S.book.outline) || {};
  if (o.macro) bits.push('大纲');
  const people = Object.values((S.book && S.book.characters) || {}).reduce((n, arr) => n + (Array.isArray(arr) ? arr.length : 0), 0);
  if (people) bits.push(`人物 ${people}`);
  const concept = (S.book && S.book.concept) || {};
  if (concept.core) bits.push('核心设定');
  box.innerHTML = bits.length
    ? bits.map((b) => `<span class="chat-ctx-chip">${esc(b)}</span>`).join('')
    : '<span class="chat-ctx-chip">还没打开章节</span>';
}

function fmtChat(text) {
  let raw = String(text || '')
    .replace(/<(?:think|thinking|reasoning|analysis)>[\s\S]*?<\/(?:think|thinking|reasoning|analysis)>/gi, '')
    .replace(/^\s*(?:思考过程|思考|分析过程|分析|推理过程|推理)\s*[:：][\s\S]*?\n\s*\n/, '')
    .replace(/^\s*(?:最终回答|最终改写|改写结果|答案)\s*[:：]\s*/, '');
  let s = esc(raw);
  s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/^#{1,3}\s*(.+)$/gm, '<strong>$1</strong>');
  /* Shannon 取回的落盘文件，做成能点的下载链接 */
  s = s.replace(/\[([^\]\n]{1,60})\]\((\/api\/shannon\/files\/[^)\s]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  s = s.replace(/(https?:\/\/[^\s<]+|\/api\/shannon\/files\/[^\s<>"']+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
  return s;
}

function renderChat() {
  const log = $('#chatLog');
  log.innerHTML = S.chat.length ? S.chat.map((m, i) => {
    if (m.role === 'user') return `<div class="chat-line me">
      <div class="chat-msg me"><div class="chat-body">${esc(m.text)}</div></div>
      <div class="chat-tools">
        <button class="chat-tool" data-cact="retract" data-i="${i}">撤回</button>
        <button class="chat-tool" data-cact="edit" data-i="${i}">编辑</button>
      </div>
    </div>`;
    if (m.role === 'system') return `<div class="chat-msg sys">${esc(m.text)}</div>`;
    const tgt = (m.target && m.target.confident && m.target.id && m.target.id !== m.ch) ? m.target.name : '';
    return `<div class="chat-msg ai">
      <div class="chat-body">${fmtChat(m.text)}</div>
      ${(m.reads && m.reads.length) ? `<div class="chat-did"><span>已读 ${m.reads.map((x) => esc(x)).join('、')}</span></div>` : ''}
      ${(m.deai && m.deai.rounds) ? `<div class="chat-did"><span>人味改写 ${m.deai.rounds} 轮${m.deai.score != null ? ' · ' + m.deai.score + ' 分' : ''}</span></div>` : ''}
      ${tgt ? `<div class="chat-did"><span>这段稿子属「${esc(tgt)}」</span></div>` : ''}
      ${(m.updates && m.updates.length) ? `<div class="chat-did">${m.updates.map((u) => `<span>已改 ${esc(u.label)}</span>`).join('')}</div>` : ''}
      ${(m.edits && m.edits.length) ? `<div class="chat-did"><span>已改正文 ${m.edits.length} 处${m.edit_chapter && m.edit_chapter.name ? ' · ' + esc(m.edit_chapter.name) : ''}</span></div>` : ''}
      ${(m.acts && m.acts.length) ? `<div class="chat-did">${m.acts.map((a) => `<span>${esc(a)}</span>`).join('')}</div>` : ''}
      <div class="chat-acts">
        <button class="chat-act" data-cact="insert" data-i="${i}">融入正文</button>
        <button class="chat-act" data-cact="copy" data-i="${i}">复制</button>
      </div>
    </div>`;
  }).join('') : '<div class="chat-msg sys">把卡点、想写的桥段、要改的段落丢进来，它读的是这本书的设定和大纲。</div>';
  scrollChat();
  updateChatCtx();
  renderChatMode();
}
function scrollChat() { const log = $('#chatLog'); if (log) log.scrollTop = log.scrollHeight; }
/* ---------------- 搭子：多对话与历史 ---------------- */
function newConvId() { return 'cv_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }

function loadConversations(name) {
  const saved = store.json(KEY.convs(name), null);
  let list = (saved && Array.isArray(saved.list))
    ? saved.list.filter((c) => c && c.id && Array.isArray(c.msgs)) : [];
  if (!list.length) {
    const old = store.json(KEY.chat(name), []);
    list = [{ id: newConvId(), title: '', ts: Date.now(), msgs: Array.isArray(old) ? old.slice(-60) : [] }];
  }
  const active = (saved && list.some((c) => c.id === saved.active)) ? saved.active : list[0].id;
  S.convs = { active, list };
  S.chat = (list.find((c) => c.id === active) || list[0]).msgs;
}

function convTitle(c) {
  if (!c) return '新对话';
  if (c.title) return c.title;
  const u = (c.msgs || []).find((m) => m.role === 'user');
  const t = u ? String(u.text || '').trim().replace(/\s+/g, ' ') : '';
  return t ? (t.length > 18 ? t.slice(0, 18) + '…' : t) : '新对话';
}

function saveConvs() {
  if (!S.book || !S.convs) return;
  const cur = S.convs.list.find((c) => c.id === S.convs.active);
  if (cur) cur.ts = Date.now();
  if (cur && cur.msgs !== S.chat) {
    /* 原地替换，别换数组：切换对话时可能还有请求在往旧数组里写 */
    const keep = S.chat.slice(-60);
    cur.msgs.length = 0;
    cur.msgs.push(...keep);
  }
  store.setJson(KEY.convs(S.book.name), S.convs);
}

function saveChat() { saveConvs(); }

function newConversation() {
  if (!S.book || !S.convs) return;
  if (!S.chat.length) {
    const b = $('#chatInput');
    if (b) b.focus();
    return;
  }
  const c = { id: newConvId(), title: '', ts: Date.now(), msgs: [] };
  S.convs.list.unshift(c);
  S.convs.active = c.id;
  S.chat = c.msgs;
  saveConvs();
  renderChat();
  const b = $('#chatInput');
  if (b) { b.focus(); autoGrow(b, 150); }
  toast('新对话');
}

function switchConversation(id) {
  if (!S.convs) return;
  const c = S.convs.list.find((x) => x.id === id);
  if (!c || c.id === S.convs.active) return;
  saveConvs();
  S.convs.active = id;
  S.chat = c.msgs;
  saveConvs();
  renderChat();
  scrollChat();
}

async function deleteConversation(id) {
  if (!S.convs) return;
  const ok = await askConfirm('删除对话', '只删这段聊天记录，不动正文。', '删除');
  if (!ok) return;
  S.convs.list = S.convs.list.filter((x) => x.id !== id);
  if (!S.convs.list.length) S.convs.list.push({ id: newConvId(), title: '', ts: Date.now(), msgs: [] });
  if (!S.convs.list.some((x) => x.id === S.convs.active)) {
    S.convs.active = S.convs.list[0].id;
    S.chat = S.convs.list[0].msgs;
  }
  saveConvs();
  renderChat();
}

function openConvHistory(anchor) {
  if (!S.convs) return;
  const items = S.convs.list.slice().sort((a, b) => (b.ts || 0) - (a.ts || 0)).map((c) => ({
    label: convTitle(c),
    note: `${(c.msgs || []).length} 条`,
    current: c.id === S.convs.active,
    action: () => switchConversation(c.id),
  }));
  items.push({ sep: true });
  items.push({ label: '新建对话', action: () => newConversation() });
  if (S.convs.list.length > 1) {
    items.push({ label: '删除当前对话', danger: true, action: () => deleteConversation(S.convs.active) });
  }
  showMenu(anchor, items);
}

/* 撤回 / 编辑：截到这条提问之前，把原话放回输入框 */
async function retractQuestion(i) {
  const msg = S.chat[i];
  if (!msg || msg.role !== 'user') return;
  const text = String(msg.text || '');
  const removed = S.chat.slice(i);
  S.chat.splice(i);
  saveConvs();
  renderChat();
  const box = $('#chatInput');
  if (box) {
    box.value = text;
    autoGrow(box, 150);
    box.focus();
    box.setSelectionRange(text.length, text.length);
  }
  toast('已撤回，改完再发');
  try {
    const r = await undoChatEffects(removed);
    if (r && (r.chapterN || r.projectN)) {
      const bits = [];
      if (r.chapterN) bits.push(`正文 ${r.chapterN} 处`);
      if (r.projectN) bits.push(`设置 ${r.projectN} 项`);
      toast('已一并撤回改动：' + bits.join('、') + (r.skipped ? `（${r.skipped} 处后来又被改过，已保留）` : ''));
    }
  } catch (e) { /* 撤回改动失败不阻断撤回提问 */ }
}

/* 局域网 http 下没有 navigator.clipboard，退回 execCommand */
async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) { /* fallthrough */ }
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch (e) {
    return false;
  }
}

let chatBusy = false;

const STUDIO_MOD_NAME = {
  project: '项目', concept: '概念', world: '世界观', characters: '人物',
  outline: '大纲', writing: '正文', script: '剧本', toolbox: '工具箱',
};
const PANEL_NAME = { note: '便签', world: '设定', ai: '灵感', check: '自检', companion: '搭子' };
const THEME_ALIAS = {
  paper: 'paper', 日间: 'paper', 白天: 'paper', 浅色: 'paper', 明亮: 'paper', 白: 'paper',
  eye: 'eye', 护眼: 'eye', 绿色: 'eye', 淡绿: 'eye',
  night: 'night', 夜间: 'night', 夜晚: 'night', 暗色: 'night', 深色: 'night', 黑夜: 'night', 暗: 'night',
};
const THEME_NAME = { paper: '日间', eye: '护眼', night: '夜间' };
const PAPER_ALIAS = {
  plain: 'plain', 素白: 'plain', 白纸: 'plain', 纯白: 'plain',
  rice: 'rice', 米黄: 'rice', 米色: 'rice', 暖黄: 'rice',
  grid: 'grid', 格线: 'grid', 格子: 'grid', 方格: 'grid',
};
const PAPER_NAME = { plain: '素白', rice: '米黄', grid: '格线' };

function chatNav(name) {
  const a = document.querySelector(`.ml-nav a[data-nav="${name}"]`);
  if (a) a.click();
}

/* 执行搭子给的动作：跳转、开面板、换主题、跳章节 */
function chatRunActions(actions) {
  const done = [];
  (Array.isArray(actions) ? actions : []).slice(0, 3).forEach((a) => {
    const kind = String(a.do || a.type || '').toLowerCase();
    try {
      if (kind === 'open') {
        const target = String(a.target || a.to || '').toLowerCase();
        if (target === 'studio' || target === 'ai') {
          const mod = String(a.module || a.mod || 'concept').toLowerCase();
          chatNav('ai');
          if (window.Studio) window.Studio.open(mod);
          done.push('已打开 AI 工坊 · ' + (STUDIO_MOD_NAME[mod] || mod));
        } else if (target === 'writer') { chatNav('writer'); done.push('已回到写作台'); }
        else if (target === 'library') { chatNav('library'); done.push('已打开书架'); }
        else if (target === 'settings') { chatNav('settings'); done.push('已打开设置'); }
        else if (target === 'review' || target === 'check') { chatNav('review'); done.push('已打开自检'); }
      } else if (kind === 'theme') {
        const raw = String(a.set || a.value || a.theme || '').trim();
        const theme = THEME_ALIAS[raw] || THEME_ALIAS[raw.toLowerCase()] || '';
        if (theme) {
          setUi({ theme });
          done.push('已切换主题 · ' + THEME_NAME[theme]);
        } else {
          openModal('bgModal');
          done.push('已打开背景与主题');
        }
      } else if (kind === 'paper') {
        const raw = String(a.set || a.value || a.paper || '').trim();
        const paper = PAPER_ALIAS[raw] || PAPER_ALIAS[raw.toLowerCase()] || '';
        if (paper) {
          setUi({ paper });
          done.push('已换纸面 · ' + PAPER_NAME[paper]);
        } else {
          openModal('bgModal');
          done.push('已打开背景与主题');
        }
      } else if (kind === 'chapter') {
        const title = String(a.title || a.chapter || '');
        const f = S.files.find((x) => x.type === 'FILE' && title && (x.name === title || x.name.includes(title)));
        if (f) { openChapter(f.id); done.push('已跳到' + f.name); }
      } else if (kind === 'panel') {
        const tab = String(a.tab || 'check');
        setRightTab(tab);
        done.push('已切到右栏 · ' + (PANEL_NAME[tab] || tab));
      }
    } catch (e) { /* 单个动作失败不影响回答 */ }
  });
  return done;
}

async function sendChat(prefill) {
  if (chatBusy) return;
  if (!ensureApi()) return;
  const box = $('#chatInput');
  const text = (prefill || box.value).trim();
  if (!text) return;
  box.value = '';
  autoGrow(box, 150);
  if (handleAdultCommand(text)) return;
  const selection = chatSelection();
  /* 记下这次提问时的选中段与光标，回复要融进正文时按它定位 */
  const selSnap = selection.slice(0, 3000);
  const chSnap = S.chapterId || '';
  const elSnap = input();
  const curSnap = elSnap
    ? { id: chSnap, start: elSnap.selectionStart || 0, end: elSnap.selectionEnd || 0 }
    : null;
  /* 锁住这一次提问所属的对话：中途切换对话，回复也不能落到新对话里 */
  const chat = S.chat;
  const convId = S.convs ? S.convs.active : null;
  chat.push({ role: 'user', text });
  renderChat();
  saveChat();

  chatBusy = true;
  const log = $('#chatLog');
  const fetching = /https?:\/\//.test(text);
  const pendingLabel = fetching ? '正在取数' : '正在读稿';
  const pending = document.createElement('div');
  pending.className = 'chat-msg ai pending';
  pending.innerHTML = `<span class="chat-dots">${pendingLabel} · 0s</span>`;
  log.appendChild(pending);
  scrollChat();
  const t0 = Date.now();
  const timer = setInterval(() => {
    pending.innerHTML = `<span class="chat-dots">${pendingLabel} · ${Math.round((Date.now() - t0) / 1000)}s</span>`;
  }, 1000);

  try {
    const history = chat.slice(-13, -1).map((m) => ({ role: m.role === 'user' ? 'user' : 'model', text: m.text }));
    const r = await api('/agent/chat', {
      method: 'POST',
      body: {
        project_name: S.book ? S.book.name : '',
        chapter_id: S.chapterId || '',
        chapter_text: elSnap ? String(elSnap.value || '').slice(0, 60000) : '',
        selection,
        messages: history,
        user_message: text,
        adult: adultState().on,
        human_flaws: store.json(KEY.ui, {}).humanFlaws !== false,
      },
    });
    const reply = String(r.response || '').replace(/<act>[\s\S]*?<\/act>/g, '').trim() || '（没有返回内容）';
    const acted = chatRunActions(r.actions);
    /* 先记下改动前的值，撤回这条提问时按原值退回去 */
    const undoProj = (r.updates || []).map((u) => ({
      t: 'project', path: u.path,
      before: getPath(S.book, String(u.path || '').split('.')),
      after: u.value,
    }));
    chat.push({ role: 'model', text: reply, sel: selSnap, ch: chSnap, cur: curSnap,
                acts: acted, actions: r.actions || [], reads: r.reads || [],
                target: r.target || null, updates: r.updates || [], undo: undoProj,
                edits: r.edits || [], edit_chapter: r.edit_chapter || null,
                deai: r.deai || null });
    if (r.updates && r.updates.length) await applyProjectUpdates(r.updates);
    pending.remove();
    if (!S.convs || S.convs.active === convId) renderChat();
    /* 搭子在编辑框里直接改正文：当着用户的面一个字一个字敲 */
    if (r.edits && r.edits.length && (!S.convs || S.convs.active === convId)) {
      await runChapterEdits(chat[chat.length - 1], r);
    }
    if (r.context && r.context.chapter && !(r.edits && r.edits.length)) {
      const bits = [r.context.chapter];
      if (r.context.chapters_total) bits.push(`全书 ${r.context.chapters_total} 章`);
      if (r.context.people) bits.push(`人物 ${r.context.people}`);
      if (r.context.has_selection) bits.push('选中段');
      toast('已读：' + bits.join(' · '));
    }
    if (r.updates && r.updates.length) toast('已改：' + r.updates.map(u => u.label).join('、'));
    if (acted && acted.length) toast(acted.join(' · '));
  } catch (e) {
    pending.remove();
    chat.push({ role: 'system', text: '出错：' + e.message });
    if (!S.convs || S.convs.active === convId) renderChat();
  }
  clearInterval(timer);
  chatBusy = false;
  saveChat();
  updateChatCtx();
}

function enterFocus() {
  document.body.classList.add('focus-on');
}
function exitFocus() {
  rmClose();
  document.body.classList.remove('focus-on');
}

/* ================= 阅读模式：全文多人有声剧 ================= */
/* 选角逻辑参照开源项目 talebook/voicebook：角色表 → 性别 / 年龄段 / 气质 → 固定音色。
   旁白一种播音腔；每个角色一个固定音色；男女老少各用不同音色与音高语速区分。
   整章合成为一个 mp3（服务端拼接并回传每段时长），播放时按时间轴高亮台词。 */

const RM_VOICE_META = {
  'zh-CN-YunyangNeural': { name: '云扬', sex: 'm', age: '中年', tag: '播音沉稳' },
  'zh-CN-YunjianNeural': { name: '云健', sex: 'm', age: '中年', tag: '浑厚有力' },
  'zh-CN-YunxiNeural': { name: '云希', sex: 'm', age: '青年', tag: '青年明亮' },
  'zh-CN-YunxiaNeural': { name: '云夏', sex: 'm', age: '少年', tag: '软糯童声' },
  'zh-TW-YunJheNeural': { name: '云哲', sex: 'm', age: '青年', tag: '台湾青年' },
  'zh-HK-WanLungNeural': { name: '云龙', sex: 'm', age: '中年', tag: '港腔男声' },
  'zh-CN-XiaoxiaoNeural': { name: '晓晓', sex: 'f', age: '中年', tag: '温润知性' },
  'zh-CN-XiaoyiNeural': { name: '晓伊', sex: 'f', age: '少女', tag: '少女活泼' },
  'zh-CN-liaoning-XiaobeiNeural': { name: '晓北', sex: 'f', age: '青年', tag: '东北爽朗' },
  'zh-CN-shaanxi-XiaoniNeural': { name: '晓妮', sex: 'f', age: '青年', tag: '陕西俏皮' },
  'zh-TW-HsiaoChenNeural': { name: '晓臻', sex: 'f', age: '中年', tag: '台湾柔声' },
  'zh-TW-HsiaoYuNeural': { name: '晓雨', sex: 'f', age: '少女', tag: '台湾甜声' },
  'zh-HK-HiuMaanNeural': { name: '晓曼', sex: 'f', age: '青年', tag: '港腔女声' },
  'zh-HK-HiuGaaiNeural': { name: '晓佳', sex: 'f', age: '中年', tag: '港腔柔声' },
};

/* 角色原型：音色 + 音高 / 语速 / 音量（Hz、百分比、百分比） */
const RM_ARCH = {
  narrator: { voice: 'zh-CN-YunyangNeural', rate: -4, pitch: 0, vol: 0 },
  old_m: { voice: 'zh-CN-YunjianNeural', rate: -24, pitch: -16, vol: -4 },
  old_f: { voice: 'zh-CN-XiaoxiaoNeural', rate: -22, pitch: -12, vol: -4 },
  mid_m: { voice: 'zh-CN-YunjianNeural', rate: -8, pitch: -4, vol: 0 },
  mid_f: { voice: 'zh-CN-XiaoxiaoNeural', rate: -8, pitch: -2, vol: 0 },
  young_m: { voice: 'zh-CN-YunxiNeural', rate: 0, pitch: 2, vol: 0 },
  young_f: { voice: 'zh-CN-XiaoyiNeural', rate: 0, pitch: 4, vol: 0 },
  teen_m: { voice: 'zh-CN-YunxiaNeural', rate: 2, pitch: 10, vol: 2 },
  teen_f: { voice: 'zh-CN-XiaoyiNeural', rate: 4, pitch: 14, vol: 2 },
  child_m: { voice: 'zh-CN-YunxiaNeural', rate: 2, pitch: 18, vol: 4 },
  child_f: { voice: 'zh-CN-XiaoyiNeural', rate: 4, pitch: 22, vol: 4 },
  rough_m: { voice: 'zh-CN-YunjianNeural', rate: 6, pitch: -10, vol: 8 },
  villain_m: { voice: 'zh-CN-YunjianNeural', rate: -12, pitch: -8, vol: 4 },
  villain_f: { voice: 'zh-CN-XiaoxiaoNeural', rate: -12, pitch: -6, vol: 2 },
  gentle_f: { voice: 'zh-CN-XiaoxiaoNeural', rate: -10, pitch: 2, vol: 0 },
  witty_f: { voice: 'zh-CN-liaoning-XiaobeiNeural', rate: 0, pitch: 2, vol: 2 },
  witty_m: { voice: 'zh-TW-YunJheNeural', rate: 0, pitch: 0, vol: 0 },
  crowd: { voice: 'zh-CN-YunjianNeural', rate: -6, pitch: -6, vol: -2 },
};

/* 同一年龄层里可替换的音色（保证不同角色绝不撞音） */
const RM_POOL = {
  old_m: ['zh-CN-YunjianNeural', 'zh-HK-WanLungNeural'],
  old_f: ['zh-CN-XiaoxiaoNeural', 'zh-HK-HiuGaaiNeural'],
  mid_m: ['zh-CN-YunjianNeural', 'zh-CN-YunyangNeural', 'zh-HK-WanLungNeural'],
  mid_f: ['zh-CN-XiaoxiaoNeural', 'zh-TW-HsiaoChenNeural', 'zh-HK-HiuGaaiNeural'],
  young_m: ['zh-CN-YunxiNeural', 'zh-TW-YunJheNeural'],
  young_f: ['zh-CN-XiaoyiNeural', 'zh-TW-HsiaoYuNeural', 'zh-HK-HiuMaanNeural', 'zh-CN-liaoning-XiaobeiNeural', 'zh-CN-shaanxi-XiaoniNeural'],
  teen_m: ['zh-CN-YunxiaNeural', 'zh-CN-YunxiNeural'],
  teen_f: ['zh-CN-XiaoyiNeural', 'zh-TW-HsiaoYuNeural', 'zh-HK-HiuMaanNeural', 'zh-CN-liaoning-XiaobeiNeural'],
  child_m: ['zh-CN-YunxiaNeural'],
  child_f: ['zh-CN-XiaoyiNeural'],
  rough_m: ['zh-CN-YunjianNeural', 'zh-HK-WanLungNeural'],
  villain_m: ['zh-CN-YunjianNeural', 'zh-HK-WanLungNeural'],
  villain_f: ['zh-CN-XiaoxiaoNeural', 'zh-HK-HiuGaaiNeural'],
  gentle_f: ['zh-CN-XiaoxiaoNeural', 'zh-TW-HsiaoChenNeural'],
  witty_f: ['zh-CN-liaoning-XiaobeiNeural', 'zh-CN-shaanxi-XiaoniNeural'],
  witty_m: ['zh-TW-YunJheNeural', 'zh-CN-YunxiNeural'],
  crowd: ['zh-CN-YunjianNeural', 'zh-HK-WanLungNeural'],
};

const RM = {
  all: [], chapters: [], cache: new Map(), audio: null, playing: false, token: 0,
  cur: -1, mode: 'drama', rate: '+0%', mix: 'auto', resolver: null, noServer: false, cast: new Map(),
  dict: null, dictBook: '', pov: '', povAt: '',
};

function rmEsc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}
function rmHint(t) { const h = $('#rmHint'); if (h) h.textContent = t || ''; }

/* ---- 角色画像 ---- */
const RM_RE = {
  old: /老|年迈|苍老|白发|花甲|古稀|七旬|八旬|九旬|皱纹|佝偻|拐杖|老汉|老妇|婆婆|公公|太爷|老太太|老爷子|长老|翁|叟|妪/,
  child: /孩童|孩子|小童|稚子|娃娃|七岁|八岁|九岁|十岁|垂髫|总角|幼童|小娃/,
  teen: /少年|少女|十五六|十六七|十七八|十四五|及笄|束发|豆蔻|丫头|丫鬟/,
  female: /女|她|姑娘|少女|妇人|夫人|小姐|丫头|婆|嫂|姐|妹|母|妃|后|公主|姑|奶|侍女|妇|妪|娘|媚|柔/,
  male: /男|他|少年|男子|汉子|公子|少爷|老爷|大人|先生|将军|将士|父|兄|弟|叔|伯|爷|僧|道|侠|客|汉/,
};

function rmHash(s) {
  let h = 0;
  for (let i = 0; i < String(s).length; i++) h = (h * 31 + String(s).charCodeAt(i)) >>> 0;
  return h;
}

const RM_CN = { 零: 0, 一: 1, 二: 2, 两: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10, 廿: 20, 卅: 30 };

function rmCnNum(s) {
  if (!s) return 0;
  if (s.length === 1) return RM_CN[s] || 0;
  if (s[0] === '十') return 10 + (RM_CN[s[1]] || 0);
  if (s.includes('十')) {
    const [a, b] = s.split('十');
    return (RM_CN[a] || 1) * 10 + (RM_CN[b] || 0);
  }
  return RM_CN[s[0]] || 0;
}

/* 把「十三四岁 / 十六七岁 / 二十上下 / 三十五」转成年龄区间 */
function rmAgeBucket(str) {
  const s = String(str || '');
  if (!s) return '';
  const ar = s.match(/(\d{1,3})\s*(?:岁|周岁|出头|有余|上下|左右)?/);
  let n = ar ? parseInt(ar[1], 10) : 0;
  if (!n) {
    const cn = s.match(/([一二三四五六七八九十廿卅]{1,3})\s*岁/);
    if (cn) n = rmCnNum(cn[1]);
    else {
      const cn2 = s.match(/([一二三四五六七八九十廿卅]{1,3})(?:上下|出头|有余|左右|来岁|多岁|许)/);
      if (cn2) n = rmCnNum(cn2[1]);
    }
  }
  if (/老年|年迈|花甲|古稀|花白|晚年|年过半百|五旬|六旬|七旬|八旬/.test(s)) n = Math.max(n, 60);
  if (/中年|不惑|知天命|四旬|半百/.test(s)) n = n || 45;
  if (/少年|少女|及笄|束发|豆蔻/.test(s)) n = n || 15;
  if (/幼|孩童|稚/.test(s)) n = n || 6;
  if (!n) return '';
  if (n <= 12) return 'child';
  if (n <= 18) return 'teen';
  if (n <= 35) return 'young';
  if (n <= 55) return 'mid';
  return 'old';
}

function rmTrait(label, text, group, meta) {
  const t = String(label || '') + ' ' + String(text || '');
  let sex = '';
  if (meta && meta.gender) {
    if (/女|雌|姑娘|妇/.test(meta.gender)) sex = 'f';
    else if (/男|雄|少年/.test(meta.gender)) sex = 'm';
  }
  if (!sex) {
    /* 身份词直接定性别 */
    if (/老汉|老翁|公公|老头|老爷子|大伯|大叔|兄长|汉子|公子|少年|男子|士兵|兵|将军|掌柜|僧|道|侠|甲/.test(label)) sex = 'm';
    else if (/老妇|婆婆|老太太|妇人|女子|姑娘|少女|丫头|嫂子|夫人|娘|姐|妹|婢|妃/.test(label)) sex = 'f';
  }
  if (!sex) {
    let fem = 0, masc = 0;
    if (RM_RE.female.test(t)) fem += 2;
    if (RM_RE.male.test(t)) masc += 2;
    if (label) { if (RM_RE.female.test(label)) fem += 3; if (RM_RE.male.test(label)) masc += 3; }
    sex = fem > masc ? 'f' : (masc > fem ? 'm' : (rmHash(label) % 2 ? 'f' : 'm'));
  }
  let age = meta ? rmAgeBucket(meta.age) : '';
  if (!age) {
    if (RM_RE.old.test(t)) age = 'old';
    else if (RM_RE.child.test(t)) age = 'child';
    else if (RM_RE.teen.test(t)) age = 'teen';
    else age = 'mid';
  }
  return { sex, age, group: group || '' };
}

function rmArchetype(t) {
  if (t.age === 'old') return t.sex === 'f' ? 'old_f' : 'old_m';
  if (t.age === 'child') return t.sex === 'f' ? 'child_f' : 'child_m';
  if (t.age === 'teen') return t.sex === 'f' ? 'teen_f' : 'teen_m';
  if (t.sex === 'f') {
    if (t.group === '反派') return 'villain_f';
    if (/泼辣|爽利|爽朗|江湖|侠女|刀马|东北|陕西/.test(t.tone || '')) return 'witty_f';
    if (/温婉|柔弱|端庄|大家闺秀|闺秀/.test(t.tone || '')) return 'gentle_f';
    return 'young_f';
  }
  if (t.group === '反派') return 'villain_m';
  if (/粗豪|莽|壮|汉|刀客|江湖|匪|兵|屠/.test(t.tone || '')) return 'rough_m';
  return 'young_m';
}

function rmCharDict() {
  if (RM.dict && RM.dictBook === (S.book && S.book.name)) return RM.dict;
  const dict = [];
  const chars = (S.book && S.book.characters) || {};
  Object.keys(chars).forEach((g) => {
    (chars[g] || []).forEach((c) => {
      const o = typeof c === 'string' ? { name: c } : (c || {});
      if (!o.name) return;
      const text = [o.role, o.identity, o.desc, o.tagline, o.intro, o.personality, o.appearance, (o.purpose || []).join(' ')]
        .filter(Boolean).join(' ');
      dict.push({
        name: o.name, aliases: o.aliases || [], group: g, text,
        gender: o.gender || '', age: o.age || '',
      });
    });
  });
  RM.dict = dict;
  RM.dictBook = (S.book && S.book.name) || '';
  return dict;
}

/* 第一人称「我」对应的主角（角色卡「主角」组优先，否则本章提及最多的人名） */
function rmProtagonist(text) {
  const t = String(text || '');
  if (RM.povAt === t) return RM.pov;
  RM.povAt = t;
  RM.pov = '';
  if (!/我/.test(t)) return '';
  const dict = rmCharDict();
  const lead = dict.find((c) => /主角|主人公/.test(c.group || ''));
  let name = lead ? lead.name : '';
  if (!name) {
    let best = '', cnt = 0;
    dict.forEach((c) => {
      let n = t.split(c.name).length - 1;
      (c.aliases || []).forEach((al) => { n += t.split(al).length - 1; });
      if (n > cnt) { cnt = n; best = c.name; }
    });
    name = best;
  }
  RM.pov = name;
  return name;
}

/* ---- 文本切段 ---- */
function rmSentences(txt) {
  const out = [];
  let cur = '';
  let inQ = false;
  const s = String(txt || '');
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    cur += ch;
    if ('「“『'.includes(ch)) inQ = true;
    else if ('」”』'.includes(ch)) inQ = false;
    if (!inQ && '。！？!?；;'.includes(ch)) {
      const t = cur.trim();
      if (t) out.push(t);
      cur = '';
    }
  }
  if (cur.trim()) out.push(cur.trim());
  /* 合并纯标点段 */
  const merged = [];
  out.forEach((t) => {
    if (/^[。！？!?；;…—～\s]+$/.test(t) && merged.length) merged[merged.length - 1] += t;
    else merged.push(t);
  });
  return merged.filter((t) => t.replace(/[\s…—～]/g, '').length > 0);
}

const RM_ADV = '(?:低声|轻声|沉声|冷声|厉声|颤声|笑着|冷笑|怒|急|连忙|缓缓|淡淡|咬牙|叹|又|才|便|就|终于|忽然|突然|开口|接着|继续)?';
const RM_VERB = '(?:说道|说着|说|道|问道|问|答道|答|喊道|喊|叫道|叫|骂道|骂|笑道|笑|喝道|喝|嘀咕|嚷|开口|回应|低吼)';

/* 从「X 说 / X 道 / X 的声音 / X 压低声音」里抽说话人，取最后一个匹配 */
function rmSpeakersIn(txt) {
  const s = String(txt || '');
  /* 先认角色卡里的姓名 / 别名，最后一个出场的赢 */
  const dict = rmCharDict();
  const names = [];
  dict.forEach((c) => {
    names.push({ n: c.name, k: c.name });
    (c.aliases || []).forEach((al) => { if (al) names.push({ n: al, k: c.name }); });
  });
  names.sort((a, b) => b.n.length - a.n.length);
  const hits = [];
  names.forEach((x) => {
    let idx = s.indexOf(x.n);
    while (idx >= 0) {
      hits.push({ idx, key: x.k });
      idx = s.indexOf(x.n, idx + 1);
    }
  });
  if (hits.length) {
    hits.sort((a, b) => b.idx - a.idx);
    return [hits[0].key];
  }
  /* 再认身份词 */
  const roles = ['老汉', '老妇人', '老妇', '老太太', '老爷子', '老翁', '少年', '少女', '妇人', '汉子',
    '姑娘', '婆婆', '公公', '公子', '掌柜', '银甲人', '士兵', '众人', '小二', '车夫'];
  const ridx = roles
    .map((r) => ({ r, i: s.lastIndexOf(r) }))
    .filter((x) => x.i >= 0)
    .sort((a, b) => b.i - a.i);
  if (ridx.length) return [ridx[0].r];
  /* 最后用「X 说 / X 道」泛化匹配（严格过滤，避免抓到句子碎片） */
  const re = new RegExp(`([\\u4e00-\\u9fa5]{2,4})\\s*(?:[，,、]?\\s*${RM_ADV}\\s*)${RM_VERB}`, 'g');
  const bad = /[的了着过是在又还便就都也才再很太更最这那他她它您你咱俺们么呢吧啊呀哦吗轻声劝说叹息想看听走笑转伸抬低沉缓咬抓握]|^[一二三四五六七八九十]|人|事|声|话|手|眼|口|头|身|心|地|吃|喝|坐|站|默|静|上|下|前|后|里|外|之|其|所|被|把|让|给|向|从|对|和|与|的/;
  const out = [];
  let m;
  while ((m = re.exec(s)) !== null) {
    let n = m[1].replace(/^(于是|然后|只是|但是|可是|不过|因此|所以|这时|那时|只见|随后|紧接着)+/, '');
    if (!n || n.length < 2 || bad.test(n)) continue;
    out.push(n);
  }
  return out;
}

function rmBuildAll() {
  RM.all = [];
  RM.chapters = [];
  rmReadChapters().forEach((c, ci) => {
    const start = RM.all.length;
    RM.all.push({ text: c.name, kind: 'chapter', who: '', br: true, ch: ci, mood: { rate: 0, pitch: 0, vol: 0 } });
    rmParseText(c.text, ci, RM.all);
    RM.chapters.push({ name: c.name, start, end: RM.all.length });
  });
}

function rmReadChapters() {
  const scope = $('#rmScope') ? $('#rmScope').value : 'chapter';
  const out = [];
  const f = currentFile();
  if (scope === 'book' && S.book) {
    S.files.filter((x) => x.type === 'FILE').forEach((x) => {
      const body = (f && x.id === f.id) ? (input().value || '') : (x.content || '');
      if (body && body.trim()) out.push({ name: x.name, text: body });
    });
  } else if (f) {
    out.push({ name: f.name, text: input().value || '' });
  }
  return out;
}

function rmParseText(text, ci, out) {
  const ctx = { lastDlg: '', lastDlg2: '', pending: '', pov: rmProtagonist(text), nextWho: '', narLast: '' };
  const lines = String(text || '').replace(/\r/g, '').split('\n');
  lines.forEach((raw, li) => {
    const line = raw.replace(/^[\s　]+|[\s　]+$/g, '');
    if (!line) return;
    /* 台词独占一行时，后一行「X 的声音…/X 压低声音」可决定归属 */
    let nxt = '';
    for (let k = li + 1; k < lines.length && k <= li + 3; k += 1) {
      const t = (lines[k] || '').replace(/^[\s　]+|[\s　]+$/g, '');
      if (t) { nxt = t; break; }
    }
    ctx.nextWho = rmLeadSpeaker(nxt);
    rmParseLine(line, ci, out, ctx);
  });
}

/* 句首出现角色名 + 说话动作 → 归属上一句台词 */
function rmLeadSpeaker(line) {
  const s = String(line || '').trim();
  if (!s) return '';
  const hit = rmSpeakersIn(s);
  if (!hit.length) return '';
  const name = hit[0];
  const i = s.indexOf(name);
  if (i < 0 || i > 12) return '';
  if (!/的(?:声音|话音|嗓音)|压低声音|开口|出声|应声|牙关|牙关咬紧|吐出了|说出|问出|应道|回道|道：|说道/.test(s)) return '';
  return name;
}

function rmParseLine(line, ci, out, ctx) {
  /* 先拆成「旁白 / 台词」token，台词保留整段引号内容 */
  const tokens = [];
  let buf = '';
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if ('「“『'.includes(ch)) {
      if (buf.trim()) tokens.push({ kind: 'nar', text: buf.trim() });
      buf = '';
      const close = ch === '「' ? '」' : (ch === '『' ? '』' : '”');
      let j = i + 1;
      while (j < line.length && line[j] !== close) j++;
      tokens.push({ kind: 'dlg', text: line.slice(i + 1, j).trim() });
      i = j;
    } else {
      buf += ch;
    }
  }
  if (buf.trim()) tokens.push({ kind: 'nar', text: buf.trim() });

  let first = true;
  const push = (seg) => {
    seg.br = first || seg.br;
    first = false;
    out.push(seg);
  };

  tokens.forEach((tok, ti) => {
    const pre = (tokens[ti - 1] && tokens[ti - 1].kind === 'nar') ? tokens[ti - 1].text : '';
    const post = (tokens[ti + 1] && tokens[ti + 1].kind === 'nar') ? tokens[ti + 1].text : '';
    if (tok.kind === 'nar') {
      ctx.narLast = tok.text;
      rmSentences(tok.text).forEach((t) => {
        rmMention(t, ctx);
        push({ text: t, kind: 'nar', who: '', ch: ci, mood: rmMood(t, 'nar') });
      });
      return;
    }
    /* 台词：先定说话人，再按句切分（同一段引号的句子都用同一个说话人） */
    const onlyDlg = tokens.every((x) => x.kind === 'dlg');
    let who = rmResolveWho(pre || (onlyDlg ? (ctx.narLast || '') : ''), post, tok.text, ctx);
    rmSentences(tok.text).forEach((t, k) => {
      if (!who && k === 0 && ctx.pending) who = ctx.pending;
      push({ text: t, kind: 'dlg', who: who || '', ch: ci, mood: rmMood(t, 'dlg') });
    });
    if (who) {
      if (ctx.lastDlg !== who) { ctx.lastDlg2 = ctx.lastDlg; ctx.lastDlg = who; }
      ctx.pending = '';
    } else if (ctx.pending) {
      who = ctx.pending;
      ctx.pending = '';
    }
  });
}

/* 旁白里出现的人名，作为下一句台词默认说话人 */
function rmMention(text, ctx) {
  const names = rmCharDict().map((c) => c.name).filter((n) => n && text.includes(n));
  names.sort((a, b) => b.length - a.length);
  if (names.length) ctx.pending = names[0];
  else {
    const roles = ['老者', '老妇人', '老太太', '老爷子', '少年', '少女', '妇人', '汉子', '姑娘', '婆婆',
      '公公', '公子', '掌柜', '众人', '士兵', '银甲人'];
    const hit = roles.find((r) => text.includes(r));
    if (hit) ctx.pending = hit;
    else if (/私语|议论|喧哗|叫喊|惊呼|哄笑|窃窃/.test(text)) ctx.pending = '众人';
  }
}

function rmResolveWho(pre, post, text, ctx) {
  const cand = [...rmSpeakersIn(post), ...rmSpeakersIn(pre)];
  if (cand.length) return cand[cand.length - 1];
  if (ctx.nextWho) return ctx.nextWho;
  /* 第一人称：旁白里「我说 / 我道 / 我压低声音」→ 主角开口 */
  if (ctx.pov && /我[^我，,。]{0,6}(?:说|道|问|答|喊|笑|叹|低声|轻声|沉声|冷笑|咬牙|开口|抢白|嚷)/.test(pre)) return ctx.pov;
  if (ctx.pov && /你|您/.test(text) && /我/.test(pre)) return ctx.pov;
  /* 第一人称正文里，前一句旁白是「我……」且没有别的角色 → 主角在说话 */
  if (ctx.pov && /我/.test(pre) && !rmSpeakersIn(pre).length) return ctx.pov;
  /* 呵斥/示警类短句多是护卫、兵士喊的 */
  if (/让开|滚开|闪开|刺客|护主|来人|救人|快走/.test(text) && /[！!]/.test(text)) return '护卫';
  if (!ctx.lastDlg) return ctx.pending || '';
  /* 无署名时：出现“你/您”多半是对话的另一方 */
  if (/你|您/.test(text) && ctx.lastDlg2) return ctx.lastDlg2;
  /* 双人对话：来回接话，避免整段都归到最后一个人 */
  if (ctx.lastDlg2 && ctx.lastDlg2 !== ctx.lastDlg &&
      !/众人|护卫|士兵|人群/.test(ctx.lastDlg + ctx.lastDlg2)) return ctx.lastDlg2;
  return ctx.pending && ctx.pending !== ctx.lastDlg ? ctx.pending : ctx.lastDlg;
}

/* ---- 情绪 → 语速 / 音高 / 音量 ---- */
const RM_MOODS = [
  { re: /(怒吼|厉声|喝问|喝道|咆哮|暴怒|大怒|怒斥|咬牙|恨声)/, rate: 10, pitch: 8, vol: 12 },
  { re: /(哽咽|哭腔|抽泣|泪|悲痛|悲声|哀声|颤声|颤抖)/, rate: -12, pitch: -4, vol: -2 },
  { re: /(惊呼|大惊|骇然|惊恐|尖叫|慌张|慌乱)/, rate: 12, pitch: 10, vol: 6 },
  { re: /(大笑|笑|欣喜|欢喜|喜悦|欣然|打趣)/, rate: 5, pitch: 4, vol: 5 },
  { re: /(低声|轻声|喃喃|耳语|悄声|压低)/, rate: -8, pitch: -4, vol: -20 },
  { re: /(沉声|冷声|淡淡|平静|缓缓|从容)/, rate: -8, pitch: -6, vol: 0 },
  { re: /(急忙|连忙|赶紧|疾声|急促|脱口)/, rate: 12, pitch: 4, vol: 4 },
];

function rmMood(text, kind) {
  const d = { rate: 0, pitch: 0, vol: 0 };
  RM_MOODS.forEach((m) => {
    if (m.re.test(text)) { d.rate += m.rate; d.pitch += m.pitch; d.vol += m.vol; }
  });
  const scale = kind === 'nar' ? 0.35 : 1;
  d.rate = Math.round(d.rate * scale);
  d.pitch = Math.round(d.pitch * scale);
  d.vol = Math.round(d.vol * scale);
  if (/！|!/.test(text)) d.rate += 3;
  if (/？|\?/.test(text)) d.pitch += 2;
  if (/……/.test(text)) d.rate -= 3;
  return d;
}

/* 无名台词的兜底角色名：先认正文里的身份词，再按台词分配甲乙丙丁 */
const RM_ANON = ['路人甲', '路人乙', '路人丙', '路人丁'];
function rmAnonLabel(text) {
  const t = String(text || '');
  const roles = ['老汉', '老妇', '老翁', '婆婆', '公公', '少年', '少女', '孩童', '妇人', '汉子', '掌柜', '士兵', '众人'];
  const hit = roles.find((r) => t.includes(r));
  if (hit) return hit;
  return RM_ANON[rmHash(t) % 4];
}

/* 选角结果按「书」持久化：同一角色跨章、跨次播放都保持同一音色，不 OOC */
function rmCastKey() {
  return 'fj_rm_cast_' + ((S.book && S.book.name) || '');
}
function rmCastLoad() {
  try { return JSON.parse(localStorage.getItem(rmCastKey()) || '{}') || {}; } catch (e) { return {}; }
}
function rmCastSave() {
  try {
    const o = {};
    RM.cast.forEach((v, k) => {
      o[k] = { voice: v.voice, pitch: v.pitch, rate: v.rate, vol: v.vol, arch: v.arch, sex: v.sex || '' };
    });
    localStorage.setItem(rmCastKey(), JSON.stringify(o));
  } catch (e) { /* 忽略容量/隐私模式错误 */ }
}

/* ---- 选角：给每个角色固定音色，保证不撞音 ---- */
function rmCastAll() {
  RM.cast = new Map();
  if (RM.mode !== 'drama') {
    /* 单人朗读：一个温润女声读全部 */
    RM.all.forEach((s) => { s.voice = 'zh-CN-XiaoxiaoNeural'; s.pitch = 0; s.rate = -4; s.vol = 0; });
    return;
  }
  const dict = rmCharDict();
  const used = new Set();
  const saved = rmCastLoad();
  const narrator = RM_ARCH.narrator;

  const findChar = (who) => {
    const hit = dict.find((c) => c.name === who || (c.aliases || []).includes(who));
    return hit || null;
  };
  const pick = (who, kind) => {
    const sv = saved[who];
    if (sv && sv.voice) {
      used.add(`${sv.voice}|${Math.round((sv.pitch || 0) / 4)}`);
      return { who, kind, voice: sv.voice, pitch: sv.pitch || 0, rate: sv.rate || 0,
        vol: sv.vol || 0, arch: sv.arch || 'young_m', sex: sv.sex || '', note: '' };
    }
    const c = findChar(who);
    const tone = c ? c.text : '';
    const group = c ? c.group : '';
    const labelTrait = rmTrait(who, tone + ' ' + who, group, c);
    let arch = rmArchetype({ ...labelTrait, tone });
    if (c && /反派/.test(group)) arch = labelTrait.sex === 'f' ? 'villain_f' : 'villain_m';
    /* 身份词直接定原型，避免「护卫」被随机分到女声 */
    const byLabel = [
      [/护卫|侍卫|兵士|士兵|甲士|亲卫|军士|守卫/, 'rough_m'],
      [/众人|人群|百姓|群众|围观/, 'crowd'],
      [/掌柜|小二|摊主|老板|店家/, 'mid_m'],
      [/老妇|老妇人|婆婆|老太太|妇人|嬷嬷|婆子/, 'old_f'],
    ].find((x) => x[0].test(who));
    if (byLabel) arch = byLabel[1];
    const pool = RM_POOL[arch] || [RM_ARCH[arch].voice];
    const base = RM_ARCH[arch];
    let voice = base.voice;
    let pitch = base.pitch;
    let rate = base.rate;
    /* 同音色已用 → 换池内音色；池空/也撞 → 音高错开 */
    let tries = 0;
    while (used.has(`${voice}|${Math.round(pitch / 4)}`) && tries < 24) {
      tries++;
      const alt = pool[tries % pool.length];
      if (!used.has(`${alt}|${Math.round(pitch / 4)}`)) { voice = alt; break; }
      const dir = tries % 2 ? 1 : -1;
      pitch = Math.max(-26, Math.min(30, base.pitch + dir * (4 + tries * 2)));
    }
    used.add(`${voice}|${Math.round(pitch / 4)}`);
    return { who, kind, voice, pitch, rate, vol: base.vol, arch, sex: labelTrait.sex, note: c ? c.text : '' };
  };

  RM.all.forEach((s) => {
    if (s.kind === 'chapter') { s.voice = narrator.voice; s.pitch = 0; s.rate = narrator.rate; s.vol = 0; return; }
    if (s.kind === 'nar') {
      s.voice = narrator.voice; s.pitch = (s.mood.pitch || 0) * 0.5;
      s.rate = narrator.rate + (s.mood.rate || 0) * 0.6; s.vol = (s.mood.vol || 0) * 0.5;
      return;
    }
    const who = s.who || rmAnonLabel(s.text);
    s.who = who;
    if (!RM.cast.has(who)) RM.cast.set(who, pick(who, s.kind));
  });
  rmCastSave();

  RM.all.forEach((s) => {
    if (s.kind !== 'dlg' || !s.who) return;
    const c = RM.cast.get(s.who);
    if (!c) return;
    s.voice = c.voice;
    s.pitch = c.pitch + (s.mood.pitch || 0);
    s.rate = c.rate + (s.mood.rate || 0);
    s.vol = c.vol + (s.mood.vol || 0);
  });
}

function rmCastLabel(voice) {
  const m = RM_VOICE_META[voice];
  return m ? `${m.name} · ${m.age}${m.sex === 'f' ? '女' : '男'}` : voice;
}

function rmRenderCast() {
  const box = $('#rmCastStrip');
  if (!box) return;
  const chips = [];
  chips.push(`<span class="rm-chip rm-chip-nar" title="旁白">旁白 <em>${rmCastLabel(RM_ARCH.narrator.voice)}</em></span>`);
  RM.cast.forEach((c) => {
    const meta = RM_VOICE_META[c.voice] || {};
    chips.push(`<span class="rm-chip" title="${rmEsc((meta.tag || '') + (meta.age || ''))}">${rmEsc(c.who)} <em>${rmCastLabel(c.voice)}</em></span>`);
  });
  box.innerHTML = chips.join('');
}

function rmRender() {
  $('#rmStage').innerHTML = RM.all.map((s, i) => {
    const cls = `rm-seg ${s.kind}${s.br ? ' br' : ''}`;
    const who = s.kind === 'dlg' && s.who ? ` title="${rmEsc(s.who)}"` : '';
    if (s.kind === 'chapter') return `<div class="rm-ch" data-rm="${i}">${rmEsc(s.text)}</div>`;
    return `${s.br ? '<br>' : ''}<span class="${cls}" data-rm="${i}"${who}>${rmEsc(s.text)}</span>`;
  }).join('');
}

function rmHighlight(i) {
  $$('#rmStage .rm-seg, #rmStage .rm-ch').forEach((el) => {
    const k = Number(el.dataset.rm);
    el.classList.toggle('on', k === i);
    el.classList.toggle('done', k < i);
  });
  const cur = $(`#rmStage [data-rm="${i}"]`);
  if (cur && cur.scrollIntoView) cur.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

function rmSyncPlay() {
  const b = $('#rmPlay');
  if (b) { b.textContent = RM.playing ? '❚❚' : '▶'; b.title = RM.playing ? '暂停' : '播放'; }
}

function rmChapterOf(g) {
  for (let i = 0; i < RM.chapters.length; i++) {
    if (g >= RM.chapters[i].start && g < RM.chapters[i].end) return i;
  }
  return RM.chapters.length - 1;
}

/* 服务端一次最多 800 段；整章一次请求才能保证场景音/BGM 连续，超长章节才分批 */
async function rmPostDrama(segs) {
  const res = await fetch('/api/tts/drama', {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ segments: segs, mix: RM.mix }),
  });
  if (!res.ok) throw new Error('tts ' + res.status);
  const buf = await res.arrayBuffer();
  const durs = String(res.headers.get('X-FJ-Durations') || '').split(',').map((x) => parseInt(x, 10) || 0);
  return { buf, durs, scenes: parseInt(res.headers.get('X-FJ-Scenes') || '0', 10) || 0 };
}

async function rmChapterAudio(ci) {
  const key = `${ci}|${RM.mode}|${RM.rate}|${RM.mix}`;
  if (RM.cache.has(key)) return RM.cache.get(key);
  const ch = RM.chapters[ci];
  if (!ch) throw new Error('no-chapter');
  const segs = RM.all.slice(ch.start, ch.end).map((s) => ({
    text: s.text, voice: s.voice,
    rate: `${Math.round((s.rate || 0) + (parseInt(RM.rate, 10) || 0))}%`,
    pitch: `${Math.round(s.pitch || 0) >= 0 ? '+' : ''}${Math.round(s.pitch || 0)}Hz`,
    volume: `${Math.round(s.vol || 0) >= 0 ? '+' : ''}${Math.round(s.vol || 0)}%`, kind: s.kind, mood: s.mood || '',
  }));
  const task = (async () => {
    const groups = [];
    for (let i = 0; i < segs.length; i += 800) groups.push(segs.slice(i, i + 800));
    const parts = [];
    for (let i = 0; i < groups.length; i += 1) {
      parts.push(await rmPostDrama(groups[i]));
    }
    const blob = new Blob(parts.map((p) => p.buf), { type: 'audio/mpeg' });
    const durs = parts.reduce((a, p) => a.concat(p.durs), []);
    const scenes = parts.reduce((a, p) => a + p.scenes, 0);
    return { url: URL.createObjectURL(blob), blob, durs, scenes, total: durs.reduce((a, b) => a + b, 0) };
  })();
  RM.cache.set(key, task);
  task.catch(() => RM.cache.delete(key));
  return task;
}

/* 播放某一章的某一段；结束后 resolve(true)，被停止 resolve(false) */
function rmPlayChapterFrom(ci, localIdx, token) {
  return new Promise(async (resolve) => {
    let meta;
    try {
      meta = await rmChapterAudio(ci);
    } catch (e) {
      RM.noServer = true;
      resolve(false);
      return;
    }
    if (token !== RM.token) { resolve(false); return; }
    const ch = RM.chapters[ci];
    const startMs = meta.durs.slice(0, localIdx).reduce((a, b) => a + b, 0);
    const audio = new Audio(meta.url);
    RM.audio = audio;
    RM.resolver = () => resolve(false);
    audio.ontimeupdate = () => {
      if (token !== RM.token) return;
      const t = audio.currentTime * 1000;
      let acc = 0;
      let idx = localIdx;
      for (let i = localIdx; i < meta.durs.length; i++) {
        if (t < acc + meta.durs[i]) { idx = i; break; }
        acc += meta.durs[i];
        idx = i;
      }
      const g = ch.start + idx;
      if (g !== RM.cur) {
        RM.cur = g;
        rmHighlight(g);
        const seg = RM.all[g];
        const who = seg && seg.kind === 'dlg' && seg.who ? ` · ${seg.who}` : '';
        rmHint(`${g + 1} / ${RM.all.length}${who}`);
      }
    };
    let started = false;
    const kick = () => {
      if (started || token !== RM.token) return;
      started = true;
      if (startMs > 0) { try { audio.currentTime = startMs / 1000; } catch (e) { /* 忽略 */ } }
      audio.play().catch(() => { RM.audio = null; RM.resolver = null; resolve(false); });
    };
    audio.onended = () => { RM.audio = null; RM.resolver = null; resolve(true); };
    audio.onerror = () => { RM.audio = null; RM.resolver = null; resolve(false); };
    audio.onloadedmetadata = kick;
    audio.oncanplay = kick;
    /* 没有元数据事件时兜底 */
    setTimeout(() => { if (RM.audio === audio) kick(); }, 80);
  });
}

async function rmPlayFrom(start) {
  if (!RM.all.length) return;
  rmStopAudio();
  const token = ++RM.token;
  RM.playing = true;
  rmSyncPlay();
  let i = Math.max(0, Math.min(start, RM.all.length - 1));
  if (RM.all[i].kind === 'chapter') i += 1;
  while (i < RM.all.length && token === RM.token) {
    const ci = rmChapterOf(i);
    const local = i - RM.chapters[ci].start;
    rmHint(`合成中… ${i + 1} / ${RM.all.length}`);
    if (ci + 1 < RM.chapters.length) rmChapterAudio(ci + 1).catch(() => {});
    const ok = await rmPlayChapterFrom(ci, local, token);
    if (!ok || token !== RM.token) break;
    i = RM.chapters[ci].end;
  }
  if (token === RM.token) {
    RM.playing = false;
    RM.cur = -1;
    rmSyncPlay();
    rmHint('配音结束');
  }
}

function rmStopAudio() {
  RM.token++;
  RM.playing = false;
  if (RM.resolver) { const r = RM.resolver; RM.resolver = null; r(); }
  if (RM.audio) { try { RM.audio.pause(); } catch (e) { /* 忽略 */ } RM.audio = null; }
  if (window.speechSynthesis) { try { speechSynthesis.cancel(); } catch (e) { /* 忽略 */ } }
  rmSyncPlay();
}

function rmTogglePlay() {
  if (RM.playing) { rmStopAudio(); rmHint('已暂停'); return; }
  if (!RM.all.length) return;
  rmPlayFrom(RM.cur >= 0 ? RM.cur : 0);
}

function rmOpen() {
  const f = currentFile();
  if (!f) { toast('先选一章再进阅读模式'); return; }
  rmStopAudio();
  RM.cache.forEach((p) => p.then((m) => { try { URL.revokeObjectURL(m.url); } catch (e) { /* 忽略 */ } }).catch(() => {}));
  RM.cache.clear();
  RM.noServer = false;
  RM.cur = -1;
  rmBuildAll();
  if (!RM.all.length) { toast('没有可配音的正文'); return; }
  RM.mode = $('#rmCast').value;
  RM.rate = $('#rmRate').value;
  rmCastAll();
  const scope = $('#rmScope') ? $('#rmScope').value : 'chapter';
  $('#rmTitle').textContent = f.name;
  $('#rmSub').textContent = `${RM.all.length} 段 · ${RM.chapters.length} 章 · ${RM.mode === 'drama' ? '多人有声剧' : '单人朗读'}`;
  rmRenderCast();
  rmRender();
  $('#readMode').hidden = false;
  $('#rmStage').scrollTop = 0;
  rmHint('点 ▶ 开始配音');
  /* 后台先把第一章合成好，点播放时就不用等 */
  rmChapterAudio(0).catch(() => {});
  if (scope === 'book') toast('全书配音：共 ' + RM.chapters.length + ' 章，会按章节依次播放');
}

function rmClose() {
  rmStopAudio();
  const box = $('#readMode');
  if (box) box.hidden = true;
}

function rmDownload() {
  if (!RM.all.length) return;
  const ci = rmChapterOf(RM.cur >= 0 ? RM.cur : 0);
  rmChapterAudio(ci).then((m) => {
    const a = document.createElement('a');
    a.href = m.url;
    a.download = `${RM.chapters[ci].name || 'chapter'}_多人有声剧.mp3`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    toast('已导出本章 mp3（' + Math.round(m.total / 1000) + ' 秒）');
  }).catch(() => toast('导出失败：服务器未安装 edge-tts'));
}

/* ---------------- 主题与其它面板渲染 ---------------- */
function renderSnapList() {
  const f = currentFile();
  const list = f ? store.json(KEY.snaps(f.id), []) : [];
  $('#snapList').innerHTML = list.length ? list.map((s, i) => `<div class="snap-row">
      <span class="st1">${new Date(s.t).toLocaleTimeString('zh-CN', { hour12: false })}</span>
      <span class="st2">${new Date(s.t).toLocaleDateString('zh-CN')} · ${fmt(wordCount(s.content))} 字</span>
      <span class="acts">
        <button class="mini-btn" data-restore-snap="${i}">恢复</button>
        <button class="mini-btn" data-del-snap="${i}">删除</button>
      </span>
    </div>`).join('') : '<div class="snap-row"><span class="st2">还没有快照。写满 5 分钟或点「存稿」就会留一份。</span></div>';
}
async function restoreSnap(i) {
  const f = currentFile();
  if (!f) return;
  const list = store.json(KEY.snaps(f.id), []);
  const s = list[i];
  if (!s) return;
  const ok = await askConfirm('恢复快照', `恢复到 ${new Date(s.t).toLocaleString('zh-CN')} 的版本？当前内容会先自动存一份快照。`, '恢复');
  if (!ok) return;
  takeSnapshot(true);
  histCommit();
  input().value = s.content;
  f.content = s.content;
  onEditorInput();
  histCommit();
  closeModal($('#snapModal'));
  toast('已恢复到 ' + new Date(s.t).toLocaleTimeString('zh-CN', { hour12: false }));
}
function deleteSnap(i) {
  const f = currentFile();
  if (!f) return;
  const list = store.json(KEY.snaps(f.id), []);
  list.splice(i, 1);
  store.setJson(KEY.snaps(f.id), list);
  renderSnapList();
}
function renderTrashList() {
  const list = store.json(KEY.trash(S.book ? S.book.name : '_'), []);
  $('#trashList').innerHTML = list.length ? list.map((t, i) => `<div class="snap-row">
      <span class="st1">${esc(t.file.name)}</span>
      <span class="st2">${fmt(wordCount(t.file.content))} 字</span>
      <span class="acts">
        <button class="mini-btn" data-restore-trash="${i}">恢复</button>
        <button class="mini-btn" data-purge-trash="${i}">彻底删除</button>
      </span>
    </div>`).join('') + `<div class="snap-row" style="border:none"><button class="mini-btn seal" style="margin-left:auto" id="trashClearBtn">清空回收站</button></div>`
    : '<div class="snap-row"><span class="st2">回收站是空的</span></div>';
}
function renderLexModal() {
  $('#lexModalBox').innerHTML = lexList().map((w) => `<span class="lex">${esc(w)}<i data-del-lex="${esc(w)}">×</i></span>`).join('');
}
function renderShortcuts() {
  const rows = [
    ['撤销', 'Ctrl / ⌘ + Z'], ['重做', 'Ctrl / ⌘ + Y 或 Ctrl / ⌘ + Shift + Z'],
    ['保存', 'Ctrl / ⌘ + S'], ['查找', 'Ctrl / ⌘ + F'], ['快捷键', 'Ctrl / ⌘ + /'],
    ['退出专注', 'Esc'], ['新建章节', 'Ctrl / ⌘ + Enter'], ['打开手机预览', 'Ctrl / ⌘ + P'],
  ];
  $('#scList').innerHTML = rows.map(([a, b]) => `<div class="snap-row"><span class="st1">${a}</span><span class="st2" style="margin-left:auto">${b}</span></div>`).join('');
}

/* ---------------- 导出 ---------------- */
function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function safeName(s) { return String(s || 'untitled').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 60); }

function exportChapter(id) {
  const f = fileById(id || S.chapterId);
  if (!f) { toast('先选一个章节'); return; }
  downloadText(`${safeName(f.name)}.txt`, `${f.name}\n\n${f.content || ''}`);
  toast('本章已导出');
}

function exportVolume(volId) {
  if (!S.book) return;
  const v = fileById(volId);
  if (!v) return;
  const list = S.files.filter((f) => f.type === 'FILE' && f.parentId === volId);
  if (!list.length) { toast('这一卷还没有章节'); return; }
  const text = list.map((f) => `${f.name}\n\n${f.content || ''}`).join('\n\n\n');
  downloadText(`${safeName(S.book.name)}_${safeName(v.name)}.txt`, text);
  toast('本卷已导出');
}

function exportBook(format) {
  if (!S.book) return;
  const vols = volumeFolders();
  const rootFiles = S.files.filter((f) => f.type === 'FILE' && f.parentId === 'root');
  const blocks = [];
  const addFiles = (files) => files.forEach((f) => {
    const body = f.content || '';
    blocks.push(format === 'md' ? `## ${f.name}\n\n${body}` : `${f.name}\n\n${body}`);
  });
  if (rootFiles.length) addFiles(rootFiles);
  vols.forEach((v) => {
    const files = S.files.filter((f) => f.type === 'FILE' && f.parentId === v.id);
    if (!files.length) return;
    blocks.push(format === 'md' ? `# ${v.name}` : `\n========== ${v.name} ==========\n`);
    addFiles(files);
  });
  if (!blocks.length) { toast('这本书还没有内容'); return; }
  const head = format === 'md' ? `# ${S.book.name}\n\n> ${S.book.genre || ''} ${S.book.style || ''}\n\n` : `${S.book.name}\n\n`;
  downloadText(`${safeName(S.book.name)}.${format}`, head + blocks.join('\n\n'));
  toast('全书已导出');
}

function exportMenu(anchor) {
  showMenu(anchor, [
    { label: '导出本章 (.txt)', icon: '章', action: () => exportChapter() },
    ...(volumeFolders().length ? [{ label: '导出当前分卷 (.txt)', icon: '卷', action: () => exportVolume(currentFile() ? currentFile().parentId : volumeFolders()[0].id) }] : []),
    { label: '导出全书 (.txt)', icon: '书', action: () => exportBook('txt') },
    { label: '导出全书 (.md)', icon: 'MD', action: () => exportBook('md') },
  ]);
}

/* ---------------- 书架 ---------------- */
function renderShelf() {
  const grid = $('#shelfGrid');
  if (!S.books.length) {
    grid.innerHTML = '<div class="shelf-empty">书架还是空的，点右上「＋新建书籍」开始。</div>';
    return;
  }
  grid.innerHTML = S.books.map((b) => {
    const isCurrent = S.book && b.name === S.book.name;
    const words = isCurrent ? bookWords() : (b.words || 0);
    const chapters = isCurrent ? chapterFiles().length : (b.chapters || 0);
    return `<div class="shelf-card${isCurrent ? ' on' : ''}" data-book="${esc(b.name)}">
      <div class="shelf-cover" style="${b.cover ? `background-image:url('${b.cover}')` : ''}">${b.cover ? '' : esc((b.name || '书').slice(0, 1))}</div>
      <div class="shelf-meta">
        <b>${esc(b.name)}</b>
        <span class="tag">${esc([b.genre, b.style].filter(Boolean).join(' · ') || '未设置题材')}${b.author ? ' · ' + esc(b.author) : ''}</span>
        <span class="nums"><b>${fmt(words)}</b> 字 · <b>${chapters}</b> 章${b.updated_at ? ' · ' + String(b.updated_at).slice(5, 10) : ''}</span>
      </div>
      <div class="shelf-ops">
        <button class="icon-btn" data-shelf-settings="${esc(b.name)}" title="书籍设置"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-2.9 1.2V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 7 19.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.7 1.7 0 0 0 3 15H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.7 9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.7 1.7 0 0 0 9 4.7V4a2 2 0 1 1 4 0v.1A1.7 1.7 0 0 0 15 5.7l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0 1.2 2.9H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg></button>
      </div>
    </div>`;
  }).join('');
}

async function openShelf() {
  try { await loadBooks(); } catch (e) { toast('读取书架失败：' + e.message); }
  renderShelf();
  openModal('shelfModal');
}

/* ---------------- 书籍设置 ---------------- */
function openBookSettings(name) {
  const target = name ? S.books.find((b) => b.name === name) : S.book;
  if (!target) { toast('先选一本书'); return; }
  if (name && S.book && name !== S.book.name) {
    openBook(name).then(() => fillBookSettings()).catch((e) => toast(e.message));
    return;
  }
  fillBookSettings();
}

function fillBookSettings() {
  if (!S.book) return;
  $('#bsName').value = S.book.name || '';
  $('#bsAuthor').value = S.book.author || '';
  $('#bsDesc').value = S.book.description || '';
  $('#bsGenre').value = S.book.genre || '';
  $('#bsStyle').value = S.book.style || '';
  $('#bsSubgenre').value = S.book.subgenre || '';
  $('#bsRef').value = S.book.ref_author || '';
  $('#bsWords').value = S.book.words_per_chapter || 2500;
  $('#bsChapters').value = S.book.chapter_count || 400;
  updateCoverPreview(S.book);
  $('#bsStatus').textContent = '';
  openModal('bookSettingsModal');
  setTimeout(() => $('#bsName').focus(), 50);
}

function updateCoverPreview(book) {
  const box = $('#bsCoverPreview');
  if (!box) return;
  const ch = (book && book.name ? book.name.slice(0, 1) : '书');
  $('#bsCoverChar').textContent = ch;
  if (book && book.cover) {
    box.style.backgroundImage = `url("${book.cover}")`;
    box.classList.add('has-image');
    $('#bsCoverClear').hidden = false;
  } else {
    box.style.backgroundImage = '';
    box.classList.remove('has-image');
    $('#bsCoverClear').hidden = true;
  }
}

async function handleCoverFile(file) {
  if (!file || !S.book) return;
  if (file.size > 6 * 1024 * 1024) { toast('封面超过 6MB，请压缩后再传'); return; }
  const dataUrl = await new Promise((res) => {
    const fr = new FileReader();
    fr.onload = () => res(fr.result);
    fr.readAsDataURL(file);
  });
  try {
    const r = await api(`/books/${encodeURIComponent(S.book.name)}/cover`, { method: 'POST', body: { data: dataUrl } });
    S.book.cover = r.url;
    updateCoverPreview(S.book);
    renderBookHead();
    await loadBooks();
    renderShelf();
    toast('封面已更新');
  } catch (e) { toast('上传失败：' + e.message); }
}

async function saveBookSettings() {
  if (!S.book) return;
  const oldName = S.book.name;
  const newName = $('#bsName').value.trim();
  if (!newName) { $('#bsStatus').textContent = '书名不能为空'; return; }
  const meta = {
    author: $('#bsAuthor').value.trim(),
    description: $('#bsDesc').value.trim(),
    genre: $('#bsGenre').value.trim(),
    style: $('#bsStyle').value.trim(),
    subgenre: $('#bsSubgenre').value.trim(),
    ref_author: $('#bsRef').value.trim(),
    words_per_chapter: Number($('#bsWords').value) || 2500,
    chapter_count: Number($('#bsChapters').value) || 400,
  };
  try {
    $('#bsStatus').textContent = '保存中…';
    let finalName = oldName;
    if (newName !== oldName) {
      const r = await api(`/projects/${encodeURIComponent(oldName)}/rename`, { method: 'POST', body: { new_name: newName } });
      finalName = r.name || newName;
      store.set(KEY.lastBook, finalName);
      S.book.name = finalName;
    }
    Object.assign(S.book, meta);
    await api(`/projects/${encodeURIComponent(finalName)}`, { method: 'PUT', body: meta });
    await loadBooks();
    renderBookHead();
    renderShelf();
    $('#bsStatus').textContent = '已保存';
    toast('书籍设置已保存');
    setTimeout(() => closeModal($('#bookSettingsModal')), 400);
  } catch (e) {
    $('#bsStatus').textContent = '保存失败：' + e.message;
  }
}

/* ---------------- 创作数据 ---------------- */
function renderStats() {
  if (!$('#statWords')) return;
  const files = chapterFiles();
  const words = bookWords();
  const chapters = files.length;
  const avg = chapters ? Math.round(words / chapters) : 0;
  const daily = store.json(KEY.daily, {});
  const today = daily[todayKey()] || 0;

  let streak = 0;
  const d = new Date();
  for (;;) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    if ((daily[key] || 0) > 0) { streak++; d.setDate(d.getDate() - 1); } else break;
    if (streak > 400) break;
  }

  const setS = (sel, v) => { const el = $(sel); if (el) el.textContent = v; };
  setS('#statWords', fmt(words));
  setS('#statChapters', chapters);
  setS('#statAvg', fmt(avg));
  setS('#statToday', fmt(today));
  setS('#statStreak', streak);

  const targetTotal = (S.book && S.book.chapter_count ? S.book.chapter_count : 400) * (S.book && S.book.words_per_chapter ? S.book.words_per_chapter : 2500);
  const remain = Math.max(0, targetTotal - words);
  const pace = S.goal || 3000;
  setS('#statEta', remain <= 0
    ? `已达成 ${fmt(targetTotal)} 字计划（当前 ${fmt(words)} 字）`
    : `写满 ${fmt(targetTotal)} 字还差 ${fmt(remain)} 字，按每天 ${fmt(pace)} 字约需 ${Math.ceil(remain / pace)} 天`);
}

/* ---------------- 提示音 ---------------- */
function beep(times) {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    for (let i = 0; i < (times || 1); i++) {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.connect(g); g.connect(ctx.destination);
      o.type = 'sine';
      o.frequency.value = 880;
      const t = ctx.currentTime + i * 0.22;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.12, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.18);
      o.start(t); o.stop(t + 0.2);
    }
    setTimeout(() => ctx.close().catch(() => {}), 800);
  } catch {}
}

/* ---------------- 导入书籍 / 章节 ---------------- */
const importState = { files: [], mode: 'current', split: 'auto' };

function openImportModal(mode) {
  importState.files = [];
  importState.mode = mode || 'current';
  importState.split = 'auto';
  const inp = $('#importFileInput');
  if (inp) inp.value = '';
  $('#importFileInfo').textContent = '未选择文件';
  $('#importPaste').value = '';
  $('#importStatus').textContent = '';
  $('#importBookName').value = '';
  $('#importNameField').hidden = importState.mode !== 'new';
  $$('#importModeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.mode === importState.mode));
  $$('#importSplitSeg button').forEach((b) => b.classList.toggle('on', b.dataset.split === 'auto'));
  openModal('importModal');
}

async function readFileSmart(file) {
  const buf = await file.arrayBuffer();
  try { return new TextDecoder('utf-8', { fatal: true }).decode(buf); } catch {}
  try { return new TextDecoder('gbk').decode(buf); } catch {}
  return new TextDecoder('utf-8').decode(buf);
}

const CHAPTER_LINE = /^\s*(?:第\s*[0-9零〇一二三四五六七八九十百千两]{1,8}\s*[章节回卷][^\n]{0,40}|(?:Chapter|CHAPTER)\s+\d+[^\n]{0,40}|\d{1,4}\s*[、.．]\s*[^\n]{0,30})\s*$/;
/* 楔子 / 契子 / 序章 / 番外 这类非编号标题 */
const SPECIAL_LINE = /^(?:楔\s*子|契\s*子|序\s*章|序\s*言|引\s*子|引\s*言|前\s*言|题\s*记|尾\s*声|尾\s*章|终\s*章|后\s*记|补\s*记|外\s*传|特\s*别\s*篇|番\s*外|序|楔|跋)(?:\s*[0-9零〇一二三四五六七八九十百]{1,3})?(?:(?:\s*[:：·、.\-—]+\s*|\s+)[^\n，。！？；]{0,20})?$/;

function isChapterHeading(line) {
  const s = String(line || '').trim();
  if (!s || s.length > 60) return false;
  if (CHAPTER_LINE.test(s) || SPECIAL_LINE.test(s)) return true;
  /* 允许 【楔子】【第一章】这类带括号的写法 */
  const bare = s.replace(/^[【\[（(「《]+/, '').replace(/[】\]）)」》]+$/, '').trim();
  return bare !== s && (CHAPTER_LINE.test(bare) || SPECIAL_LINE.test(bare));
}

function splitChapters(text, fallbackTitle) {
  const t = (text || '').replace(/\r\n?/g, '\n').trim();
  if (!t) return [];
  const lines = t.split('\n');
  const idx = [];
  lines.forEach((line, i) => {
    const s = line.trim();
    if (s && s.length <= 60 && isChapterHeading(line)) idx.push(i);
  });
  if (!idx.length) {
    const first = (lines[0] || '').trim();
    const useFirst = first && first.length <= 40 && !/[。！？]/.test(first);
    return [{ title: useFirst ? first : fallbackTitle, content: (useFirst ? lines.slice(1).join('\n') : t).trim() }];
  }
  const preOf = (start) => {
    const preLines = lines.slice(0, start);
    const pre = preLines.join('\n').trim();
    const plain = pre.replace(/\s/g, '');
    /* 短书名/作者行丢掉；有句子标点或够长，就当正文留下 */
    if (plain.length < 120 && !/[。！？…]/.test(pre)) return null;
    const first = (preLines.find((x) => x.trim()) || '').trim();
    const useFirst = first && first.length <= 40 && !/[。！？]/.test(first) && !isChapterHeading(first);
    return { title: useFirst ? first : '开篇', content: (useFirst ? preLines.slice(1).join('\n') : pre).trim() };
  };
  if (idx.length === 1) {
    const res = [];
    const pre = preOf(idx[0]);
    if (pre) res.push(pre);
    res.push({ title: lines[idx[0]].trim().slice(0, 60), content: lines.slice(idx[0] + 1).join('\n').trim() });
    return res;
  }
  const out = [];
  /* 第一个章节标题之前的正文（没标题的楔子、内容简介）别丢 */
  const pre = preOf(idx[0]);
  if (pre) out.push(pre);
  for (let k = 0; k < idx.length; k++) {
    const start = idx[k];
    const end = k + 1 < idx.length ? idx[k + 1] : lines.length;
    const title = lines[start].trim().slice(0, 60);
    const body = lines.slice(start + 1, end).join('\n').trim();
    out.push({ title, content: body });
  }
  return out.filter((c) => c.title || c.content);
}

function uniqueChapterName(name, used) {
  let n = name || '未命名';
  if (!used.has(n)) { used.add(n); return n; }
  let i = 2;
  while (used.has(`${n} (${i})`)) i++;
  const out = `${n} (${i})`;
  used.add(out);
  return out;
}

async function autoFillProject(name) {
  if (!name) return null;
  toast('正在读正文识别设定（书籍信息/概念/世界观/人物/关系/大纲/细纲/伏笔），约需 1–3 分钟…');
  try {
    const r = await api(`/projects/${encodeURIComponent(name)}/ai-fill`, { method: 'POST', body: {} });
    await loadBooks();
    if (S.book && S.book.name === name) await openBook(name);
    const parts = (r.changed || []).join(' · ');
    const errs = (r.errors || []).filter(Boolean);
    if (parts) toast(`已自动填入：${parts}${errs.length ? '（部分未识别：' + errs.join('；') + '）' : ''}`);
    else toast('没有识别到可填的设定' + (errs.length ? '：' + errs.join('；') : ''));
    return r;
  } catch (e) {
    toast('自动识别失败：' + e.message);
    return null;
  }
}

async function importTextAsNewBook(name, chapters) {
  let finalName = name || '导入的书';
  const existing = new Set((await loadBooks()).map((b) => b.name));
  let i = 2;
  const base = finalName;
  while (existing.has(finalName)) finalName = `${base} ${i++}`;
  await api('/projects', { method: 'POST', body: { name: finalName } });
  const volId = newId('vol_');
  const used = new Set();
  const files = [
    { id: 'root', parentId: null, name: 'Root', type: 'FOLDER', lastModified: Date.now() },
    { id: volId, parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() },
    ...chapters.map((c) => ({
      id: newId('ch_'), parentId: volId, name: uniqueChapterName(c.title, used),
      type: 'FILE', content: c.content || '', lastModified: Date.now(), metadata: {},
    })),
  ];
  await api(`/files/${encodeURIComponent(finalName)}`, { method: 'POST', body: { files } });
  await loadBooks();
  await openBook(finalName);
  /* 导入后自动识别世界观/人物/大纲/概念并填入 */
  try { await autoFillProject(finalName); } catch (e) { /* 忽略 */ }
  return finalName;
}

async function importTextAsChapters(chapters) {
  if (!S.book) throw new Error('请先打开一本书');
  let vol = volumeFolders()[0];
  if (!vol) {
    vol = { id: newId('vol_'), parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() };
    S.files.push(vol);
  }
  const used = new Set(S.files.filter((f) => f.type === 'FILE').map((f) => f.name));
  chapters.forEach((c) => {
    S.files.push({
      id: newId('ch_'), parentId: vol.id, name: uniqueChapterName(c.title, used),
      type: 'FILE', content: c.content || '', lastModified: Date.now(), metadata: {},
    });
  });
  await pushFiles();
  renderToc();
  updateStats();
  return chapters.length;
}

async function runImport() {
  const status = $('#importStatus');
  const files = importState.files;
  const pasted = ($('#importPaste').value || '').trim();
  if (!files.length && !pasted) { toast('先选择文件或粘贴文本'); return; }
  const btn = $('#importStart');
  btn.disabled = true;
  status.textContent = '导入中…';
  let addedChapters = 0;
  let addedBooks = 0;
  try {
    const jsonFiles = files.filter((f) => /\.json$/i.test(f.name));
    const textFiles = files.filter((f) => !/\.json$/i.test(f.name));

    for (const f of jsonFiles) {
      const raw = await readFileSmart(f);
      const obj = JSON.parse(raw);
      if (obj && Array.isArray(obj.projects)) {
        for (const p of obj.projects) {
          await api('/projects/import', { method: 'POST', body: { project: p, name: p.name, overwrite: true } });
          addedBooks++;
        }
      } else {
        const name = (importState.mode === 'new' && $('#importBookName').value.trim()) || obj.name || f.name.replace(/\.json$/i, '');
        await api('/projects/import', { method: 'POST', body: { project: obj, name, overwrite: true } });
        addedBooks++;
      }
    }

    const chapters = [];
    for (const f of textFiles) {
      const text = await readFileSmart(f);
      const base = f.name.replace(/\.[^.]+$/, '');
      if (importState.split === 'file') chapters.push({ title: base, content: text.trim() });
      else chapters.push(...splitChapters(text, base));
    }
    if (pasted) {
      const pasteName = $('#importBookName').value.trim() || '粘贴导入';
      if (importState.split === 'file') chapters.push({ title: pasteName, content: pasted });
      else chapters.push(...splitChapters(pasted, pasteName));
    }

    if (chapters.length) {
      if (importState.mode === 'new') {
        const name = $('#importBookName').value.trim()
          || (textFiles[0] ? textFiles[0].name.replace(/\.[^.]+$/, '') : '粘贴导入');
        await importTextAsNewBook(name, chapters);
        addedBooks++;
        addedChapters += chapters.length;
      } else {
        addedChapters += await importTextAsChapters(chapters);
      }
    }

    await loadBooks();
    renderShelf();
    status.textContent = `完成：${addedChapters} 章${addedBooks ? '，' + addedBooks + ' 本书' : ''}`;
    toast(`导入完成：${addedChapters} 章${addedBooks ? ' / ' + addedBooks + ' 本书' : ''}`);
    setTimeout(() => { closeModal($('#importModal')); }, 600);
  } catch (e) {
    status.textContent = '导入失败：' + e.message;
    toast('导入失败：' + e.message);
  }
  btn.disabled = false;
}

/* ---------------- 事件绑定 ---------------- */
/* ================= 融合「易创」客户端：开书模板 / 成就徽章 / 素材库 ================= */
const EW_TPL_KEY = 'fj:ew:tpl';
const EW_BADGE_KEY = 'fj:ew:badges';
const EW_MOD_KEY = 'fj:ew:mods';
const EW_SCENE = (f) => `assets/scenes/${f}`;
const EW_ASSET = (f) => `assets/ew/${f}`;

const EW_TEMPLATES = [
  {
    id: 'xuanhuan', name: '东方玄幻', tag: '起点 · 长线升级', cover: EW_SCENE('ink-dragon.jpg'),
    genre: '东方玄幻', style: '热血爽文 · 单线升级',
    desc: '少年自边荒小城起势，一路破境、夺宝、踏宗门，最终问鼎九天。开篇三章立目标，十章内给第一次大爽点。',
    chapters: ['第1章 边城少年', '第2章 废材觉醒', '第3章 初露锋芒', '第4章 宗门来使', '第5章 血战擂台'],
  },
  {
    id: 'xianxia', name: '仙侠修真', tag: '番茄 · 稳健流', cover: EW_SCENE('green-mountain.jpg'),
    genre: '仙侠修真', style: '清冷仙气 · 谋定后动',
    desc: '凡人入道，以符箓与阵道立身。主角谨慎多谋，一步一劫，靠推演与积累把小优势滚成大势。',
    chapters: ['第1章 山雨入道', '第2章 拜师清玄', '第3章 筑基难', '第4章 秘境开', '第5章 一符定生死'],
  },
  {
    id: 'guyan', name: '古言权谋', tag: '晋江 · 女频', cover: EW_SCENE('paper-bamboo.jpg'),
    genre: '古代言情', style: '权谋宅斗 · 细腻克制',
    desc: '深宫棋局，人人皆子。女主以柔克刚，从棋子走到执棋人。情感线与权谋线双线咬合，每章留一个钩子。',
    chapters: ['第1章 入宫', '第2章 初见锋芒', '第3章 暗流', '第4章 结盟', '第5章 宫变'],
  },
  {
    id: 'xuanyi', name: '悬疑灵异', tag: '七猫 · 强悬念', cover: EW_SCENE('ink-wash.jpg'),
    genre: '悬疑灵异', style: '冷峻写实 · 层层反转',
    desc: '一桩看似普通的失踪案，牵出小镇百年的秘密。开篇即抛出诡异细节，每三章一次认知翻盘。',
    chapters: ['第1章 失踪的第七天', '第2章 井底的声音', '第3章 旧档案', '第4章 深夜访客', '第5章 真相的一半'],
  },
  {
    id: 'erci', name: '二次元轻小说', tag: '轻小说 · 校园异能', cover: EW_SCENE('sakura-blade.jpg'),
    genre: '二次元轻小说', style: '轻快日常 · 张力战斗',
    desc: '转生到剑与樱花的异世界，开局一把断刀。日常写羁绊，战斗写代价，每卷一个小高潮。',
    chapters: ['第1章 转生与断刀', '第2章 樱花下的邂逅', '第3章 第一次契约', '第4章 学院排名战', '第5章 雨夜决战'],
  },
  {
    id: 'guoman', name: '国漫热血', tag: '短剧改编 · 强画面', cover: EW_SCENE('ne-zha.jpg'),
    genre: '热血国漫', style: '画面感 · 逆天改命',
    desc: '天生异象的少年被视作灾星，逆天而行。写法重画面与台词节奏，适合改编短剧与漫画。',
    chapters: ['第1章 灾星降世', '第2章 第一次觉醒', '第3章 宿敌', '第4章 闹海', '第5章 逆天'],
  },
  {
    id: 'dushi', name: '都市高武', tag: '番茄 · 快节奏', cover: EW_SCENE('tokusatsu.jpg'),
    genre: '都市高武', style: '快节奏 · 强冲突',
    desc: '灵气复苏，城市成为猎场。主角开局觉醒冷门异能，用信息差与狠劲在城市夹缝中崛起。',
    chapters: ['第1章 灵气复苏', '第2章 觉醒', '第3章 第一战', '第4章 猎人协会', '第5章 封神之路'],
  },
];

let ewTpl = null;

function ewRenderTemplates() {
  const box = $('#tplStrip');
  if (!box) return;
  box.innerHTML = EW_TEMPLATES.map((t) => `
    <button class="tpl-card${ewTpl === t.id ? ' on' : ''}" data-tpl="${t.id}" title="${esc(t.desc)}">
      <i style="background-image:url('${t.cover}')"></i>
      <b>${esc(t.name)}</b><span>${esc(t.tag)}</span>
    </button>`).join('')
    + `<button class="tpl-card tpl-clear${ewTpl ? '' : ' on'}" data-tpl=""><b>空白书</b><span>不用模板</span></button>`;
}

function ewPickTemplate(id) {
  ewTpl = id || null;
  const t = EW_TEMPLATES.find((x) => x.id === id);
  if (t) {
    $('#newBookGenre').value = t.genre;
    $('#newBookStyle').value = t.style;
    $('#newBookName').placeholder = `${t.name}·书名`;
  } else {
    $('#newBookGenre').value = '';
    $('#newBookStyle').value = '';
    $('#newBookName').placeholder = '例如：青冥引';
  }
  ewRenderTemplates();
}

/* ---- 成就徽章 ---- */
function ewDayKey(d) { return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; }

function ewStats() {
  const daily = store.json(KEY.daily, {}) || {};
  const vals = Object.keys(daily).map((k) => Number(daily[k]) || 0);
  const total = vals.reduce((a, b) => a + b, 0);
  const days = vals.filter((v) => v > 0).length;
  const maxDay = vals.length ? Math.max.apply(null, vals) : 0;
  let streak = 0;
  for (let i = 0; i < 500; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const v = Number(daily[ewDayKey(d)] || 0);
    if (v > 0) streak++;
    else if (i > 0) break;
  }
  const chapters = (S.files || []).filter((f) => f.type === 'FILE').length;
  const bookWords = (S.files || []).filter((f) => f.type === 'FILE').reduce((a, f) => a + wordCount(f.content), 0);
  const chars = S.book ? charList() : [];
  const villains = chars.filter((c) => c.group === '反派').length;
  const worldLen = S.book && S.book.world ? String(S.book.world.content || '').length : 0;
  const fores = S.book ? (store.json(KEY.foreshadow(S.book.name), []) || []).length : 0;
  const snaps = S.book ? (store.json(KEY.snaps(S.book.name), []) || []).length : 0;
  const chats = (S.chat || []).filter((m) => m.role === 'user').length;
  const mods = (store.json(EW_MOD_KEY, []) || []).length;
  return {
    total, days, maxDay, streak, books: (S.books || []).length, chapters, bookWords,
    chars: chars.length, villains, worldLen, fores, snaps, chats, mods,
    desc: S.book ? String(S.book.description || '').length : 0,
    hasMeta: !!(S.book && S.book.genre && S.book.style),
    hasAuthor: !!(S.book && S.book.author),
    selfCheck: Number(store.get('fj:ew:selfcheck', '0')) || 0,
  };
}

const EW_BADGES = [
  { id: '01-first-login', name: '初来乍到', desc: '第一次打开写作台', ok: () => true },
  { id: '02-new-author', name: '新晋作者', desc: '为作品填上笔名', ok: (s) => s.hasAuthor },
  { id: '03-first-writing', name: '初次落笔', desc: '累计码字 100 字', ok: (s) => s.total >= 100 },
  { id: '04-checkin-master', name: '签到达人', desc: '连续 7 天有产出', ok: (s) => s.streak >= 7 },
  { id: '05-diligent-author', name: '勤奋作者', desc: '累计写作 15 天', ok: (s) => s.days >= 15 },
  { id: '06-first-chapter', name: '首章达成', desc: '书里出现第 1 个章节', ok: (s) => s.chapters >= 1 },
  { id: '07-ten-chapters', name: '十章里程碑', desc: '章节数达到 10', ok: (s) => s.chapters >= 10 },
  { id: '08-hundred-chapter-author', name: '百章大家', desc: '章节数达到 100', ok: (s) => s.chapters >= 100 },
  { id: '09-character-director', name: '人物总监', desc: '人物档案 10 个', ok: (s) => s.chars >= 10 },
  { id: '09-synopsis-polisher', name: '简介打磨师', desc: '作品简介 80 字以上', ok: (s) => s.desc >= 80 },
  { id: '10-ai-partner', name: 'AI 搭档', desc: '与搭子对话 10 轮', ok: (s) => s.chats >= 10 },
  { id: '10-genre-positioner', name: '题材定位师', desc: '填写题材与风格', ok: (s) => s.hasMeta },
  { id: '11-worldbuilding-collector', name: '世界观收藏家', desc: '世界观设定 300 字', ok: (s) => s.worldLen >= 300 },
  { id: '12-villain-designer', name: '反派设计师', desc: '反派档案 3 个', ok: (s) => s.villains >= 3 },
  { id: '13-foreshadowing-weaver', name: '伏笔编织者', desc: '记录 5 条伏笔', ok: (s) => s.fores >= 5 },
  { id: '14-ai-inspiration-hunter', name: '灵感猎手', desc: '与搭子聊满 5 轮', ok: (s) => s.chats >= 5 },
  { id: '15-chapter-draft-sprinter', name: '章节冲刺者', desc: '单日码字 5000', ok: (s) => s.maxDay >= 5000 },
  { id: '16-revision-trainer', name: '改稿训练师', desc: '保存 10 个版本快照', ok: (s) => s.snaps >= 10 },
  { id: '17-workflow-explorer', name: '工作流探索者', desc: '用过 3 个 AI 工坊模块', ok: (s) => s.mods >= 3 },
  { id: '18-workflow-master', name: '工作流大师', desc: '用过全部 8 个模块', ok: (s) => s.mods >= 8 },
  { id: '19-self-check-author', name: '自检作者', desc: '打开过一次自检面板', ok: (s) => s.selfCheck },
  { id: '20-continuity-guardian', name: '连贯守护者', desc: '自检 5 次', ok: (s) => s.selfCheck >= 5 },
  { id: '01-thousand-words', name: '千字起步', desc: '本书正文 1000 字', ok: (s) => s.bookWords >= 1000 },
  { id: '02-ten-thousand-words', name: '万字小成', desc: '本书正文 10000 字', ok: (s) => s.bookWords >= 10000 },
  { id: '03-hundred-thousand-author', name: '十万字作家', desc: '本书正文 100000 字', ok: (s) => s.bookWords >= 100000 },
  { id: '04-one-day-sprint', name: '单日爆发', desc: '单日码字 10000', ok: (s) => s.maxDay >= 10000 },
  { id: '05-steady-output', name: '稳定输出', desc: '连续 3 天有产出', ok: (s) => s.streak >= 3 },
  { id: '06-serial-beginner', name: '连载新星', desc: '章节数达到 5', ok: (s) => s.chapters >= 5 },
  { id: '07-thirty-chapter-trial', name: '三十章试炼', desc: '章节数达到 30', ok: (s) => s.chapters >= 30 },
];

function ewBadgeFile(id) { return EW_ASSET(`badges/${id}.png`); }

function ewUnlocked() { return store.json(EW_BADGE_KEY, {}) || {}; }

function ewCheckBadges(announce) {
  const got = ewUnlocked();
  const s = ewStats();
  let added = [];
  EW_BADGES.forEach((b) => {
    if (got[b.id]) return;
    if (b.ok(s)) { got[b.id] = todayKey(); added.push(b); }
  });
  if (added.length) {
    store.setJson(EW_BADGE_KEY, got);
    if (announce) added.slice(0, 3).forEach((b) => toast(`解锁成就：${b.name}`));
  }
}

function ewRenderBadges() {
  const grid = $('#badgeGrid');
  if (!grid) return;
  const got = ewUnlocked();
  const s = ewStats();
  const n = EW_BADGES.filter((b) => got[b.id]).length;
  $('#badgeSummary').textContent = `已点亮 ${n} / ${EW_BADGES.length} 枚 · 累计 ${s.total.toLocaleString()} 字 · ${s.chapters} 章 · 连续 ${s.streak} 天`;
  grid.innerHTML = EW_BADGES.map((b) => {
    const on = !!got[b.id];
    return `<div class="badge-item${on ? ' on' : ''}" title="${esc(b.desc)}">
      <img src="${ewBadgeFile(b.id)}" alt="" loading="lazy">
      <b>${esc(b.name)}</b><span>${esc(on ? ('点亮于 ' + got[b.id]) : b.desc)}</span>
    </div>`;
  }).join('');
}

function ewOpenBadges() {
  ewCheckBadges(true);
  ewRenderBadges();
  openModal('badgeModal');
}

/* ---- 素材库 ---- */
const EW_GALLERY = {
  scene: [
    { name: '水墨留白', path: EW_SCENE('ink-wash.jpg'), id: 'ink-wash' },
    { name: '宣纸竹影', path: EW_SCENE('paper-bamboo.jpg'), id: 'paper-bamboo' },
    { name: '青绿山水', path: EW_SCENE('green-mountain.jpg'), id: 'green-mountain' },
    { name: '水墨双龙', path: EW_SCENE('ink-dragon.jpg'), id: 'ink-dragon' },
    { name: '青绿青龙', path: EW_SCENE('green-dragon.jpg'), id: 'green-dragon' },
    { name: '樱雨刀光', path: EW_SCENE('sakura-blade.jpg'), id: 'sakura-blade' },
    { name: '哪吒闹海', path: EW_SCENE('ne-zha.jpg'), id: 'ne-zha' },
    { name: '都市巨兽', path: EW_SCENE('tokusatsu.jpg'), id: 'tokusatsu' },
  ],
  texture: [
    { name: '宣纸纹', path: EW_ASSET('textures/paper-texture.png') },
    { name: '墨环', path: EW_ASSET('textures/ink-ring.webp') },
    { name: '金墨飞白', path: EW_ASSET('textures/golden-ink.png') },
    { name: '笔锋分隔', path: EW_ASSET('textures/brush-divider.webp') },
    { name: '流光缎带', path: EW_ASSET('textures/shimmer-ribbon.png') },
    ...[1, 2, 3, 4, 5].map((i) => ({ name: `会员主题 ${i}`, path: EW_ASSET(`vip/vip${i}.webp`) })),
  ],
  icon: [
    { name: 'OpenAI', path: EW_ASSET('provider/openai.svg') },
    { name: 'Claude', path: EW_ASSET('provider/claude.svg') },
    { name: 'Gemini', path: EW_ASSET('provider/gemini.svg') },
    { name: 'DeepSeek', path: EW_ASSET('provider/deepseek.ico') },
    { name: 'MiniMax', path: EW_ASSET('provider/minimax.ico') },
    { name: '通义', path: EW_ASSET('provider/tongyi.svg') },
    { name: '火山引擎', path: EW_ASSET('provider/volcengine.png') },
    { name: '智谱', path: EW_ASSET('provider/bigmodel.png') },
    { name: 'OpenRouter', path: EW_ASSET('provider/openrouter.ico') },
    { name: '硅基流动', path: EW_ASSET('provider/siliconflow.ico') },
    { name: 'xAI', path: EW_ASSET('provider/xai.svg') },
    { name: '起点', path: EW_ASSET('platform/qidian.ico') },
    { name: '番茄', path: EW_ASSET('platform/fanqie.png') },
    { name: '晋江', path: EW_ASSET('platform/jjwxc.ico') },
    { name: '七猫', path: EW_ASSET('platform/qimao.ico') },
    { name: '长佩', path: EW_ASSET('platform/changpei.ico') },
    { name: '言选', path: EW_ASSET('platform/yanxuan.ico') },
    { name: '小忆', path: EW_ASSET('mascot/xiaoyi-mini.png') },
    { name: '小忆徽章', path: EW_ASSET('mascot/xiaoyi-badge.png') },
  ],
  audio: [
    { name: '犬吠（打字音）', path: EW_ASSET('audio/dragon-studio-dog-bark-382732.mp3') },
    { name: '枪响（打字音）', path: EW_ASSET('audio/microsammy-ak-47-firing-8760.mp3') },
  ],
};

function ewRenderAssets(tab) {
  const grid = $('#assetGrid');
  if (!grid) return;
  $$('#assetTabs button').forEach((b) => b.classList.toggle('on', b.dataset.assetTab === tab));
  const list = EW_GALLERY[tab] || [];
  grid.dataset.tab = tab;
  if (!list.length) { grid.innerHTML = '<div class="hint">这一类暂时没有素材。</div>'; return; }
  grid.innerHTML = list.map((it, i) => {
    if (tab === 'audio') {
      return `<button class="asset-item audio" data-asset="${i}"><b>▶</b><span>${esc(it.name)}</span></button>`;
    }
    return `<button class="asset-item" data-asset="${i}"><i style="background-image:url('${it.path}')"></i><span>${esc(it.name)}</span></button>`;
  }).join('');
}

function ewApplyAsset(tab, idx) {
  const it = (EW_GALLERY[tab] || [])[idx];
  if (!it) return;
  if (tab === 'audio') {
    const a = new Audio(it.path);
    a.volume = 0.8;
    a.play().catch(() => toast('浏览器拦了自动播放，先点一下页面再试'));
    return;
  }
  if (tab === 'scene') {
    setUi({ scene: it.id, customImage: '' });
    renderSceneChoices();
    closeModal($('#assetModal'));
    toast(`氛围背景已切换为「${it.name}」`);
    return;
  }
  setUi({ scene: 'custom', customImage: it.path });
  renderSceneChoices();
  closeModal($('#assetModal'));
  toast(`已设为自定义背景：${it.name}`);
}

/* ================= 第二批融合：全局搜索 / 灵感素材 / 竞品拆书 / 创作中心 ================= */
const EW_INSP_KEY = 'fj:ew:insp';
const EW_BD_KEY = 'fj:ew:bd';
const EW_CHECKIN_KEY = 'fj:ew:checkin';
let EW_SEARCH_CACHE = { books: [], chapters: [], cmds: [] };
let EW_GS_SEL = 0;
let EW_BD_LAST = null;

/* ---- 全局搜索命令表 ---- */
const EW_CMD = [
  { name: '新建书籍', desc: '开一本新书，可选 7 套模板', keys: ['新建', '新书', '开书', '模板', 'create', 'xinjian'], run: () => openBookModal() },
  { name: '切换书籍', desc: '打开书架，切换当前作品', keys: ['书架', '切换', '作品', 'shelf', 'qiehuan'], run: () => openShelf() },
  { name: '导入书籍', desc: '导入 txt / md / json', keys: ['导入', 'import', 'daoru'], run: () => openImportModal('current') },
  { name: '导出正文', desc: '导出当前章节或全书', keys: ['导出', '备份', 'export', 'daochu'], run: '#exportBtn' },
  { name: '书籍设置', desc: '题材、风格、简介、封面', keys: ['设置', '书籍设置', '简介', 'shezhi'], run: () => { if (!S.book) return toast('先打开一本书'); openBookSettings(); } },
  { name: '成就徽章', desc: '29 枚本地成就', keys: ['徽章', '成就', 'badge', 'huizhang'], run: () => ewOpenBadges() },
  { name: '素材库', desc: '背景、纹理、图标、音效', keys: ['素材', '背景图', '纹理', 'sucai'], run: () => { ewRenderAssets('scene'); openModal('assetModal'); } },
  { name: '创作中心', desc: '签到与码字排行', keys: ['签到', '排行', '榜单', 'hub', 'qiandao'], run: () => ewOpenHub() },
  { name: '竞品拆书', desc: '本地拆解竞品章节结构', keys: ['拆书', '竞品', '拆解', 'chaishu'], run: () => ewOpenBd() },
  { name: '灵感素材', desc: '收集场景、桥段、金句、反转', keys: ['灵感', '素材库', '桥段', '金句', 'linggan'], run: () => ewFocusInsp() },
  { name: '便签', desc: '本章大纲、伏笔、随手便签', keys: ['便签', '大纲', '伏笔', 'bianqian', 'fubi'], run: () => setRightTab('note') },
  { name: '世界观设定', desc: '人物、世界观、核心概念', keys: ['设定', '世界观', '人物', 'shezhi', 'renwu'], run: () => setRightTab('world') },
  { name: '写作搭子', desc: '和 AI 聊设定、桥段、改稿', keys: ['搭子', 'ai', '聊天', 'dazi'], run: () => setRightTab('companion') },
  { name: '自检面板', desc: '敏感词、AI 味、段落节奏', keys: ['自检', '敏感词', '检查', 'zijian'], run: () => setRightTab('check') },
  { name: 'AI 味检测', desc: '五维检测当前章节', keys: ['ai味', '检测', '降重', 'jiance'], run: () => { setRightTab('check'); setTimeout(() => { const b = $('#judgeBtn'); if (b) b.click(); }, 80); } },
  { name: '阅读模式', desc: '全文多人有声剧配音', keys: ['阅读', '有声', '配音', 'yuedu'], run: () => rmOpen() },
  { name: '专注模式', desc: '全屏沉浸写作', keys: ['专注', '全屏', 'zhuanzhu'], run: () => enterFocus() },
  { name: '番茄钟', desc: '25 分钟专注计时', keys: ['番茄', '计时', 'pomodoro', 'fanqie'], run: () => togglePomodoro() },
  { name: '码字锁', desc: '锁定目标字数才能换章', keys: ['码字锁', '锁定', 'mazisuo'], run: '#lockChipBtn' },
  { name: '背景与主题', desc: '氛围场景与主题色', keys: ['背景', '主题', '场景', 'beijing'], run: () => { renderSceneChoices(); openModal('bgModal'); } },
  { name: '设置', desc: '外观、AI、同步等设置', keys: ['设置', '外观', 'shezhi'], run: () => openSettings('appearance') },
  { name: '快捷键', desc: '查看全部快捷键', keys: ['快捷键', 'shortcut', 'kuaijie'], run: () => { renderShortcuts(); openModal('shortcutsModal'); } },
  { name: '伏笔清单', desc: '记录与回收伏笔', keys: ['伏笔', '回收', 'fubi'], run: () => setRightTab('note') },
  { name: '划词搜索', desc: '在当前章节查找文字', keys: ['查找', '搜索', 'find', 'chazhao'], run: () => openFind() },
];

function ewNorm(s) { return String(s || '').toLowerCase(); }
function ewHit(text, term) { return ewNorm(text).indexOf(term) >= 0; }

function ewMark(text, q) {
  const src = esc(String(text == null ? '' : text));
  const t = String(q || '').trim();
  if (!t) return src;
  try {
    const re = new RegExp(t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
    return src.replace(re, (m) => `<mark>${m}</mark>`);
  } catch (e) { return src; }
}

function ewSearchIndex(q) {
  const term = String(q || '').trim().toLowerCase();
  const out = { books: [], chapters: [], cmds: [] };
  if (!term) return out;
  (S.books || []).forEach((b) => {
    if (ewHit(b.name, term) || ewHit(b.genre, term) || ewHit(b.style, term)) {
      const isCur = !!(S.book && S.book.name === b.name);
      out.books.push({ name: b.name, genre: b.genre || '', words: Number(b.words) || 0, cur: isCur, score: (isCur ? 2 : 0) + (ewHit(b.name, term) ? 3 : 0) });
    }
  });
  out.books.sort((a, b) => b.score - a.score);
  const files = (S.files || []).filter((f) => f.type === 'FILE');
  for (let i = 0; i < files.length && out.chapters.length < 12; i++) {
    const f = files[i];
    const content = String(f.content || '');
    let idx = ewNorm(f.name).indexOf(term);
    let from = 'name';
    if (idx < 0) { idx = ewNorm(content).indexOf(term); from = 'content'; }
    if (idx < 0) continue;
    let snippet = '';
    if (from === 'content') {
      const a = Math.max(0, idx - 18);
      const b = Math.min(content.length, idx + term.length + 24);
      snippet = (a > 0 ? '…' : '') + content.slice(a, b) + (b < content.length ? '…' : '');
    }
    out.chapters.push({ id: f.id, name: f.name, book: S.book ? S.book.name : '', snippet });
  }
  EW_CMD.forEach((c) => {
    const hay = [c.name, c.desc].concat(c.keys || []).join(' | ').toLowerCase();
    if (hay.indexOf(term) >= 0) out.cmds.push(c);
  });
  return out;
}

function ewRenderSearch(q) {
  const box = $('#gsResults');
  if (!box) return;
  const term = String(q || '').trim();
  const idx = ewSearchIndex(term);
  EW_SEARCH_CACHE = idx;
  EW_GS_SEL = 0;
  if (!term) {
    box.innerHTML = '<div class="hint">输入书名、章节名或功能名。也可以直接把一句需求发给 AI。</div>';
    return;
  }
  let html = '';
  if (idx.books.length) {
    html += '<div class="gs-group">作品</div>' + idx.books.map((b, i) => `
      <button class="gs-item" data-kind="book" data-idx="${i}">
        <b class="gs-ico">书</b>
        <span class="gs-main"><b>${ewMark(b.name, term)}</b><i>${esc(b.genre || '未设题材')}${b.words ? ' · ' + fmt(b.words) + ' 字' : ''}</i></span>
        ${b.cur ? '<span class="gs-tag">当前</span>' : ''}
      </button>`).join('');
  }
  if (idx.chapters.length) {
    html += '<div class="gs-group">章节</div>' + idx.chapters.map((c, i) => `
      <button class="gs-item" data-kind="chapter" data-idx="${i}">
        <b class="gs-ico">章</b>
        <span class="gs-main"><b>${ewMark(c.name, term)}</b><i>${esc(c.book)}${c.snippet ? ' · ' + ewMark(c.snippet, term) : ''}</i></span>
      </button>`).join('');
  }
  if (idx.cmds.length) {
    html += '<div class="gs-group">功能</div>' + idx.cmds.map((c, i) => `
      <button class="gs-item" data-kind="cmd" data-idx="${i}">
        <b class="gs-ico">功</b>
        <span class="gs-main"><b>${ewMark(c.name, term)}</b><i>${ewMark(c.desc, term)}</i></span>
      </button>`).join('');
  }
  html += `<div class="gs-group">问 AI</div>
    <button class="gs-item" data-kind="ask" data-idx="0">
      <b class="gs-ico">AI</b>
      <span class="gs-main"><b>问 AI：${esc(term)}</b><i>把这个问题发给写作搭子</i></span>
    </button>`;
  box.innerHTML = html;
  const first = box.querySelector('.gs-item');
  if (first) first.classList.add('on');
}

async function ewRunSearchItem(kind, idx, q) {
  const term = String(q || '').trim();
  const modal = $('#gsModal');
  if (kind === 'ask') {
    if (!term) return;
    if (modal) closeModal(modal);
    if (isMobileView()) openMobilePane('companion', 'ai');
    else setRightTab('companion');
    setTimeout(() => sendChat(term), 80);
    return;
  }
  if (kind === 'book') {
    const b = EW_SEARCH_CACHE.books[idx];
    if (!b) return;
    if (modal) closeModal(modal);
    openBook(b.name).catch((e) => toast(e.message));
    return;
  }
  if (kind === 'chapter') {
    const c = EW_SEARCH_CACHE.chapters[idx];
    if (!c) return;
    if (modal) closeModal(modal);
    try {
      if (c.book && (!S.book || S.book.name !== c.book)) await openBook(c.book);
      await openChapter(c.id);
    } catch (e) { toast('打开章节失败：' + e.message); }
    return;
  }
  if (kind === 'cmd') {
    const c = EW_SEARCH_CACHE.cmds[idx];
    if (!c) return;
    if (modal) closeModal(modal);
    setTimeout(() => {
      try {
        if (typeof c.run === 'string') { const el = $(c.run); if (el) el.click(); }
        else if (typeof c.run === 'function') c.run();
      } catch (e) { toast('执行失败：' + e.message); }
    }, 60);
  }
}

function ewOpenSearch(prefill) {
  const inp = $('#gsInput');
  if (!inp) return;
  inp.value = prefill || '';
  openModal('gsModal');
  ewRenderSearch(inp.value);
  setTimeout(() => { inp.focus(); inp.select(); }, 60);
}

function ewFocusInsp() {
  if (isMobileView()) openMobilePane('companion', 'ai');
  else setRightTab('ai');
  setTimeout(() => {
    const el = $('#inspInput');
    if (el) { el.scrollIntoView({ block: 'center' }); el.focus(); }
  }, 100);
}

function bindSearch() {
  const btn = $('#gsBtn');
  if (btn) btn.addEventListener('click', () => ewOpenSearch());
  const inp = $('#gsInput');
  if (inp) {
    inp.addEventListener('input', () => ewRenderSearch(inp.value));
    inp.addEventListener('keydown', (e) => {
      const items = $$('#gsResults .gs-item');
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!items.length) return;
        EW_GS_SEL = (EW_GS_SEL + (e.key === 'ArrowDown' ? 1 : items.length - 1)) % items.length;
        items.forEach((it, i) => it.classList.toggle('on', i === EW_GS_SEL));
        items[EW_GS_SEL].scrollIntoView({ block: 'nearest' });
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        const el = items[EW_GS_SEL] || items[0];
        if (el) ewRunSearchItem(el.dataset.kind, Number(el.dataset.idx), inp.value);
      }
    });
  }
  const box = $('#gsResults');
  if (box) box.addEventListener('click', (e) => {
    const el = e.target.closest('.gs-item');
    if (!el) return;
    ewRunSearchItem(el.dataset.kind, Number(el.dataset.idx), $('#gsInput').value);
  });
  document.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && String(e.key || '').toLowerCase() === 'k') {
      e.preventDefault();
      ewOpenSearch();
    }
  });
}

/* ---- 灵感素材库 ---- */
let EW_INSP_KIND = '场景';

function ewInspList() {
  const v = store.json(EW_INSP_KEY, []);
  return Array.isArray(v) ? v : [];
}

function ewInspSave(list) { store.setJson(EW_INSP_KEY, (list || []).slice(0, 200)); }

function ewFmtTime(t) {
  const d = new Date(Number(t) || Date.now());
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function ewRenderInsp() {
  const box = $('#inspList');
  const all = ewInspList();
  const cnt = $('#inspCount');
  if (cnt) cnt.textContent = `${all.length} 条`;
  if (!box) return;
  if (!all.length) {
    box.innerHTML = '<div class="hint">还没有素材。写一句收进来，写正文时能一键放进光标处。</div>';
    return;
  }
  box.innerHTML = all.slice(0, 20).map((it) => `
    <div class="insp-item">
      <div class="insp-head"><span class="insp-kind">${esc(it.kind || '素材')}</span><span class="insp-time">${ewFmtTime(it.t)}</span></div>
      <div class="insp-text">${esc(it.text || '')}</div>
      <div class="insp-acts">
        <button data-insp-act="insert" data-id="${esc(it.id)}">放入正文</button>
        <button data-insp-act="chat" data-id="${esc(it.id)}">发给搭子</button>
        <button data-insp-act="del" data-id="${esc(it.id)}">删除</button>
      </div>
    </div>`).join('');
}

function ewAddInsp() {
  const el = $('#inspInput');
  const text = el ? String(el.value || '').trim() : '';
  if (!text) { toast('先写一句灵感'); return; }
  const list = ewInspList();
  list.unshift({ id: newId('insp_'), t: Date.now(), kind: EW_INSP_KIND, text });
  ewInspSave(list);
  if (el) { el.value = ''; autoGrow(el, 220); }
  ewRenderInsp();
  ewCheckBadges(false);
  toast('已收进灵感素材库');
}

function ewInsertText(text) {
  if (!S.book) { toast('先打开一本书'); return false; }
  const f = currentFile();
  if (!f) { toast('先选一个章节'); return false; }
  const el = input();
  if (!el) return false;
  const v = String(el.value || '');
  const pos = (S.cursor && S.cursor.id === f.id && S.cursor.start <= v.length) ? S.cursor.start : (el.selectionStart || 0);
  takeSnapshot(true);
  histCommit();
  const next = v.slice(0, pos) + text + v.slice(pos);
  el.value = next;
  f.content = next;
  const caret = pos + text.length;
  el.focus();
  el.setSelectionRange(caret, caret);
  S.cursor = { id: f.id, start: caret, end: caret };
  onEditorInput();
  histCommit();
  scheduleSave();
  return true;
}

async function ewInspAct(act, id) {
  const list = ewInspList();
  const it = list.find((x) => x.id === id);
  if (!it) return;
  if (act === 'insert') {
    const ok = ewInsertText('\n' + it.text + '\n');
    if (ok) toast('已放入正文');
  } else if (act === 'chat') {
    if (isMobileView()) openMobilePane('companion', 'ai');
    else setRightTab('companion');
    setTimeout(() => {
      const box = $('#chatInput');
      if (!box) return;
      box.value = `用这条灵感帮我写一段：${it.text}`;
      autoGrow(box, 150);
      box.focus();
    }, 80);
  } else if (act === 'del') {
    if (!await askConfirm('删除素材', '这条灵感会从素材库移除，正文不受影响。', '删除')) return;
    ewInspSave(list.filter((x) => x.id !== id));
    ewRenderInsp();
  }
}

function bindInsp() {
  const add = $('#inspAddBtn');
  if (add) add.addEventListener('click', ewAddInsp);
  const seg = $('#inspKindSeg');
  if (seg) seg.addEventListener('click', (e) => {
    const b = e.target.closest('[data-kind]');
    if (!b) return;
    EW_INSP_KIND = b.dataset.kind;
    $$('#inspKindSeg button').forEach((x) => x.classList.toggle('on', x === b));
  });
  const list = $('#inspList');
  if (list) list.addEventListener('click', (e) => {
    const b = e.target.closest('[data-insp-act]');
    if (b) ewInspAct(b.dataset.inspAct, b.dataset.id);
  });
  const bd = $('#breakdownBtn');
  if (bd) bd.addEventListener('click', () => ewOpenBd());
  ewRenderInsp();
}

/* ---- 竞品拆书 ---- */
const EW_STOP = new Set(['的', '了', '在', '是', '他', '她', '我', '你', '也', '就', '都', '而', '不', '有', '这', '那', '与', '和', '被', '把', '让', '给', '对', '说', '道', '着', '过', '一个', '没有', '自己', '什么', '我们', '他们', '起来', '出来', '下去', '知道', '觉得', '看着', '听得', '只是', '还是', '已经', '如果', '因为', '所以']);

function ewBreakdown(text) {
  const src = String(text || '').trim();
  const chars = wordCount(src);
  const paras = src.split(/\n+/).map((s) => s.trim()).filter(Boolean);
  const paraCount = paras.length;
  const avg = paraCount ? Math.round(chars / paraCount) : 0;
  const longest = paras.reduce((m, p) => Math.max(m, p.length), 0);
  const dlg = paras.filter((p) => /[“”「」：]/.test(p)).length;
  const dlgPct = paraCount ? Math.round((dlg / paraCount) * 100) : 0;
  const ex = (src.match(/[！!]/g) || []).length;
  const qu = (src.match(/[？?]/g) || []).length;
  const head = src.slice(0, 60);
  const tail = src.slice(-60);
  const tokens = src.match(/[\u4e00-\u9fa5]{2,}/g) || [];
  const freq = Object.create(null);
  tokens.forEach((t) => {
    if (t.length > 6 || EW_STOP.has(t)) return;
    freq[t] = (freq[t] || 0) + 1;
  });
  const top = Object.keys(freq).sort((a, b) => freq[b] - freq[a]).slice(0, 12).map((w) => ({ w, c: freq[w] }));
  const senseHits = (src.match(/像|似|仿佛|气味|声音|触感|光|影|风|雨|血|冷|烫|光|暗/g) || []).length;
  const visual = Math.min(100, Math.round(senseHits * 6));
  const rhythm = Math.round(Math.max(0, Math.min(100, (avg <= 45 ? 100 : Math.max(0, 100 - (avg - 45) * 2)) - (longest > 180 ? 20 : 0))));
  const hook = /[？?！!]|却|突然|竟|原来|门|声音|血|死|消失|不见/.test(tail) ? 88 : 40;
  const score = Math.round((visual + rhythm + hook) / 3);
  const dims = [
    { name: '画面感', v: visual },
    { name: '节奏', v: rhythm },
    { name: '钩子', v: hook },
  ];
  const low = dims.slice().sort((a, b) => a.v - b.v)[0];
  const tips = [];
  if (low.name === '画面感') {
    tips.push('增加可感知的细节：气味、声音、温度、光线，每段至少一个。');
    tips.push('把抽象情绪换成动作：不写「他很愤怒」，写「他捏碎了杯沿」。');
    tips.push('用一处比喻锚定场景，但全章不要超过三处，避免堆砌。');
  } else if (low.name === '节奏') {
    tips.push('把超过 120 字的长段拆成 3–5 行短段，手机阅读更顺。');
    tips.push('紧张处用短句，铺垫处再放长句，形成长短交替。');
    tips.push('每 800–1000 字安排一个小转折，别让读者长时间平走。');
  } else {
    tips.push('章末留一个未解的问题或反常动作，不要把所有信息交代完。');
    tips.push('最后 100 字引入新变量：一个访客、一条消息、一个声音。');
    tips.push('把「结果」往后挪，先给读者一个必须看下一章的悬念。');
  }
  return { chars, paraCount, avg, longest, dlgPct, ex, qu, head, tail, top, visual, rhythm, hook, score, tips };
}

function ewBdText(r, title) {
  return [
    `【${title || '竞品拆书'}】`,
    `总字数：${r.chars}　段落：${r.paraCount}　平均段长：${r.avg}`,
    `综合分：${r.score}　画面感：${r.visual}　节奏：${r.rhythm}　钩子：${r.hook}`,
    `对话行占比：${r.dlgPct}%　感叹句：${r.ex}　问句：${r.qu}`,
    '',
    `开篇钩子：${r.head}`,
    `结尾钩子：${r.tail}`,
    '',
    `高频词：${r.top.map((x) => `${x.w}×${x.c}`).join('　')}`,
    '',
    '建议：',
    ...r.tips.map((t, i) => `${i + 1}. ${t}`),
  ].join('\n');
}

function ewRenderBdReport(r) {
  const box = $('#bdResult');
  if (!box) return;
  box.innerHTML = `
    <div class="bd-scores">
      <div class="bd-score"><b>${r.visual}</b><span>画面感</span></div>
      <div class="bd-score"><b>${r.rhythm}</b><span>节奏</span></div>
      <div class="bd-score"><b>${r.hook}</b><span>钩子</span></div>
    </div>
    <div class="bd-rows">
      <span>总字数 <b>${r.chars}</b></span>
      <span>段落 <b>${r.paraCount}</b></span>
      <span>平均段长 <b>${r.avg}</b></span>
      <span>最长段 <b>${r.longest}</b></span>
      <span>对话占比 <b>${r.dlgPct}%</b></span>
      <span>感叹 / 问句 <b>${r.ex} / ${r.qu}</b></span>
    </div>
    <div class="bd-hook">
      <div><i>开篇 60 字</i><p>${esc(r.head)}</p></div>
      <div><i>结尾 60 字</i><p>${esc(r.tail)}</p></div>
    </div>
    <div class="bd-chips">${r.top.map((x) => `<span>${esc(x.w)}<b>×${x.c}</b></span>`).join('')}</div>
    <div class="bd-tips">${r.tips.map((t) => `<p>${esc(t)}</p>`).join('')}</div>`;
}

function ewBdList() {
  const v = store.json(EW_BD_KEY, []);
  return Array.isArray(v) ? v : [];
}

function ewRenderBdHistory() {
  const box = $('#bdHistory');
  if (!box) return;
  const list = ewBdList();
  if (!list.length) { box.innerHTML = '<div class="hint">拆解后可存进档案，最多保留 20 篇。</div>'; return; }
  box.innerHTML = list.map((it, i) => `
    <button class="bd-his-item" data-bd-his="${i}">
      <b>${esc(it.title || '未命名')}</b>
      <span>${Number(it.chars) || 0} 字 · 综合 ${Number(it.score) || 0}</span>
    </button>`).join('');
}

function ewOpenBd() {
  const inp = $('#bdInput');
  if (inp && !inp.value) inp.value = '';
  ewRenderBdHistory();
  openModal('bdModal');
  if (inp) setTimeout(() => inp.focus(), 60);
}

function ewCopyText(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => toast('报告已复制')).catch(() => ewCopyFallback(text));
      return;
    }
  } catch (e) { /* 忽略 */ }
  ewCopyFallback(text);
}

function ewCopyFallback(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); toast('报告已复制'); } catch (e) { toast('复制失败，请手动选择'); }
  ta.remove();
}

function bindBreakdown() {
  const run = $('#bdRun');
  if (run) run.addEventListener('click', () => {
    const text = String(($('#bdInput') || {}).value || '').trim();
    if (wordCount(text) < 100) { toast('太短了，至少贴 100 字'); return; }
    const r = ewBreakdown(text);
    EW_BD_LAST = r;
    ewRenderBdReport(r);
    const save = $('#bdSave');
    if (save) save.disabled = false;
  });
  const save = $('#bdSave');
  if (save) save.addEventListener('click', () => {
    if (!EW_BD_LAST) { toast('先点「开始拆解」'); return; }
    const text = String(($('#bdInput') || {}).value || '').trim();
    const title = text.split(/\n/)[0].slice(0, 20) || '竞品拆书';
    const list = ewBdList();
    list.unshift({ t: Date.now(), title, chars: EW_BD_LAST.chars, score: EW_BD_LAST.score, report: ewBdText(EW_BD_LAST, title) });
    store.setJson(EW_BD_KEY, list.slice(0, 20));
    ewRenderBdHistory();
    toast('已存入拆书档案');
  });
  const copy = $('#bdCopy');
  if (copy) copy.addEventListener('click', () => {
    if (!EW_BD_LAST) { toast('先点「开始拆解」'); return; }
    ewCopyText(ewBdText(EW_BD_LAST, '竞品拆书'));
  });
  const clear = $('#bdClearHistory');
  if (clear) clear.addEventListener('click', async () => {
    if (!ewBdList().length) { toast('档案已经是空的'); return; }
    if (!await askConfirm('清空拆书档案', '所有已保存的拆解记录都会删除。', '清空')) return;
    store.setJson(EW_BD_KEY, []);
    ewRenderBdHistory();
  });
  const his = $('#bdHistory');
  if (his) his.addEventListener('click', (e) => {
    const b = e.target.closest('[data-bd-his]');
    if (!b) return;
    const it = ewBdList()[Number(b.dataset.bdHis)];
    const box = $('#bdResult');
    if (it && box) box.textContent = it.report || '';
  });
}

/* ---- 创作中心：签到 + 本地排行 ---- */
function ewCheckinData() {
  const v = store.json(EW_CHECKIN_KEY, {});
  if (!v || !Array.isArray(v.dates)) return { dates: [], last: '' };
  return v;
}

function ewCheckinStreak() {
  const dates = ewCheckinData().dates;
  let n = 0;
  for (let i = 0; i < 400; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    if (dates.indexOf(ewDayKey(d)) >= 0) n++;
    else if (i > 0) break;
  }
  return n;
}

function ewRenderHub() {
  const daily = store.json(KEY.daily, {}) || {};
  const today = Number(daily[ewDayKey(new Date())] || 0);
  const done = ewCheckinData().dates.indexOf(ewDayKey(new Date())) >= 0;
  const streak = ewCheckinStreak();
  const st = $('#hubStreak');
  if (st) st.textContent = `连续 ${streak} 天 · 今日 ${today} 字`;
  const btn = $('#hubCheckinBtn');
  if (btn) {
    btn.disabled = done;
    btn.textContent = done ? '今日已签到' : '签到';
  }
  const rank = $('#hubRank');
  if (rank) {
    const books = (S.books || []).slice().sort((a, b) => (Number(b.words) || 0) - (Number(a.words) || 0)).slice(0, 8);
    if (!books.length) rank.innerHTML = '<div class="hint">还没有作品，先开一本书。</div>';
    else {
      const max = Math.max.apply(null, books.map((b) => Number(b.words) || 0)) || 1;
      rank.innerHTML = books.map((b, i) => {
        const w = Number(b.words) || 0;
        return `<div class="hub-rank-row">
          <b>${i + 1}</b>
          <span class="hub-name">${esc(b.name)}</span>
          <i class="hub-bar"><em style="width:${Math.round((w / max) * 100)}%"></em></i>
          <span class="hub-words">${w ? fmt(w) : '0'}</span>
        </div>`;
      }).join('');
    }
  }
  const week = $('#hubWeek');
  if (week) {
    let sum = 0;
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const v = Number(daily[ewDayKey(d)] || 0);
      sum += v;
      days.push({ label: `${d.getMonth() + 1}/${d.getDate()}`, v });
    }
    const max = Math.max.apply(null, days.map((x) => x.v)) || 1;
    week.innerHTML = days.map((x) => `<div class="hub-day${x.v ? ' on' : ''}"><i style="height:${Math.max(4, Math.round((x.v / max) * 56))}px"></i><span>${x.v || ''}</span><em>${x.label}</em></div>`).join('');
    const sumEl = $('#hubWeekSum');
    if (sumEl) sumEl.textContent = `${sum} 字`;
  }
  const tip = $('#hubTip');
  if (tip) {
    const goal = Number(S.goal) || 0;
    if (!today) tip.textContent = '今天还没有产出，先写 300 字热身。';
    else if (goal && today < goal * 0.5) tip.textContent = `今天 ${today} 字，离目标 ${goal} 字还差 ${goal - today} 字，先补一小段。`;
    else if (goal && today >= goal) tip.textContent = `今天 ${today} 字，已超过目标 ${goal} 字，状态不错。`;
    else tip.textContent = `今天 ${today} 字，保持这个节奏。`;
  }
}

function ewCheckin() {
  const dates = ewCheckinData();
  const key = ewDayKey(new Date());
  if (dates.dates.indexOf(key) >= 0) { toast('今天已经签过到了'); return; }
  const daily = store.json(KEY.daily, {}) || {};
  if (!Number(daily[key] || 0)) { toast('今天还没码字，先写几个字再来签到'); return; }
  dates.dates.push(key);
  dates.dates = dates.dates.slice(-400);
  dates.last = key;
  store.setJson(EW_CHECKIN_KEY, dates);
  ewRenderHub();
  toast(`签到成功 · 连续 ${ewCheckinStreak()} 天`);
}

function ewOpenHub() {
  ewRenderHub();
  openModal('hubModal');
}

function bindHub() {
  const open = $('#shelfHubBtn');
  if (open) open.addEventListener('click', ewOpenHub);
  const btn = $('#hubCheckinBtn');
  if (btn) btn.addEventListener('click', ewCheckin);
}

function bindEw() {
  bindSearch();
  bindInsp();
  bindBreakdown();
  bindHub();
  const tplBox = $('#tplStrip');
  if (tplBox) tplBox.addEventListener('click', (e) => {
    const b = e.target.closest('[data-tpl]');
    if (b) ewPickTemplate(b.dataset.tpl);
  });
  const badgeBtn = $('#shelfBadgeBtn');
  if (badgeBtn) badgeBtn.addEventListener('click', ewOpenBadges);
  const assetBtn = $('#assetLibBtn');
  if (assetBtn) assetBtn.addEventListener('click', () => { ewRenderAssets('scene'); openModal('assetModal'); });
  const tabs = $('#assetTabs');
  if (tabs) tabs.addEventListener('click', (e) => {
    const b = e.target.closest('[data-asset-tab]');
    if (b) ewRenderAssets(b.dataset.assetTab);
  });
  const grid = $('#assetGrid');
  if (grid) grid.addEventListener('click', (e) => {
    const b = e.target.closest('[data-asset]');
    if (b) ewApplyAsset(grid.dataset.tab || 'scene', Number(b.dataset.asset));
  });
  /* 自检 / 工坊模块使用记录，用于成就徽章 */
  const selfcheck = document.querySelectorAll('[data-nav="review"], .rtab[data-tab="check"]');
  selfcheck.forEach((el) => el.addEventListener('click', () => {
    store.set('fj:ew:selfcheck', String(Number(store.get('fj:ew:selfcheck', '0')) + 1));
  }));
  if (window.Studio && Studio.setModule && !Studio.__ewHooked) {
    const orig = Studio.setModule;
    Studio.setModule = function (m) {
      try {
        const mods = store.json(EW_MOD_KEY, []) || [];
        if (m && !mods.includes(m)) { mods.push(m); store.setJson(EW_MOD_KEY, mods); }
      } catch (e2) { /* 忽略 */ }
      return orig.apply(this, arguments);
    };
    Studio.__ewHooked = true;
  }
  ewCheckBadges(false);
  setInterval(() => ewCheckBadges(true), 90000);
}

function bind() {
  bindEw();
  /* 顶部 */
  $('#bookSwitchBtn').addEventListener('click', (e) => toggleMenu(e.currentTarget, switchBookMenu));
  $('#saveChip').addEventListener('click', () => saveNow());
  $('#pomoChip').addEventListener('click', togglePomodoro);
  $('#bgChip').addEventListener('click', () => { renderSceneChoices(); openModal('bgModal'); });
  $('#focusChip').addEventListener('click', enterFocus);
  $('#focusExit').addEventListener('click', exitFocus);
  /* 阅读模式：全文多人有声剧配音 */
  $('#readEnter').addEventListener('click', rmOpen);
  $('#rmClose').addEventListener('click', rmClose);
  $('#rmPlay').addEventListener('click', rmTogglePlay);
  $('#rmPrev').addEventListener('click', () => {
    const to = Math.max(0, (RM.cur < 0 ? 0 : RM.cur) - 1);
    rmPlayFrom(to);
  });
  $('#rmNext').addEventListener('click', () => {
    const to = Math.min(RM.all.length - 1, (RM.cur < 0 ? -1 : RM.cur) + 1);
    rmPlayFrom(to);
  });
  $('#rmRate').addEventListener('change', () => {
    const at = RM.cur;
    RM.rate = $('#rmRate').value;
    RM.cache.forEach((p) => p.then((m) => { try { URL.revokeObjectURL(m.url); } catch (e) { /* 忽略 */ } }).catch(() => {}));
    RM.cache.clear();
    rmChapterAudio(rmChapterOf(at < 0 ? 0 : at)).catch(() => {});
    if (RM.playing) rmPlayFrom(at < 0 ? 0 : at);
  });
  $('#rmCast').addEventListener('change', () => {
    const at = RM.cur;
    RM.mode = $('#rmCast').value;
    RM.cache.forEach((p) => p.then((m) => { try { URL.revokeObjectURL(m.url); } catch (e) { /* 忽略 */ } }).catch(() => {}));
    RM.cache.clear();
    rmCastAll();
    rmRenderCast();
    $('#rmSub').textContent = `${RM.all.length} 段 · ${RM.chapters.length} 章 · ${RM.mode === 'drama' ? '多人有声剧' : '单人朗读'}`;
    if (RM.playing) rmPlayFrom(at < 0 ? 0 : at);
    else rmChapterAudio(0).catch(() => {});
  });
  $('#rmMix').addEventListener('change', () => {
    const at = RM.cur;
    RM.mix = $('#rmMix').value;
    RM.cache.forEach((p) => p.then((m) => { try { URL.revokeObjectURL(m.url); } catch (e) { /* 忽略 */ } }).catch(() => {}));
    RM.cache.clear();
    rmChapterAudio(rmChapterOf(at < 0 ? 0 : at)).catch(() => {});
    if (RM.playing) rmPlayFrom(at < 0 ? 0 : at);
  });
  $('#rmScope').addEventListener('change', rmOpen);
  $('#rmDl').addEventListener('click', rmDownload);
  $('#rmStage').addEventListener('click', (e) => {
    const el = e.target.closest('[data-rm]');
    if (el) rmPlayFrom(Number(el.dataset.rm));
  });
  $('#settingsBtn').addEventListener('click', openSettings);
  $('#modelChip').addEventListener('click', openSettings);
  $('#lockChipBtn').addEventListener('click', () => {
    const ui = store.json(KEY.ui, {});
    const goal = ui.lockGoal || 500;
    $('#lockGoal').value = goal;
    $$('#lockSeg button').forEach((b) => b.classList.toggle('on', Number(b.textContent) === Number(goal)));
    openModal('lockModal');
  });

  /* 站点导航 */
  $$('.ml-nav a').forEach((a) => a.addEventListener('click', (e) => {
    e.preventDefault();
    const nav = a.dataset.nav;
    $$('.ml-nav a').forEach((x) => x.classList.toggle('on', x === a));
    if (nav === 'writer') { exitFocus(); }
    if (nav === 'library') openShelf();
    if (nav === 'ai') { if (window.Studio) window.Studio.open('concept'); else setRightTab('ai'); }
    if (nav === 'review') setRightTab('check');
    if (nav === 'settings') openSettings();
  }));

  /* 左栏 */
  $('#dailyGoalSettings').addEventListener('click', () => { $('#goalInput').value = S.goal; openModal('goalModal'); });
  $('#goalSave').addEventListener('click', () => {
    const v = Number($('#goalInput').value) || 3000;
    S.goal = v;
    store.set(KEY.goal(S.book ? S.book.name : '_'), String(v));
    closeModal($('#goalModal'));
    updateStats();
  });
  $$('#goalSeg button').forEach((b) => b.addEventListener('click', () => {
    $$('#goalSeg button').forEach((x) => x.classList.toggle('on', x === b));
    $('#goalInput').value = b.textContent;
  }));
  $('#tocSearch').addEventListener('focus', (e) => e.target.removeAttribute('readonly'));
  $('#tocSearch').addEventListener('input', () => { S.searchTouched = true; renderToc(); });
  $('#newChapterBtn').addEventListener('click', () => newChapter());
  $('#tocExpandBtn').addEventListener('click', () => {
    if (!S.book) return;
    const map = collapsedMap();
    const anyOpen = Object.keys(map).some((k) => !map[k]);
    volumeFolders().forEach((v) => { map[v.id] = anyOpen; });
    saveCollapsed(map);
    renderToc();
  });
  $('#snapBtn').addEventListener('click', () => { renderSnapList(); openModal('snapModal'); });
  $('#trashBtn').addEventListener('click', () => { renderTrashList(); openModal('trashModal'); });
  $('#exportBtn').addEventListener('click', (e) => toggleMenu(e.currentTarget, exportMenu));
  $('#newVolumeBtn').addEventListener('click', newVolume);
  $('#snapNowBtn').addEventListener('click', () => takeSnapshot(false));
  $('#leftToggle').addEventListener('click', () => {
    /* 桌面端：整条目录栏收起 / 展开；手机端仍走抽屉 */
    if (!MOBILE_MQ.matches) {
      const ui = store.json(KEY.ui, {});
      setUi({ leftHidden: !ui.leftHidden });
      return;
    }
    const left = $('#left');
    left.classList.toggle('mobile-open');
    $('#right').classList.remove('mobile-open');
    syncDrawerOffset();
  });
  $('#rightToggle').addEventListener('click', () => {
    if (!MOBILE_MQ.matches) {
      const ui = store.json(KEY.ui, {});
      setUi({ rightHidden: !ui.rightHidden });
      return;
    }
    const right = $('#right');
    right.classList.toggle('mobile-open');
    $('#left').classList.remove('mobile-open');
    syncDrawerOffset();
  });
  window.addEventListener('resize', syncDrawerOffset);

  $('#tocTree').addEventListener('click', (e) => {
    const hit = e.target.closest('.toc-hit');
    if (hit) { closeMobileSheets(); openChapter(hit.dataset.hit); return; }
    const volRow = e.target.closest('.vol-row');
    const item = e.target.closest('.ch-item');
    const act = e.target.closest('[data-act]');
    if (act && item) {
      e.stopPropagation();
      const id = item.dataset.id;
      if (act.dataset.act === 'rename') renameChapter(id);
      if (act.dataset.act === 'more') chapterMenu(id, act);
      return;
    }
    if (act && volRow) {
      const vid = volRow.parentElement.dataset.vol;
      if (act.dataset.act === 'add-to') newChapter(vid);
      if (act.dataset.act === 'vol-more') volumeMenu(vid, act);
      return;
    }
    if (volRow) {
      const vol = volRow.parentElement;
      const id = vol.dataset.vol;
      if (id === 'root') return;
      const map = collapsedMap();
      map[id] = !map[id];
      saveCollapsed(map);
      vol.classList.toggle('collapsed', map[id]);
      return;
    }
    if (item) { openChapter(item.dataset.id); $('#left').classList.remove('mobile-open'); }
  });

  /* 中栏 */
  $('#chTitle').addEventListener('input', () => autoGrow($('#chTitle'), 220));
  $('#chTitle').addEventListener('blur', onTitleChange);
  $('#chTitle').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); input().focus(); } });

  const el = input();
  lastLen = el.value.length;
  el.addEventListener('input', onEditorInput);
  /* 输入法：中间态不计数，提交时按提交的字数计一次 */
  el.addEventListener('compositionstart', () => { imeComposing = true; });
  el.addEventListener('compositionend', (ev) => {
    imeComposing = false;
    const n = String(ev.data || '').length;
    imeCommit = n;
    if (n) recordTyped(n);
    setTimeout(() => { imeCommit = 0; }, 0);
  });
  /* 速率每秒检查一次：整分钟到点才结算并更新，平时不动 */
  let rateShown = 0;
  setInterval(() => {
    const settled = tickRate();
    if (settled === undefined) return;
    const r = String(currentRate());
    if (r === rateShown) return;
    rateShown = r;
    ['#stRate', '#rateWords', '#fsRate'].forEach((sel) => {
      const node = $(sel);
      if (node) node.textContent = r;
    });
  }, 1000);
  el.addEventListener('scroll', () => { $('#backdrop').scrollTop = el.scrollTop; });
  el.addEventListener('click', () => { if (document.body.classList.contains('typewriter-on')) scrollCaretToCenter(el.selectionStart); });

  $('#typoBtn').addEventListener('click', () => openModal('typoModal'));
  $('#twBtn').addEventListener('click', () => {
    const ui = store.json(KEY.ui, {});
    setUi({ typewriter: !ui.typewriter });
    if (!ui.typewriter) scrollCaretToCenter(el.selectionStart || 0);
  });
  $('#findBtn').addEventListener('click', openFind);
  const undoBtn = $('#undoBtn');
  if (undoBtn) undoBtn.addEventListener('click', histUndo);
  const redoBtn = $('#redoBtn');
  if (redoBtn) redoBtn.addEventListener('click', histRedo);
  $('#findInput').addEventListener('input', (e) => doFind(e.target.value));
  $('#findInput').addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (!S.find.hits.length) return;
    S.find.idx = e.shiftKey
      ? (S.find.idx - 1 + S.find.hits.length) % S.find.hits.length
      : (S.find.idx + 1) % S.find.hits.length;
    renderBackdrop();
    jumpToFind();
  });
  $('#findNext').addEventListener('click', () => { if (!S.find.hits.length) return; S.find.idx = (S.find.idx + 1) % S.find.hits.length; renderBackdrop(); jumpToFind(); });
  $('#findPrev').addEventListener('click', () => { if (!S.find.hits.length) return; S.find.idx = (S.find.idx - 1 + S.find.hits.length) % S.find.hits.length; renderBackdrop(); jumpToFind(); });
  $('#findClose').addEventListener('click', closeFind);
  $('#phoneBtn').addEventListener('click', () => { renderPhonePreview(); $('#phoneDrawer').classList.add('show'); $('#drawerMask').classList.add('show'); });
  $('#phWidth').addEventListener('change', renderPhonePreview);
  $('#phApply').addEventListener('click', async () => {
    const f = currentFile();
    if (!f) { toast('先打开一章'); return; }
    const width = Number($('#phWidth').value) || 70;
    const mobile = mobileFormat(f.content || '', width);
    if (applyFormattedText(mobile, '手机排版')) {
      renderPhonePreview();
      toast('已按手机排版写回正文，可用「历史快照」撤回');
    }
  });
  $('#phCopy').addEventListener('click', async () => {
    const f = currentFile();
    if (!f) return;
    const mobile = mobileFormat(f.content || '', Number($('#phWidth').value) || 70);
    try {
      await navigator.clipboard.writeText(mobile);
      toast('已复制手机排版全文');
    } catch {
      const ta = document.createElement('textarea');
      ta.value = mobile;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      toast('已复制');
    }
  });
  const afOptions = () => ({
    punct: $('#afPunct').checked,
    merge: $('#afMerge').checked,
    blank: $('#afBlank').checked,
    indent: $('#afIndent').checked,
    dialog: $('#afDialog').checked,
  });
  $('#afPreview').addEventListener('click', () => {
    const f = currentFile();
    if (!f) { toast('先打开一章'); return; }
    const out = autoFormat(f.content || '', afOptions());
    const box = $('#afPreviewBox');
    box.hidden = false;
    box.textContent = out || '（正文为空）';
    box.scrollTop = 0;
  });
  $('#afApply').addEventListener('click', async () => {
    const f = currentFile();
    if (!f) { toast('先打开一章'); return; }
    const scopeBtn = $('#afScopeSeg .on');
    const scope = scopeBtn ? scopeBtn.dataset.afscope : 'book';
    if (scope === 'book') {
      const ok = await askConfirm('应用到全书', '会对本书所有章节执行自动排版；改动前会留快照，可在历史快照里找回。', '开始');
      if (!ok) return;
      let changed = 0;
      let words = 0;
      chapterFiles().forEach((ch) => {
        const out = autoFormat(ch.content || '', afOptions());
        if (out && out !== ch.content) { ch.content = out; changed++; words += out.length; }
      });
      if (!changed) { toast('所有章节都已是整理后的格式'); return; }
      await pushFiles();
      renderToc();
      updateStats();
      toast(`已重排全书 ${changed} 章`);
      return;
    }
    const out = autoFormat(f.content || '', afOptions());
    if (applyFormattedText(out, '自动排版')) {
      const box = $('#afPreviewBox');
      box.hidden = false;
      box.textContent = out;
    }
  });
  $$('#afScopeSeg button').forEach((b) => b.addEventListener('click', () => {
    $$('#afScopeSeg button').forEach((x) => x.classList.toggle('on', x === b));
  }));
  $('#phoneClose').addEventListener('click', closePhone);
  /* 抽屉顶部让开顶部两条工具栏，避免页签被盖住 */
  function syncDrawerOffset() {
    const bar = $('#topbar') || document.querySelector('header.ml-topbar');
    const y = bar ? Math.max(0, Math.round(bar.getBoundingClientRect().bottom)) : 0;
    ['#left', '#right'].forEach((sel) => {
      const el = $(sel);
      if (!el) return;
      /* 只有真正浮在页面上的抽屉才需要让开顶栏；并排显示的侧栏不要加内边距 */
      const floating = el.classList.contains('mobile-open') && getComputedStyle(el).position === 'fixed';
      el.style.paddingTop = floating ? y + 'px' : '';
    });
  }
  $('#drawerMask').addEventListener('click', () => {
    closePhone();
    $('#left').classList.remove('mobile-open');
    $('#right').classList.remove('mobile-open');
    $('#drawerMask').classList.remove('show');
    syncDrawerOffset();
  });
  /* 窄屏抽屉：点外面任何地方也能收起，不依赖遮罩的层叠顺序 */
  document.addEventListener('click', (e) => {
    const right = $('#right');
    const left = $('#left');
    /* 并排显示的侧栏不参与「点外面自动收起」，否则一点正文面板就没了 */
    const floating = (el) => el.classList.contains('mobile-open') && getComputedStyle(el).position === 'fixed';
    if (!floating(right) && !floating(left)) return;
    if (e.target.closest('#right') || e.target.closest('#left')
      || e.target.closest('#rightToggle') || e.target.closest('#leftToggle')
      || e.target.closest('#drawerMask') || e.target.closest('.modal-mask')
      || e.target.closest('#studio') || e.target.closest('#toasts')
      || e.target.closest('#ctxMenu') || e.target.closest('.menu')
      || e.target.closest('#phoneDrawer')) return;
    right.classList.remove('mobile-open');
    left.classList.remove('mobile-open');
    $('#drawerMask').classList.remove('show');
    syncDrawerOffset();
  }, true);
  $('#aiBtn').addEventListener('click', openAiCompanion);
  const ftToggle = $('#ftToggle');
  if (ftToggle) ftToggle.addEventListener('click', (e) => {
    e.stopPropagation();
    const ui = store.json(KEY.ui, {});
    setUi({ ftMin: !ui.ftMin });
  });
  const ftHandle = $('#ftHandle');
  if (ftHandle) {
    ftHandle.addEventListener('click', (e) => { e.stopPropagation(); setUi({ ftMin: false }); });
    ftHandle.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setUi({ ftMin: false }); }
    });
  }
  /* 侧栏收起后贴边的箭头把手 → 点一下把该栏拉回来 */
  ['leftHandle', 'rightHandle'].forEach((id) => {
    const el = $(`#${id}`);
    if (!el) return;
    const reopen = () => setUi(id === 'leftHandle' ? { leftHidden: false } : { rightHidden: false });
    el.addEventListener('click', (e) => { e.stopPropagation(); reopen(); });
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); reopen(); }
    });
  });
  /* 分类按钮 → 抽屉 */
  document.querySelectorAll('.ft-cat').forEach((b) => {
    b.addEventListener('click', (e) => { e.stopPropagation(); openFtDrawer(b.dataset.cat); });
  });
  const ftDrawerEl = $('#ftDrawer');
  if (ftDrawerEl) ftDrawerEl.addEventListener('click', (e) => { if (e.target.closest('.ft')) closeFtDrawer(); });
  document.addEventListener('click', (e) => {
    if (e.target.closest('#ftDrawer') || e.target.closest('.float-tools')) return;
    closeFtDrawer();
  });
  syncFloatTools();
  let ftRaf = 0;
  const queueFtSync = () => { cancelAnimationFrame(ftRaf); ftRaf = requestAnimationFrame(syncFloatTools); };
  window.addEventListener('resize', queueFtSync);
  if (window.ResizeObserver) new ResizeObserver(queueFtSync).observe($('#center'));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(queueFtSync).catch(() => {});
  $('#writeSetBtn').addEventListener('click', () => { renderSceneChoices(); syncSfxUi(); openModal('bgModal'); });
  $('#dictateBtn').addEventListener('click', toggleDictate);
  $('#canvasBtn').addEventListener('click', openCanvas);
  $('#worldCanvasBtn').addEventListener('click', openCanvas);
  $('#canvasClose').addEventListener('click', () => closeModal($('#canvasModal')));
  $('#sfxSeg').addEventListener('click', (e) => {
    const b = e.target.closest('[data-sfx]');
    if (!b) return;
    setUi({ sfx: b.dataset.sfx });
    syncSfxUi();
    if (b.dataset.sfx !== 'none') { sfxLast = 0; sfxOn(); }
  });
  $('#sfxVol').addEventListener('input', (e) => {
    const v = Number(e.target.value);
    setUi({ sfxVol: v });
    $('#sfxVolVal').textContent = v + '%';
  });
  /* 写作设置：正文排版 / 字色 / 光标居中 */
  [['wsSize', 'size'], ['wsLeading', 'leading'], ['wsIndent', 'indent'], ['wsSide', 'side']].forEach(([id, key]) => {
    const el = $('#' + id);
    if (el) el.addEventListener('input', () => setUi({ [key]: Number(el.value) }));
  });
  $$('#wsFamily button').forEach((b) => b.addEventListener('click', () => setUi({ family: b.dataset.family, fontName: '' })));
  $('#wsFontApply').addEventListener('click', () => {
    const v = $('#wsFontName').value.trim();
    setUi({ fontName: v });
    toast(v ? '正文字体：' + v : '已恢复默认字体');
  });
  $$('#wsInkSeg button').forEach((b) => b.addEventListener('click', () => {
    setUi({ ink: b.dataset.ink === 'custom' ? ($('#wsInkColor').value || '#1d1e20') : '' });
  }));
  $('#wsInkColor').addEventListener('input', (e) => setUi({ ink: e.target.value }));
  $('#wsTypewriter').addEventListener('click', () => {
    const ui = store.json(KEY.ui, {});
    setUi({ typewriter: !ui.typewriter });
  });
  $('#scHint').addEventListener('click', () => { renderShortcuts(); openModal('shortcutsModal'); });

  /* 右栏 */
  $$('.rtab').forEach((b) => b.addEventListener('click', () => {
    setRightTab(b.dataset.tab);
    if (b.dataset.tab !== 'companion') $('#right').classList.remove('ai-float-mode');
  }));
  $('#outlineSaveBtn').addEventListener('click', saveChapterOutline);
  $('#outlineNote').addEventListener('blur', saveChapterOutline);
  $('#scratchNote').addEventListener('input', () => store.set(KEY.scratch(S.book ? S.book.name : '_'), $('#scratchNote').value));
  $('#foreshadowAdd').addEventListener('click', async () => {
    const text = await askText('记一笔伏笔', '可以换行，每行记成一条；Ctrl / ⌘ + Enter 提交', '', 'multiline');
    if (!text) return;
    const list = foreshadowItems();
    text.split(/\n+/).map((s) => s.trim()).filter(Boolean).forEach((t) => list.push({ text: t, done: false }));
    await saveForeshadows();
  });
  $('#foreshadowList').addEventListener('click', async (e) => {
    const edit = e.target.closest('[data-fs-edit]');
    if (edit) {
      const list = foreshadowItems();
      const i = Number(edit.dataset.fsEdit);
      const cur = list[i];
      if (!cur) return;
      const v = await askText('编辑伏笔', '可以换行，提交后保留换行', cur.text || '', 'multiline');
      if (v === null) return;
      cur.text = v;
      await saveForeshadows();
      return;
    }
    const del = e.target.closest('[data-fs-del]');
    if (del) {
      const list = foreshadowItems();
      const i = Number(del.dataset.fsDel);
      const ok = await askConfirm('删除伏笔', `确定删除「${(list[i] || {}).text || ''}」？`, '删除');
      if (!ok) return;
      list.splice(i, 1);
      await saveForeshadows();
    }
  });
  $('#foreshadowList').addEventListener('change', async (e) => {
    const i = e.target.dataset.fs;
    if (i == null) return;
    const list = foreshadowItems();
    if (list[i]) { list[i].done = e.target.checked; await saveForeshadows(); }
  });
  $('#worldRefresh').addEventListener('click', async () => {
    renderWorld();
    await scanChapterCharacters(true);
  });
  $('#worldGen').addEventListener('click', aiWorld);
  $('#worldSave').addEventListener('click', saveWorldText);
  $('#worldText').addEventListener('blur', () => { if (S.book) saveWorldText(); });
  $('#conceptGen').addEventListener('click', aiConcept);
  $('#addCharBtn').addEventListener('click', () => {
    resetCharForm();
    openModal('charModal');
    setTimeout(() => $('#charName').focus(), 50);
  });
  $('#charSave').addEventListener('click', addCharacter);
  $$('#charGroup button').forEach((b) => b.addEventListener('click', () => {
    $$('#charGroup button').forEach((x) => x.classList.toggle('on', x === b));
  }));
  $$('#charPurpose .ch-chip').forEach((b) => b.addEventListener('click', () => b.classList.toggle('on')));
  $('#worldList').addEventListener('click', (e) => {
    const ins = e.target.closest('[data-insert]');
    if (ins) { insertAtCursor(ins.dataset.insert); return; }
    const openChar = e.target.closest('[data-char-open]');
    if (openChar) {
      const it = charList()[Number(openChar.dataset.charOpen)];
      if (it && window.Studio && window.Studio.openCharacter) window.Studio.openCharacter(it.name);
      return;
    }
    const del = e.target.closest('[data-char-del]');
    if (del) deleteCharacter(Number(del.dataset.charDel));
  });

  $('#aiGenChapter').addEventListener('click', aiGenerateChapter);
  $('#aiContinue').addEventListener('click', aiContinue);
  $('#aiRewrite').addEventListener('click', aiRewrite);
  $('#aiHumanize').addEventListener('click', aiHumanize);
  $('#aiNames').addEventListener('click', aiNames);
  $('#aiIdea').addEventListener('click', aiIdea);
  $('#aiOutline').addEventListener('click', aiOutline);
  $('#aiOutlineSaveBtn').addEventListener('click', saveAiOutline);
  $('#namePool').addEventListener('click', (e) => {
    const b = e.target.closest('[data-insert]');
    if (b) insertAtCursor(b.dataset.insert);
  });
  $('#nameModal').addEventListener('click', (e) => {
    const cat = e.target.closest('[data-ngcat]');
    if (cat) {
      const st = ngState();
      st.cat = cat.dataset.ngcat;
      st.names = [];
      st.engine = '';
      renderNameGen();
      return;
    }
    const opt = e.target.closest('[data-ngopt]');
    if (opt) { const st = ngState(); st.vals[st.cat][opt.dataset.ngopt] = opt.dataset.ngval; renderNameGen(); return; }
    const nm = e.target.closest('[data-ngname]');
    if (nm) { insertAtCursor(nm.dataset.ngname); toast('已插入：' + nm.dataset.ngname); return; }
    if (e.target.closest('#ngRun')) { runNameGen(); return; }
    if (e.target.closest('#ngClear')) {
      const st = ngState();
      st.names = [];
      st.engine = '';
      renderNameGen();
    }
  });
  $('#nameModal').addEventListener('input', (e) => {
    const st = ngState();
    if (e.target.id === 'ngCount') {
      st.count = Number(e.target.value) || 14;
      $('#ngCountVal').textContent = st.count;
      return;
    }
    if (e.target.id === 'ngReq') { st.req = e.target.value; return; }
    if (e.target.dataset.nginput) st.vals[st.cat][e.target.dataset.nginput] = e.target.value;
  });
  $('#aiInsertBtn').addEventListener('click', () => insertAtCursor(S.lastAi.text || ''));
  $('#aiReplaceBtn').addEventListener('click', async () => {
    const f = currentFile();
    if (!f || !S.lastAi.text) return;
    const ok = await askConfirm('替换正文', '整章正文会被 AI 产出覆盖（可先存一份快照）。', '替换');
    if (!ok) return;
    takeSnapshot(true);
    input().value = S.lastAi.text;
    f.content = S.lastAi.text;
    onEditorInput();
    toast('已替换');
  });

  $('#lexBtn').addEventListener('click', () => { renderLexModal(); openModal('lexModal'); });
  $('#lexAddBtn').addEventListener('click', addLex);
  $('#lexInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') addLex(); });
  $('#lexModalBox').addEventListener('click', (e) => {
    const d = e.target.closest('[data-del-lex]');
    if (!d) return;
    const custom = store.json(KEY.lex, []).filter((w) => w !== d.dataset.delLex);
    store.setJson(KEY.lex, custom);
    renderLexModal(); applySensitivity();
  });
  $('#judgeBtn').addEventListener('click', judgeAi);
  const jmode = $('#judgeModeSeg');
  if (jmode) {
    jmode.addEventListener('click', (e) => {
      const b = e.target.closest('[data-jmode]');
      if (!b) return;
      Array.from(jmode.querySelectorAll('button')).forEach((x) => x.classList.toggle('on', x === b));
    });
  }
  const judgeDetail = $('#judgeDetail');
  if (judgeDetail) {
    judgeDetail.addEventListener('click', (e) => {
      const hit = e.target.closest('[data-jpara]');
      if (hit) judgeJumpParagraph(Number(hit.dataset.jpara));
    });
  }
  $('#senList').addEventListener('click', (e) => {
    const t = e.target.closest('[data-jump]');
    if (!t) return;
    jumpToWord(t.dataset.jump);
  });
  const repeatList = $('#repeatList');
  if (repeatList) {
    repeatList.addEventListener('click', (e) => {
      const t = e.target.closest('[data-jump]');
      if (t) jumpToWord(t.dataset.jump);
    });
  }
  const rhythmList = $('#rhythmList');
  if (rhythmList) {
    rhythmList.addEventListener('click', (e) => {
      const t = e.target.closest('[data-jpara]');
      if (t) judgeJumpParagraph(Number(t.dataset.jpara));
    });
  }

  $('#chatSend').addEventListener('click', () => sendChat());
  $('#chatInput').addEventListener('input', () => autoGrow($('#chatInput'), 150));
  $('#chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  $('#chatQuick').addEventListener('click', (e) => {
    const b = e.target.closest('[data-prompt]');
    if (b) sendChat(b.dataset.prompt);
  });
  $('#chatLog').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-cact]');
    if (!b) return;
    const msg = S.chat[Number(b.dataset.i)];
    if (!msg) return;
    if (b.dataset.cact === 'retract' || b.dataset.cact === 'edit') {
      retractQuestion(Number(b.dataset.i));
      return;
    }
    if (b.dataset.cact === 'insert') { applyChatToText(b, msg); return; }
    if (b.dataset.cact === 'copy') {
      const ok = await copyText(msg.text);
      toast(ok ? '已复制' : '复制失败，请手动选中');
    }
  });
  $('#chatHistory').addEventListener('click', (e) => openConvHistory(e.currentTarget));
  $('#chatNew').addEventListener('click', () => newConversation());
  $('#chatClear').addEventListener('click', async () => {
    if (!S.chat.length) return;
    const ok = await askConfirm('清空对话', '只清空聊天记录，不动正文。', '清空');
    if (!ok) return;
    S.chat.length = 0;
    saveChat();
    renderChat();
  });
  $('#input').addEventListener('mouseup', updateChatCtx);
  $('#input').addEventListener('keyup', updateChatCtx);
  /* Ctrl+Z 撤销 / Ctrl+Y、Ctrl+Shift+Z 重做 */
  $('#input').addEventListener('keydown', (e) => {
    if (!(e.ctrlKey || e.metaKey)) return;
    const k = String(e.key || '').toLowerCase();
    if (k === 'z') { e.preventDefault(); if (e.shiftKey) histRedo(); else histUndo(); return; }
    if (k === 'y') { e.preventDefault(); histRedo(); }
  });
  const rememberCursor = () => {
    const el = input();
    if (!el || !S.chapterId) return;
    S.cursor = { id: S.chapterId, start: el.selectionStart || 0, end: el.selectionEnd || 0 };
  };
  ['input', 'keyup', 'mouseup', 'click', 'blur'].forEach((ev) => $('#input').addEventListener(ev, rememberCursor));

  /* 手机端顶栏 / 底部标签 */
  $('#mTocBtn').addEventListener('click', openMobileToc);
  $('#mMoreBtn').addEventListener('click', () => {
    const sheet = $('#mMoreSheet');
    const show = sheet.hidden;
    closeMobileSheets(true);
    sheet.hidden = !show;
    setMobileTab(show ? 'more' : 'write');
  });
  $$('#mTabs .m-tab').forEach((b) => b.addEventListener('click', () => {
    const k = b.dataset.mtab;
    if (k === 'write') {
      closeMobileSheets();
      const el = input();
      if (el) el.focus();
    } else if (k === 'toc') {
      openMobileToc();
    } else if (k === 'ai') {
      openMobilePane('companion', 'ai');
    } else if (k === 'world') {
      openMobilePane('world', 'world');
    } else {
      const sheet = $('#mMoreSheet');
      const show = sheet.hidden;
      closeMobileSheets(true);
      sheet.hidden = !show;
      setMobileTab(show ? 'more' : 'write');
    }
  }));
  $$('#mLeftTabs button').forEach((b) => b.addEventListener('click', () => setLeftTab(b.dataset.ltab)));
  const bookCardEl = document.querySelector('#left .book-card');
  if (bookCardEl) {
    bookCardEl.style.cursor = 'pointer';
    bookCardEl.title = '点击编辑书籍信息';
    bookCardEl.addEventListener('click', () => {
      if (S.book) openBookSettings();
      else openShelf();
    });
  }
  const moreActions = {
    mSheetBook: () => { closeMobileSheets(true); setLeftTab('book'); $('#left').classList.add('mobile-open'); setMobileTab('toc'); },
    mSheetBookSettings: () => {
      closeMobileSheets();
      if (S.book) openBookSettings();
      else openShelf();
    },
    mSheetStudio: () => { closeMobileSheets(); if (window.Studio) window.Studio.open('project'); },
    mSheetShelf: () => { closeMobileSheets(); openShelf(); },
    mSheetSettings: () => { closeMobileSheets(); openSettings('api'); },
    mSheetTypo: () => { closeMobileSheets(); $('#typoBtn').click(); },
    mSheetUndo: () => { closeMobileSheets(); histUndo(); },
    mSheetRedo: () => { closeMobileSheets(); histRedo(); },
    mSheetFind: () => { closeMobileSheets(); openFind(); },
    mSheetFocus: () => { closeMobileSheets(); enterFocus(); },
    mSheetPhone: () => { closeMobileSheets(); renderPhonePreview(); $('#phoneDrawer').classList.add('show'); $('#drawerMask').classList.add('show'); },
    mSheetSnap: () => { closeMobileSheets(); takeSnapshot(false); },
    mSheetWriteSet: () => { closeMobileSheets(); renderSceneChoices(); syncSfxUi(); openModal('bgModal'); },
    mSheetDictate: () => { closeMobileSheets(); toggleDictate(); },
    mSheetCanvas: () => { closeMobileSheets(); openCanvas(); },
    mSheetImport: () => { closeMobileSheets(); openImportModal('chapter'); },
    mSheetExport: () => { closeMobileSheets(); $('#exportBtn').click(); },
  };
  Object.keys(moreActions).forEach((id) => {
    const el = $('#' + id);
    if (el) el.addEventListener('click', moreActions[id]);
  });
  document.addEventListener('click', (e) => {
    const sheet = $('#mMoreSheet');
    if (!sheet || sheet.hidden) return;
    if (e.target.closest('#mMoreSheet') || e.target.closest('#mMoreBtn') || e.target.closest('[data-mtab="more"]')) return;
    sheet.hidden = true;
    setMobileTab('write');
  }, true);
  MOBILE_MQ.addEventListener('change', applyMobileChrome);
  applyMobileChrome();
  initDesktopShell();
  renderChatMode();

  /* 页内输入 / 确认 */
  $$('textarea.note-area:not(.chat-input)').forEach((el) => {
    el.addEventListener('input', () => autoGrow(el, 260));
    autoGrow(el, 260);
  });
  $('#inputOk').addEventListener('click', () => settleInput(true));
  $('#inputCancel').addEventListener('click', () => settleInput(false));
  $('#inputValue').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); settleInput(true); } });
  $('#inputArea').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); settleInput(true); }
  });
  $('#inputArea').addEventListener('input', () => autoGrow($('#inputArea'), 320));
  $('#confirmOk').addEventListener('click', () => settleConfirm(true));
  $('#confirmCancel').addEventListener('click', () => settleConfirm(false));
  $('#pickCancel').addEventListener('click', () => settlePick(null));
  $('#pickList').addEventListener('click', (e) => {
    const b = e.target.closest('.pick-item');
    if (b) settlePick(b.dataset.pk);
  });

  /* 弹窗关闭 */
  document.addEventListener('click', (e) => {
    const close = e.target.closest('[data-close]');
    if (close) { const m = close.closest('.modal-mask'); if (m) closeModal(m); return; }
    if (e.target.classList.contains('modal-mask')) closeModal(e.target);
  });

  /* 菜单外点击收起 */
  document.addEventListener('click', (e) => {
    const menu = $('#ctxMenu');
    if (!menu || menu.hidden) return;
    if (menu.contains(e.target)) return;
    if (menuAnchorEl && menuAnchorEl.contains(e.target)) return;
    hideMenu();
  });

  /* 窄屏抽屉：点空白处收起 */
  document.addEventListener('pointerdown', (e) => {
    const left = $('#left');
    const right = $('#right');
    const floating = (el) => el.classList.contains('mobile-open') && getComputedStyle(el).position === 'fixed';
    if (!floating(left) && !floating(right)) return;
    if (e.target.closest('#left') || e.target.closest('#right')) return;
    if (e.target.closest('#leftToggle') || e.target.closest('#rightToggle')) return;
    left.classList.remove('mobile-open');
    right.classList.remove('mobile-open');
  });
  $('#lockStart').addEventListener('click', () => {
    S.lock.on = true;
    S.lock.goal = Number($('#lockGoal').value) || 500;
    S.lock.startWords = wordCount(currentFile() && currentFile().content);
    closeModal($('#lockModal'));
    renderLock();
    $('#lockBanner').classList.add('show');
    toast('已上锁，写满 ' + S.lock.goal + ' 字解锁');
  });
  $$('#lockSeg button').forEach((b) => b.addEventListener('click', () => {
    $$('#lockSeg button').forEach((x) => x.classList.toggle('on', x === b));
    $('#lockGoal').value = b.textContent;
  }));
  $('#newBookSave').addEventListener('click', createBook);
  $('#snapList').addEventListener('click', (e) => {
    const r = e.target.closest('[data-restore-snap]');
    if (r) { restoreSnap(Number(r.dataset.restoreSnap)); return; }
    const d = e.target.closest('[data-del-snap]');
    if (d) deleteSnap(Number(d.dataset.delSnap));
  });
  $('#trashList').addEventListener('click', (e) => {
    const r = e.target.closest('[data-restore-trash]');
    if (r) { restoreFromTrash(Number(r.dataset.restoreTrash)); return; }
    const p = e.target.closest('[data-purge-trash]');
    if (p) { purgeTrash(Number(p.dataset.purgeTrash)); return; }
    if (e.target.closest('#trashClearBtn')) clearTrash();
  });
  $('#lockCancel').addEventListener('click', () => {
    S.lock.on = false;
    $('#lockBanner').classList.remove('show');
    renderLock();
    toast('码字锁已解除');
  });
  $('#bsSave').addEventListener('click', saveBookSettings);
  $('#bsCoverUpload').addEventListener('click', () => { const inp = $('#bsCoverFile'); inp.value = ''; inp.click(); });
  $('#bsCoverFile').addEventListener('change', (e) => handleCoverFile(e.target.files && e.target.files[0]));
  $('#bsCoverClear').addEventListener('click', async () => {
    if (!S.book) return;
    await saveProjectFields({ cover: '' });
    S.book.cover = '';
    updateCoverPreview(S.book);
    renderBookHead();
    await loadBooks();
    renderShelf();
    toast('封面已清除');
  });
  $('#bsDelete').addEventListener('click', async () => {
    if (!S.book) return;
    const typed = await askText('删除书籍', `输入书名「${S.book.name}」以确认删除（服务端会保留一份 projects/_trash 备份）`, '');
    if (typed !== S.book.name) {
      if (typed !== null) toast('书名不一致，已取消');
      return;
    }
    closeModal($('#bookSettingsModal'));
    await deleteBook(true);
  });
  $('#shelfNewBtn').addEventListener('click', () => { closeModal($('#shelfModal')); openBookModal(); });
  $('#shelfImportBtn').addEventListener('click', () => { closeModal($('#shelfModal')); openImportModal('new'); });
  $('#importChapterBtn').addEventListener('click', () => openImportModal('current'));
  $('#importPick').addEventListener('click', () => $('#importFileInput').click());
  $('#importFileInput').addEventListener('change', (e) => {
    importState.files = Array.from(e.target.files || []);
    const names = importState.files.map((f) => f.name);
    $('#importFileInfo').textContent = importState.files.length
      ? `${importState.files.length} 个文件：${names.slice(0, 3).join('、')}${names.length > 3 ? '…' : ''}`
      : '未选择文件';
    if (!$('#importBookName').value && importState.files.length) {
      $('#importBookName').value = importState.files[0].name.replace(/\.[^.]+$/, '');
    }
  });
  $$('#importModeSeg button').forEach((b) => b.addEventListener('click', () => {
    importState.mode = b.dataset.mode;
    $$('#importModeSeg button').forEach((x) => x.classList.toggle('on', x === b));
    $('#importNameField').hidden = importState.mode !== 'new';
  }));
  $$('#importSplitSeg button').forEach((b) => b.addEventListener('click', () => {
    importState.split = b.dataset.split;
    $$('#importSplitSeg button').forEach((x) => x.classList.toggle('on', x === b));
  }));
  $('#importStart').addEventListener('click', runImport);
  $('#shelfGrid').addEventListener('click', (e) => {
    const setBtn = e.target.closest('[data-shelf-settings]');
    if (setBtn) {
      e.stopPropagation();
      const name = setBtn.dataset.shelfSettings;
      closeModal($('#shelfModal'));
      openBookSettings(name);
      return;
    }
    const card = e.target.closest('[data-book]');
    if (!card) return;
    const name = card.dataset.book;
    closeModal($('#shelfModal'));
    if (S.book && name === S.book.name) return;
    openBook(name).catch((err) => toast(err.message));
  });
  bindDrag();

  /* 排版滑块 */
  $('#typoSize').addEventListener('input', (e) => setUi({ size: Number(e.target.value) }));
  $('#typoLeading').addEventListener('input', (e) => setUi({ leading: Number(e.target.value) }));
  $('#typoIndent').addEventListener('input', (e) => setUi({ indent: Number(e.target.value) }));
  $$('#typoFamily button').forEach((b) => b.addEventListener('click', () => setUi({ family: b.dataset.family })));
  $$('#themeSeg button, #setThemeSeg button').forEach((b) => b.addEventListener('click', () => setUi({ theme: b.dataset.themeBtn })));
  $$('#paperSeg button, #setPaperSeg button').forEach((b) => b.addEventListener('click', () => setUi({ paper: b.dataset.paperBtn })));
  $$('#sceneScopeSeg button, #setScopeSeg button').forEach((b) => b.addEventListener('click', () => setUi({ sceneScope: b.dataset.scope })));
  const pickScene = (id) => {
    if (id === 'custom' && !store.json(KEY.ui, {}).customImage) { pickBackgroundImage(); return; }
    setUi({ scene: id });
  };
  $('#sceneChoices').addEventListener('click', (e) => {
    const b = e.target.closest('[data-scene]');
    if (b) pickScene(b.dataset.scene);
  });
  $('#setSceneSeg').addEventListener('click', (e) => {
    const b = e.target.closest('[data-scene]');
    if (b) pickScene(b.dataset.scene);
  });
  [['sceneOpacity', 'opacity'], ['sceneBlur', 'blur'], ['sceneScrim', 'scrim'],
   ['setSceneOpacity', 'opacity'], ['setSceneBlur', 'blur'], ['setSceneScrim', 'scrim'],
   ['paperAlpha', 'paperAlpha']].forEach(([id, key]) => {
    const el = $('#' + id);
    if (el) el.addEventListener('input', () => setUi({ [key]: Number(el.value) }));
  });
  $$('#autoAlphaSeg button').forEach((b) => b.addEventListener('click', () => {
    setUi({ autoAlpha: b.dataset.autoAlpha === '1' });
  }));
  [$('#bgUploadBtn'), $('#setLookUpload')].forEach((b) => b && b.addEventListener('click', pickBackgroundImage));
  $('#bgFileInput').addEventListener('change', (e) => handleBackgroundFile(e.target.files && e.target.files[0]));
  $('#bgUrlApply').addEventListener('click', () => {
    const url = ($('#bgUrlInput').value || '').trim();
    if (!url) { toast('先粘贴图片地址'); return; }
    setUi({ customImage: url, scene: 'custom' });
    toast('自定义背景已应用');
  });
  [$('#bgClearCustom'), $('#setLookClear')].forEach((b) => b && b.addEventListener('click', () => {
    setUi({ customImage: '', scene: 'none' });
    toast('已清除自定义背景');
  }));

  /* 设置面板 */
  $$('#setTabs button').forEach((b) => b.addEventListener('click', () => switchSettingsTab(b.dataset.setTab)));
  $('#setSave').addEventListener('click', saveSettings);
  /* 同步页 */
  $$('#setSyncRole button').forEach((b) => b.addEventListener('click', () => {
    renderSyncRole(b.dataset.syncRole);
  }));
  $('#setSyncSave').addEventListener('click', () => saveSyncConfig());
  $('#setSyncNow').addEventListener('click', async () => {
    try {
      const st = await api('/sync/run', { method: 'POST' });
      renderSyncStatus(st);
      if (st.last_error) toast('同步出错：' + st.last_error);
      else toast('已同步');
    } catch (e) { toast('同步失败：' + e.message); }
  });
  $('#setSyncTest').addEventListener('click', testSyncHub);
  $('#setSyncRotate').addEventListener('click', async () => {
    if (!confirm('换新令牌后，其他设备要重新填一次。继续？')) return;
    await saveSyncConfig({ rotate: true });
  });
  $('#setSyncCopyToken').addEventListener('click', async () => {
    const v = $('#setSyncToken').value;
    try { await navigator.clipboard.writeText(v); toast('令牌已复制'); }
    catch (_) { $('#setSyncToken').select(); document.execCommand('copy'); toast('令牌已复制'); }
  });
  $('#ttsSampleBtn').addEventListener('click', async () => {
    const st = $('#ttsStatus');
    const au = $('#ttsSampleAudio');
    st.textContent = '合成中…';
    try {
      const r = await fetch('/api/tts/sample', {
        method: 'POST',
        headers: authHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({
          text: '他站在城头，风把衣角扯得猎猎作响，远处雪线上升起一线狼烟。',
          voice: 'zh-CN-YunyangNeural', rate: '-2%', pitch: '+0Hz', volume: '+0%', mood: '沉冷',
        }),
      });
      if (!r.ok) {
        let msg = 'HTTP ' + r.status;
        try { const js = await r.json(); msg = js.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      const blob = await r.blob();
      au.src = URL.createObjectURL(blob);
      au.style.display = 'inline-block';
      au.play();
      st.textContent = '引擎：' + (r.headers.get('X-FJ-Provider') || '') + '（保存后整章都会用这个引擎）';
    } catch (e) {
      st.textContent = '试听失败：' + e.message;
    }
  });
  $('#dictModelBtn').addEventListener('click', downloadDictModel);
  $('#setTest').addEventListener('click', async () => {
    $('#setStatus').textContent = '测试中…';
    try { const r = await api('/health'); $('#setStatus').textContent = r.status === 'ok' ? '后端在线' : '异常'; }
    catch (e) { $('#setStatus').textContent = '连接失败'; }
  });
  $('#setOpenBg').addEventListener('click', () => { closeModal($('#settingsModal')); renderSceneChoices(); openModal('bgModal'); });
  $('#setWriteSave').addEventListener('click', saveWritingPrefs);
  $('#setLexManage').addEventListener('click', () => { renderLexModal(); openModal('lexModal'); });
  $('#setTypo').addEventListener('click', () => { closeModal($('#settingsModal')); openModal('typoModal'); });
  $('#setExportAll').addEventListener('click', exportAllProjects);
  $('#setOpenTrash').addEventListener('click', loadProjectTrash);
  $('#setClearLocal').addEventListener('click', clearLocalCache);
  $('#setTrashList').addEventListener('click', async (e) => {
    const b = e.target.closest('[data-trash-file]');
    if (!b) return;
    const ok = await askConfirm('恢复项目', '把这份备份恢复到书架？', '恢复');
    if (!ok) return;
    try {
      const r = await api('/trash/restore', { method: 'POST', body: { file: b.dataset.trashFile } });
      toast('已恢复：' + r.name);
      await loadBooks();
      loadProjectTrash();
    } catch (err) { toast('恢复失败：' + err.message); }
  });

  /* 快捷键 */
  document.addEventListener('keydown', (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveNow(); }
    if (mod && e.key.toLowerCase() === 'f') { e.preventDefault(); openFind(); }
    if (mod && e.key === '/') { e.preventDefault(); renderShortcuts(); openModal('shortcutsModal'); }
    if (mod && e.key === 'Enter') { e.preventDefault(); newChapter(); }
    if (mod && e.key.toLowerCase() === 'p') { e.preventDefault(); renderPhonePreview(); $('#phoneDrawer').classList.add('show'); $('#drawerMask').classList.add('show'); }
    if (e.key === 'Escape') {
      exitFocus();
      closePhone();
      if ($('#left').classList.contains('mobile-open') || $('#right').classList.contains('mobile-open')) {
        closeMobileSheets();
        syncDrawerOffset();
      }
      if (S.findVisible) closeFind();
      $$('.modal-mask.show').forEach((m) => closeModal(m));
    }
  });

  window.addEventListener('beforeunload', () => { if (S.book) saveNow(true); });
  setInterval(() => { if ($('#saveText').textContent === '正在落存…') saveNow(true); }, 10000);
  setInterval(() => {
    const d = new Date();
    $('#fsClock').textContent = `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }, 20000);
}

function closePhone() {
  $('#phoneDrawer').classList.remove('show');
  $('#drawerMask').classList.remove('show');
}

function addLex() {
  const v = ($('#lexInput').value || '').trim();
  if (!v) return;
  const custom = store.json(KEY.lex, []);
  if (!custom.includes(v) && !DEFAULT_LEX.includes(v)) custom.push(v);
  store.setJson(KEY.lex, custom);
  $('#lexInput').value = '';
  renderLexModal();
  applySensitivity();
}

function saveChapterOutline() {
  const f = currentFile();
  if (!f) return;
  f.metadata = f.metadata || {};
  f.metadata.outline = $('#outlineNote').value;
  scheduleSave();
}

/* ---------------- 启动 ---------------- */
async function init() {
  const authed = await ensureAuth();
  if (!authed) return;
  bind();
  renderSceneChoices();
  applyUi();
  renderShortcuts();
  $('#tocSearch').value = '';
  [300, 1200, 2500].forEach((ms) => setTimeout(() => {
    const el = $('#tocSearch');
    if (el && !S.searchTouched && el.value) { el.value = ''; renderToc(); }
  }, ms));
  $('#edEmpty').classList.remove('show');
  renderBackdrop();
  await loadSettings();
  try { await loadBooks(); } catch (e) { toast('后端未就绪：' + e.message); }
  const last = store.get(KEY.lastBook, '');
  const target = S.books.find((b) => b.name === last) || S.books[0];
  if (target) {
    try { await openBook(target.name); } catch (e) { toast('打开书籍失败：' + e.message); }
  } else {
    renderBookHead(); renderToc(); updateEditorChrome();
  }
  setSave('idle', '尚未落存');
  startSyncWatch();
  renderTrashCount();
  renderStats();
  updateStats();

  /* 写作中每 5 分钟自动留一份快照 */
  setInterval(() => {
    const f = currentFile();
    if (!f || !S.book) return;
    if (document.hidden) return;
    takeSnapshot(true);
  }, 5 * 60 * 1000);
}

/* ---------------- 工坊桥接（studio.js 使用） ---------------- */
window.App = {
  S,
  api,
  toast,
  esc,
  fmt,
  wordCount,
  currentFile,
  chapterFiles,
  fileById,
  volumeFolders,
  saveProjectFields,
  loadBooks,
  openBook,
  downloadText,
  askText,
  askConfirm,
  openModal,
  closeModal,
  saveNow,
  openChapter,
  openImportModal,
  autoFillProject,
  refreshUi() {
    renderBookHead();
    renderToc();
    renderWorld();
    renderForeshadow();
    updateStats();
  },
  setRightTab,
};

document.addEventListener('DOMContentLoaded', init);

/* PWA：安装到桌面 / 手机主屏幕（https 或 localhost 下浏览器才允许注册） */
if ('serviceWorker' in navigator) {
  const pwaSecure = location.protocol === 'https:' || ['127.0.0.1', 'localhost'].includes(location.hostname);
  if (pwaSecure) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    });
  }
}
})();
