/* ==========================================================
   工坊：对齐桌面版《烽火南境》的七大模块
   项目 / 概念 / 世界观 / 人物 / 大纲 / 正文 / 剧本 / 工具箱
   ========================================================== */
(() => {
'use strict';

const A = () => window.App;
const $ = (s, r = document) => (r || document).querySelector(s);
const $$ = (s, r = document) => Array.from((r || document).querySelectorAll(s));

const META = {
  project: ['项目', '概览 · 导入导出 · 复制 · 书籍信息'],
  concept: ['概念', '六节分写 · 单节重生 · 版本回滚'],
  world: ['世界观', '生成 · 编辑 · 一致性检查'],
  characters: ['人物', '角色档案 · 关系图 · 出场章节'],
  outline: ['大纲', '宏观 · 逐章细纲 · 伏笔 · 情感曲线 · 章节依赖'],
  writing: ['正文', '批量生成 · 章节直达'],
  script: ['剧本', '正文转分场 · 导出'],
  toolbox: ['工具箱', '提示词模板 · 文风参考 · 生成历史'],
};

const S = { mod: 'project', cache: { toolbox: null }, polling: null, conceptDraft: null };

const esc = (s) => A().esc(s);
const fmt = (n) => A().fmt(n);
const api = (p, o) => A().api(p, o);
const toast = (m) => A().toast(m);

/* ---------------- 基础 ---------------- */
function openStudio(mod) {
  $('#studio').hidden = false;
  setModule(mod || S.mod || 'project');
}
function closeStudio() {
  $('#studio').hidden = true;
  if (S.polling) { clearInterval(S.polling); S.polling = null; }
  A().refreshUi();
}

function setModule(mod) {
  S.mod = mod;
  $$('.studio-nav button').forEach((b) => b.classList.toggle('on', b.dataset.mod === mod));
  const meta = META[mod] || ['工坊', ''];
  $('#stTitle').textContent = meta[0];
  $('#stSub').textContent = meta[1];
  render();
}

async function render() {
  const body = $('#studioBody');
  const book = A().S.book;
  if (!book) {
    body.innerHTML = `<div class="st-card"><b>还没有打开的书</b><div class="hint" style="margin-top:8px">先在写作台选择一本书，或到书架新建。</div>
      <div class="st-row" style="margin-top:12px"><button class="mini-btn primary" id="stGoShelf">去书架</button></div></div>`;
    $('#stGoShelf').onclick = () => { closeStudio(); document.querySelector('.ml-nav a[data-nav="library"]').click(); };
    return;
  }
  try {
    if (S.mod === 'project') await renderProject(body);
    else if (S.mod === 'concept') await renderConcept(body);
    else if (S.mod === 'world') await renderWorld(body);
    else if (S.mod === 'characters') await renderCharacters(body);
    else if (S.mod === 'outline') await renderOutline(body);
    else if (S.mod === 'writing') await renderWriting(body);
    else if (S.mod === 'script') await renderScript(body);
    else if (S.mod === 'toolbox') await renderToolbox(body);
  } catch (e) {
    body.innerHTML = `<div class="st-card"><b>加载失败</b><div class="hint">${esc(e.message)}</div></div>`;
  }
}

function loading(btn, on) {
  if (!btn) return;
  btn.classList.toggle('st-loading', !!on);
  if (on) { btn.dataset.t = btn.textContent; btn.textContent = '处理中…'; }
  else if (btn.dataset.t) btn.textContent = btn.dataset.t;
}

/* ---------------- 项目 ---------------- */
async function renderProject(body) {
  const book = A().S.book;
  const files = A().S.files;
  const chapters = files.filter((f) => f.type === 'FILE');
  const words = chapters.reduce((n, f) => n + A().wordCount(f.content), 0);
  const volumes = files.filter((f) => f.type === 'FOLDER' && f.parentId === 'root' && f.id !== 'root');
  const tb = await api('/toolbox');
  S.cache.toolbox = tb;
  const hist = (tb.history || []).filter((h) => h.project === book.name).slice(0, 8);

  const today = (() => {
    try {
      const daily = JSON.parse(localStorage.getItem('fj:daily') || '{}');
      const d = new Date();
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      return Number(daily[key] || 0);
    } catch { return 0; }
  })();

  body.innerHTML = `
    <div class="st-grid c3" style="margin-bottom:12px">
      <div class="st-card"><div class="hint">全书写字</div><div style="font-family:var(--mono);font-size:26px;margin-top:4px">${fmt(words)}</div><div class="hint">${chapters.length} 章 · ${volumes.length} 卷</div></div>
      <div class="st-card"><div class="hint">今日码字</div><div style="font-family:var(--mono);font-size:26px;margin-top:4px">${fmt(today)}</div><div class="hint">目标 ${fmt(A().S.goal || 0)} 字</div></div>
      <div class="st-card"><div class="hint">AI 生成记录</div><div style="font-family:var(--mono);font-size:26px;margin-top:4px">${tb.history.length}</div><div class="hint">最近：${hist[0] ? esc(hist[0].kind) + ' · ' + esc(hist[0].ts.slice(5, 16)) : '暂无'}</div></div>
    </div>
    <div class="st-grid c2">
      <div class="st-card">
        <h4>书籍信息 <button class="mini-btn primary" id="stSaveMeta">保存</button></h4>
        <div class="st-row" style="gap:10px">
          <div class="st-field" style="flex:1"><label>书名</label><input id="stMName" value="${esc(book.name)}" readonly></div>
          <div class="st-field" style="flex:1"><label>作者署名</label><input id="stMAuthor" value="${esc(book.author || '')}" placeholder="笔名"></div>
        </div>
        <div class="st-row" style="gap:10px">
          <div class="st-field" style="flex:1"><label>题材</label><input id="stMGenre" value="${esc(book.genre || '')}"></div>
          <div class="st-field" style="flex:1"><label>风格</label><input id="stMStyle" value="${esc(book.style || '')}"></div>
        </div>
        <div class="st-row" style="gap:10px">
          <div class="st-field" style="flex:1"><label>参考大神</label><input id="stMRef" value="${esc(book.ref_author || '')}"></div>
          <div class="st-field" style="flex:1"><label>每章字数</label><input id="stMWords" type="number" value="${book.words_per_chapter || 2500}"></div>
          <div class="st-field" style="flex:1"><label>计划章数</label><input id="stMCh" type="number" value="${book.chapter_count || 400}"></div>
        </div>
        <div class="st-field"><label>书籍简介</label>
          <textarea id="stMDesc" class="st-textarea" style="min-height:72px">${esc(book.description || '')}</textarea>
        </div>
        <div class="hint">封面、改名请到写作台的「书籍设置」，会同步显示到书架。</div>
      </div>
      <div class="st-card">
        <h4>项目操作</h4>
        <div class="st-row" style="margin-bottom:8px">
          <button class="mini-btn" id="stExport">导出项目 JSON</button>
          <button class="mini-btn" id="stImport">导入书籍 / 章节</button>
          <button class="mini-btn" id="stDup">复制一本</button>
          <button class="mini-btn" id="stAutoFill">AI 识别设定</button>
        </div>
        <div class="hint">导出为完整项目（含章节、概念、人物、大纲、剧本），可用于备份或换机；导入支持 .txt/.md/.json；「AI 识别设定」会读正文自动填书籍信息、概念、世界观、人物、关系、大纲、细纲、伏笔。</div>
        <h4 style="margin-top:14px">最近 AI 记录</h4>
        <div class="st-list">
          ${hist.length ? hist.map((h) => `<div class="st-item"><div class="t">${esc(h.kind)}<span class="st-badge">${fmt(h.chars)} 字</span></div><div class="d">${esc(h.ts)} · ${esc((h.preview || '').slice(0, 60))}</div></div>`).join('') : '<div class="st-empty">还没有生成记录</div>'}
        </div>
      </div>
    </div>`;

  $('#stSaveMeta').onclick = async () => {
    await A().saveProjectFields({
      author: $('#stMAuthor').value.trim(),
      description: $('#stMDesc').value.trim(),
      genre: $('#stMGenre').value.trim(),
      style: $('#stMStyle').value.trim(),
      subgenre: book.subgenre || '',
      ref_author: $('#stMRef').value.trim(),
      words_per_chapter: Number($('#stMWords').value) || 2500,
      chapter_count: Number($('#stMCh').value) || 400,
    });
    toast('书籍信息已保存');
    A().refreshUi();
  };
  $('#stExport').onclick = async () => {
    const data = await api('/projects/' + encodeURIComponent(book.name));
    A().downloadText(book.name + '.json', JSON.stringify(data, null, 2));
    toast('已导出');
  };
  $('#stImport').onclick = () => {
    closeStudio();
    if (A().openImportModal) A().openImportModal('new');
    else toast('导入入口未就绪');
  };
  $('#stAutoFill').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      if (A().autoFillProject) await A().autoFillProject(book.name);
      render();
    } finally {
      loading(btn, false);
    }
  };
  $('#stDup').onclick = async () => {
    const name = await A().askText('复制项目', '新书名', book.name + ' 副本');
    if (!name) return;
    try {
      await api(`/projects/${encodeURIComponent(book.name)}/duplicate`, { method: 'POST', body: { new_name: name } });
      await A().loadBooks();
      toast('已复制为 ' + name);
      render();
    } catch (e) { toast('复制失败：' + e.message); }
  };
}

/* ---------------- 概念 ---------------- */
const CONCEPT_FIELDS = [
  ['core', '一句话核心故事'],
  ['theme', '主题与内核'],
  ['positioning', '市场定位与差异化'],
  ['plot_structure', '剧情主线（三幕式）'],
  ['character_arc', '主角定位与成长弧光'],
  ['style_guide', '风格锚点与创作指南'],
];

async function renderConcept(body) {
  const book = A().S.book;
  const c = book.concept || {};
  const versions = book.concept_versions || [];
  body.innerHTML = `
    <div class="st-card" style="margin-bottom:12px">
      <h4>核心概念
        <span class="st-row">
          <button class="mini-btn" id="stCGen">AI 生成全部</button>
          <button class="mini-btn" id="stCSave">保存</button>
          <button class="mini-btn" id="stCVersion">存为版本</button>
        </span>
      </h4>
      <div class="hint">生成后可以在每一节里微调；「单节重生」只会重写这一节，其余保持不动。</div>
      ${versions.length ? `<div class="st-row" style="margin-top:10px">
        <select id="stCVer" class="st-field" style="height:34px;padding:0 10px;border-radius:10px;border:1px solid var(--line);background:var(--paper)">
          ${versions.map((v, i) => `<option value="${i}">${esc(v.ts || '版本 ' + (i + 1))}</option>`).join('')}
        </select>
        <button class="mini-btn" id="stCLoadVer">载入该版本</button>
      </div>` : ''}
    </div>
    <div class="st-grid c2" id="stConceptGrid">
      ${CONCEPT_FIELDS.map(([k, label]) => `<div class="st-card" data-k="${k}">
        <h4>${label}<button class="mini-btn" data-regen="${k}">单节重生</button></h4>
        <textarea class="st-textarea" data-field="${k}" style="min-height:110px">${esc(c[k] || '')}</textarea>
      </div>`).join('')}
    </div>`;

  const collect = () => {
    const out = {};
    $$('[data-field]', body).forEach((el) => { out[el.dataset.field] = el.value.trim(); });
    return out;
  };
  const saveConcept = async (concept) => {
    await A().saveProjectFields({ concept });
    toast('概念已保存');
  };

  $('#stCSave').onclick = () => saveConcept(collect());
  $('#stCGen').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/generate/concept', { method: 'POST', body: bookCtx() });
      $('#stConceptGrid').innerHTML = CONCEPT_FIELDS.map(([k, label]) => `<div class="st-card" data-k="${k}">
        <h4>${label}<button class="mini-btn" data-regen="${k}">单节重生</button></h4>
        <textarea class="st-textarea" data-field="${k}" style="min-height:110px">${esc((r.concept || {})[k] || '')}</textarea>
      </div>`).join('');
      await saveConcept(r.concept || {});
    } catch (err) { toast('生成失败：' + err.message); }
    loading(btn, false);
  };
  body.addEventListener('click', async (e) => {
    const b = e.target.closest('[data-regen]');
    if (!b) return;
    const key = b.dataset.regen;
    loading(b, true);
    try {
      const r = await api('/ai/concept/section', { method: 'POST', body: { project_name: book.name, section: key } });
      const ta = $(`[data-field="${key}"]`, body);
      if (ta) ta.value = r.text || '';
      await saveConcept(collect());
    } catch (err) { toast('重生失败：' + err.message); }
    loading(b, false);
  });
  $('#stCVersion').onclick = async () => {
    const concept = collect();
    const list = (A().S.book.concept_versions || []).slice();
    list.push({ ts: new Date().toLocaleString('zh-CN'), data: concept });
    await A().saveProjectFields({ concept_versions: list.slice(-20) });
    toast('已存为版本');
    render();
  };
  const loadBtn = $('#stCLoadVer');
  if (loadBtn) loadBtn.onclick = () => {
    const i = Number($('#stCVer').value);
    const v = (A().S.book.concept_versions || [])[i];
    if (!v) return;
    const data = v.data || v;
    CONCEPT_FIELDS.forEach(([k]) => {
      const ta = $(`[data-field="${k}"]`, body);
      if (ta) ta.value = data[k] || '';
    });
    toast('已载入，记得点保存');
  };
}

/* ---------------- 世界观 ---------------- */
async function renderWorld(body) {
  const book = A().S.book;
  const w = book.world || {};
  const text = typeof w === 'string' ? w : (w.content || '');
  body.innerHTML = `
    <div class="st-card" style="margin-bottom:12px">
      <h4>世界观
        <span class="st-row">
          <button class="mini-btn" id="stWGen">AI 生成</button>
          <button class="mini-btn" id="stWCheck">一致性检查</button>
          <button class="mini-btn" id="stWSave">保存</button>
        </span>
      </h4>
      <div class="hint">生成会覆盖编辑框内容；保存后才写进项目。检查会同时看人物设定。</div>
      <textarea class="st-textarea" id="stWText" style="min-height:340px;margin-top:10px">${esc(text)}</textarea>
    </div>
    <div class="st-card" id="stWIssues" hidden>
      <h4>检查结果</h4>
      <div class="st-list" id="stWIssueList"></div>
    </div>`;

  $('#stWSave').onclick = async () => {
    const world = (typeof book.world === 'object' && book.world) ? { ...book.world, content: $('#stWText').value } : { content: $('#stWText').value };
    await A().saveProjectFields({ world });
    toast('世界观已保存');
  };
  $('#stWGen').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/generate/world', { method: 'POST', body: bookCtx() });
      $('#stWText').value = (r.world && r.world.content) || '';
      await A().saveProjectFields({ world: r.world || {} });
      toast('已生成并保存');
    } catch (err) { toast('生成失败：' + err.message); }
    loading(btn, false);
  };
  $('#stWCheck').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/ai/world/check', { method: 'POST', body: { project_name: book.name, world: { content: $('#stWText').value } } });
      const box = $('#stWIssues');
      box.hidden = false;
      $('#stWIssueList').innerHTML = (r.issues || []).length
        ? r.issues.map((s) => `<div class="st-item"><div class="d" style="font-size:12.5px;color:var(--ink-2)">${esc(s)}</div></div>`).join('')
        : '<div class="st-empty">没有发现明显矛盾</div>';
    } catch (err) { toast('检查失败：' + err.message); }
    loading(btn, false);
  };
}

/* ---------------- 人物 ---------------- */
const PURPOSE_PRESETS = [
  '推动主线', '制造冲突', '提供信息', '情感线', '衬托主角',
  '埋伏笔', '喜剧担当', '展示世界观', '导师', '对手', '工具人',
];
const REL_TYPES = ['师徒', '父子', '母子', '兄弟', '姐妹', '夫妻', '情侣', '青梅竹马', '挚友',
  '同门', '上下级', '主仆', '合作', '利用', '竞争对手', '仇敌', '杀父之仇', '秘密关联', '单恋', '暗恋'];

function charGroups() {
  const chars = A().S.book.characters || {};
  const groups = {};
  Object.keys(chars).forEach((g) => { if (Array.isArray(chars[g])) groups[g] = chars[g]; });
  ['主角', '配角', '反派'].forEach((g) => { if (!groups[g]) groups[g] = []; });
  return groups;
}

function splitList(v) {
  if (Array.isArray(v)) return v.map((s) => String(s).trim()).filter(Boolean);
  return String(v || '').split(/[、,，;；\s]+/).map((s) => s.trim()).filter(Boolean);
}

function normChar(c, group, index) {
  const o = (typeof c === 'string') ? { name: c } : Object.assign({}, c || {});
  o.name = String(o.name || o['姓名'] || '').trim();
  o.group = group;
  o.index = index;
  return o;
}

function allChars() {
  const groups = charGroups();
  const out = [];
  Object.keys(groups).forEach((g) => {
    groups[g].forEach((c, i) => {
      const o = normChar(c, g, i);
      if (o.name) out.push(o);
    });
  });
  return out;
}

const charId = (c) => `${c.group}::${c.index}`;

function entryRef(group, index) {
  const chars = charGroups();
  const arr = chars[group] || (chars[group] = []);
  let e = arr[index];
  if (typeof e === 'string') { e = { name: e }; arr[index] = e; }
  if (!e || typeof e !== 'object') { e = { name: '' }; arr[index] = e; }
  return e;
}

function charKeys(c) {
  const keys = [c.name, ...splitList(c.aliases)].filter(Boolean);
  return Array.from(new Set(keys)).sort((a, b) => b.length - a.length);
}

function chapterTexts() {
  return A().chapterFiles().map((f) => ({ id: f.id, title: f.name, text: f.content || '' }));
}

function scanOne(c, chapters) {
  const list = chapters || chapterTexts();
  const keys = charKeys(c);
  const rows = [];
  let total = 0;
  list.forEach((ch) => {
    let n = 0;
    keys.forEach((k) => { if (k && ch.text.indexOf(k) >= 0) n += ch.text.split(k).length - 1; });
    if (n) { rows.push({ id: ch.id, title: ch.title, count: n }); total += n; }
  });
  return { rows, total, chapters: rows.length, first: rows[0] || null };
}

function scanAll(list) {
  const chapters = chapterTexts();
  const map = {};
  list.forEach((c) => { map[charId(c)] = scanOne(c, chapters); });
  return map;
}

function emptyChar(group) {
  return {
    name: '', aliases: [], group: group || '主角', role: '', gender: '', age: '', identity: '',
    purpose: [], tagline: '', intro: '', background: '', appearance: '', personality: '',
    ability: '', quote: '', goal: '', arc: '', relations: [], graph: null, avatar: '',
  };
}

function charState() {
  if (!S.char) S.char = { view: 'detail', sel: null, draft: null, editRef: null, dirty: false, query: '', filter: '全部', ai: [], aiRole: '配角' };
  return S.char;
}

function markDirty() {
  const st = charState();
  st.dirty = true;
  const el = $('#chDirty');
  if (el) el.hidden = false;
}

async function renderCharacters(body) {
  const book = A().S.book;
  const st = charState();
  if (st.book !== book.name) {
    Object.assign(st, { book: book.name, view: 'detail', sel: null, draft: null, editRef: null, dirty: false, query: '', filter: '全部', ai: [], aiRole: '配角', mapFocus: '' });
  }
  const all = allChars();
  const apps = scanAll(all);
  if (st.sel && !all.some((c) => charId(c) === st.sel)) { st.sel = null; st.draft = null; st.editRef = null; }
  if (!st.sel && !st.draft && all.length) {
    const first = all[0];
    st.sel = charId(first);
    st.draft = JSON.parse(JSON.stringify(first));
    st.editRef = { group: first.group, index: first.index };
  }

  body.innerHTML = `<div class="ch-shell" id="chShell">${charSidebar(all, apps)}<section class="ch-main" id="chMain">${
    st.view === 'map' ? charMapShell(all) : st.view === 'ai' ? charAiShell() : charDetailShell(all, apps)
  }</section></div>`;

  bindCharEvents(all, apps);
  if (st.view === 'map') mountCharMap();
  if (st.view === 'ai') renderAiList();
}

function charItemsHtml(all, apps) {
  const st = charState();
  const q = (st.query || '').trim().toLowerCase();
  const f = st.filter || '全部';
  const list = all.filter((c) => {
    if (f !== '全部' && c.group !== f) return false;
    if (!q) return true;
    const hay = [c.name, ...splitList(c.aliases), c.role, c.identity, c.tagline, ...(c.purpose || [])].join(' ').toLowerCase();
    return hay.indexOf(q) >= 0;
  });
  if (!list.length) return '<div class="st-empty">没有匹配的人物</div>';
  return list.map((c) => {
    const a = apps[charId(c)] || { chapters: 0, total: 0 };
    const purposes = (Array.isArray(c.purpose) ? c.purpose : splitList(c.purpose)).slice(0, 3);
    return `<div class="ch-card ${st.sel === charId(c) ? 'on' : ''}" data-csel="${charId(c)}">
      <div class="ch-card-n"><img class="ch-ava-sm" src="${avatarHref(c)}" alt="" data-portrait="${esc(charId(c))}"><b>${esc(c.name)}</b>${c.role ? `<span class="ch-tag">${esc(c.role)}</span>` : ''}</div>
      <div class="ch-card-m"><span>${esc(c.group)}</span><span>${a.chapters} 章 · ${fmt(a.total)} 次</span></div>
      ${purposes.length ? `<div class="ch-card-m">${purposes.map((p) => `<span class="ch-tag">${esc(p)}</span>`).join('')}</div>` : ''}
    </div>`;
  }).join('');
}

function charSidebar(all, apps) {
  const st = charState();
  const groups = ['全部', ...Object.keys(charGroups())];
  return `<aside class="ch-side">
    <div class="ch-side-top">
      <input id="chSearch" class="ch-search" type="search" autocomplete="off" placeholder="搜索姓名 / 别名 / 用途" value="${esc(st.query || '')}">
      <div class="ch-filter" id="chFilter">${groups.map((g) => `<button class="${(st.filter || '全部') === g ? 'on' : ''}" data-cfilter="${esc(g)}">${esc(g)}</button>`).join('')}</div>
    </div>
    <div class="ch-items" id="chItems">${charItemsHtml(all, apps)}</div>
    <div class="ch-side-foot">
      <button class="mini-btn primary" id="chAdd">＋ 新建人物</button>
      <button class="mini-btn" id="chAiBtn">AI 批量生成</button>
    </div>
  </aside>`;
}

function relRow(r, i) {
  return `<div class="ch-rel">
    <input class="ch-in" list="chCharNames" data-rel-target="${i}" value="${esc(r.target || '')}" placeholder="对象">
    <input class="ch-in" list="chRelTypes" data-rel-type="${i}" value="${esc(r.type || '')}" placeholder="关系">
    <input class="ch-in" type="range" min="1" max="5" step="1" data-rel-strength="${i}" value="${Number(r.strength) || 3}" title="强度">
    <input class="ch-in" data-rel-note="${i}" value="${esc(r.note || '')}" placeholder="备注">
    <button class="icon-btn" data-rel-del="${i}" title="删除关系">×</button>
  </div>`;
}

function chapRows(st) {
  if (!st.rows.length) return '<div class="st-empty">正文里还没出现这个名字</div>';
  return `<div class="ch-chaps">${st.rows.map((r) => `<div class="ch-chap" data-cchap="${esc(r.id)}"><span>${esc(r.title)}</span><span class="hint">${r.count} 次</span></div>`).join('')}</div>`;
}

function detailField(label, f, value, opts) {
  const o = opts || {};
  if (o.textarea) {
    return `<div class="st-field" style="${o.span ? 'grid-column:1/-1' : ''}"><label>${label}</label><textarea class="st-textarea" data-f="${f}" style="min-height:${o.h || 66}px" placeholder="${esc(o.ph || '')}">${esc(value || '')}</textarea></div>`;
  }
  return `<div class="st-field" style="${o.span ? 'grid-column:1/-1' : ''}"><label>${esc(label)}</label><input data-f="${f}" value="${esc(value || '')}" placeholder="${esc(o.ph || '')}"></div>`;
}

function charDetailShell(all, apps) {
  const st = charState();
  const d = st.draft;
  if (!d) return '<div class="ch-panel"><div class="st-empty">左侧选择人物，或点「新建人物」开始设定</div></div>';
  const stat = (st.sel && apps[st.sel]) ? apps[st.sel] : scanOne(d);
  const isNew = !st.editRef;
  const purpose = Array.isArray(d.purpose) ? d.purpose : splitList(d.purpose);
  const rels = Array.isArray(d.relations) ? d.relations : [];
  const groups = Object.keys(charGroups());
  return `<div class="ch-panel">
    <div class="ch-head">
      <div class="st-row">
        <b class="ch-title">${isNew ? '新增人物' : esc(d.name || '未命名')}</b>
        <span class="st-badge">${esc(d.group)}</span>
        <span class="ch-dirty" id="chDirty" ${st.dirty ? '' : 'hidden'}>未保存</span>
      </div>
      <div class="st-row">
        <button class="mini-btn" id="chPortraitBtn">立绘</button>
        <button class="mini-btn" id="chToMap">关系图</button>
        <button class="mini-btn primary" id="chSave">保存</button>
        ${isNew ? '' : '<button class="mini-btn seal" id="chDel">删除</button>'}
      </div>
    </div>

    <div class="ch-sec" style="border-top:none;margin-top:0;padding-top:0">
      <h5>基本信息</h5>
      <div class="ch-form-grid">
        ${detailField('姓名 *', 'name', d.name, { ph: '必填' })}
        ${detailField('别名 / 称呼（顿号分隔）', 'aliases', splitList(d.aliases).join('、'), { ph: '小七、阿辞' })}
        <div class="st-field"><label>分组</label><select data-f="group">${groups.map((g) => `<option ${g === d.group ? 'selected' : ''}>${esc(g)}</option>`).join('')}</select></div>
        ${detailField('定位', 'role', d.role, { ph: '男主 / 女主 / 幕后黑手' })}
        ${detailField('性别', 'gender', d.gender, { ph: '男 / 女' })}
        ${detailField('年龄', 'age', d.age, { ph: '17 / 三十余岁' })}
        ${detailField('身份 / 职业', 'identity', d.identity, { ph: '青冥剑宗外门弟子', span: true })}
      </div>
    </div>

    <div class="ch-sec">
      <h5>用途 <span class="hint">这个角色在故事里承担什么，可多选</span></h5>
      <div class="ch-chips" id="chPurpose">
        ${PURPOSE_PRESETS.map((p) => `<button class="ch-chip ${purpose.includes(p) ? 'on' : ''}" data-ctoggle="${esc(p)}">${esc(p)}</button>`).join('')}
        ${purpose.filter((p) => !PURPOSE_PRESETS.includes(p)).map((p) => `<button class="ch-chip on" data-ctoggle="${esc(p)}">${esc(p)}</button>`).join('')}
      </div>
      <div class="st-row" style="margin-top:8px"><input id="chPurposeAdd" class="ch-in" style="flex:1" placeholder="自定义用途，回车添加"></div>
    </div>

    <div class="ch-sec">
      <h5>角色介绍</h5>
      ${detailField('一句话介绍', 'tagline', d.tagline, { ph: '用一句话说清他是谁、想要什么', span: true })}
      ${detailField('角色介绍（详细）', 'intro', d.intro, { textarea: true, h: 96, span: true, ph: '出身、经历、与主线的关系…' })}
      <div class="ch-form-grid">
        ${detailField('外貌', 'appearance', d.appearance, { textarea: true })}
        ${detailField('性格', 'personality', d.personality, { textarea: true })}
        ${detailField('能力 / 金手指', 'ability', d.ability, { textarea: true })}
        ${detailField('口头禅', 'quote', d.quote, { textarea: true, h: 56 })}
        ${detailField('目标 / 动机', 'goal', d.goal, { textarea: true, h: 56 })}
        ${detailField('成长弧光', 'arc', d.arc, { textarea: true, h: 56 })}
      </div>
    </div>

    <div class="ch-sec">
      <h5>关系网络 <span class="hint">这里改的关系会同步到关系图</span>
        <button class="mini-btn" id="chRelAdd">＋ 添加关系</button>
      </h5>
      ${rels.length ? rels.map((r, i) => relRow(r, i)).join('') : '<div class="st-empty">还没有关系，点「＋ 添加关系」</div>'}
      <datalist id="chRelTypes">${REL_TYPES.map((t) => `<option>${t}</option>`).join('')}</datalist>
      <datalist id="chCharNames">${all.filter((c) => c.name !== d.name).map((c) => `<option>${esc(c.name)}</option>`).join('')}</datalist>
    </div>

    <div class="ch-sec">
      <h5>出场章节 <span class="hint">按正文实时统计</span></h5>
      <div class="ch-stat">
        <span><b>${stat.chapters}</b> 章</span>
        <span><b>${fmt(stat.total)}</b> 次</span>
        <span>首次：${stat.first ? esc(stat.first.title) : '—'}</span>
      </div>
      ${chapRows(stat)}
    </div>
  </div>`;
}

function charAiShell() {
  const st = charState();
  const cur = st.aiRole || '配角';
  return `<div class="ch-panel">
    <div class="ch-head">
      <b class="ch-title">AI 批量生成人物</b>
      <button class="mini-btn" id="chAiBack">返回档案</button>
    </div>
    <div class="st-row" style="margin-bottom:8px">
      <select id="chAiRole" class="ch-in" style="width:110px">${['主角', '配角', '反派', '龙套'].map((g) => `<option ${g === cur ? 'selected' : ''}>${g}</option>`).join('')}</select>
      <input id="chAiCount" class="ch-in" type="number" min="1" max="10" value="3" style="width:70px">
      <button class="mini-btn primary" id="chAiRun">生成</button>
    </div>
    <div class="hint">生成结果需逐条「采纳」才写入人物表；每张卡片可以单独选归属分组，默认写回生成时的分组，已有同名角色不会重复写入。</div>
    <div class="st-list" id="chAiList" style="margin-top:10px"><div class="st-empty">还没有生成</div></div>
  </div>`;
}

function renderAiList() {
  const box = $('#chAiList');
  if (!box) return;
  const st = charState();
  const list = st.ai || [];
  const roles = ['主角', '配角', '反派', '龙套'];
  box.innerHTML = list.length ? list.map((c, i) => `<div class="st-item">
      <div class="t">${esc(c.name)} ${c.role ? `<span class="st-badge">${esc(c.role)}</span>` : ''}${(c.purpose || []).slice(0, 2).map((p) => `<span class="st-badge">${esc(p)}</span>`).join('')}${c.adopted ? `<span class="st-badge">已入 ${esc(c.adopted)}</span>` : ''}</div>
      <div class="d">${esc(c.tagline || c.intro || [c.desc, c.personality, c.ability].filter(Boolean).join(' · '))}</div>
      <div class="st-row" style="margin-top:8px">
        ${c.adopted ? '<span class="hint">已写进人物表</span>' : `<select class="ch-in" data-airole="${i}" style="width:96px">${roles.map((g) => `<option ${g === (c.group || st.aiRole || '配角') ? 'selected' : ''}>${g}</option>`).join('')}</select>
        <button class="mini-btn primary" data-adopt="${i}">采纳</button>`}
      </div>
    </div>`).join('') : '<div class="st-empty">没有解析到人物，换个模型或再试一次</div>';
}

function selectCharObj(c) {
  const st = charState();
  st.sel = charId(c);
  st.draft = JSON.parse(JSON.stringify(c));
  st.editRef = { group: c.group, index: c.index };
  st.dirty = false;
  st.view = 'detail';
  /* 换了人物，关系图焦点也要跟着换，别停在上一张图 */
  st.mapFocus = '';
}

async function saveCharDraft() {
  const st = charState();
  const d = st.draft;
  if (!d) return;
  if (!String(d.name || '').trim()) { toast('姓名不能为空'); return; }
  const chars = charGroups();
  const rec = {
    name: String(d.name).trim(),
    aliases: splitList(d.aliases),
    role: d.role || '', gender: d.gender || '', age: d.age || '', identity: d.identity || '',
    purpose: Array.isArray(d.purpose) ? d.purpose : splitList(d.purpose),
    tagline: d.tagline || '', intro: d.intro || '', background: d.background || '',
    appearance: d.appearance || '', personality: d.personality || '',
    ability: d.ability || '', quote: d.quote || '', goal: d.goal || '', arc: d.arc || '',
    relations: (d.relations || []).filter((r) => r.target && r.type).map((r) => ({
      target: r.target, type: r.type, strength: Number(r.strength) || 3, note: r.note || '',
    })),
    desc: d.tagline || d.identity || d.role || '',
  };
  if (d.graph && typeof d.graph.x === 'number') rec.graph = { x: d.graph.x, y: d.graph.y };
  if (d.avatar) rec.avatar = d.avatar;
  const tg = d.group || '主角';
  if (!Array.isArray(chars[tg])) chars[tg] = [];
  let idx;
  if (st.editRef) {
    const og = st.editRef.group;
    const oi = st.editRef.index;
    if (og === tg) { chars[og][oi] = rec; idx = oi; }
    else { chars[og].splice(oi, 1); chars[tg].push(rec); idx = chars[tg].length - 1; }
  } else {
    chars[tg].push(rec);
    idx = chars[tg].length - 1;
  }
  await A().saveProjectFields({ characters: chars });
  A().refreshUi();
  Object.assign(st, { sel: `${tg}::${idx}`, editRef: { group: tg, index: idx }, dirty: false });
  st.draft = Object.assign({}, rec, { group: tg, index: idx });
  toast('人物已保存');
  render();
}

async function deleteCharAt(group, index, name) {
  const ok = await A().askConfirm('删除人物', `确定删除「${name}」？其他人物指向他的关系也会一并移除。`, '删除');
  if (!ok) return;
  const chars = charGroups();
  chars[group].splice(index, 1);
  Object.values(chars).forEach((arr) => arr.forEach((c) => {
    if (c && typeof c === 'object' && Array.isArray(c.relations)) {
      c.relations = c.relations.filter((r) => r.target !== name);
    }
  }));
  await A().saveProjectFields({ characters: chars });
  A().refreshUi();
  const st = charState();
  st.sel = null; st.draft = null; st.editRef = null; st.dirty = false;
  toast('已删除');
  render();
}

/* ---- 人物立绘（头像） ---- */
const AVA_CACHE = new Map();

function avatarSeed(c) {
  const s = `${c.name || ''}|${c.gender || ''}|${c.age || ''}|${c.role || ''}|${c.identity || ''}`;
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; }
  return h >>> 0;
}

/* 没有 AI 立绘时，按人设画一张古风头像（确定性、离线可用） */
function avatarSvg(c) {
  const seed = avatarSeed(c);
  const txt = `${c.gender || ''}${c.role || ''}${c.identity || ''}${c.name || ''}`;
  const female = /女|姑娘|小姐|夫人|妃|婢|娘|姐|妹|母|婆|公主|郡主|姑/.test(txt);
  const old = /老|翁|媪|婆|公|父|母|将军|掌门|长老|祖/.test(`${c.age || ''}${c.role || ''}`);
  const bad = /反派|敌|仇|暗|邪|毒|魔/.test(`${c.role || ''}${c.identity || ''}${c.personality || ''}`);
  const palettes = bad
    ? [['#40323c', '#241d26'], ['#4a3640', '#2a2029'], ['#473042', '#241a24']]
    : female
      ? [['#8f5b52', '#5a3630'], ['#7a6a8a', '#463a52'], ['#8b6a4e', '#543b2a'], ['#6f7f86', '#3f4b52']]
      : [['#4f5d63', '#2f383d'], ['#5d5346', '#37302a'], ['#4a5566', '#2b323d'], ['#5a4a52', '#33282f']];
  const [c1, c2] = palettes[seed % palettes.length];
  const skin = old ? '#e6cdb6' : (female ? '#f4dcc8' : '#eccfb4');
  const hair = old ? '#c9c6bf' : '#1d1a18';
  const ornament = bad ? '#8c3b3b' : '#a5382e';
  const tilt = ((seed >> 3) % 7) - 3;
  const bun = female
    ? `<circle cx="64" cy="${20 + tilt / 3}" r="11" fill="${hair}"/>
       <circle cx="46" cy="26" r="7" fill="${hair}"/><circle cx="82" cy="26" r="7" fill="${hair}"/>
       <rect x="${56 + tilt}" y="10" width="16" height="3.4" rx="1.7" fill="${ornament}" transform="rotate(${tilt} 64 12)"/>`
    : `<path d="M50 24 Q64 8 78 24 Z" fill="${hair}"/>
       <rect x="56" y="16" width="16" height="4" rx="2" fill="${ornament}"/>`;
  const beard = old && !female
    ? `<path d="M52 88 Q64 100 76 88 L76 94 Q64 106 52 94 Z" fill="${hair}" opacity=".55"/>` : '';
  const browY = 58 + tilt / 2;
  const eyeY = 66 + tilt / 2;
  const smile = bad ? `M56 ${78 + tilt / 2} Q64 ${75 + tilt / 2} 72 ${78 + tilt / 2}` : `M56 ${78 + tilt / 2} Q64 ${82 + tilt / 2} 72 ${78 + tilt / 2}`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <radialGradient id="bg" cx="50%" cy="38%" r="72%">
      <stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/>
    </radialGradient>
    <linearGradient id="robe" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f3ece0" stop-opacity=".92"/><stop offset="100%" stop-color="#d9cdbc" stop-opacity=".8"/>
    </linearGradient>
    <clipPath id="clip"><circle cx="64" cy="64" r="63"/></clipPath>
  </defs>
  <g clip-path="url(#clip)">
    <rect width="128" height="128" fill="url(#bg)"/>
    <circle cx="64" cy="52" r="52" fill="#ffffff" opacity=".05"/>
    <path d="M18 128 Q28 92 64 89 Q100 92 110 128 Z" fill="url(#robe)"/>
    <path d="M64 89 L86 128 L52 128 Z" fill="#efe6d8"/>
    <path d="M64 88 L64 128" stroke="#b8a992" stroke-width="1.2" opacity=".6"/>
    <path d="M58 76 L58 92 Q64 96 70 92 L70 76 Z" fill="${skin}"/>
    <ellipse cx="64" cy="${62 + tilt / 3}" rx="21" ry="24" fill="${skin}"/>
    <path d="M43 ${58 + tilt / 3} Q64 ${26 + tilt} 85 ${58 + tilt / 3} Q80 ${46 + tilt} 64 ${44 + tilt} Q48 ${46 + tilt} 43 ${58 + tilt / 3} Z" fill="${hair}"/>
    ${bun}
    ${female ? `<path d="M43 60 Q38 84 46 100" stroke="${hair}" stroke-width="5" fill="none" stroke-linecap="round"/>
    <path d="M85 60 Q90 84 82 100" stroke="${hair}" stroke-width="5" fill="none" stroke-linecap="round"/>` : ''}
    <path d="M50 ${browY} Q55 ${browY - 3} 60 ${browY}" stroke="${hair}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    <path d="M68 ${browY} Q73 ${browY - 3} 78 ${browY}" stroke="${hair}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    <ellipse cx="56" cy="${eyeY}" rx="2.6" ry="1.7" fill="${hair}"/>
    <ellipse cx="72" cy="${eyeY}" rx="2.6" ry="1.7" fill="${hair}"/>
    <path d="M64 ${eyeY + 4} L64 ${eyeY + 9}" stroke="${skin}" stroke-width="1.2" opacity=".55"/>
    <path d="${smile}" stroke="#b8716c" stroke-width="2" fill="none" stroke-linecap="round"/>
    ${beard}
    ${female ? `<circle cx="${84 + tilt}" cy="${36}" r="3.2" fill="${ornament}" opacity=".9"/>` : ''}
  </g>
  <circle cx="64" cy="64" r="62" fill="none" stroke="#ffffff" stroke-opacity=".28" stroke-width="2"/>
</svg>`;
}

function avatarHref(c) {
  if (!c) return '';
  const key = `${c.name || ''}|${c.avatar || ''}|${c.gender || ''}|${c.age || ''}|${c.role || ''}|${c.identity || ''}|${c.personality || ''}`;
  if (AVA_CACHE.has(key)) return AVA_CACHE.get(key);
  const href = c.avatar ? c.avatar : ('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(avatarSvg(c)));
  AVA_CACHE.set(key, href);
  return href;
}

/* ---- 关系图 ---- */
const MAP_MODES = { topo: '拓扑', live: '星链', tree: '全览' };
/* 全览里手动摆好的位置：按书缓存并落 localStorage，切换角色/重启都不丢 */
const TREE_MEM = {};
function treePosMap(book) {
  if (TREE_MEM[book]) return TREE_MEM[book];
  const m = new Map();
  try {
    const obj = JSON.parse(localStorage.getItem('fj:treePos:' + book) || '{}');
    Object.keys(obj).forEach((k) => {
      const v = obj[k];
      if (v && typeof v.x === 'number' && typeof v.y === 'number') m.set(k, { x: v.x, y: v.y });
    });
  } catch (e) { /* ignore */ }
  TREE_MEM[book] = m;
  return m;
}
function treePosSave(book, m) {
  try {
    const obj = {};
    m.forEach((v, k) => { obj[k] = { x: Math.round(v.x), y: Math.round(v.y) }; });
    localStorage.setItem('fj:treePos:' + book, JSON.stringify(obj));
  } catch (e) { /* ignore */ }
}
/* 拓扑 / 星链的坐标也按书缓存，切模式、重进人物页都不重新乱排 */
const MAP_MEM = {};
function mapPosMap(book) {
  if (!MAP_MEM[book]) MAP_MEM[book] = new Map();
  return MAP_MEM[book];
}

function charMapShell(all) {
  if (!all.length) return '<div class="ch-panel"><div class="st-empty">还没有人物，先在左侧「新建人物」</div></div>';
  const st = charState();
  const mode = st.mapMode || 'topo';
  const seg = Object.keys(MAP_MODES).map((k) => `<button data-mapmode="${k}" class="${mode === k ? 'on' : ''}">${MAP_MODES[k]}</button>`).join('');
  return `<div class="ch-map-wrap">
    <div class="ch-map" id="chMap">
      <div class="ch-map-tools">
        <span class="ch-seg" id="chModeSeg">${seg}</span>
        <button class="mini-btn" id="chRelayout">自动排版</button>
        <button class="mini-btn" id="chFit">复位</button>
        <span class="ch-legend"><i class="g-主角"></i>主角<i class="g-配角"></i>配角<i class="g-反派"></i>反派</span>
      </div>
      <svg id="chSvg"></svg>
      <div class="chg-cards" id="chCards" hidden></div>
      <div class="ch-map-hint" id="chMapHint" hidden></div>
    </div>
    <aside class="ch-map-side" id="chMapSide"></aside>
  </div>`;
}

function charAdjacency(nodes, links) {
  const adj = new Map(nodes.map((n) => [n.id, []]));
  links.forEach((l) => {
    if (!adj.has(l.a) || !adj.has(l.b)) return;
    adj.get(l.a).push({ id: l.b, link: l });
    adj.get(l.b).push({ id: l.a, link: l });
  });
  return adj;
}

function hopsFrom(focusId, adj, maxHops) {
  const dist = new Map([[focusId, 0]]);
  let frontier = [focusId];
  for (let h = 1; h <= maxHops; h++) {
    const next = [];
    frontier.forEach((id) => (adj.get(id) || []).forEach(({ id: o }) => {
      if (!dist.has(o)) { dist.set(o, h); next.push(o); }
    }));
    frontier = next;
  }
  return dist;
}

/* 力导向：一次跑多步（拓扑/全览），或每帧跑一步（星链） */
function forceStep(nodes, links, W, H, step, alpha) {
  const n = nodes.length;
  if (!n) return;
  const k = Math.sqrt((W * H) / n) * 0.62;
  const cx = W / 2;
  const cy = H / 2;
  const disp = nodes.map(() => ({ x: 0, y: 0 }));
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      let dx = nodes[i].x - nodes[j].x;
      let dy = nodes[i].y - nodes[j].y;
      let d = Math.hypot(dx, dy) || 0.01;
      if (d < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d = 1; }
      const f = (k * k) / d;
      disp[i].x += (dx / d) * f; disp[i].y += (dy / d) * f;
      disp[j].x -= (dx / d) * f; disp[j].y -= (dy / d) * f;
    }
  }
  const idx = new Map(nodes.map((nd, i) => [nd.id, i]));
  links.forEach((l) => {
    const a = idx.get(l.a);
    const b = idx.get(l.b);
    if (a == null || b == null) return;
    const dx = nodes[a].x - nodes[b].x;
    const dy = nodes[a].y - nodes[b].y;
    const d = Math.hypot(dx, dy) || 0.01;
    const f = ((d * d) / k) * 0.9;
    disp[a].x -= (dx / d) * f; disp[a].y -= (dy / d) * f;
    disp[b].x += (dx / d) * f; disp[b].y += (dy / d) * f;
  });
  nodes.forEach((nd, i) => {
    disp[i].x += (cx - nd.x) * 0.035;
    disp[i].y += (cy - nd.y) * 0.035;
    if (nd.fixed) return;
    const len = Math.hypot(disp[i].x, disp[i].y) || 0.01;
    const cap = Math.min(len, 26);
    nd.x += (disp[i].x / len) * cap * alpha;
    nd.y += (disp[i].y / len) * cap * alpha;
    const pad = nd.w ? nd.w / 2 + 12 : 46;
    nd.x = Math.max(pad, Math.min(W - pad, nd.x));
    nd.y = Math.max(pad, Math.min(H - pad, nd.y));
  });
}

function mountCharMap() {
  const wrap = $('#chMap');
  const svg = $('#chSvg');
  const cardsBox = $('#chCards');
  const hint = $('#chMapHint');
  if (!wrap || !svg) return;

  const st = charState();
  const W = wrap.clientWidth || 760;
  const H = wrap.clientHeight || 520;
  let mode = st.mapMode || 'topo';
  if (!MAP_MODES[mode]) mode = 'topo';
  const isLive = mode === 'live';
  const isTree = mode === 'tree';

  /* ---------- 数据 ---------- */
  const raw = charGroups();
  const nodes = [];
  Object.keys(raw).forEach((g) => raw[g].forEach((c, i) => {
    const name = typeof c === 'string' ? c : String((c && c.name) || '').trim();
    if (!name) return;
    const rec = (typeof c === 'object' && c) ? c : { name };
    const graph = rec.graph || null;
    nodes.push({
      id: `${g}::${i}`, group: g, index: i, name, rec,
      role: rec.role || rec.identity || '', avatar: rec.avatar || '',
      x: graph && typeof graph.x === 'number' ? graph.x : null,
      y: graph && typeof graph.y === 'number' ? graph.y : null,
      fixed: false,
      vx: 0, vy: 0, w: 0,
    });
  }));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const bookKey = (A().S && A().S.book && A().S.book.name) || 'default';
  const posMem = mapPosMap(bookKey);
  nodes.forEach((nd) => {
    nd.w = mode === 'topo' ? 104 : 56;
    if (nd.x == null) {
      const m = posMem.get(nd.id);
      if (m) { nd.x = m.x; nd.y = m.y; }
    }
    nd.fixed = nd.x != null;
    if (nd.x == null) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.min(W, H) * 0.28 * Math.sqrt(Math.random());
      nd.x = W / 2 + Math.cos(a) * r;
      nd.y = H / 2 + Math.sin(a) * r;
    }
  });

  const links = [];
  const seen = new Set();
  function rebuildLinks() {
    const fresh = charGroups();
    links.length = 0;
    const seenKeys = new Set();
    nodes.forEach((nd) => {
      const e = fresh[nd.group] && fresh[nd.group][nd.index];
      const rels = (e && typeof e === 'object' && Array.isArray(e.relations)) ? e.relations : [];
      rels.forEach((r, ri) => {
        const t = nodes.find((x) => x.name === r.target);
        if (!t || t.id === nd.id) return;
        const key = [nd.id, t.id].sort().join('|');
        if (seenKeys.has(key)) return;
        seenKeys.add(key);
        links.push({
          a: nd.id, b: t.id, type: r.type || '关系', strength: Number(r.strength) || 3,
          note: r.note || '', ownerGroup: nd.group, ownerIndex: nd.index, relIdx: ri,
        });
      });
    });
  }
  rebuildLinks();
  const adj = charAdjacency(nodes, links);

  /* ---------- 焦点 ---------- */
  let focusId = '';
  if (st.mapFocus) {
    const hit = nodes.find((n) => n.name === st.mapFocus);
    if (hit) focusId = hit.id;
  }
  if (!focusId && st.sel && byId.has(st.sel)) focusId = st.sel;
  if (!focusId) {
    const p = nodes.find((n) => n.group === '主角') || nodes[0];
    focusId = p ? p.id : '';
  }

  const side = $('#chMapSide');
  const state = { sel: focusId ? { kind: 'node', id: focusId } : null, drag: null, pan: null, moved: false, hover: '' };
  const view = { x: 0, y: 0, k: 1 };

  function linkOf(aId, bId) {
    return links.find((l) => (l.a === aId && l.b === bId) || (l.a === bId && l.b === aId)) || null;
  }

  /* 只画「中心人物 + 与他直接相关的人」，无关人物不出现 */
  function relatedIds() {
    const set = new Set();
    if (focusId) set.add(focusId);
    (adj.get(focusId) || []).forEach(({ id }) => set.add(id));
    return set;
  }

  /* ---------- 布局 ---------- */
  /* 画布边界随人数伸缩：拖拽/力导向/适配都用它，不再被固定画面尺寸卡死 */
  const CARD = { w: mode === 'topo' ? 118 : 84, h: mode === 'topo' ? 78 : 72 };
  const BOUND = { x0: 0, y0: 0, x1: W, y1: H };
  const clampX = (v) => Math.max(BOUND.x0 + 46, Math.min(BOUND.x1 - 46, v));
  const clampY = (v) => Math.max(BOUND.y0 + 38, Math.min(BOUND.y1 - 38, v));

  function syncBounds(pts, padX, padY) {
    const b = bboxOf(pts || nodes);
    const px = padX || 100;
    const py = padY || 90;
    BOUND.x0 = Math.min(0, b.minX - px);
    BOUND.y0 = Math.min(0, b.minY - py);
    BOUND.x1 = Math.max(W, b.maxX + px + 200);
    BOUND.y1 = Math.max(H, b.maxY + py + 200);
  }

  /* 人多时把绘图区按人数放大，再整体缩放到视口里，避免都挤在一屏 */
  function layoutArea() {
    const n = Math.max(1, nodes.length);
    const gapX = mode === 'topo' ? 44 : 30;
    const gapY = mode === 'topo' ? 44 : 30;
    /* 每格按「卡片 + 间距」再放大 1/0.62，缩到 0.62 倍时仍分得清 */
    const cellW = (CARD.w + gapX) / 0.62;
    const cellH = (CARD.h + gapY) / 0.62;
    const ratio = Math.max(0.55, Math.min(1.9, W / H));
    const cols = Math.max(1, Math.round(Math.sqrt(n * ratio)));
    const rows = Math.ceil(n / cols);
    return { LW: Math.max(W, cols * cellW), LH: Math.max(H, rows * cellH) };
  }

  function scatter(list, LW, LH) {
    if (!list.length) return;
    const cols = Math.max(1, Math.ceil(Math.sqrt(list.length * (LW / LH))));
    const rows = Math.ceil(list.length / cols);
    const cw = LW / cols;
    const ch = LH / Math.max(1, rows);
    list.forEach((nd, i) => {
      const c = i % cols;
      const r = Math.floor(i / cols);
      nd.fixed = false;
      nd.x = (c + 0.5) * cw + (Math.random() - 0.5) * cw * 0.28;
      nd.y = (r + 0.5) * ch + (Math.random() - 0.5) * ch * 0.28;
    });
  }

  function settleSteps(LW, LH, steps) {
    for (let i = 0; i < steps; i++) {
      const alpha = Math.max(0.03, 1 - i / steps);
      forceStep(nodes, links, LW, LH, i, alpha);
    }
  }

  /* 力导向管不住卡片重叠，最后按卡片外框硬掰开 */
  function spreadOverlaps() {
    const bw = CARD.w + 12;
    const bh = CARD.h + 12;
    for (let iter = 0; iter < 30; iter++) {
      let moved = false;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const ox = bw - Math.abs(dx);
          const oy = bh - Math.abs(dy);
          if (ox <= 0 || oy <= 0) continue;
          moved = true;
          if (a.fixed && b.fixed) continue;
          if (ox < oy) {
            const s = (dx >= 0 ? 1 : -1) * ox;
            if (a.fixed) b.x += s;
            else if (b.fixed) a.x -= s;
            else { a.x -= s / 2; b.x += s / 2; }
          } else {
            const s = (dy >= 0 ? 1 : -1) * oy;
            if (a.fixed) b.y += s;
            else if (b.fixed) a.y -= s;
            else { a.y -= s / 2; b.y += s / 2; }
          }
        }
      }
      if (!moved) break;
    }
  }

  function bboxOf(pts) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    pts.forEach((p) => {
      minX = Math.min(minX, p.x);
      minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x);
      maxY = Math.max(maxY, p.y);
    });
    if (!isFinite(minX)) return { minX: 0, minY: 0, maxX: W, maxY: H };
    return { minX, minY, maxX, maxY };
  }

  /* 把整张图缩放平移到视口里（留边距，别缩到看不清） */
  function fitView(pts, padX, padY, minK) {
    const b = bboxOf(pts);
    const bw = Math.max(80, b.maxX - b.minX) + (padX || 60) * 2;
    const bh = Math.max(80, b.maxY - b.minY) + (padY || 60) * 2;
    const k = Math.max(minK || 0.5, Math.min(1.3, Math.min(W / bw, H / bh)));
    view.k = k;
    view.x = (W - (b.maxX - b.minX) * k) / 2 - b.minX * k;
    view.y = (H - (b.maxY - b.minY) * k) / 2 - b.minY * k;
  }

  function autoLayout() {
    const { LW, LH } = layoutArea();
    nodes.forEach((nd) => { nd.fixed = false; });
    scatter(nodes, LW, LH);
    settleSteps(LW, LH, mode === 'live' ? 300 : 320);
    spreadOverlaps();
    syncBounds(nodes);
    nodes.forEach((nd) => posMem.set(nd.id, { x: nd.x, y: nd.y }));
  }

  /* ---------- 渲染 ---------- */
  const dist = () => hopsFrom(focusId, adj, 9);

  function edgePath(a, b) {
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len = Math.hypot(dx, dy) || 1;
    const curve = Math.min(30, len * 0.12);
    const nx = -dy / len;
    const ny = dx / len;
    /* 二次贝塞尔的 t=0.5 实际落在控制点方向的一半处，标签要贴在这里才不脱离线 */
    return { d: `M${a.x.toFixed(1)},${a.y.toFixed(1)} Q${(mx + nx * curve).toFixed(1)},${(my + ny * curve).toFixed(1)} ${b.x.toFixed(1)},${b.y.toFixed(1)}`, mx: mx + nx * curve * 0.5, my: my + ny * curve * 0.5 };
  }

  function nodeSvg(nd, d) {
    const isFocus = nd.id === focusId;
    const href = avatarHref(nd.rec);
    const cls = `chg-node${isFocus ? ' focus' : ''}${state.sel && state.sel.kind === 'node' && state.sel.id === nd.id ? ' on' : ''}${state.hover === nd.id ? ' hover' : ''}`;
    if (mode === 'topo') {
      const w = 104; const h = 58;
      return `<g class="${cls}" data-node="${nd.id}" style="transform:translate(${nd.x.toFixed(1)}px,${nd.y.toFixed(1)}px)">
        <rect x="${-w / 2}" y="${-h / 2}" width="${w}" height="${h}" rx="14" class="chg-card-bg"></rect>
        <image href="${href}" x="${-w / 2 + 9}" y="${-h / 2 + 11}" width="36" height="36" style="clip-path:circle(50%)"></image>
        <text class="chg-name" x="${-w / 2 + 52}" y="-2">${esc(nd.name.slice(0, 5))}</text>
        <text class="chg-role" x="${-w / 2 + 52}" y="15">${esc((nd.role || nd.group).slice(0, 7))}</text>
      </g>`;
    }
    const r = isFocus ? 30 : 24;
    return `<g class="${cls}" data-node="${nd.id}" style="transform:translate(${nd.x.toFixed(1)}px,${nd.y.toFixed(1)}px)">
      <circle r="${r + 6}" class="chg-halo"></circle>
      <circle r="${r}" class="chg-ring g-${esc(nd.group)}"></circle>
      <image href="${href}" x="${-r}" y="${-r}" width="${r * 2}" height="${r * 2}" style="clip-path:circle(50%)"></image>
      <text class="chg-name" y="${r + 16}" text-anchor="middle">${esc(nd.name.slice(0, 6))}</text>
    </g>`;
  }

  function edgeSvg(l, i, dm) {
    const a = byId.get(l.a);
    const b = byId.get(l.b);
    if (!a || !b) return '';
    const focusEdge = l.a === focusId || l.b === focusId;
    const hot = state.hover === l.a || state.hover === l.b || (state.sel && state.sel.kind === 'link' && state.sel.i === i);
    const g = edgePath(a, b);
    const sw = (1 + (Number(l.strength) || 3) * 0.32).toFixed(2);
    const label = (hot || focusEdge)
      ? `<g class="chg-edge-tag"><rect x="${(g.mx - (String(l.type).length * 10 + 14) / 2).toFixed(1)}" y="${(g.my - 9).toFixed(1)}" width="${(String(l.type).length * 10 + 14)}" height="18" rx="9"></rect><text x="${g.mx.toFixed(1)}" y="${(g.my + 3.5).toFixed(1)}" text-anchor="middle">${esc(l.type)}</text></g>`
      : '';
    return `<g class="chg-edge${focusEdge ? ' main' : ''}${hot ? ' hot' : ''}" data-link="${i}">
      <path d="${g.d}" style="stroke-width:${sw}"></path>
      ${label}
    </g>`;
  }

  const particles = links.map(() => Math.random());

  function draw() {
    const dm = dist();
    const vis = relatedIds();
    const visible = nodes.filter((nd) => vis.has(nd.id));
    const shown = [];
    links.forEach((l, i) => { if (vis.has(l.a) && vis.has(l.b)) shown.push({ l, i }); });
    const edgeHtml = shown.map(({ l, i }) => edgeSvg(l, i)).join('');
    const nodeHtml = visible.map((nd) => nodeSvg(nd, dm.get(nd.id) ?? 9)).join('');
    const dots = isLive
      ? shown.map(({ l, i }) => {
        const a = byId.get(l.a); const b = byId.get(l.b);
        if (!a || !b) return '';
        const t = particles[i];
        const x = a.x + (b.x - a.x) * t;
        const y = a.y + (b.y - a.y) * t;
        return `<circle class="chg-spark" data-i="${i}" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.2"></circle>`;
      }).join('')
      : '';
    svg.innerHTML = `<g transform="translate(${view.x.toFixed(1)} ${view.y.toFixed(1)}) scale(${view.k.toFixed(3)})">
      ${edgeHtml}${dots}${nodeHtml}
    </g>`;
    if (hint) {
      const f = byId.get(focusId);
      const n = f ? (adj.get(f.id) || []).length : 0;
      hint.hidden = !!n;
      hint.textContent = f ? `${f.name} 还没有任何关系，右侧「＋ 关系」加一条就会连起来` : '';
    }
  }

  function renderCards() {
    svg.style.display = 'none';
    cardsBox.hidden = false;
    if (hint) hint.hidden = true;
    const f = byId.get(focusId);
    if (!f) return;
    const dmap = hopsFrom(focusId, adj, 1);
    let near = nodes.filter((n) => dmap.get(n.id) === 1);
    near.sort((a, b) => a.name.localeCompare(b.name, 'zh'));
    const extra = Math.max(0, near.length - 8);
    near = near.slice(0, 8);
    const cx = W / 2;
    const cy = H / 2 + 12;
    const R = Math.max(120, Math.min(W / 2 - 96, H / 2 - 84));
    const lines = near.map((n, i) => {
      const a = -Math.PI / 2 + (i / Math.max(1, near.length)) * Math.PI * 2;
      n._cx = cx + Math.cos(a) * R;
      n._cy = cy + Math.sin(a) * R;
      return `<line x1="${cx}" y1="${cy}" x2="${n._cx}" y2="${n._cy}" class="chg-line" style="animation-delay:${i * 60}ms"/>`;
    }).join('');
    const fRole = [f.group, f.rec.role || f.rec.identity || ''].filter(Boolean).join(' · ');
    const center = `<div class="chg-card center" data-node="${f.id}" style="left:${cx}px;top:${cy}px">
      <img class="chg-ava" src="${avatarHref(f.rec)}" alt="">
      <b>${esc(f.name)}</b>
      <em>${esc(fRole)}</em>
      <small>${near.length} 段关系${extra ? ` · 另有 ${extra} 位` : ''}</small>
    </div>`;
    const cardsHtml = near.map((n, i) => {
      const l = linkOf(f.id, n.id);
      const sub = n.rec.role || n.rec.identity || n.group;
      const dots = l ? Array.from({ length: 5 }, (_, k) => `<s class="${k < (Number(l.strength) || 3) ? 'on' : ''}"></s>`).join('') : '';
      return `<div class="chg-card near" data-node="${n.id}" style="left:${n._cx}px;top:${n._cy}px;animation-delay:${120 + i * 70}ms">
        <img class="chg-ava" src="${avatarHref(n.rec)}" alt="">
        <b>${esc(n.name)}</b>
        <em>${esc(String(sub).slice(0, 14))}</em>
        <span class="chg-rel">${l ? `<i>${esc(l.type)}</i><span class="chg-dots">${dots}</span>` : '<i>无直接关系</i>'}</span>
      </div>`;
    }).join('');
    cardsBox.innerHTML = `<svg class="chg-links" width="${W}" height="${H}">${lines}</svg>${center}${cardsHtml}`;
  }

  function paint() {
    if (isTree) { renderTree(); return; }
    if (mode === 'cards') { renderCards(); return; }
    svg.style.display = '';
    cardsBox.hidden = true;
    draw();
  }

  /* ---------- 全览：层级关系树（自动排版，可折叠、可换根、可单卡拖动） ---------- */
  const treeState = { collapsed: new Set() };
  let treeNeedFit = true;
  const treeBookKey = (A().S && A().S.book && A().S.book.name) || 'default';
  treeState.pos = treePosMap(treeBookKey);
  const TW = 132; const TH = 54; const HGAP = 22; const VGAP = 86;

  function treeLayout(children, roots) {
    const posT = new Map();
    let cursor = 0;
    const visit = (id, depth) => {
      const kids = treeState.collapsed.has(id) ? [] : (children.get(id) || []);
      if (!kids.length) {
        const x = cursor;
        cursor += TW + HGAP;
        posT.set(id, { x, y: depth * VGAP, depth });
        return x;
      }
      const xs = kids.map((k) => visit(k, depth + 1));
      const x = (xs[0] + xs[xs.length - 1]) / 2;
      posT.set(id, { x, y: depth * VGAP, depth });
      return x;
    };
    roots.forEach((r) => { visit(r, 0); cursor += HGAP * 2; });
    const width = Math.max(TW, cursor - HGAP);
    const dx = Math.max(20, (W - width) / 2);
    let maxDepth = 0;
    posT.forEach((p) => { maxDepth = Math.max(maxDepth, p.depth); });
    const dy = Math.max(58, (H - (maxDepth * VGAP + TH)) / 2);
    posT.forEach((p) => { p.x += dx; p.y += dy; });
    return posT;
  }

  function relBetween(aId, bId) {
    const l = links.find((x) => (x.a === aId && x.b === bId) || (x.a === bId && x.b === aId));
    return l ? l.type : '';
  }

  function renderTree() {
    svg.style.display = '';
    cardsBox.hidden = true;
    if (hint) hint.hidden = true;
    const rootId = byId.has(focusId) ? focusId : (nodes[0] && nodes[0].id);
    if (!rootId) return;
    /* 只保留中心人物 + 与他直接相关的人，其余不画 */
    const kids = (adj.get(rootId) || []).map(({ id }) => id).filter((id) => byId.has(id));
    const parent = new Map(kids.map((k) => [k, rootId]));
    const children = new Map();
    children.set(rootId, kids);
    kids.forEach((k) => children.set(k, []));
    const roots = [rootId];
    const base = treeLayout(children, roots);
    /* 已经手动摆过的人物沿用旧坐标，换根/重进都不再重排 */
    const posT = new Map();
    base.forEach((p, id) => {
      const saved = treeState.pos.get(id);
      if (saved) posT.set(id, { x: saved.x, y: saved.y, depth: p.depth });
      else { posT.set(id, p); treeState.pos.set(id, { x: p.x, y: p.y }); }
    });
    const edgeHtml = [];
    syncBounds(Array.from(posT.values()), TW / 2 + 60, TH / 2 + 60);
    if (treeNeedFit) {
      fitView(Array.from(posT.values()), 50, 50, 0.42);
      treeNeedFit = false;
    }
    /* 从卡片中心朝对方方向，取卡片边框上的出头点（自由拖动后也不会歪） */
    const cardExit = (from, to) => {
      const dx = to.x - from.x;
      const dy = to.y - from.y;
      if (!dx && !dy) return { x: from.x, y: from.y };
      const hx = TW / 2 + 5;
      const hy = TH / 2 + 5;
      const sx = dx ? hx / Math.abs(dx) : Infinity;
      const sy = dy ? hy / Math.abs(dy) : Infinity;
      const s = Math.min(sx, sy);
      return { x: from.x + dx * s, y: from.y + dy * s };
    };
    posT.forEach((p, id) => {
      const par = parent.get(id);
      if (!par || !posT.has(par)) return;
      const a = posT.get(par);
      const hot = state.hover === id || state.hover === par;
      const g = edgePath(cardExit(a, p), cardExit(p, a));
      edgeHtml.push(`<path class="chg-tree-link${hot ? ' hot' : ''}" d="${g.d}"></path>`);
      const t = relBetween(par, id);
      if (t) {
        const tw = String(t).length * 10 + 14;
        edgeHtml.push(`<g class="chg-tree-tag"><rect x="${(g.mx - tw / 2).toFixed(1)}" y="${(g.my - 9).toFixed(1)}" width="${tw}" height="18" rx="9"></rect><text x="${g.mx.toFixed(1)}" y="${(g.my + 3.5).toFixed(1)}" text-anchor="middle">${esc(t)}</text></g>`);
      }
    });
    const nodeHtml = [];
    posT.forEach((p, id) => {
      const nd = byId.get(id);
      if (!nd) return;
      const kids = children.get(id) || [];
      const isFocus = id === focusId;
      const collapsed = treeState.collapsed.has(id);
      nodeHtml.push(`<g class="chg-tree-node${isFocus ? ' focus' : ''}${state.hover === id ? ' hover' : ''}" data-node="${id}" style="transform:translate(${p.x.toFixed(1)}px,${p.y.toFixed(1)}px)">
        <rect x="${-TW / 2}" y="${-TH / 2}" width="${TW}" height="${TH}" rx="13" class="chg-card-bg"></rect>
        <image href="${avatarHref(nd.rec)}" x="${-TW / 2 + 8}" y="${-TH / 2 + 9}" width="30" height="30" style="clip-path:circle(50%)"></image>
        <text class="chg-name" x="${-TW / 2 + 46}" y="-2">${esc(nd.name.slice(0, 6))}</text>
        <text class="chg-role" x="${-TW / 2 + 46}" y="15">${esc((nd.role || nd.group).slice(0, 8))}</text>
        ${kids.length ? `<g class="chg-tree-toggle" data-toggle="${id}">
          <circle cx="${TW / 2 - 11}" cy="${TH / 2 - 11}" r="8"></circle>
          <text x="${TW / 2 - 11}" y="${TH / 2 - 7.5}" text-anchor="middle">${collapsed ? '+' : '−'}</text>
        </g>` : ''}
      </g>`);
    });
    svg.innerHTML = `<g transform="translate(${view.x.toFixed(1)} ${view.y.toFixed(1)}) scale(${view.k.toFixed(3)})">
      ${edgeHtml.join('')}${nodeHtml.join('')}
    </g>`;
  }

  /* ---------- 星链动画（只移动光点，不重绘整张图，避免闪烁发虚） ---------- */
  let raf = 0;
  function liveLoop() {
    if (!isLive) return;
    if (!document.body.contains(svg)) { stopLoop(); return; }
    svg.querySelectorAll('.chg-spark').forEach((el) => {
      const i = Number(el.dataset.i);
      const l = links[i];
      if (!l) return;
      const a = byId.get(l.a);
      const b = byId.get(l.b);
      if (!a || !b) return;
      particles[i] = (particles[i] + 0.0035 + (i % 5) * 0.0005) % 1;
      const t = particles[i];
      el.setAttribute('cx', (a.x + (b.x - a.x) * t).toFixed(1));
      el.setAttribute('cy', (a.y + (b.y - a.y) * t).toFixed(1));
    });
    raf = requestAnimationFrame(liveLoop);
  }
  function stopLoop() { if (raf) { cancelAnimationFrame(raf); raf = 0; } }

  /* ---------- 右侧面板 ---------- */
  function renderSide(node, link) {
    if (!side) return;
    if (!node && !link) {
      side.innerHTML = '<div class="hint">拖人物卡单独摆位（全览/星链/拓扑都行）、拖空白处平移、滚轮缩放；点人物看关系，双击打开档案。</div>';
      return;
    }
    if (link) {
      const a = byId.get(link.a);
      const b = byId.get(link.b);
      side.innerHTML = `<div class="ch-side-title"><b>${esc(a ? a.name : '')} ↔ ${esc(b ? b.name : '')}</b></div>
        <div class="ch-sec" style="border-top:none;margin-top:8px;padding-top:0">
          <div class="st-field"><label>关系</label><input class="ch-in" data-lf="type" value="${esc(link.type)}" list="chRelTypes2"></div>
          <div class="st-field"><label>强度 <b id="chLfVal">${link.strength}</b></label><input type="range" min="1" max="5" step="1" data-lf="strength" value="${link.strength}"></div>
          <div class="st-field"><label>备注</label><input class="ch-in" data-lf="note" value="${esc(link.note)}"></div>
          <button class="mini-btn seal" data-link-del>删除这条关系</button>
          <datalist id="chRelTypes2">${REL_TYPES.map((t) => `<option>${t}</option>`).join('')}</datalist>
        </div>`;
      return;
    }
    const e = entryRef(node.group, node.index);
    const rels = Array.isArray(e.relations) ? e.relations : [];
    const stat = scanOne({ name: e.name || node.name, aliases: e.aliases });
    const inbound = [];
    nodes.forEach((from) => {
      if (from.id === node.id) return;
      const fe = raw[from.group] && raw[from.group][from.index];
      const flist = (fe && typeof fe === 'object' && Array.isArray(fe.relations)) ? fe.relations : [];
      flist.forEach((r, ri) => {
        if (r.target === node.name) inbound.push({ from: from.name, fromId: from.id, type: r.type, g: from.group, i: from.index, ri });
      });
    });
    side.innerHTML = `<div class="ch-side-title"><img class="ch-side-ava" src="${avatarHref(e)}" alt=""><b>${esc(node.name)}</b></div>
      <div class="hint">${esc(node.group)}${e.role ? ' · ' + esc(e.role) : ''} · ${stat.chapters} 章 / ${fmt(stat.total)} 次</div>
      <div class="st-row" style="margin-top:8px">
        <button class="mini-btn" id="chPortrait">看立绘</button>
        <button class="mini-btn" id="chMapDetail">打开档案</button>
      </div>
      <div class="ch-sec">
        <h5>关系 <span class="hint">改完即存</span></h5>
        ${rels.length ? rels.map((r, i) => `<div class="ch-rel-mini">
          <input class="ch-in" data-mf="target" data-mi="${i}" value="${esc(r.target || '')}" list="chCharNames2" placeholder="对象">
          <input class="ch-in" data-mf="type" data-mi="${i}" value="${esc(r.type || '')}" list="chRelTypes2" placeholder="关系">
          <input type="range" min="1" max="5" step="1" data-mf="strength" data-mi="${i}" value="${Number(r.strength) || 3}">
          <button class="icon-btn" data-mdel="${i}">×</button>
        </div>`).join('') : '<div class="hint">暂无主动关系</div>'}
        ${inbound.length ? `<div class="ch-inbound">${inbound.map((r) => `<div class="ch-inbound-row">
          <button class="ch-inbound-name" data-gofocus="${esc(r.fromId)}">${esc(r.from)}</button>
          <span class="ch-inbound-type">${esc(r.type || '关系')}</span>
          <button class="icon-btn" data-indel="${esc(r.g)}|${r.i}|${r.ri}" title="删掉这条反向关系">×</button>
        </div>`).join('')}</div>` : ''}
        <div class="st-row" style="margin-top:8px">
          <button class="mini-btn" id="chMapAddRel">＋ 关系</button>
        </div>
        <datalist id="chCharNames2">${nodes.filter((x) => x.id !== node.id).map((x) => `<option>${esc(x.name)}</option>`).join('')}</datalist>
        <datalist id="chRelTypes2">${REL_TYPES.map((t) => `<option>${t}</option>`).join('')}</datalist>
      </div>`;
  }

  function setFocus(id, keepSide) {
    if (!byId.has(id)) return;
    focusId = id;
    const nd = byId.get(id);
    st.mapFocus = nd.name;
    state.sel = { kind: 'node', id };
    paint();
    if (!keepSide) renderSide(nd, null);
  }

  /* ---------- 事件 ---------- */
  wrap.addEventListener('click', (ev) => {
    const mBtn = ev.target.closest('[data-mapmode]');
    if (mBtn) {
      st.mapMode = mBtn.dataset.mapmode;
      render();
      return;
    }
    const tg = ev.target.closest('[data-toggle]');
    if (tg) {
      const tid = String(tg.dataset.toggle);
      if (treeState.collapsed.has(tid)) treeState.collapsed.delete(tid);
      else treeState.collapsed.add(tid);
      renderTree();
      return;
    }
    const nodeEl = ev.target.closest('[data-node]');
    if (nodeEl) {
      const id = nodeEl.dataset.node;
      /* 直接点头像 → 看立绘；点卡片其它地方 → 聚焦 */
      if (ev.target.tagName === 'image') {
        const nd0 = byId.get(id);
        if (nd0) { openPortrait(nd0.group, nd0.index); return; }
      }
      if (id === focusId) {
        state.sel = { kind: 'node', id };
        renderSide(byId.get(id), null);
        paint();
        return;
      }
      setFocus(id);
      return;
    }
    const linkEl = ev.target.closest('[data-link]');
    if (linkEl) {
      const i = Number(linkEl.dataset.link);
      state.sel = { kind: 'link', i };
      renderSide(null, links[i]);
      paint();
    }
  });

  wrap.addEventListener('dblclick', (ev) => {
    const nodeEl = ev.target.closest('[data-node]');
    if (!nodeEl) return;
    const nd = byId.get(nodeEl.dataset.node);
    if (!nd) return;
    openArchive(nd.group, nd.index);
  });

  wrap.addEventListener('pointerover', (ev) => {
    const nodeEl = ev.target.closest('[data-node]');
    const linkEl = ev.target.closest('[data-link]');
    const id = nodeEl ? nodeEl.dataset.node : (linkEl ? (links[Number(linkEl.dataset.link)] || {}).a : '');
    if (id !== state.hover) {
      state.hover = id || '';
      if (mode !== 'cards') { if (isTree) renderTree(); else draw(); }
    }
  });

  const relayoutBtn = $('#chRelayout');
  if (relayoutBtn) relayoutBtn.onclick = () => {
    if (isTree) {
      treeState.collapsed.clear();
      treeState.pos.clear();
      treeNeedFit = true;
      try { localStorage.removeItem('fj:treePos:' + treeBookKey); } catch (e) { /* ignore */ }
      paint();
      toast('已按当前中心重新排版，可拖动任意人物卡');
      return;
    }
    autoLayout();
    fitView(nodes);
    saveTopo();
    paint();
    toast('已重新排版');
  };
  const fit = $('#chFit');
  if (fit) fit.onclick = () => {
    if (isTree) { treeNeedFit = true; paint(); return; }
    fitView(nodes);
    paint();
  };

  const svgPoint = (ev) => {
    const r = svg.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top };
  };

  svg.addEventListener('pointerdown', (ev) => {
    if (mode === 'cards') return;
    const hitNode = ev.target.closest('[data-node]');
    const hitToggle = ev.target.closest('[data-toggle]');
    state.downNode = hitNode ? hitNode.dataset.node : '';
    state.downToggle = hitToggle ? String(hitToggle.dataset.toggle) : '';
    state.downIsImg = ev.target.tagName === 'image';
    state.panMoved = false;
    const p = svgPoint(ev);
    if (hitNode && isTree) {
      /* 全览：单独拖动一张人物卡 */
      const id = hitNode.dataset.node;
      const cur = treeState.pos.get(id) || { x: 0, y: 0 };
      state.treeDrag = { id, dx: cur.x - (p.x - view.x) / view.k, dy: cur.y - (p.y - view.y) / view.k, x0: cur.x, y0: cur.y };
      state.moved = false;
    } else if (hitNode) {
      const gEl = hitNode;
      const nd = byId.get(gEl.dataset.node);
      if (!nd) return;
      state.drag = { nd, dx: nd.x - (p.x - view.x) / view.k, dy: nd.y - (p.y - view.y) / view.k, x0: nd.x, y0: nd.y };
      state.moved = false;
    } else {
      state.pan = { sx: ev.clientX, sy: ev.clientY, ox: view.x, oy: view.y };
    }
    try { svg.setPointerCapture(ev.pointerId); } catch (e) { /* ignore */ }
  });

  svg.addEventListener('pointermove', (ev) => {
    if (mode === 'cards') return;
    if (state.treeDrag) {
      const t = state.treeDrag;
      const p = svgPoint(ev);
      const nx = clampX((p.x - view.x) / view.k + t.dx);
      const ny = clampY((p.y - view.y) / view.k + t.dy);
      if (Math.abs(nx - t.x0) > 0.5 || Math.abs(ny - t.y0) > 0.5) state.moved = true;
      if (!state.moved) return;
      treeState.pos.set(t.id, { x: nx, y: ny });
      renderTree();
      return;
    }
    if (state.drag) {
      const nd = state.drag.nd;
      const p = svgPoint(ev);
      nd.x = clampX((p.x - view.x) / view.k + state.drag.dx);
      nd.y = clampY((p.y - view.y) / view.k + state.drag.dy);
      nd.fixed = true;
      if (Math.abs(nd.x - (state.drag.x0 || nd.x)) > 0.5) state.moved = true;
      draw();
    } else if (state.pan) {
      const dx = ev.clientX - state.pan.sx;
      const dy = ev.clientY - state.pan.sy;
      if (Math.hypot(dx, dy) > 4) state.panMoved = true;
      if (!state.panMoved) return;
      view.x = state.pan.ox + dx;
      view.y = state.pan.oy + dy;
      paint();
    }
  });

  function saveTopo() {
    nodes.forEach((nd) => {
      const e = entryRef(nd.group, nd.index);
      e.graph = { x: Math.round(nd.x), y: Math.round(nd.y) };
      posMem.set(nd.id, { x: nd.x, y: nd.y });
    });
    A().saveProjectFields({ characters: charGroups() }).catch(() => {});
  }

  const endDrag = () => {
    const moved = state.panMoved || (state.drag && state.moved) || (state.treeDrag && state.moved);
    if (state.treeDrag && state.moved) {
      /* 手动摆位已存进 treeState.pos，这里落盘并刷新连线 */
      treePosSave(treeBookKey, treeState.pos);
      renderTree();
    } else if (state.drag && state.moved) {
      saveTopo();
      syncBounds(nodes);
    } else if (!moved && state.downToggle) {
      if (treeState.collapsed.has(state.downToggle)) treeState.collapsed.delete(state.downToggle);
      else treeState.collapsed.add(state.downToggle);
      paint();
    } else if (!moved && state.downNode) {
      if (state.downIsImg) {
        const nd = byId.get(state.downNode);
        if (nd) openPortrait(nd.group, nd.index);
      } else if (state.downNode !== focusId) {
        setFocus(state.downNode);
      } else {
        state.sel = { kind: 'node', id: focusId };
        renderSide(byId.get(focusId), null);
        paint();
      }
    }
    state.downNode = '';
    state.downToggle = '';
    state.downIsImg = false;
    state.panMoved = false;
    state.drag = null;
    state.treeDrag = null;
    state.pan = null;
  };
  svg.addEventListener('pointerup', endDrag);
  svg.addEventListener('pointercancel', endDrag);

  svg.addEventListener('wheel', (ev) => {
    if (mode === 'cards') return;
    ev.preventDefault();
    const rect = svg.getBoundingClientRect();
    const mx = ev.clientX - rect.left;
    const my = ev.clientY - rect.top;
    const k2 = Math.max(0.45, Math.min(2.6, view.k * (ev.deltaY < 0 ? 1.1 : 0.9)));
    view.x = mx - (mx - view.x) * (k2 / view.k);
    view.y = my - (my - view.y) * (k2 / view.k);
    view.k = k2;
    paint();
  }, { passive: false });

  /* 侧栏编辑（与原逻辑一致） */
  if (side) {
    side.addEventListener('input', (ev) => {
      const t = ev.target;
      if (t.dataset.mf) {
        const node = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (!node) return;
        const e = entryRef(node.group, node.index);
        if (!Array.isArray(e.relations)) e.relations = [];
        const r = e.relations[Number(t.dataset.mi)];
        if (!r) return;
        r[t.dataset.mf] = t.dataset.mf === 'strength' ? Number(t.value) : t.value;
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        if (t.dataset.mf === 'target' || t.dataset.mf === 'type') { rebuildLinks(); paint(); }
      }
      if (t.dataset.lf) {
        const i = state.sel && state.sel.kind === 'link' ? state.sel.i : -1;
        const l = links[i];
        if (!l) return;
        const e = entryRef(l.ownerGroup, l.ownerIndex);
        const r = Array.isArray(e.relations) ? e.relations[l.relIdx] : null;
        if (!r) return;
        r[t.dataset.lf] = t.dataset.lf === 'strength' ? Number(t.value) : t.value;
        l[t.dataset.lf] = r[t.dataset.lf];
        const v = $('#chLfVal');
        if (v && t.dataset.lf === 'strength') v.textContent = String(l.strength);
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        paint();
      }
    });
    side.addEventListener('click', (ev) => {
      const goFocus = ev.target.closest('[data-gofocus]');
      if (goFocus) { setFocus(goFocus.dataset.gofocus); return; }
      const inde = ev.target.closest('[data-indel]');
      if (inde) {
        const [g, i, ri] = inde.dataset.indel.split('|');
        const src = raw[g] && raw[g][Number(i)];
        if (src && Array.isArray(src.relations)) src.relations.splice(Number(ri), 1);
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        const cur = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (cur) renderSide(cur, null);
        rebuildLinks(); paint();
        return;
      }
      if (ev.target.closest('#chPortrait')) {
        const node = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (node) openPortrait(node.group, node.index);
        return;
      }
      if (ev.target.closest('#chMapDetail')) {
        const node = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (!node) return;
        openArchive(node.group, node.index);
        return;
      }
      const del = ev.target.closest('[data-mdel]');
      if (del) {
        const node = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (!node) return;
        const e = entryRef(node.group, node.index);
        if (Array.isArray(e.relations)) e.relations.splice(Number(del.dataset.mdel), 1);
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        renderSide(node, null);
        rebuildLinks(); paint();
        return;
      }
      if (ev.target.closest('[data-link-del]')) {
        const i = state.sel && state.sel.kind === 'link' ? state.sel.i : -1;
        const l = links[i];
        if (!l) return;
        const e = entryRef(l.ownerGroup, l.ownerIndex);
        if (Array.isArray(e.relations)) e.relations.splice(l.relIdx, 1);
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        state.sel = { kind: 'node', id: focusId };
        renderSide(byId.get(focusId), null);
        rebuildLinks(); paint();
        return;
      }
      if (ev.target.closest('#chMapAddRel')) {
        const node = state.sel && state.sel.kind === 'node' ? byId.get(state.sel.id) : null;
        if (!node) return;
        const e = entryRef(node.group, node.index);
        if (!Array.isArray(e.relations)) e.relations = [];
        const other = nodes.find((x) => x.id !== node.id);
        e.relations.push({ target: other ? other.name : '', type: '关系', strength: 3, note: '' });
        A().saveProjectFields({ characters: charGroups() }).catch(() => {});
        renderSide(node, null);
        rebuildLinks(); paint();
      }
    });
  }

  /* ---------- 首屏 ---------- */
  if (mode !== 'cards') {
    if (nodes.some((n) => !n.fixed)) {
      const { LW, LH } = layoutArea();
      scatter(nodes.filter((n) => !n.fixed), LW, LH);
      settleSteps(LW, LH, mode === 'live' ? 300 : 320);
    }
    if (!isTree) {
      /* 老坐标可能贴在一起，进图时轻推一次，避免一进来就压卡 */
      nodes.forEach((nd) => { nd.fixed = false; });
      spreadOverlaps();
      nodes.forEach((nd) => { nd.fixed = true; posMem.set(nd.id, { x: nd.x, y: nd.y }); });
      syncBounds(nodes);
      fitView(nodes);
    }
  }
  paint();
  const fNode = byId.get(focusId);
  if (fNode) {
    renderSide(fNode, null);
    state.sel = { kind: 'node', id: focusId };
  } else {
    renderSide(null, null);
  }
  if (isLive) liveLoop();
  wrap.addEventListener('chg:leave', stopLoop);
}

/* ---- 人物立绘弹窗 ---- */
function openPortrait(group, index) {
  const chars = charGroups();
  const arr = chars[group] || [];
  const c = arr[index];
  if (!c) return;
  const rec = (typeof c === 'object') ? c : { name: String(c) };
  const stat = scanOne({ name: rec.name, aliases: rec.aliases });
  let mask = $('#portraitMask');
  if (!mask) {
    mask = document.createElement('div');
    mask.id = 'portraitMask';
    mask.className = 'modal-mask';
    document.body.appendChild(mask);
  }
  const rels = (Array.isArray(rec.relations) ? rec.relations : []).filter((r) => r.target);
  mask.innerHTML = `<div class="modal portrait-modal">
    <div class="portrait-grid">
      <div class="portrait-figure">
        <img id="portraitImg" src="${avatarHref(rec)}" alt="">
        <div class="portrait-cap">
          <b>${esc(rec.name || '')}</b>
          <span>${esc([group, rec.role, rec.identity].filter(Boolean).join(' · '))}</span>
        </div>
      </div>
      <div class="portrait-info">
        <h3>${esc(rec.name || '')}</h3>
        <div class="md">${esc(rec.tagline || rec.desc || '')}</div>
        <div class="portrait-actions">
          <button class="mini-btn primary" id="pAi">AI 绘立绘</button>
          <button class="mini-btn" id="pUp">上传图片</button>
          <button class="mini-btn" id="pClr">清除</button>
        </div>
        <div class="portrait-rows">
          ${rec.gender ? `<div><span>性别</span><b>${esc(rec.gender)}</b></div>` : ''}
          ${rec.age ? `<div><span>年龄</span><b>${esc(rec.age)}</b></div>` : ''}
          ${rec.identity ? `<div><span>身份</span><b>${esc(rec.identity)}</b></div>` : ''}
          ${rec.appearance ? `<div><span>外貌</span><b>${esc(rec.appearance)}</b></div>` : ''}
          ${rec.personality ? `<div><span>性格</span><b>${esc(rec.personality)}</b></div>` : ''}
          ${rec.ability ? `<div><span>能力</span><b>${esc(rec.ability)}</b></div>` : ''}
          ${rec.goal ? `<div><span>目标</span><b>${esc(rec.goal)}</b></div>` : ''}
          <div><span>出场</span><b>${stat.chapters} 章 · ${fmt(stat.total)} 次</b></div>
        </div>
        ${rels.length ? `<div class="portrait-rels">${rels.map((r) => `<span class="ch-tag">${esc(r.target)} · ${esc(r.type || '关系')}</span>`).join('')}</div>` : ''}
        <div class="hint" id="pTip">未配置绘图 API 时用内置古风立绘；想用 AI 精绘，去「设置 → 接口」填绘图 API。</div>
      </div>
    </div>
    <div class="mrow"><button class="pill-btn" data-close>关闭</button></div>
  </div>`;
  mask.classList.add('show');
  mask.addEventListener('click', (e) => { if (e.target === mask || e.target.closest('[data-close]')) mask.classList.remove('show'); });

  const refresh = async () => {
    const fresh = charGroups()[group] && charGroups()[group][index];
    if (fresh) {
      const img = $('#portraitImg');
      AVA_CACHE.clear();
      if (img) img.src = avatarHref(fresh);
      A().refreshUi();
      paint();
    }
  };

  const tip = (t) => { const el = $('#pTip'); if (el) el.textContent = t; };

  const ai = $('#pAi');
  if (ai) ai.onclick = async () => {
    ai.disabled = true;
    const old = ai.textContent;
    ai.textContent = '绘制中…';
    tip('正在调用绘图模型，约 20–90 秒…');
    try {
      const r = await api(`/books/${encodeURIComponent(A().S.book.name)}/characters/avatar`, {
        method: 'POST', body: { group, index },
      });
      const fresh = charGroups()[group][index];
      if (fresh) fresh.avatar = r.url;
      await refresh();
      tip('已生成新的立绘');
    } catch (e) {
      tip(e.message || '生成失败');
    } finally {
      ai.disabled = false;
      ai.textContent = old;
    }
  };

  const up = $('#pUp');
  if (up) up.onclick = () => {
    const inp = document.createElement('input');
    inp.type = 'file';
    inp.accept = 'image/*';
    inp.onchange = () => {
      const file = inp.files && inp.files[0];
      if (!file) return;
      const fr = new FileReader();
      fr.onload = async () => {
        try {
          const r = await api(`/books/${encodeURIComponent(A().S.book.name)}/characters/avatar`, {
            method: 'POST', body: { group, index, data: fr.result },
          });
          const fresh = charGroups()[group][index];
          if (fresh) fresh.avatar = r.url;
          await refresh();
          tip('已换上新图');
        } catch (e) { tip(e.message || '上传失败'); }
      };
      fr.readAsDataURL(file);
    };
    inp.click();
  };

  const clr = $('#pClr');
  if (clr) clr.onclick = async () => {
    try {
      await api(`/books/${encodeURIComponent(A().S.book.name)}/characters/avatar`, {
        method: 'POST', body: { group, index, clear: true },
      });
      const fresh = charGroups()[group][index];
      if (fresh) fresh.avatar = '';
      await refresh();
      tip('已恢复内置立绘');
    } catch (e) { tip(e.message || '操作失败'); }
  };
}

/* ---- 角色卡片式档案：把这个人所有字段摊在一张卡上 ---- */
function openArchive(group, index) {
  const chars = charGroups();
  const arr = chars[group] || [];
  const c = arr[index];
  if (!c) return;
  const rec = normChar(c, group, index);
  const stat = scanOne({ name: rec.name, aliases: rec.aliases });
  const rels = (Array.isArray(rec.relations) ? rec.relations : []).filter((r) => r.target);
  const purposes = Array.isArray(rec.purpose) ? rec.purpose : splitList(rec.purpose);
  const aliases = splitList(rec.aliases).join('、');

  let mask = $('#archiveMask');
  if (!mask) {
    mask = document.createElement('div');
    mask.id = 'archiveMask';
    mask.className = 'modal-mask';
    document.body.appendChild(mask);
  }

  const row = (label, val) => `<div class="arc-row"><span>${label}</span><b>${esc(val || '—')}</b></div>`;
  const block = (title, val) => (val ? `<section class="arc-sec"><h4>${title}</h4><p>${esc(val)}</p></section>` : '');
  const chips = [rec.group, rec.role, rec.gender, rec.age, rec.identity]
    .filter(Boolean).map((t) => `<span class="arc-chip">${esc(t)}</span>`).join('');
  const relHtml = rels.length ? `<section class="arc-sec"><h4>关系网 <span class="hint">点名字看他的档案</span></h4>
      <div class="arc-rels">${rels.map((r) => `<button class="arc-rel" data-arcgo="${esc(r.target)}">
        <b>${esc(r.target)}</b><i>${esc(r.type || '关系')}</i>
        <span class="arc-dots">${Array.from({ length: 5 }, (_, k) => `<s class="${k < (Number(r.strength) || 3) ? 'on' : ''}"></s>`).join('')}</span>
        ${r.note ? `<em>${esc(r.note)}</em>` : ''}
      </button>`).join('')}</div></section>` : '';
  const infoRows = [
    row('阵营', rec.group), row('定位', rec.role), row('性别', rec.gender), row('年龄', rec.age),
    row('身份', rec.identity), row('别名', aliases),
    row('出场', `${stat.chapters} 章 · ${fmt(stat.total)} 次` + (stat.first ? ` · 首次「${stat.first.title}」` : '')),
  ].join('');
  const half = [
    block('性格', rec.personality), block('外貌', rec.appearance), block('能力 / 武力', rec.ability),
  ].join('');
  const purposeHtml = purposes.length
    ? `<section class="arc-sec"><h4>动机与目的</h4><ul>${purposes.map((p) => `<li>${esc(p)}</li>`).join('')}</ul></section>`
    : '';

  mask.innerHTML = `<div class="modal arc-modal">
    <div class="arc-hero">
      <img class="arc-ava" src="${avatarHref(rec)}" alt="">
      <div class="arc-id">
        <h2>${esc(rec.name || '未命名')}</h2>
        ${aliases ? `<div class="arc-alias">${esc(aliases)}</div>` : ''}
        <div class="arc-chips">${chips}</div>
        ${rec.tagline ? `<div class="arc-tagline">「${esc(rec.tagline)}」</div>` : ''}
      </div>
    </div>
    <div class="arc-body">
      <div class="arc-cols">
        <div class="arc-col">${infoRows}</div>
        <div class="arc-col">${half}</div>
      </div>
      ${block('目标', rec.goal)}
      ${purposeHtml}
      ${block('背景', rec.background)}
      ${block('简介', rec.intro)}
      ${block('成长弧线', rec.arc)}
      ${block('口头禅', rec.quote)}
      ${relHtml}
    </div>
    <div class="mrow">
      <button class="mini-btn" id="arcPortrait">看立绘</button>
      <button class="mini-btn primary" id="arcEdit">编辑档案</button>
      <button class="pill-btn" data-close>关闭</button>
    </div>
  </div>`;
  mask.classList.add('show');
  mask.onclick = (e) => {
    if (e.target === mask || e.target.closest('[data-close]')) { mask.classList.remove('show'); return; }
    const go = e.target.closest('[data-arcgo]');
    if (go) {
      const hit = allChars().find((x) => x.name === go.dataset.arcgo);
      if (hit) openArchive(hit.group, hit.index);
    }
  };

  const pBtn = $('#arcPortrait');
  if (pBtn) pBtn.onclick = () => openPortrait(group, index);
  const eBtn = $('#arcEdit');
  if (eBtn) eBtn.onclick = () => {
    mask.classList.remove('show');
    selectCharObj(normChar(c, group, index));
    render();
  };
}

/* ---- 事件绑定 ---- */
function bindCharEvents(all, apps) {
  const root = $('#chShell');
  if (!root) return;
  const st = charState();

  root.addEventListener('click', async (ev) => {
    const t = ev.target;
    const filter = t.closest('[data-cfilter]');
    if (filter) {
      st.filter = filter.dataset.cfilter;
      $$('#chFilter button').forEach((b) => b.classList.toggle('on', b.dataset.cfilter === st.filter));
      $('#chItems').innerHTML = charItemsHtml(allChars(), scanAll(allChars()));
      return;
    }
    const portraitEl = t.closest('[data-portrait]');
    if (portraitEl) {
      const [pg, pi] = String(portraitEl.dataset.portrait).split('::');
      openPortrait(pg, Number(pi));
      return;
    }
    if (t.closest('#chPortraitBtn')) {
      if (st.editRef) openPortrait(st.editRef.group, st.editRef.index);
      else toast('先把人物保存下来，再生成立绘');
      return;
    }
    const pick = t.closest('[data-csel]');
    if (pick) {
      const id = pick.dataset.csel;
      if (id === st.sel) return;
      if (st.dirty && !await A().askConfirm('有未保存的修改', '切换人物会丢弃当前未保存的编辑，继续？', '丢弃')) return;
      const target = allChars().find((c) => charId(c) === id);
      if (!target) return;
      selectCharObj(target);
      render();
      return;
    }
    if (t.closest('#chAdd')) {
      if (st.dirty && !await A().askConfirm('有未保存的修改', '新建人物会丢弃当前未保存的编辑，继续？', '丢弃')) return;
      Object.assign(st, { view: 'detail', sel: null, editRef: null, dirty: false });
      st.draft = emptyChar(st.filter && st.filter !== '全部' ? st.filter : '主角');
      render();
      return;
    }
    if (t.closest('#chAiBtn')) { st.view = 'ai'; render(); return; }
    if (t.closest('#chAiBack')) { st.view = 'detail'; render(); return; }
    if (t.closest('#chSave')) { await saveCharDraft(); return; }
    if (t.closest('#chDel')) {
      if (st.editRef) await deleteCharAt(st.editRef.group, st.editRef.index, st.draft.name);
      return;
    }
    if (t.closest('#chToMap')) { st.mapFocus = ''; st.view = 'map'; render(); return; }
    const chip = t.closest('[data-ctoggle]');
    if (chip && st.draft) {
      const p = chip.dataset.ctoggle;
      const list = Array.isArray(st.draft.purpose) ? st.draft.purpose : splitList(st.draft.purpose);
      const i = list.indexOf(p);
      if (i >= 0) list.splice(i, 1); else list.push(p);
      st.draft.purpose = list;
      chip.classList.toggle('on', i < 0);
      markDirty();
      return;
    }
    if (t.closest('#chRelAdd') && st.draft) {
      if (!Array.isArray(st.draft.relations)) st.draft.relations = [];
      const other = all.find((c) => c.name !== st.draft.name);
      st.draft.relations.push({ target: other ? other.name : '', type: '', strength: 3, note: '' });
      markDirty();
      render();
      return;
    }
    const relDel = t.closest('[data-rel-del]');
    if (relDel && st.draft) {
      st.draft.relations.splice(Number(relDel.dataset.relDel), 1);
      markDirty();
      render();
      return;
    }
    const chap = t.closest('[data-cchap]');
    if (chap) {
      closeStudio();
      A().openChapter(chap.dataset.cchap).catch(() => {});
      return;
    }
    if (t.closest('#chAiRun')) {
      const btn = t.closest('#chAiRun');
      loading(btn, true);
      try {
        const r = await api('/ai/characters', {
          method: 'POST',
          body: { project_name: A().S.book.name, role_type: $('#chAiRole').value, count: Number($('#chAiCount').value) || 3 },
        });
        const role = $('#chAiRole').value;
        const chSt = charState();
        chSt.aiRole = role;
        chSt.ai = (r.characters || []).map((c) => ({ ...c, group: c.group || role }));
        renderAiList();
      } catch (err) { toast('生成失败：' + err.message); }
      loading(btn, false);
      return;
    }
    const adopt = t.closest('[data-adopt]');
    if (adopt) {
      const st2 = charState();
      const i = Number(adopt.dataset.adopt);
      const c = (st2.ai || [])[i];
      if (!c) return;
      const pick = $(`[data-airole="${i}"]`);
      const g = (pick && pick.value) || c.group || st2.aiRole || '配角';
      const chars = charGroups();
      Object.keys(chars).forEach((k) => { if (!Array.isArray(chars[k])) chars[k] = []; });
      if (!Array.isArray(chars[g])) chars[g] = [];
      const dup = Object.keys(chars).some((k) => chars[k].some((x) => (typeof x === 'string' ? x : x && x.name) === c.name));
      if (dup) {
        c.adopted = g;
        c.group = g;
        renderAiList();
        toast(`人物表里已有「${c.name}」，没有重复写入`);
        return;
      }
      const idx = chars[g].length;
      chars[g].push({
        name: c.name,
        group: g,
        role: c.role || '',
        gender: c.gender || '',
        age: c.age || '',
        identity: c.identity || '',
        tagline: c.tagline || c.desc || '',
        desc: c.desc || c.tagline || '',
        intro: c.intro || c.background || '',
        purpose: Array.isArray(c.purpose) && c.purpose.length ? c.purpose : [g],
        appearance: c.appearance || '',
        personality: c.personality || '',
        background: c.background || '',
        ability: c.ability || '',
        quote: c.quote || '',
        goal: c.goal || '',
        arc: c.arc || '',
        relations: (c.relations || []).map((r) => ({ target: r.target, type: r.type, strength: 3, note: '' })),
      });
      await A().saveProjectFields({ characters: chars });
      A().refreshUi();
      c.adopted = g;
      c.group = g;
      /* 采纳后选中刚写入的这位，回到档案就能看到它，不用再翻列表 */
      st2.sel = `${g}::${idx}`;
      st2.draft = null;
      st2.editRef = null;
      const itemsBox = $('#chItems');
      if (itemsBox) {
        st2.filter = '全部';
        $$('#chFilter button').forEach((b) => b.classList.toggle('on', b.dataset.cfilter === '全部'));
        itemsBox.innerHTML = charItemsHtml(allChars(), scanAll(allChars()));
      }
      renderAiList();
      toast(`已采纳到「${g}」：${c.name}`);
    }
  });

  root.addEventListener('input', (ev) => {
    const t = ev.target;
    if (t.id === 'chSearch') {
      st.query = t.value;
      $('#chItems').innerHTML = charItemsHtml(allChars(), scanAll(allChars()));
      return;
    }
    if (t.id === 'chAiRole') { st.aiRole = t.value; return; }
    if (t.dataset.airole != null) {
      const item = (st.ai || [])[Number(t.dataset.airole)];
      if (item) item.group = t.value;
      return;
    }
    if (!st.draft) return;
    if (t.dataset.f) {
      const f = t.dataset.f;
      if (f === 'aliases') st.draft.aliases = splitList(t.value);
      else st.draft[f] = t.value;
      markDirty();
      return;
    }
    if (t.dataset.relTarget != null) {
      const r = (st.draft.relations || [])[Number(t.dataset.relTarget)];
      if (r) { r.target = t.value; markDirty(); }
      return;
    }
    if (t.dataset.relType != null) {
      const r = (st.draft.relations || [])[Number(t.dataset.relType)];
      if (r) { r.type = t.value; markDirty(); }
      return;
    }
    if (t.dataset.relStrength != null) {
      const r = (st.draft.relations || [])[Number(t.dataset.relStrength)];
      if (r) { r.strength = Number(t.value); markDirty(); }
      return;
    }
    if (t.dataset.relNote != null) {
      const r = (st.draft.relations || [])[Number(t.dataset.relNote)];
      if (r) { r.note = t.value; markDirty(); }
    }
  });

  root.addEventListener('keydown', (ev) => {
    if (ev.target.id === 'chPurposeAdd' && ev.key === 'Enter') {
      ev.preventDefault();
      const v = ev.target.value.trim();
      if (!v || !st.draft) return;
      const list = Array.isArray(st.draft.purpose) ? st.draft.purpose : splitList(st.draft.purpose);
      if (!list.includes(v)) list.push(v);
      st.draft.purpose = list;
      ev.target.value = '';
      markDirty();
      render();
    }
  });
}

/* ---------------- 大纲 ---------------- */
function svgSpark(points) {
  if (!points.length) return '<div class="st-empty">没有数据</div>';
  const w = 640, h = 72, max = 100;
  const step = points.length > 1 ? w / (points.length - 1) : w;
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(h - (p.intensity / max) * (h - 8) - 4).toFixed(1)}`).join(' ');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <path d="${d}" fill="none" stroke="var(--seal)" stroke-width="2" stroke-linejoin="round"/>
  </svg>`;
}

function odRowsHtml(detailed) {
  const keys = Object.keys(detailed || {}).sort((a, b) => Number(a) - Number(b));
  if (!keys.length) return '<div class="st-empty">还没有细纲，可点「手动新增」自己写，或用「AI 生成」起个底</div>';
  return `<div class="st-od-list">${keys.map((k) => {
    const v = detailed[k] || {};
    return `<div class="st-od" data-odk="${esc(k)}">
      <div class="st-od-head">
        <span class="st-od-no">第 ${esc(k)} 章</span>
        <input data-odf="title" value="${esc(v.title || '')}" placeholder="章节标题">
        <button class="icon-btn" data-oddel="${esc(k)}" title="删除这一章细纲">×</button>
      </div>
      <div class="st-od-grid">
        <textarea class="st-textarea" data-odf="idea" placeholder="本意：这一章要完成什么">${esc(v.idea || '')}</textarea>
        <textarea class="st-textarea" data-odf="scenes" placeholder="场景：发生在哪、谁在场">${esc(v.scenes || '')}</textarea>
        <textarea class="st-textarea" data-odf="conflict" placeholder="冲突：谁和谁、为什么">${esc(v.conflict || '')}</textarea>
        <textarea class="st-textarea" data-odf="hook" placeholder="钩子：章末留什么">${esc(v.hook || '')}</textarea>
      </div>
    </div>`;
  }).join('')}</div>`;
}

async function renderOutline(body) {
  const book = A().S.book;
  const o = book.outline || {};
  const detailed = o.detailed || {};
  const fores = (o.foreshadows || []).slice();

  body.innerHTML = `
    <div class="st-card" style="margin-bottom:12px">
      <h4>宏观大纲
        <span class="st-row">
          <button class="mini-btn" id="stOMacroGen">AI 生成</button>
          <button class="mini-btn" id="stOMacroSave">保存</button>
        </span>
      </h4>
      <textarea class="st-textarea" id="stOMacro" style="min-height:180px">${esc(o.macro || '')}</textarea>
      <div class="hint" style="margin-top:6px">也可以自己手填，写完点右上「保存」；AI 生成只是给个底稿。</div>
    </div>

    <div class="st-card" style="margin-bottom:12px">
      <h4>逐章细纲
        <span class="st-row">
          <button class="mini-btn" id="stODAdd">＋ 手动新增</button>
          <span class="hint">起始章</span><input id="stOStart" type="number" value="${Object.keys(detailed).length + 1}" style="width:70px;height:30px;border-radius:9px;border:1px solid var(--line);background:var(--paper);padding:0 8px">
          <span class="hint">数量</span><input id="stOCount" type="number" value="5" min="1" max="20" style="width:60px;height:30px;border-radius:9px;border:1px solid var(--line);background:var(--paper);padding:0 8px">
          <button class="mini-btn primary" id="stODGen">AI 生成</button>
          <button class="mini-btn" id="stODApply" hidden>按细纲建章节</button>
        </span>
      </h4>
      <div class="hint" style="margin-bottom:8px">标题、本意、场景、冲突、钩子都能直接改，离开输入框即自动保存；也可以手动新增一章。</div>
      <div id="stODResult">${odRowsHtml(detailed)}</div>
    </div>

    <div class="st-grid c2">
      <div class="st-card">
        <h4>伏笔清单 <button class="mini-btn" id="stFAdd">＋ 新增</button></h4>
        <div class="st-list" id="stFList">
          ${fores.length ? fores.map((f, i) => `<div class="st-item">
            <div class="t">
              <input type="checkbox" data-ftoggle="${i}" ${f.done ? 'checked' : ''}>
              <span data-fedit="${i}" title="点击编辑" style="font-weight:400;white-space:pre-wrap;cursor:pointer;${f.done ? 'text-decoration:line-through;color:var(--muted)' : ''}">${esc(f.text)}</span>
              <button class="icon-btn" data-fdel="${i}" title="删除">×</button>
            </div>
            <div class="d">${esc(f.chapter || '')}</div>
          </div>`).join('') : '<div class="st-empty">还没有伏笔，点右上新增</div>'}
        </div>
      </div>
      <div class="st-card">
        <h4>情感曲线 <button class="mini-btn" id="stEmoRun">分析当前章</button></h4>
        <div id="stEmoBox"><div class="st-empty">选一章正文后点分析</div></div>
      </div>
    </div>

    <div class="st-card" style="margin-top:12px">
      <h4>章节依赖 <button class="mini-btn" id="stDepRun">分析全书</button></h4>
      <div id="stDepBox"><div class="st-empty">分析章节之间共享的人物与关键词，找断链和重复</div></div>
    </div>`;

  const saveOutline = async (patch) => {
    const outline = { ...(A().S.book.outline || {}), ...patch };
    await A().saveProjectFields({ outline });
    A().refreshUi();
  };

  $('#stOMacroSave').onclick = async () => { await saveOutline({ macro: $('#stOMacro').value }); toast('大纲已保存'); };
  $('#stOMacroGen').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/generate/outline', { method: 'POST', body: bookCtx() });
      $('#stOMacro').value = (r.outline && r.outline.macro) || '';
      await saveOutline({ macro: $('#stOMacro').value });
      toast('已生成并保存');
    } catch (err) { toast('生成失败：' + err.message); }
    loading(btn, false);
  };

  let pendingItems = null;
  $('#stODGen').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/ai/detailed-outline', {
        method: 'POST',
        body: { project_name: book.name, start: Number($('#stOStart').value) || 1, count: Number($('#stOCount').value) || 5 },
      });
      const items = r.items || [];
      if (!items.length) { toast('没有解析到细纲，换个模型再试'); loading(btn, false); return; }
      pendingItems = items;
      const patch = {};
      items.forEach((it) => {
        const num = (it.chapter.match(/\d+/) || [String(Object.keys(detailed).length + 1)])[0];
        patch[num] = it;
        detailed[num] = it;
      });
      $('#stODResult').innerHTML = odRowsHtml(detailed);
      $('#stODApply').hidden = false;
      $('#stODApply').dataset.patch = JSON.stringify(patch);
      await saveOutline({ detailed });
      toast(`已写入 ${items.length} 章细纲，可直接改`);
    } catch (err) { toast('生成失败：' + err.message); }
    loading(btn, false);
  };

  /* 手动填写细纲：失焦即存 */
  const odBox = $('#stODResult');
  odBox.addEventListener('change', async (e) => {
    const f = e.target.dataset.odf;
    if (!f) return;
    const row = e.target.closest('[data-odk]');
    if (!row) return;
    const k = row.dataset.odk;
    if (!detailed[k]) detailed[k] = { chapter: `第${k}章` };
    detailed[k][f] = e.target.value;
    await saveOutline({ detailed });
    toast('细纲已保存');
  });
  odBox.addEventListener('click', async (e) => {
    const del = e.target.closest('[data-oddel]');
    if (!del) return;
    const k = del.dataset.oddel;
    const ok = await A().askConfirm('删除细纲', `确定删除第 ${k} 章的细纲？`, '删除');
    if (!ok) return;
    delete detailed[k];
    await saveOutline({ detailed });
    render();
  });
  $('#stODAdd').onclick = async () => {
    const nums = Object.keys(detailed).map(Number).filter((n) => !isNaN(n));
    const next = nums.length ? Math.max(...nums) + 1 : 1;
    detailed[next] = { chapter: `第${next}章`, title: '', idea: '', scenes: '', conflict: '', hook: '' };
    await saveOutline({ detailed });
    render();
    toast(`已新增第 ${next} 章细纲，直接填就行`);
  };
  $('#stODApply').onclick = async (e) => {
    const patch = JSON.parse(e.currentTarget.dataset.patch || '{}');
    const nums = Object.keys(patch).sort((a, b) => Number(a) - Number(b));
    const ok = await A().askConfirm('按细纲建章节', `将为 ${nums.length} 章创建章节文件（同名会跳过）`, '创建');
    if (!ok) return;
    const S0 = A().S;
    const vol = A().volumeFolders()[0];
    let volId = vol ? vol.id : null;
    if (!volId) {
      volId = 'vol_' + Date.now();
      S0.files.push({ id: volId, parentId: 'root', name: '01_正文', type: 'FOLDER', lastModified: Date.now() });
    }
    nums.forEach((n) => {
      const it = patch[n];
      const name = `第${n}章${it.title ? ' · ' + it.title : ''}`;
      if (S0.files.some((f) => f.type === 'FILE' && f.name === name)) return;
      S0.files.push({
        id: 'ch_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 5),
        parentId: volId, name, type: 'FILE', content: '', lastModified: Date.now(),
        metadata: { outline: [it.idea, it.scenes, it.conflict, it.hook].filter(Boolean).join('\n') },
      });
    });
    await api(`/files/${encodeURIComponent(S0.book.name)}`, { method: 'POST', body: { files: S0.files } });
    A().refreshUi();
    toast('已创建章节');
  };

  $('#stFAdd').onclick = async () => {
    const text = await A().askText('新增伏笔', '可以换行，每行会拆成一条；Ctrl / ⌘ + Enter 提交', '', { multiline: true });
    if (!text) return;
    const list = (A().S.book.outline || {}).foreshadows || [];
    text.split(/\n+/).map((s) => s.trim()).filter(Boolean).forEach((t) => list.push({ text: t, done: false, chapter: '' }));
    await saveOutline({ foreshadows: list });
    render();
  };
  $$('[data-fedit]', body).forEach((el) => {
    el.onclick = async () => {
      const list = (A().S.book.outline || {}).foreshadows || [];
      const i = Number(el.dataset.fedit);
      const cur = list[i];
      if (!cur) return;
      const v = await A().askText('编辑伏笔', '可以换行，提交后合成一段', cur.text, { multiline: true });
      if (v === null) return;
      cur.text = v.replace(/\n+/g, ' ');
      await saveOutline({ foreshadows: list });
      render();
    };
  });
  $$('[data-fdel]', body).forEach((el) => {
    el.onclick = async () => {
      const list = (A().S.book.outline || {}).foreshadows || [];
      const i = Number(el.dataset.fdel);
      const ok = await A().askConfirm('删除伏笔', `确定删除「${(list[i] || {}).text || ''}」？`, '删除');
      if (!ok) return;
      list.splice(i, 1);
      await saveOutline({ foreshadows: list });
      render();
    };
  });
  $$('[data-ftoggle]', body).forEach((el) => {
    el.onchange = async () => {
      const list = (A().S.book.outline || {}).foreshadows || [];
      const i = Number(el.dataset.ftoggle);
      if (list[i]) list[i].done = el.checked;
      await saveOutline({ foreshadows: list });
      render();
    };
  });

  $('#stEmoRun').onclick = async (e) => {
    const f = A().currentFile();
    if (!f) { toast('先在写作台打开一章'); return; }
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/analysis/emotion', { method: 'POST', body: { text: f.content || '' } });
      const pts = r.points || [];
      const peak = pts.slice().sort((a, b) => b.intensity - a.intensity)[0];
      const tone = peak && peak.tone !== '中性' ? peak.tone : '中性';
      $('#stEmoBox').innerHTML = pts.length
        ? `${svgSpark(pts)}<div class="hint" style="margin-top:6px">「${esc(f.name)}」共 ${pts.length} 段 · 峰值第 ${peak ? peak.i : 0} 段（${esc(tone)} ${peak ? peak.intensity : 0}）</div>`
        : '<div class="st-empty">这一章还没有正文</div>';
    } catch (err) { toast('分析失败：' + err.message); }
    loading(btn, false);
  };

  $('#stDepRun').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const names = Object.values(charGroups()).flat().map((c) => (typeof c === 'string' ? c : c.name)).filter(Boolean);
      const chapters = A().chapterFiles().map((f) => ({ id: f.id, title: f.name, content: f.content || '' }));
      const r = await api('/analysis/dependency', { method: 'POST', body: { chapters, characters: names } });
      const links = r.links || [];
      $('#stDepBox').innerHTML = links.length
        ? `<table class="st-table"><thead><tr><th>章节</th><th>关联</th><th>强度</th><th>共享人物</th></tr></thead><tbody>
            ${links.slice(0, 20).map((l) => `<tr><td>${esc(l.fromTitle)}</td><td>${esc(l.toTitle)}</td><td>${l.weight}</td><td>${esc((l.shared || []).join('、'))}</td></tr>`).join('')}
          </tbody></table>`
        : '<div class="st-empty">没有明显关联</div>';
    } catch (err) { toast('分析失败：' + err.message); }
    loading(btn, false);
  };
}

/* ---------------- 正文（批量） ---------------- */
async function renderWriting(body) {
  const book = A().S.book;
  const files = A().chapterFiles();
  body.innerHTML = `
    <div class="st-card" style="margin-bottom:12px">
      <h4>批量生成章节</h4>
      <div class="st-row" style="margin-bottom:10px">
        <span class="hint">起始章</span><input id="stWStart" type="number" value="${files.length + 1}" style="width:80px;height:32px;border-radius:9px;border:1px solid var(--line);background:var(--paper);padding:0 8px">
        <span class="hint">生成几章</span><input id="stWCount" type="number" min="1" max="20" value="3" style="width:70px;height:32px;border-radius:9px;border:1px solid var(--line);background:var(--paper);padding:0 8px">
        <button class="mini-btn primary" id="stWBatch">开始</button>
        <button class="mini-btn" id="stWStop" hidden>停止</button>
      </div>
      <div class="hint">会按「全书大纲 + 逐章细纲 + 文风」逐章写，同名章节自动跳过。生成期间可切回写作台继续写。</div>
      <div id="stWProg" hidden style="margin-top:12px">
        <div class="st-bar"><i id="stWBar" style="width:0%"></i></div>
        <div class="hint" id="stWLog" style="margin-top:8px;white-space:pre-wrap"></div>
      </div>
    </div>
    <div class="st-card">
      <h4>章节列表 <span class="st-badge">${files.length} 章</span></h4>
      <div class="st-list">
        ${files.length ? files.map((f) => `<div class="st-item">
          <div class="t">${esc(f.name)} <span class="st-badge">${fmt(A().wordCount(f.content))} 字</span></div>
          <div class="st-row" style="margin-top:6px"><button class="mini-btn" data-open="${f.id}">打开写作</button></div>
        </div>`).join('') : '<div class="st-empty">还没有章节</div>'}
      </div>
    </div>`;

  $$('[data-open]', body).forEach((b) => {
    b.onclick = async () => {
      const id = b.dataset.open;
      closeStudio();
      if (A().openChapter) await A().openChapter(id);
    };
  });

  $('#stWBatch').onclick = async (e) => {
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const r = await api('/ai/batch', {
        method: 'POST',
        body: { project_name: book.name, start: Number($('#stWStart').value) || 1, count: Number($('#stWCount').value) || 3 },
      });
      const job = r.job;
      $('#stWProg').hidden = false;
      $('#stWStop').hidden = false;
      const tick = async () => {
        try {
          const st = await api('/ai/batch/' + job.id);
          const pct = st.total ? Math.round((st.done / st.total) * 100) : 0;
          $('#stWBar').style.width = pct + '%';
          $('#stWLog').textContent = `${st.done}/${st.total}　${st.error ? '错误：' + st.error : ''}\n` + (st.log || []).join('\n');
          if (st.status !== 'running') {
            clearInterval(S.polling); S.polling = null;
            $('#stWStop').hidden = true;
            loading(btn, false);
            if (st.status === 'done') toast('批量生成完成');
            A().loadBooks().then(() => {});
            render();
          }
        } catch (err) {
          clearInterval(S.polling); S.polling = null;
          loading(btn, false);
          toast('查询进度失败：' + err.message);
        }
      };
      S.polling = setInterval(tick, 1500);
      tick();
    } catch (err) {
      toast('启动失败：' + err.message);
      loading(btn, false);
    }
  };
  $('#stWStop').onclick = () => {
    if (S.polling) { clearInterval(S.polling); S.polling = null; }
    toast('已停止轮询（后台仍会跑完当前章）');
  };
}

/* ---------------- 剧本 ---------------- */
async function renderScript(body) {
  const book = A().S.book;
  const chapters = A().chapterFiles();
  const scenes = (book.script || {}).scenes || [];
  body.innerHTML = `
    <div class="st-grid c2">
      <div class="st-card">
        <h4>选择章节 <button class="mini-btn" id="stScGen">转分场剧本</button></h4>
        <div class="hint">最多选 5 章，模型会把情节拆成可拍摄的场景。</div>
        <div class="st-list" id="stScChapters" style="max-height:360px;overflow:auto;margin-top:10px">
          ${chapters.length ? chapters.map((f) => `<label class="st-item" style="display:block">
            <span class="t" style="font-weight:400"><input type="checkbox" value="${f.id}"> ${esc(f.name)} <span class="st-badge">${fmt(A().wordCount(f.content))} 字</span></span>
          </label>`).join('') : '<div class="st-empty">还没有章节</div>'}
        </div>
      </div>
      <div class="st-card">
        <h4>分场结果 <span class="st-row">
          ${scenes.length ? '<button class="mini-btn" id="stScExport">导出 .txt</button><button class="mini-btn" id="stScExportMd">导出 .md</button>' : ''}
        </span></h4>
        <div id="stScBox" style="max-height:420px;overflow:auto">
          ${scenes.length ? `<table class="st-table"><thead><tr><th>场</th><th>地点/时间</th><th>人物</th><th>动作</th><th>对白</th></tr></thead><tbody>
            ${scenes.map((s) => `<tr><td>${esc(s.scene || '')}</td><td>${esc([s.location, s.time].filter(Boolean).join(' / '))}</td><td>${esc((s.characters || []).join('、'))}</td><td>${esc(s.action || '')}</td><td style="white-space:pre-wrap">${esc(s.dialogue || '')}</td></tr>`).join('')}
          </tbody></table>` : '<div class="st-empty">还没有剧本</div>'}
        </div>
      </div>
    </div>`;

  $('#stScGen').onclick = async (e) => {
    const picked = $$('#stScChapters input:checked', body).map((i) => i.value);
    if (!picked.length) { toast('先选章节'); return; }
    const btn = e.currentTarget;
    loading(btn, true);
    try {
      const payload = picked.map((id) => {
        const f = A().fileById(id);
        return { title: f.name, content: f.content || '' };
      });
      const r = await api('/ai/script', { method: 'POST', body: { project_name: book.name, chapters: payload } });
      const list = (r.scenes || []).map((s) => ({
        scene: s.scene, location: s.location, time: s.time,
        characters: Array.isArray(s.characters) ? s.characters : [],
        action: s.action, dialogue: s.dialogue,
      }));
      if (!list.length) { toast('没有解析到分场，换个模型再试'); loading(btn, false); return; }
      await A().saveProjectFields({ script: { scenes: list } });
      toast(`已生成 ${list.length} 场`);
      render();
    } catch (err) { toast('生成失败：' + err.message); loading(btn, false); }
  };

  const exp = $('#stScExport');
  if (exp) exp.onclick = () => {
    const list = (A().S.book.script || {}).scenes || [];
    const txt = list.map((s) => `场景 ${s.scene || ''}　${s.location || ''}　${s.time || ''}\n出场：${(s.characters || []).join('、')}\n\n${s.action || ''}\n\n${s.dialogue || ''}\n`).join('\n------------------------\n\n');
    A().downloadText(`${book.name}_剧本.txt`, txt);
    toast('剧本已导出');
  };
  const expMd = $('#stScExportMd');
  if (expMd) expMd.onclick = () => {
    const list = (A().S.book.script || {}).scenes || [];
    const md = `# ${book.name} · 分场剧本\n\n` + list.map((s) => `## 场景 ${s.scene || ''}　${s.location || ''}　${s.time || ''}\n\n**出场**：${(s.characters || []).join('、')}\n\n${s.action || ''}\n\n\`\`\`\n${s.dialogue || ''}\n\`\`\`\n`).join('\n');
    A().downloadText(`${book.name}_剧本.md`, md);
    toast('剧本已导出（Markdown）');
  };
}

/* ---------------- 工具箱 ---------------- */
async function renderToolbox(body) {
  const book = A().S.book;
  const tb = await api('/toolbox');
  S.cache.toolbox = tb;
  const styleRef = book.style_ref || '';

  body.innerHTML = `
    <div class="st-grid c2">
      <div class="st-card">
        <h4>提示词模板 <span class="st-row"><button class="mini-btn" id="stTNew">＋ 新建</button></span></h4>
        <div class="hint">模板会作为「补充要求」注入到本章生成与批量生成。</div>
        <div class="st-list" style="margin-top:10px">
          ${tb.templates.length ? tb.templates.map((t) => `<div class="st-item">
            <div class="t">${esc(t.name)} <span class="st-badge">${fmt((t.body || '').length)} 字</span></div>
            <div class="d">${esc((t.body || '').slice(0, 90))}</div>
            <div class="st-row" style="margin-top:6px">
              <button class="mini-btn" data-tuse="${t.id}">设为项目模板</button>
              <button class="mini-btn seal" data-tdel="${t.id}">删除</button>
            </div>
          </div>`).join('') : '<div class="st-empty">还没有模板</div>'}
        </div>
      </div>

      <div class="st-card">
        <h4>文风参考 <span class="st-row"><button class="mini-btn" id="stSNew">＋ 自定义</button></span></h4>
        <div class="hint">当前文风：${styleRef ? esc(styleRef) : '未选择'}。选中后生成正文会带上这套句式特征。</div>
        <div class="st-list" style="margin-top:10px;max-height:320px;overflow:auto">
          ${tb.styles.length ? tb.styles.map((s) => `<div class="st-item">
            <div class="t">${esc(s.title)} ${s.builtin ? '<span class="st-badge">内置</span>' : ''}${s.title === styleRef ? '<span class="st-badge">使用中</span>' : ''}</div>
            <div class="d">${esc((s.excerpt || '').slice(0, 70))}</div>
            <div class="st-row" style="margin-top:6px">
              <button class="mini-btn" data-suse="${esc(s.title)}">设为文风</button>
              ${s.builtin ? '' : `<button class="mini-btn seal" data-sdel="${s.id}">删除</button>`}
            </div>
          </div>`).join('') : '<div class="st-empty">没有文风参考</div>'}
        </div>
      </div>
    </div>

    <div class="st-card" style="margin-top:12px">
      <h4>使用说明</h4>
      <div class="hint" style="line-height:1.9">
        · 流程：概念 → 世界观 → 人物 → 宏观大纲 → 逐章细纲 → 正文（单章或批量）→ 剧本<br>
        · 生成正文会带上：概念内核 + 世界观 + 人物 + 全书大纲 + 本章细纲 + 文风锚点 + 项目提示词模板<br>
        · 写作台快捷键：Ctrl/⌘+S 保存，Ctrl/⌘+F 查找，Ctrl/⌘+/ 快捷键，Ctrl/⌘+Enter 新建章节，Esc 退出专注<br>
        · 数据：项目存于 projects/*.json，删除会在 projects/_trash 留底，写盘前每 5 分钟滚动备份到 projects/_backups
      </div>
    </div>

    <div class="st-card" style="margin-top:12px">
      <h4>生成历史 <span class="st-row">
        <button class="mini-btn" id="stHRefresh">刷新</button>
        <button class="mini-btn seal" id="stHClear">清空</button>
      </span></h4>
      <div class="st-list" style="margin-top:10px;max-height:420px;overflow:auto">
        ${tb.history.length ? tb.history.map((h) => `<div class="st-item">
          <div class="t">${esc(h.kind)} <span class="st-badge">${esc(h.project || '—')}</span><span class="st-badge">${fmt(h.chars)} 字</span></div>
          <div class="d">${esc(h.ts)} · ${esc((h.preview || '').slice(0, 100))}</div>
        </div>`).join('') : '<div class="st-empty">还没有记录</div>'}
      </div>
    </div>`;

  $('#stTNew').onclick = async () => {
    const name = await A().askText('新建模板', '模板名称', '');
    if (!name) return;
    const body0 = await A().askText('模板内容', '写清要求，例如：每段不超过三句，章末必须留悬念', '', 'multiline');
    if (body0 === null) return;
    await api('/toolbox/templates', { method: 'POST', body: { name, body: body0 } });
    toast('模板已保存');
    render();
  };
  $$('[data-tuse]', body).forEach((b) => {
    b.onclick = async () => {
      const t = (S.cache.toolbox.templates || []).find((x) => x.id === b.dataset.tuse);
      if (!t) return;
      await A().saveProjectFields({ prompt_template: t.body || '', prompt_template_name: t.name });
      toast('已设为项目模板：' + t.name);
    };
  });
  $$('[data-tdel]', body).forEach((b) => {
    b.onclick = async () => {
      const ok = await A().askConfirm('删除模板', '删除后不可恢复', '删除');
      if (!ok) return;
      await api('/toolbox/templates/' + b.dataset.tdel, { method: 'DELETE' });
      render();
    };
  });
  $('#stSNew').onclick = async () => {
    const title = await A().askText('自定义文风', '文风名称，如：冷峻短句', '');
    if (!title) return;
    const excerpt = await A().askText('文风样例', '贴一段代表性原文（200 字内最佳）', '', 'multiline');
    if (excerpt === null) return;
    await api('/toolbox/styles', { method: 'POST', body: { title, excerpt } });
    toast('已保存');
    render();
  };
  $$('[data-suse]', body).forEach((b) => {
    b.onclick = async () => {
      await A().saveProjectFields({ style_ref: b.dataset.suse });
      toast('文风已设为：' + b.dataset.suse);
      render();
    };
  });
  $$('[data-sdel]', body).forEach((b) => {
    b.onclick = async () => {
      await api('/toolbox/styles/' + b.dataset.sdel, { method: 'DELETE' });
      render();
    };
  });
  $('#stHRefresh').onclick = () => render();
  $('#stHClear').onclick = async () => {
    const ok = await A().askConfirm('清空历史', '会删除全部生成记录（不影响正文）', '清空');
    if (!ok) return;
    await api('/toolbox/history', { method: 'DELETE' });
    render();
  };
}

/* ---------------- 公共上下文 ---------------- */
function bookCtx() {
  const b = A().S.book || {};
  return {
    project_name: b.name || '',
    genre: b.genre || '东方玄幻',
    style: b.style || '热血励志',
    subgenre: b.subgenre || '',
    ref_author: b.ref_author || '',
    strategy: b.strategy || '',
    lang: b.lang || '',
    audience: b.audience || '',
    ending: b.ending || '',
    chapter_count: b.chapter_count || 400,
    words_per_chapter: b.words_per_chapter || 2500,
    concept: b.concept || {},
    world: b.world || {},
    characters: b.characters || {},
    outline: b.outline || {},
    style_ref: b.style_ref || '',
    extra: b.prompt_template || '',
  };
}

/* 从写作台/书架跳到某个人物的档案 */
function openCharacter(name) {
  const st = charState();
  const book = A().S.book;
  if (st.book !== (book && book.name)) {
    Object.assign(st, { book: book && book.name, view: 'detail', sel: null, draft: null, editRef: null, dirty: false, query: '', filter: '全部', ai: [] });
  }
  const found = allChars().find((c) => c.name === name);
  if (found) selectCharObj(found);
  else st.view = 'detail';
  openStudio('characters');
}

/* ---------------- 事件 ---------------- */
document.addEventListener('DOMContentLoaded', () => {
  $$('.studio-nav button').forEach((b) => b.addEventListener('click', () => setModule(b.dataset.mod)));
  $('#studioClose').addEventListener('click', closeStudio);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !$('#studio').hidden) { closeStudio(); }
  });
  window.Studio = { open: openStudio, close: closeStudio, setModule, openCharacter };
});
})();
