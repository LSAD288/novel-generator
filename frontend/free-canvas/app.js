(() => {
  "use strict";


  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const esc = (value = "") => String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
  const params = new URLSearchParams(location.search);

  const els = {
    app: $("#app"),
    canvasView: $("#canvasView"),
    writingView: $("#writingView"),
    canvasWorkspace: $("#canvasView"),
    viewport: $("#canvasViewport"),
    world: $("#canvasWorld"),
    cardLayer: $("#cardLayer"),
    edgeGroup: $("#edgeGroup"),
    strokeGroup: $("#strokeGroup"),
    draftPath: $("#draftPath"),
    inspector: $("#inspector"),
    inspectorContent: $("#inspectorContent"),
    objectStatus: $("#objectStatus"),
    zoomLabel: $("#zoomLabel"),
    bodyEditor: $("#bodyEditor"),
    writingCount: $("#writingCount"),
    themeToggle: $("#themeToggle"),
    toast: $("#toast"),
  };

  const Ink = window.WriterCanvasInk;
  const defaults={brush:"pencil",width:3,color:"auto",pressureEnabled:true,pressureStrength:.75,eraserMode:"point",eraserSize:24};
  const palette={auto:"随主题",red:"朱红",amber:"琥珀",green:"青绿",blue:"湖蓝",violet:"紫罗兰"};
  const paint=value=>{const color=Ink.color(value);return color==="auto"?"var(--ink)":color.startsWith("#")?color:`var(--canvas-ink-${color})`;};
  const state = {
    view: params.get("view") === "writing" ? "writing" : "canvas",
    theme: document.body.dataset.theme === "dark" || params.get("theme") === "dark" ? "dark" : "light",
    tool: "select",
    ink: {...defaults},
    cardShape: "rectangle",
    menu: null,
    connectSource: null,
    deferInspector: false,
    selected: null,
    selection: [],
    texts: [],
    cards: [],
    edges: [],
    strokes: [],
    viewTransform: { x: 0, y: 0, scale: 1 },
    interaction: null,
    spacePan: false,
    history: { undo: [], redo: [] },
    editBefore: null,
    body: els.bodyEditor.value,
    writingPoint: null,
    focusWriting: false,
    needsFit: true,
  };

  let primarySelection=null;
  Object.defineProperty(state,'selected',{get:()=>primarySelection,set(value){primarySelection=value;state.selection=value?[value]:[];}});
  const objectFor=item=>item?.kind==='card'?cardById(item.id):item?.kind==='edge'?edgeById(item.id):item?.kind==='text'?state.texts.find(t=>t.id===item.id):strokeById(item?.id);
  const chosen=()=>state.selection.filter(item=>objectFor(item));
  const isSelected=(kind,id)=>state.selection.some(item=>item.kind===kind&&item.id===id);
  const selectedText=()=>state.selected?.kind==='text'?objectFor(state.selected):null;
  function setSelection(items){const unique=[...new Map(items.filter(objectFor).map(item=>[item.kind+':'+item.id,item])).values()];if(JSON.stringify(unique)===JSON.stringify(chosen()))return;finishEdit();state.selected=unique.length===1?unique[0]:null;state.selection=unique;updateSelectionVisual();renderInspector();renderStrokes();}
  function objectBounds(item){const value=objectFor(item);if(!value||item.kind==='edge')return null;if(item.kind==='stroke')return strokeBounds(value);return {minX:value.x,minY:value.y,maxX:value.x+value.w,maxY:value.y+value.h};}
  function selectionBounds(items=chosen()){const boxes=items.map(objectBounds).filter(Boolean);if(!boxes.length)return null;return {minX:Math.min(...boxes.map(b=>b.minX)),minY:Math.min(...boxes.map(b=>b.minY)),maxX:Math.max(...boxes.map(b=>b.maxX)),maxY:Math.max(...boxes.map(b=>b.maxY))};}
  function renderSelection(){const layer=$('#selectionLayer'),box=state.tool==='select'?selectionBounds():null;if(!box){layer.replaceChildren();return;}layer.innerHTML=`<div class="selection-frame" style="left:${box.minX}px;top:${box.minY}px;width:${Math.max(1,box.maxX-box.minX)}px;height:${Math.max(1,box.maxY-box.minY)}px" aria-label="已选择${chosen().length}个对象">${['nw','ne','sw','se'].map(h=>`<span class="selection-grip ${h}" data-selection-grip="${h}" role="button" tabindex="0" aria-label="${({nw:'左上',ne:'右上',sw:'左下',se:'右下'})[h]}缩放手柄"></span>`).join('')}</div>`;}
  function startGroup(event,mode,handle=null){const bounds=selectionBounds();if(!bounds)return;startInteraction(event,mode,{items:chosen().map(item=>({...item})),original:JSON.parse(serialize()),bounds,handle});}
  function transformGroup(interaction,dx,dy,point){const b=interaction.bounds;if(!b)return;const resize=interaction.mode==='group-resize',anchor={x:interaction.handle?.includes('w')?b.maxX:b.minX,y:interaction.handle?.includes('n')?b.maxY:b.minY};let factor=1;if(resize){const corner={x:interaction.handle.includes('w')?b.minX:b.maxX,y:interaction.handle.includes('n')?b.minY:b.maxY},vx=corner.x-anchor.x,vy=corner.y-anchor.y;factor=clamp(((point.x-anchor.x)*vx+(point.y-anchor.y)*vy)/Math.max(1,vx*vx+vy*vy),.05,20);}const position=p=>resize?{x:anchor.x+(p.x-anchor.x)*factor,y:anchor.y+(p.y-anchor.y)*factor}:{x:p.x+dx,y:p.y+dy};
    for(const item of interaction.items){const value=objectFor(item),list=item.kind==='card'?'cards':item.kind==='text'?'texts':item.kind==='stroke'?'strokes':null,old=list&&interaction.original[list].find(v=>v.id===item.id);if(!old||!value)continue;if(item.kind==='stroke'){value.points=old.points.map(position);value.width=resize?clamp(old.width*factor,.25,256):old.width;}else{Object.assign(value,position(old));if(resize){value.w=Math.max(item.kind==='text'?24:48,old.w*factor);value.h=Math.max(item.kind==='text'?24:32,old.h*factor);if(item.kind==='text')value.fontSize=clamp(old.fontSize*factor,8,512);}if(item.kind==='card')updateCardDom(value);}}
    renderTexts();renderEdges();renderStrokes();renderSelection();
  }
  function updateTextDom(text){const node=$(`[data-text-id="${CSS.escape(text.id)}"]`);if(!node)return;node.setAttribute('aria-label','文字：'+(text.text||'空白文字').slice(0,80));Object.assign(node.style,{left:text.x+'px',top:text.y+'px',width:text.w+'px',minHeight:text.h+'px',fontSize:text.fontSize+'px',color:paint(text.color)});const body=node.querySelector('.text-body');if(body!==document.activeElement)body.textContent=text.text||'双击输入文字';}
  function renderTexts(){const layer=$('#textLayer');if(layer.contains(document.activeElement)&&document.activeElement.isContentEditable)return;layer.innerHTML=state.texts.map(text=>`<div class="canvas-text" data-text-id="${text.id}" role="button" tabindex="0" aria-label="文字：${esc(text.text||'空白文字')}"><div class="text-body" contenteditable="false"></div></div>`).join('');state.texts.forEach(updateTextDom);$$('.canvas-text').forEach(n=>n.classList.toggle('selected',isSelected('text',n.dataset.textId)));}
  function editText(id){const text=state.texts.find(t=>t.id===id);if(!text)return;select('text',id);const body=$(`[data-text-id="${CSS.escape(id)}"] .text-body`);body.textContent=text.text;body.contentEditable='plaintext-only';state.editBefore=serialize();body.focus();const range=document.createRange();range.selectNodeContents(body);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);}
  function addText(){finishEdit();const point=vacantPoint(240,48),text={id:'text-'+crypto.randomUUID(),...point,w:240,h:48,text:'',fontSize:24,color:'auto'},before=serialize();state.texts.push(text);state.tool='select';state.selected={kind:'text',id:text.id};commitHistory(before);renderAll();ensureCardVisible(text);editText(text.id);}
  let nextCardId = 1;
  let nextEdgeId = 1;
  let nextStrokeId = 1;
  let toastTimer;

  const cardById = (id) => state.cards.find((card) => card.id === id);
  const edgeById = (id) => state.edges.find((edge) => edge.id === id);
  const strokeById = (id) => state.strokes.find((stroke) => stroke.id === id);
  const selectedCard = () => state.selected?.kind === "card" ? cardById(state.selected.id) : null;
  const selectedEdge = () => state.selected?.kind === "edge" ? edgeById(state.selected.id) : null;
  const selectedStroke = () => state.selected?.kind === "stroke" ? strokeById(state.selected.id) : null;
  let legacyData=null,legacyUI={};
  let bridgeLoading=true, composing=false,lastActivityAt=performance.now();
  const emit=(type,detail)=>{if(!bridgeLoading)window.frameElement?.dispatchEvent(new CustomEvent(type,{detail}));};
  function markActivity(){lastActivityAt=performance.now();emit('writer:prototype-activity',null);}
  for(const name of ['pointerdown','pointermove','pointerup','pointercancel','click','dblclick','focusin','keydown','input','wheel','compositionstart','compositionend'])document.addEventListener(name,markActivity,{capture:true,passive:true});
  const emitData=()=>{if(!composing)emit("writer:prototype-data",JSON.parse(serialize()));};
  const viewState=()=>({viewTransform:{...state.viewTransform},selected:state.selected,ink:{...state.ink},cardShape:state.cardShape,tool:state.tool,selection:chosen()});
  const emitUI=()=>emit("writer:prototype-ui",viewState());
  const serialize = () => JSON.stringify({ cards: state.cards, edges: state.edges, strokes: state.strokes, texts:state.texts });

  function syncUrl() {
    if(window.frameElement)return;
    const url = new URL(location.href);
    url.searchParams.set("view", state.view);
    if (state.theme === "dark") url.searchParams.set("theme", "dark");
    else url.searchParams.delete("theme");
    history.replaceState(null, "", url);
  }

  function showToast(message) {
    clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.classList.add("visible");
    toastTimer = setTimeout(() => els.toast.classList.remove("visible"), 2200);
  }

  function applyTheme() {
    document.body.dataset.theme = state.theme;
    document.documentElement.style.colorScheme = state.theme;
    els.themeToggle.innerHTML = `${icon(state.theme === "light" ? "moon" : "sun")}<span>${state.theme === "light" ? "夜间" : "日间"}</span>`;
    els.themeToggle.setAttribute("aria-label", `切换为${state.theme === "light" ? "深色" : "浅色"}外观`);
  }

  function writingLength() {
    return Array.from(state.body.replace(/\s/g, "")).length;
  }

  function updateWritingCount() {
    els.writingCount.textContent = `本章 ${writingLength()} 字`;
  }

  function captureWriting() {
    state.body = els.bodyEditor.value;
    state.writingPoint = { start: els.bodyEditor.selectionStart, end: els.bodyEditor.selectionEnd, scroll: els.bodyEditor.scrollTop };
  }

  function restoreWritingFocus() {
    if (state.view !== "writing") return;
    requestAnimationFrame(() => {
      const point = state.writingPoint;
      if (point) {
        els.bodyEditor.setSelectionRange(point.start, point.end);
        els.bodyEditor.scrollTop = point.scroll;
      }
      if (state.focusWriting) els.bodyEditor.focus({ preventScroll: true });
      state.focusWriting = false;
    });
  }

  function setView(view, focusWriting = false) {
    if (state.view === "writing" && view !== "writing") captureWriting();
    if (state.view === "canvas" && view !== "canvas") finishEdit();
    state.view = view;
    state.focusWriting = focusWriting;
    els.writingView.hidden = view !== "writing";
    els.canvasView.hidden = view !== "canvas";
    $$(".work-tab").forEach((button) => button.setAttribute("aria-current", button.dataset.view === view ? "page" : "false"));
    syncUrl();
    if (view === "canvas" && state.needsFit) {
      requestAnimationFrame(() => {if(state.needsFit){state.needsFit=false;fitContent(true);}});
    }
    restoreWritingFocus();
  }

  function commitHistory(before) {
    if (!before || before === serialize()) return;
    state.history.undo.push(before);
    if (state.history.undo.length > 40) state.history.undo.shift();
    state.history.redo = [];
    updateHistoryButtons();
    emitData();
  }

  function finishEdit() {
    if (state.editBefore === null) return;
    const before = state.editBefore;
    state.editBefore = null;
    commitHistory(before);
  }

  function restoreSnapshot(snapshot) {
    composing=false;
    const data = JSON.parse(snapshot);
    state.cards = data.cards;
    state.edges = data.edges;
    state.strokes = data.strokes;
    state.texts=data.texts||[];
    const surviving=chosen();state.selected=surviving.length===1?surviving[0]:null;state.selection=surviving;
    if (state.selected) {
      const exists = objectFor(state.selected);
      if (!exists) state.selected = null;
    }
    state.connectSource = null;
    renderAll();
    emitData();emit("writer:prototype-sidebar",null);
  }

  function undo() {
    finishEdit();
    if (!state.history.undo.length) return;
    const current = serialize();
    const previous = state.history.undo.pop();
    state.history.redo.push(current);
    restoreSnapshot(previous);
    updateHistoryButtons();
  }

  function redo() {
    finishEdit();
    if (!state.history.redo.length) return;
    const current = serialize();
    const next = state.history.redo.pop();
    state.history.undo.push(current);
    restoreSnapshot(next);
    updateHistoryButtons();
  }

  function updateHistoryButtons() {
    const undoButton = $('[data-action="undo"]');
    const redoButton = $('[data-action="redo"]');
    undoButton.disabled = !state.history.undo.length;
    redoButton.disabled = !state.history.redo.length;
  }

  function updateStatus() {
    els.objectStatus.textContent = `${state.cards.length} 张卡片 · ${state.edges.length} 条连线 · ${state.strokes.length} 笔笔迹 · ${state.texts.length} 段文字`;
    els.zoomLabel.textContent = `${Math.round(state.viewTransform.scale * 100)}%`;
    updateHistoryButtons();
  }

  function updateTransform() {
    const { x, y, scale } = state.viewTransform;
    els.world.style.transform = `translate(${x}px, ${y}px) scale(${scale})`;
    els.world.style.setProperty("--inverse-zoom",1/scale);
    els.viewport.style.backgroundSize = `${24 * scale}px ${24 * scale}px`;
    els.viewport.style.backgroundPosition = `${x}px ${y}px`;
    els.viewport.dataset.scale = scale;
    els.viewport.dataset.detail = scale < .45 ? "minimal" : scale < .7 ? "summary" : "full";
    els.viewport.dataset.panX = x;
    els.viewport.dataset.panY = y;
    emitUI();
    els.zoomLabel.textContent = `${Math.round(scale * 100)}%`;
  }

  function updateToolbar() {
    $$('[data-tool]').forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.tool === state.tool || button.dataset.tool === "draw" && state.tool === "erase")));
    els.viewport.classList.toggle("tool-draw", state.tool === "draw");
    els.viewport.classList.toggle("tool-connect", state.tool === "connect");
    els.viewport.classList.toggle("tool-erase",state.tool==="erase");
    els.viewport.classList.toggle("tool-pan",state.tool==="pan");
    if(state.tool!=="erase")$("#eraserCursor").hidden=true;
    const drawButton=$('[data-menu="draw"]'),erasing=state.tool==='erase';drawButton.querySelector('span').textContent=erasing?'橡皮':'手绘';drawButton.querySelector('use').setAttribute('href',erasing?'#i-eraser':'#i-draw');drawButton.querySelector('kbd').textContent=erasing?'E':'D';drawButton.title=erasing?'橡皮设置（E），Esc返回选择':'手绘设置（D），Esc返回选择';
    const hint=$('.canvas-hints');if(hint)hint.textContent=erasing?({point:'局部橡皮',stroke:'整笔橡皮',area:'框选橡皮'})[state.ink.eraserMode]+' · 只擦笔迹 · 可撤销 · Esc 返回选择':state.tool==='draw'?({pencil:'铅笔',crayon:'蜡笔',brush:'毛笔'})[state.ink.brush]+' · 两指平移缩放 · Esc 返回选择':state.tool==='connect'?'点起点再点终点，或拖动端口 · Esc 返回选择':'拖动空白框选 · Shift 多选 · 空格/手形平移 · 双击新建';
    emitUI();
    updateHistoryButtons();
  }

  function updateSelectionVisual() {
    const active=selectedCard(),related=new Set(active?[active.id,...state.edges.filter(e=>e.from===active.id||e.to===active.id).flatMap(e=>[e.from,e.to])]:[]);
    $$(".canvas-card").forEach(n=>n.classList.toggle("unrelated",!!active&&!related.has(n.dataset.cardId)));
    $$(".edge-group").forEach(n=>{const e=edgeById(n.dataset.edgeId);n.classList.toggle("unrelated",!!active&&e.from!==active.id&&e.to!==active.id);n.classList.toggle("related",!!active&&(e.from===active.id||e.to===active.id));});
    emitUI();
    $$(".canvas-card").forEach((element) => {
      element.classList.toggle("selected", isSelected("card",element.dataset.cardId));
      element.classList.toggle("connect-source", element.dataset.cardId === state.connectSource);
    });
    $$(".edge-group").forEach((element) => element.classList.toggle("selected", isSelected("edge",element.dataset.edgeId)));
    $$(".stroke-group").forEach((element) => element.classList.toggle("selected", isSelected("stroke",element.dataset.strokeId)));
    $$(".canvas-text").forEach(n=>n.classList.toggle("selected",isSelected("text",n.dataset.textId)));renderSelection();
  }

  function renderCards() {
    els.cardLayer.innerHTML = state.cards.map((card) => `<article class="canvas-card" data-card-id="${card.id}" data-shape="${card.shape==='circle'?'circle':'rectangle'}" data-custom-color="${Ink.color(card.color)!=='auto'}" data-x="${card.x}" data-y="${card.y}" data-w="${card.w}" data-h="${card.h}" style="left:${card.x}px;top:${card.y}px;width:${card.w}px;height:${card.h}px;--card-accent:${paint(card.color)};--circle-pad:${card.w*.18}px" tabindex="0" role="button" aria-label="卡片：${esc(card.title)}"><span class="card-kind">${esc(card.kind)}</span><h2 class="card-title">${esc(card.title)}</h2><span class="card-text ${card.content ? "" : "empty"}">${esc(card.content || "在右侧写下内容…")}</span><button type="button" class="card-sidebar-add" data-action="toggle-sidebar" data-id="${card.id}" aria-label="${card.sidebarPinned?'从写作侧栏移除':'加入写作侧栏'}：${esc(card.title)}" aria-pressed="${!!card.sidebarPinned}" ${card.readOnly?'disabled':''}>${card.sidebarPinned?'✓':'+'}</button>${card.sidebarPinned?'<span class="card-pin" aria-label="已加入写作速查">◆</span>':''}<span class="connect-port" data-connect-port aria-hidden="true"></span></article>`).join("");
  }

  function updateCardDom(card) {
    const element = els.cardLayer.querySelector(`[data-card-id="${CSS.escape(card.id)}"]`);
    if (!element) return;
    element.dataset.shape=card.shape==='circle'?'circle':'rectangle';
    element.dataset.customColor=String(Ink.color(card.color)!=='auto');
    element.style.setProperty('--card-accent',paint(card.color));
    element.style.setProperty('--circle-pad',card.w*.18+'px');
    const add=element.querySelector('.card-sidebar-add');if(add){add.textContent=card.sidebarPinned?'✓':'+';add.setAttribute('aria-pressed',String(!!card.sidebarPinned));add.setAttribute('aria-label',(card.sidebarPinned?'从写作侧栏移除':'加入写作侧栏')+'：'+card.title);}
    const pinned=element.querySelector('.card-pin');if(card.sidebarPinned&&!pinned){const n=document.createElement('span');n.className='card-pin';n.textContent='◆';n.setAttribute('aria-label','已加入写作速查');element.append(n);}else if(!card.sidebarPinned)pinned?.remove();
    element.style.left = `${card.x}px`;
    element.style.top = `${card.y}px`;
    element.style.width = `${card.w}px`;
    element.style.height = `${card.h}px`;
    Object.assign(element.dataset, { x: card.x, y: card.y, w: card.w, h: card.h });
    element.setAttribute("aria-label", `卡片：${card.title}`);
    element.querySelector(".card-kind").textContent = card.kind;
    element.querySelector(".card-title").textContent = card.title;
    const text = element.querySelector(".card-text");
    text.textContent = card.content || "在右侧写下内容…";
    text.classList.toggle("empty", !card.content);
  }

  function cardCenter(card) {
    return { x: card.x + card.w / 2, y: card.y + card.h / 2 };
  }

  function cardBoundary(card, toward) {
    const center = cardCenter(card);
    const dx = toward.x - center.x;
    const dy = toward.y - center.y;
    if (!dx && !dy) return center;
    if(card.shape==='circle'){const factor=1/Math.hypot(dx/(card.w/2),dy/(card.h/2));return {x:center.x+dx*factor,y:center.y+dy*factor};}
    const tx = dx ? card.w / 2 / Math.abs(dx) : Infinity;
    const ty = dy ? card.h / 2 / Math.abs(dy) : Infinity;
    const amount = Math.min(tx, ty);
    return { x: center.x + dx * amount, y: center.y + dy * amount };
  }

  function edgeGeometry(edge) {
    const from = cardById(edge.from);
    const to = cardById(edge.to);
    if (!from || !to) return null;
    const fromCenter = cardCenter(from);
    const toCenter = cardCenter(to);
    const start = cardBoundary(from, toCenter);
    const end = cardBoundary(to, fromCenter);
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy) || 1;
    const bend = edge.bend || 0;
    const control = { x: (start.x + end.x) / 2 - dy / length * bend, y: (start.y + end.y) / 2 + dx / length * bend };
    const label = { x: (start.x + 2 * control.x + end.x) / 4, y: (start.y + 2 * control.y + end.y) / 4 };
    return { d: `M ${start.x} ${start.y} Q ${control.x} ${control.y} ${end.x} ${end.y}`, ...label };
  }

  function edgeLabel(edge) {
    return edge.label.trim() || (edge.kind === "hierarchy" ? "从属" : "关联");
  }

  function labelWidth(edge){return Math.max(32,[...edgeLabel(edge)].reduce((n,c)=>n+(/[\u0000-\u00ff]/.test(c)?7:12),0)+16);}
  const edgeSymbol=edge=>({forward:'→',back:'←',both:'↔',none:'—'})[edge.direction]||'—';
  function edgeDescription(edge){return `${cardById(edge.from)?.title||'已移除'} ${edgeSymbol(edge)} ${cardById(edge.to)?.title||'已移除'}`;}
  function renderEdges() {
    els.edgeGroup.innerHTML = state.edges.map((edge) => {
      const geometry = edgeGeometry(edge);
      if (!geometry) return "";
      const head=`head-${edge.id}`,color=paint(edge.color);
      const markerEnd = ["forward", "both"].includes(edge.direction) ? ` marker-end="url(#${head})"` : "";
      const markerStart = ["back", "both"].includes(edge.direction) ? ` marker-start="url(#${head})"` : "";
      const selected = isSelected("edge",edge.id);
      return `<g class="edge-group ${edge.kind === "relation" ? "relation" : "hierarchy"} ${selected ? "selected" : ""}" data-edge-id="${edge.id}" style="color:${color}"><defs><marker id="${head}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" style="fill:${color}"></path></marker></defs><path class="edge-hit" data-edge-hit="${edge.id}" d="${geometry.d}" tabindex="0" role="button" aria-label="连线：${esc(edgeLabel(edge))}"></path><path class="edge-visible" style="stroke:${color}" d="${geometry.d}"${markerStart}${markerEnd}></path><rect class="edge-label-bg" x="${geometry.x-labelWidth(edge)/2}" y="${geometry.y-14}" width="${labelWidth(edge)}" height="22" rx="5"></rect><text class="edge-label" style="fill:${color}" data-edge-hit="${edge.id}" x="${geometry.x}" y="${geometry.y}">${esc(edgeLabel(edge))}</text></g>`;
    }).join("");
  }

  function pointsPath(points) {
    if (!points.length) return "";
    if (points.length === 1) return `M ${points[0].x} ${points[0].y} L ${points[0].x + 0.01} ${points[0].y}`;
    let path = `M ${points[0].x} ${points[0].y}`;
    for (let index = 1; index < points.length - 1; index += 1) {
      const point = points[index];
      const next = points[index + 1];
      const middle = { x: (point.x + next.x) / 2, y: (point.y + next.y) / 2 };
      path += ` Q ${point.x} ${point.y} ${middle.x} ${middle.y}`;
    }
    const last = points[points.length - 1];
    return `${path} L ${last.x} ${last.y}`;
  }

  function strokeBounds(stroke) {
    const xs = stroke.points.map((point) => point.x);
    const ys = stroke.points.map((point) => point.y);
    const radius=(stroke.width||2.4)/2*(stroke.brush==='crayon'?1.25:1);return { minX: Math.min(...xs)-radius, minY: Math.min(...ys)-radius, maxX: Math.max(...xs)+radius, maxY: Math.max(...ys)+radius };
  }

  function renderStrokes() {
    els.strokeGroup.innerHTML = state.strokes.map((stroke) => {
      const path=pointsPath(stroke.points),outline=Ink.outline(stroke),color=paint(stroke.color);
      const selected=isSelected('stroke',stroke.id),bounds=selected?strokeBounds(stroke):null;
      return `<g class="stroke-group ${selected?'selected':''}" data-stroke-id="${stroke.id}"><path class="stroke-visible ink-outline" d="${outline}" style="fill:${color};stroke:none"></path><path class="stroke-hit" data-stroke-hit="${stroke.id}" d="${path}" tabindex="0" role="button" aria-label="手绘笔迹"></path>${bounds?`<rect class="stroke-selection" x="${bounds.minX-7}" y="${bounds.minY-7}" width="${bounds.maxX-bounds.minX+14}" height="${bounds.maxY-bounds.minY+14}"></rect>`:''}</g>`;
    }).join('');
  }
  function colorControls(target,value){return `<div class="canvas-color-choices" role="group" aria-label="${target==='ink'?'画笔':target==='card'?'卡片':target==='edge'?'连线':target==='text'?'文字':'笔迹'}颜色">${Object.entries(palette).map(([v,name])=>`<button type="button" data-color="${v}" data-color-target="${target}" aria-label="${name}色" aria-pressed="${Ink.color(value)===v}" style="--swatch:${paint(v)}"></button>`).join('')}<label class="custom-canvas-color">自选<input type="color" aria-label="自选${target==='ink'?'画笔':target==='card'?'卡片':target==='edge'?'连线':target==='text'?'文字':'笔迹'}颜色" ${target==='ink'?'data-ink-control="color"':'data-field="color"'} value="${/^#[0-9a-f]{6}$/i.test(value||'')?value:'#546778'}"></label></div>`;}
  function closeOptions(focus=false){WriterCanvasControls.close();const name=state.menu;state.menu=null;for(const n of [$('#cardOptions'),$('#drawOptions')])n.hidden=true;$$('[data-menu]').forEach(n=>{n.setAttribute('aria-expanded','false');if(n.dataset.menuTitle!==undefined){n.title=n.dataset.menuTitle;delete n.dataset.menuTitle;}});if(focus&&name)$(`[data-menu="${name}"]`)?.focus();}
  function syncOptions(){const ink=state.ink;$('#inkBrush').value=ink.brush;$('#inkWidth').value=ink.width;$('#inkWidthValue').textContent=ink.width;$('#inkPressure').checked=ink.pressureEnabled;$('#inkStrength').disabled=!ink.pressureEnabled;$('#inkStrength').value=ink.pressureStrength*100;$('#inkPressureValue').textContent=Math.round(ink.pressureStrength*100)+'%';$('#eraserMode').value=ink.eraserMode;$('#eraserSize').value=ink.eraserSize;$('#eraserSizeValue').textContent=ink.eraserSize;$('#inkColors').innerHTML=colorControls('ink',ink.color);$$('[data-ink-panel]').forEach(n=>n.hidden=n.dataset.inkPanel!==(state.tool==='erase'?'erase':'draw'));$$('[data-ink-mode]').forEach(n=>n.setAttribute('aria-pressed',String(n.dataset.inkMode===state.tool)));WriterCanvasControls.enhance($('#drawOptions'));$('#eraserPreview').style.width=$('#eraserPreview').style.height=ink.eraserSize+'px';}
  function toggleOptions(name){const open=state.menu!==name;closeOptions();if(!open)return;if(name==='draw')setTool(state.tool==='erase'?'erase':'draw');state.menu=name;syncOptions();const node=name==='cards'?$('#cardOptions'):$('#drawOptions'),button=$(`[data-menu="${name}"]`),r=button.getBoundingClientRect();node.hidden=false;node.style.left=Math.max(8,Math.min(r.left,innerWidth-Math.min(300,innerWidth-16)-8))+'px';node.style.top=Math.min(r.bottom+8,innerHeight-100)+'px';node.style.maxHeight=Math.max(80,innerHeight-r.bottom-24)+'px';button.dataset.menuTitle=button.title;button.removeAttribute('title');button.setAttribute('aria-expanded','true');node.querySelector('button,select,input')?.focus();}
  function draftInk(interaction){const stroke={...state.ink,points:interaction.points,pressures:interaction.pressures};els.draftPath.style.stroke='none';els.draftPath.style.fill=paint(stroke.color);els.draftPath.setAttribute('d',Ink.outline(stroke));}
  function eraseAt(a,b){const before=state.strokes,next=Ink.erase(before,a,b,state.ink.eraserSize/2/state.viewTransform.scale,state.ink.eraserMode);if(next.length+state.cards.length+state.edges.length>3000){showToast('笔迹分段过多，请缩小擦除范围或使用整笔橡皮');return;}state.strokes=next;renderStrokes();}

  function renderInspector() {
    WriterCanvasControls.close();
    els.canvasWorkspace.classList.toggle("inspector-open", Boolean(state.selected) && !state.deferInspector);
    emitUI();
    const card = selectedCard();
    const edge = selectedEdge();
    const stroke = selectedStroke();
    const text=selectedText();
    if(chosen().length>1){els.canvasWorkspace.classList.add('inspector-open');els.inspectorContent.innerHTML=`<div class="inspector-kicker"><strong>已选择 ${chosen().length} 个对象</strong></div><p class="inspector-help">拖动选中对象一起移动；拖动蓝色选框四角等比例缩放。Shift 点击增减选择；连线跟随卡片端点。</p><button class="button quiet danger" data-action="delete-selected">删除所选对象</button>`;return;}
    if(text){els.inspectorContent.innerHTML=`<div class="inspector-kicker"><strong>文字</strong></div><label class="field"><span>文字内容</span><textarea data-field="text" maxlength="24000">${esc(text.text)}</textarea></label><label class="field"><span>字号</span><input data-field="fontSize" type="number" min="8" max="512" value="${text.fontSize}"></label>${colorControls('text',text.color)}<p class="inspector-help">双击文字可直接输入；拖动蓝色角点缩放文字。</p><button class="button quiet danger" data-action="delete-selected">删除文字</button>`;return;}
    if (card) {
      const connections = state.edges.filter((item) => item.from === card.id || item.to === card.id);
      els.inspectorContent.innerHTML = `<div class="inspector-kicker"><strong>卡片</strong><span>${esc(card.kind)}</span></div><label class="field"><span>标题</span><input data-field="title" value="${esc(card.title)}" maxlength="200"></label><label class="field"><span>类型</span><select data-field="kind" data-editable="true">${[...new Set([card.kind,"大纲","卷纲","章纲","人物","时间","地点","便签","作品","设定","线索"])].map((kind) => `<option value="${esc(kind)}" ${kind === card.kind ? "selected" : ""}>${esc(kind)}</option>`).join("")}</select></label><label class="field"><span>形态</span><select data-field="shape"><option value="rectangle" ${card.shape!=="circle"?"selected":""}>方卡</option><option value="circle" ${card.shape==="circle"?"selected":""}>圆卡</option></select></label>${colorControls("card",card.color)}<label class="field"><span>内容</span><textarea data-field="content" maxlength="24000" placeholder="写下这张卡片真正需要记住的事">${esc(card.content)}</textarea></label><details class="canvas-sidebar-options" ${card.sidebarPinned?"open":""}><summary>写作侧栏速查</summary><label class="canvas-check"><input type="checkbox" data-field="sidebarPinned" ${card.sidebarPinned?"checked":""}>加入写作速查</label><label class="field"><span>侧栏速记（可选，最多240字）</span><textarea data-field="sidebarNote" maxlength="240" placeholder="留空时使用内容首段，不改动全文">${esc(card.sidebarNote||"")}</textarea></label></details><div class="inspector-actions"><button class="button quiet" type="button" data-action="add-child">${icon("child")}添加子卡片</button><button class="button quiet" type="button" data-action="connect-from-card">${icon("connect")}从这张卡连线</button></div><section class="connection-section"><h3>连接 · ${connections.length}</h3>${connections.length ? connections.map((item) => { const outgoing = item.from === card.id; const other = cardById(outgoing ? item.to : item.from); return `<button class="connection-row" type="button" data-action="select-edge" data-id="${item.id}"><span><strong>${esc(other?.title || "已移除卡片")}</strong><small>${item.kind === "hierarchy" ? "从属" : "关联"} · ${item.kind==="hierarchy"?(outgoing?"下级":"上级"):edgeSymbol({...item,direction:outgoing?item.direction:({forward:"back",back:"forward"})[item.direction]||item.direction})} · ${esc(edgeLabel(item))}</small></span>${icon("arrow")}</button>`; }).join("") : '<p class="inspector-help">还没有连接。可从卡片右侧圆点拖出一条线。</p>'}</section><button class="button quiet danger inspector-delete" type="button" data-action="delete-selected">${icon("trash")}删除卡片</button><p class="inspector-help">拖动卡片移动；右下角调整大小。建立父子连接不会自动改变位置。</p>`;
      if(card.readOnly)els.inspectorContent.querySelectorAll("input,textarea,select").forEach(n=>n.disabled=true);
    } else if (edge) {
      const from = cardById(edge.from);
      const to = cardById(edge.to);
      els.inspectorContent.innerHTML = `<div class="inspector-kicker"><strong>连线</strong><span>${edge.kind === "hierarchy" ? "从属" : "关联"}</span></div><p class="inspector-summary">${esc(edgeDescription(edge))}</p><label class="field"><span>关系名称</span><input data-field="label" value="${esc(edge.label)}" placeholder="例如：包含、出场、伏笔" maxlength="60"></label><label class="field"><span>关系类型</span><select data-field="kind"><option value="relation" ${edge.kind === "relation" ? "selected" : ""}>自由关联</option><option value="hierarchy" ${edge.kind === "hierarchy" ? "selected" : ""}>从属分级</option></select></label><label class="field"><span>方向</span><select data-field="direction"><option value="forward" ${edge.direction === "forward" ? "selected" : ""}>起点 → 终点</option><option value="back" ${edge.direction === "back" ? "selected" : ""}>终点 → 起点</option><option value="both" ${edge.direction === "both" ? "selected" : ""}>双向</option><option value="none" ${edge.direction === "none" ? "selected" : ""}>无方向</option></select></label>${colorControls("edge",edge.color)}<button class="button quiet danger inspector-delete" type="button" data-action="delete-selected">${icon("trash")}删除连线</button><p class="inspector-help">从属分级以起点为上级、终点为下级；同一章纲中的情节会同步层级。自由关联不改章序，卡片位置都不自动重排。</p>`;
    } else if (stroke) {
      els.inspectorContent.innerHTML = `<div class="inspector-kicker"><strong>手绘笔迹</strong><span>${stroke.points.length} 个点</span></div><label class="field"><span>线宽 · <output id="strokeWidthValue">${stroke.width}</output> px</span><input data-field="width" type="range" min="1" max="256" step="0.5" value="${stroke.width}"></label><button class="button quiet danger inspector-delete" type="button" data-action="delete-selected">${icon("trash")}删除笔迹</button>${colorControls("stroke",stroke.color)}<p class="inspector-help">按 V 返回选择后可以点选笔迹；按 Delete 可删除当前选中项。</p>`;
    } else {
      els.inspectorContent.innerHTML = `<div class="inspector-empty"><div class="inspector-kicker"><strong>详情</strong><span>未选中</span></div><h2>点一个对象，在这里直接修改</h2><p>没有第二层弹窗。卡片、连线和笔迹共用这一个详情栏。</p><ol class="empty-steps"><li><span>01</span>双击空白建一张卡，或按 N 在视野中央新建。</li><li><span>02</span>从卡片右侧圆点拖到另一张卡，松手即可连线。</li><li><span>03</span>按 D 手绘，按 V 回到选择；点线也能编辑关系。</li></ol><p>拖动空白平移，Ctrl/⌘ + 滚轮缩放。找不到内容时，点右下角“适应”。</p></div>`;
    }
    WriterCanvasControls.enhance(els.inspectorContent);
  }

  function renderAll() {
    renderCards();
    renderTexts();
    renderEdges();
    renderStrokes();
    updateTransform();
    updateToolbar();
    updateSelectionVisual();
    renderInspector();
    updateStatus();
    renderSelection();
  }

  function select(kind, id) {
    finishEdit();
    const previousKind = state.selected?.kind;
    state.selected = kind && id ? { kind, id } : null;
    updateSelectionVisual();
    renderInspector();
    if (previousKind === "stroke" || kind === "stroke") renderStrokes();
  }

  function setTool(tool, sourceId = null) {
    finishEdit();
    state.tool = tool;
    state.connectSource = null;
    state.deferInspector = false;
    if (["draw","erase","pan"].includes(tool)) select(null);
    if (tool === "connect") {
      state.connectSource = sourceId && cardById(sourceId) ? sourceId : null;
      showToast(state.connectSource ? "点另一张卡片完成连线，也可从端口拖动" : "先点起点，再点终点；端口也可直接拖出连线");
    }
    renderInspector();
    updateToolbar();
    updateSelectionVisual();
  }

  function screenToWorld(clientX, clientY) {
    const rect = els.viewport.getBoundingClientRect();
    const { x, y, scale } = state.viewTransform;
    return { x: (clientX - rect.left - x) / scale, y: (clientY - rect.top - y) / scale };
  }

  function zoomAt(nextScale, clientX, clientY) {
    const rect = els.viewport.getBoundingClientRect();
    const screenX = clientX === undefined ? rect.width / 2 : clientX - rect.left;
    const screenY = clientY === undefined ? rect.height / 2 : clientY - rect.top;
    const view = state.viewTransform;
    const scale = clamp(nextScale, 0.2, 2.5);
    const worldX = (screenX - view.x) / view.scale;
    const worldY = (screenY - view.y) / view.scale;
    view.x = screenX - worldX * scale;
    view.y = screenY - worldY * scale;
    view.scale = scale;
    updateTransform();
  }

  function contentBounds() {
    const xs = [];
    const ys = [];
    [...state.cards,...state.texts].forEach((card) => {
      xs.push(card.x, card.x + card.w);
      ys.push(card.y, card.y + card.h);
    });
    state.strokes.forEach((stroke) => {
      const bounds = strokeBounds(stroke);
      xs.push(bounds.minX, bounds.maxX);
      ys.push(bounds.minY, bounds.maxY);
    });
    if (!xs.length) return null;
    return { minX: Math.min(...xs), minY: Math.min(...ys), maxX: Math.max(...xs), maxY: Math.max(...ys) };
  }

  function fitContent(initial = false) {
    const bounds = contentBounds();
    const rect = els.viewport.getBoundingClientRect();
    if (initial && innerWidth <= 900 && rect.width && rect.height) {
      const card = cardById("chapter") || state.cards[0];
      if (card) {
        const center = cardCenter(card);
        const scale = 0.65;
        state.viewTransform.scale = scale;
        state.viewTransform.x = rect.width / 2 - center.x * scale;
        state.viewTransform.y = rect.height * 0.32 - center.y * scale;
        updateTransform();
        return;
      }
    }
    if (!bounds || !rect.width || !rect.height) {
      state.viewTransform = { x: 40, y: 40, scale: 1 };
      updateTransform();
      return;
    }
    const padding = 70;
    const width = Math.max(1, bounds.maxX - bounds.minX);
    const height = Math.max(1, bounds.maxY - bounds.minY);
    const scale = clamp(Math.min((rect.width - padding * 2) / width, (rect.height - padding * 2) / height), 0.2, 1);
    state.viewTransform.scale = scale;
    state.viewTransform.x = (rect.width - width * scale) / 2 - bounds.minX * scale;
    state.viewTransform.y = (rect.height - height * scale) / 2 - bounds.minY * scale;
    updateTransform();
  }

  function ensureCardVisible(card) {
    const rect = els.viewport.getBoundingClientRect();
    const view = state.viewTransform;
    const center = cardCenter(card);
    const screenX = center.x * view.scale + view.x;
    const screenY = center.y * view.scale + view.y;
    if (screenX > 50 && screenX < rect.width - 50 && screenY > 50 && screenY < rect.height - 50) return;
    view.x = rect.width / 2 - center.x * view.scale;
    view.y = rect.height / 2 - center.y * view.scale;
    updateTransform();
  }

  function createEdge(from, to, kind = "relation") {
    const parallel = state.edges.filter((edge) => (edge.from === from && edge.to === to) || (edge.from === to && edge.to === from)).length;
    const bend = parallel === 0 ? 0 : Math.ceil(parallel / 2) * 60 * (parallel % 2 ? 1 : -1);
    const edge = { id: `edge-${crypto.randomUUID()}`, from, to, kind, label: kind === "hierarchy" ? "包含" : "关联", direction: kind === "hierarchy" ? "forward" : "none", bend };
    state.edges.push(edge);
    return edge;
  }

  function toggleSidebar(id){const card=cardById(id);if(!card||card.readOnly)return;finishEdit();const before=serialize();card.sidebarPinned=!card.sidebarPinned;commitHistory(before);updateCardDom(card);if(selectedCard()?.id===id){const checkbox=els.inspectorContent.querySelector('[data-field=sidebarPinned]');if(checkbox)checkbox.checked=card.sidebarPinned;}emit('writer:prototype-sidebar',null);}
  function focusInspectorTitle() {
    const id=selectedCard()?.id,focused=document.activeElement,initial=els.inspectorContent.querySelector('[data-field="title"]')?.value;
    requestAnimationFrame(() => {
      if(selectedCard()?.id!==id)return;
      const input=els.inspectorContent.querySelector('[data-field="title"]'),active=document.activeElement;
      if(!input)return;
      if(active===input){if(input.value===initial)input.select();return;}
      // A deliberate focus change or already-edited title wins over autofocus.
      if(input.value!==initial||active!==focused&&active!==document.body&&active!==els.viewport)return;
      input.focus();input.select();
    });
  }

  function vacantPoint(w=240,h=150){
      const rect=els.viewport.getBoundingClientRect(),center=screenToWorld(rect.left+rect.width/2,rect.top+rect.height/2);
      const size={w,h};
      let point = { x: center.x - size.w/2, y: center.y - size.h/2 };
      // Search around the visible centre without moving existing cards.
      for(let i=0;i<81;i++){
        const ring=Math.ceil(Math.sqrt(i)),angle=i*2.399963;
        const candidate={x:point.x+Math.cos(angle)*ring*64,y:point.y+Math.sin(angle)*ring*52};
        if(![...state.cards,...state.texts].some(c=>candidate.x<c.x+c.w+16&&candidate.x+size.w+16>c.x&&candidate.y<c.y+c.h+16&&candidate.y+size.h+16>c.y)){point=candidate;break;}
      }
      return point;
  }

  function addCard(position = null, parent = null, shape = parent?.shape || state.cardShape) {
    finishEdit();
    const before = serialize();
    const point = position || vacantPoint(shape==='circle'?200:240,shape==='circle'?200:150);
    const card = { id: `card-${crypto.randomUUID()}`, x: point.x, y: point.y, w: shape==='circle'?200:240, h: shape==='circle'?200:150, shape, color:parent?.color||"auto", sidebarPinned:false, sidebarNote:"", kind: "便签", title: parent ? "新子卡片" : "新卡片", content: "" };
    state.cards.push(card);
    let edge = null;
    if (parent) edge = createEdge(parent.id, card.id, "hierarchy");
    commitHistory(before);
    state.tool = "select";
    state.connectSource = null;
    state.selected = { kind: "card", id: card.id };
    renderAll();
    ensureCardVisible(card);
    focusInspectorTitle();
    if (edge) showToast("已添加子卡片，并建立从属连线");
  }

  function addChild() {
    const parent = selectedCard();
    if (!parent) return;
    addCard({ x: parent.x + parent.w + 90, y: parent.y + 40 }, parent);
  }

  function handleConnectCard(id) {
    if (!state.connectSource) {
      state.connectSource = id;
      state.deferInspector = !els.canvasWorkspace.classList.contains("inspector-open");
      select("card", id);
      showToast("再点另一张卡片作为终点");
      updateSelectionVisual();
      return;
    }
    if (state.connectSource === id) {
      showToast("这张卡已作为起点，点另一张卡片即可");
      return;
    }
    const before = serialize();
    const edge = createEdge(state.connectSource, id, "relation");
    commitHistory(before);
    state.tool = "connect";
    state.connectSource = null;
    state.deferInspector = false;
    state.selected = { kind: "edge", id: edge.id };
    renderAll();
    showToast("连线已建立，可在右侧修改关系");
  }

  function deleteSelected() {
    const items=chosen();if(items.length>1||items[0]?.kind==='text'){finishEdit();const before=serialize(),ids=new Set(items.map(i=>i.id));state.cards=state.cards.filter(c=>!ids.has(c.id));state.texts=state.texts.filter(c=>!ids.has(c.id));state.strokes=state.strokes.filter(c=>!ids.has(c.id));state.edges=state.edges.filter(e=>!ids.has(e.id)&&!ids.has(e.from)&&!ids.has(e.to));state.selected=null;commitHistory(before);renderAll();return;}
    if (!state.selected) return;
    finishEdit();
    const before = serialize();
    const { kind, id } = state.selected;
    if (kind === "card") {
      state.cards = state.cards.filter((card) => card.id !== id);
      state.edges = state.edges.filter((edge) => edge.from !== id && edge.to !== id);
    } else if (kind === "edge") {
      state.edges = state.edges.filter((edge) => edge.id !== id);
    } else if (kind === "stroke") {
      state.strokes = state.strokes.filter((stroke) => stroke.id !== id);
    }
    commitHistory(before);
    state.selected = null;
    renderAll();
    showToast("已删除，可撤销");
  }

  function centerOnEdge(edge) {
    const geometry = edgeGeometry(edge);
    if (!geometry) return;
    const rect = els.viewport.getBoundingClientRect();
    const view = state.viewTransform;
    view.x = rect.width / 2 - geometry.x * view.scale;
    view.y = rect.height / 2 - geometry.y * view.scale;
    updateTransform();
  }

  function applyInspectorField(target) {
    const field = target.dataset.field;
    if (!field) return;
    if(state.editBefore===null)state.editBefore=serialize();
    const card = selectedCard();
    const edge = selectedEdge();
    const stroke = selectedStroke();
    if(selectedText()){const text=selectedText();text[field]=field==='fontSize'?clamp(Number(target.value)||24,8,512):target.value;updateTextDom(text);renderSelection();return;}
    if (card) {
      card[field] = target.type==='checkbox'?target.checked:target.value;
      if(field==='shape'&&card.shape==='circle')card.w=card.h=clamp(Math.max(card.w,card.h),180,460);
      updateCardDom(card);
      if(field==='shape')renderEdges();
    } else if (edge) {
      if(field==='kind'&&target.value==='hierarchy'){
        const parents=new Map();let invalid=false;
        for(const e of state.edges){if((e===edge?target.value:e.kind)!=='hierarchy')continue;if(parents.has(e.to)&&parents.get(e.to)!==e.from)invalid=true;parents.set(e.to,e.from);}
        for(const start of parents.keys()){const seen=new Set();let at=start;while(parents.has(at)){if(seen.has(at)){invalid=true;break;}seen.add(at);at=parents.get(at);}}
        if(invalid){target.value=edge.kind;showToast('从属分级不能形成环，且每张卡只能有一个上级');return;}
      }
      edge[field] = target.value;
      renderEdges();
      updateSelectionVisual();
      const summary=els.inspectorContent.querySelector(".inspector-summary");if(summary)summary.textContent=edgeDescription(edge);
    } else if(stroke && field==='color'){stroke.color=Ink.color(target.value);renderStrokes();
    } else if (stroke && field === "width") {
      stroke.width = Number(target.value);
      const output = $("#strokeWidthValue");
      if (output) output.value = target.value;
      renderStrokes();
    }
  }

  const touchPoints=new Map();let pinch=null,touchLock=false;
  function startTouch(event){if(event.pointerType!=='touch')return false;if(state.interaction&&state.interaction.pointerType!=='touch')return true;touchPoints.set(event.pointerId,{x:event.clientX,y:event.clientY});if(touchLock)return true;if(touchPoints.size<2)return false;const tool=state.tool;if(state.interaction)cancelInteraction({pointerId:state.interaction.pointerId});state.tool=tool;updateToolbar();const ids=[...touchPoints.keys()].slice(0,2),[a,b]=ids.map(id=>touchPoints.get(id)),cx=(a.x+b.x)/2,cy=(a.y+b.y)/2;pinch={ids,distance:Math.max(1,Math.hypot(b.x-a.x,b.y-a.y)),scale:state.viewTransform.scale,anchor:screenToWorld(cx,cy)};for(const id of ids)els.viewport.setPointerCapture(id);event.preventDefault();return true;}
  function moveTouch(event){if(event.pointerType!=='touch'||!touchPoints.has(event.pointerId))return false;touchPoints.set(event.pointerId,{x:event.clientX,y:event.clientY});if(touchLock)return true;if(!pinch)return false;const [a,b]=pinch.ids.map(id=>touchPoints.get(id));if(!a||!b)return true;const rect=els.viewport.getBoundingClientRect(),scale=clamp(pinch.scale*Math.hypot(b.x-a.x,b.y-a.y)/pinch.distance,.2,2.5);state.viewTransform={scale,x:(a.x+b.x)/2-rect.left-pinch.anchor.x*scale,y:(a.y+b.y)/2-rect.top-pinch.anchor.y*scale};updateTransform();event.preventDefault();return true;}
  function endTouch(event){if(event.pointerType!=='touch')return false;const consumed=!!pinch||touchLock;touchPoints.delete(event.pointerId);if(consumed){pinch=null;touchLock=touchPoints.size>0;if(els.viewport.hasPointerCapture(event.pointerId))els.viewport.releasePointerCapture(event.pointerId);}return consumed;}
  function clearTouches(){touchPoints.clear();pinch=null;touchLock=false;}

  function startInteraction(event, mode, data = {}) {
    state.interaction = { mode, pointerId: event.pointerId, pointerType:event.pointerType, startX: event.clientX, startY: event.clientY, before: serialize(), moved: false, ...data };
    els.viewport.setPointerCapture(event.pointerId);
    if (mode === "pan") els.viewport.classList.add("panning");
    event.preventDefault();
  }

  function onPointerDown(event) {
    if (state.view !== "canvas" || (event.pointerType === "mouse" && event.button !== 0)) return;
    if (event.target.closest(".zoom-controls,button,input,select,textarea,[contenteditable=true],[contenteditable=plaintext-only]")) return;
    if(startTouch(event))return;
    if(state.interaction&&state.interaction.pointerId!==event.pointerId)return;
    closeOptions();
    finishEdit();
    const cardElement = event.target.closest(".canvas-card");
    const textElement=event.target.closest(".canvas-text"),grip=event.target.closest("[data-selection-grip]");
    if(grip&&state.tool==='select'&&!state.spacePan){startGroup(event,'group-resize',grip.dataset.selectionGrip);return;}
    const edgeElement = event.target.closest("[data-edge-id]");
    const strokeElement = event.target.closest("[data-stroke-id]");
    els.viewport.dataset.pointerFocus="true";
    if (state.spacePan || state.tool==="pan") {
      startInteraction(event, "pan", { startView: { ...state.viewTransform } });
      return;
    }
    if(state.tool==='erase'){
      const point=screenToWorld(event.clientX,event.clientY);els.draftPath.style.fill='none';els.draftPath.style.stroke='var(--ink)';
      startInteraction(event,state.ink.eraserMode==='area'?'erase-area':'erase',{last:point,origin:point});
      if(state.ink.eraserMode!=='area')eraseAt(point,point);return;
    }
    if (state.tool === "draw") {
      const point = screenToWorld(event.clientX, event.clientY);
      startInteraction(event, "draw", { points: [point], pressures:[Ink.pressure(event)] });
      draftInk(state.interaction);
      return;
    }
    if (event.target.closest("[data-connect-port]") && cardElement) {
      const source = cardElement.dataset.cardId;
      state.deferInspector = !els.canvasWorkspace.classList.contains("inspector-open");
      select("card", source);
      state.connectSource = source;
      els.draftPath.style.strokeDasharray = "5 4";
      els.draftPath.style.stroke="var(--ink)";els.draftPath.style.fill="none";
      startInteraction(event, "edge-drag", { source, returnTool: state.tool });
      updateSelectionVisual();
      return;
    }
    if (state.tool === "connect" && cardElement) {
      handleConnectCard(cardElement.dataset.cardId);
      event.preventDefault();
      return;
    }
    if (event.target.closest("[data-resize-handle]") && cardElement) {
      const card = cardById(cardElement.dataset.cardId);
      select("card", card.id);
      startInteraction(event, "resize", { cardId: card.id, startCard: { ...card } });
      return;
    }
    if(textElement&&state.tool==='select'){const item={kind:'text',id:textElement.dataset.textId};if(event.shiftKey){setSelection(isSelected(item.kind,item.id)?chosen().filter(n=>n.id!==item.id):[...chosen(),item]);event.preventDefault();return;}if(!isSelected(item.kind,item.id))select(item.kind,item.id);startGroup(event,'group-move');return;}
    if (!cardElement && !edgeElement && !strokeElement && !textElement) {
      els.viewport.focus({ preventScroll: true });
      if(state.tool==='select'){const initial=event.shiftKey?chosen():[];if(!event.shiftKey)select(null);startInteraction(event,'marquee',{origin:screenToWorld(event.clientX,event.clientY),initial});}else startInteraction(event, "pan", { startView: { ...state.viewTransform } });
      return;
    }
    if (cardElement) {
      const card = cardById(cardElement.dataset.cardId);
      if(event.shiftKey&&state.tool==='select'){setSelection(isSelected('card',card.id)?chosen().filter(n=>n.id!==card.id):[...chosen(),{kind:'card',id:card.id}]);event.preventDefault();return;}
      if(!isSelected('card',card.id))select("card", card.id);
      cardElement.focus({ preventScroll: true });
      if (state.tool === "select") startGroup(event,'group-move');
      return;
    }
    if (edgeElement) {
      const item={kind:'edge',id:edgeElement.dataset.edgeId};if(event.shiftKey)setSelection(isSelected(item.kind,item.id)?chosen().filter(n=>n.id!==item.id):[...chosen(),item]);else select(item.kind,item.id);
      event.preventDefault();
      return;
    }
    if (strokeElement) {
      const item={kind:'stroke',id:strokeElement.dataset.strokeId};if(event.shiftKey)setSelection(isSelected(item.kind,item.id)?chosen().filter(n=>n.id!==item.id):[...chosen(),item]);else{if(!isSelected(item.kind,item.id))select(item.kind,item.id);startGroup(event,'group-move');}
      event.preventDefault();
    }
  }

  function onPointerMove(event) {
    if(moveTouch(event))return;
    updateEraserCursor(event);
    const interaction = state.interaction;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    const dx = event.clientX - interaction.startX;
    const dy = event.clientY - interaction.startY;
    if (Math.hypot(dx, dy) > 2) interaction.moved = true;
    if(interaction.mode==='marquee'){
      const p=screenToWorld(event.clientX,event.clientY),a=interaction.origin,box={minX:Math.min(a.x,p.x),minY:Math.min(a.y,p.y),maxX:Math.max(a.x,p.x),maxY:Math.max(a.y,p.y)},node=$('#marquee');node.hidden=false;Object.assign(node.style,{left:box.minX+'px',top:box.minY+'px',width:(box.maxX-box.minX)+'px',height:(box.maxY-box.minY)+'px'});const all=[...state.cards.map(c=>({kind:'card',id:c.id})),...state.strokes.map(c=>({kind:'stroke',id:c.id})),...state.texts.map(c=>({kind:'text',id:c.id}))];setSelection([...interaction.initial,...all.filter(item=>{const b=objectBounds(item);return b.maxX>=box.minX&&b.minX<=box.maxX&&b.maxY>=box.minY&&b.minY<=box.maxY;})]);
    }else if(['group-move','group-resize'].includes(interaction.mode)){transformGroup(interaction,dx/state.viewTransform.scale,dy/state.viewTransform.scale,screenToWorld(event.clientX,event.clientY));
    }else if (interaction.mode === "pan") {
      state.viewTransform.x = interaction.startView.x + dx;
      state.viewTransform.y = interaction.startView.y + dy;
      updateTransform();
    } else if (interaction.mode === "move") {
      const card = cardById(interaction.cardId);
      card.x = interaction.startCard.x + dx / state.viewTransform.scale;
      card.y = interaction.startCard.y + dy / state.viewTransform.scale;
      updateCardDom(card);
      renderEdges();
    } else if (interaction.mode === "resize") {
      const card = cardById(interaction.cardId);
      card.w = clamp(interaction.startCard.w + dx / state.viewTransform.scale, 180, 560);
      card.h = clamp(interaction.startCard.h + dy / state.viewTransform.scale, 110, 460);
      if(card.shape==='circle')card.w=card.h=clamp(Math.max(card.w,card.h),180,460);
      updateCardDom(card);
      renderEdges();
    } else if (interaction.mode === "edge-drag") {
      const source = cardById(interaction.source);
      const point = screenToWorld(event.clientX, event.clientY);
      const start = cardBoundary(source, point);
      els.draftPath.setAttribute("d", `M ${start.x} ${start.y} L ${point.x} ${point.y}`);
    } else if(interaction.mode==='erase'){
      const point=screenToWorld(event.clientX,event.clientY);eraseAt(interaction.last,point);interaction.last=point;
    } else if(interaction.mode==='erase-area'){
      const p=screenToWorld(event.clientX,event.clientY),a=interaction.origin;interaction.last=p;els.draftPath.setAttribute('d',`M ${a.x} ${a.y} H ${p.x} V ${p.y} H ${a.x} Z`);
    } else if (interaction.mode === "draw") {
      const samples=event.getCoalescedEvents?.();
      for(const sample of samples?.length?samples:[event]){
        const point=screenToWorld(sample.clientX,sample.clientY),last=interaction.points.at(-1);
        if(interaction.points.length>=10000&&!interaction.limitNotified){interaction.limitNotified=true;showToast('单笔已达容量，请抬笔后继续新的一笔');}
        if(Math.hypot(point.x-last.x,point.y-last.y)>1/state.viewTransform.scale&&interaction.points.length<10000){interaction.points.push(point);interaction.pressures.push(Ink.pressure(sample));}
      }
      draftInk(interaction);
    }
    event.preventDefault();
  }

  function updateEraserCursor(event){const node=$('#eraserCursor');node.hidden=state.tool!=='erase'||state.ink.eraserMode==='area';node.style.width=node.style.height=state.ink.eraserSize+'px';node.style.left=event.clientX+'px';node.style.top=event.clientY+'px';}
  els.viewport.addEventListener('pointerleave',()=>$('#eraserCursor').hidden=true);
  function clearDraft() {
    $("#marquee").hidden=true;
    els.draftPath.setAttribute("d", "");
    els.viewport.classList.remove("panning");
  }

  function onPointerUp(event) {
    if(endTouch(event))return;
    const interaction = state.interaction;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    state.interaction = null;
    if (els.viewport.hasPointerCapture(event.pointerId)) els.viewport.releasePointerCapture(event.pointerId);
    if (["move", "resize", "group-move", "group-resize"].includes(interaction.mode) && interaction.moved) commitHistory(interaction.before);
    if (interaction.mode === "edge-drag") {
      const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".canvas-card");
      if (target && target.dataset.cardId !== interaction.source) {
        const edge = createEdge(interaction.source, target.dataset.cardId, "relation");
        commitHistory(interaction.before);
        state.selected = { kind: "edge", id: edge.id };
        showToast("连线已建立，可在右侧修改关系");
      } else {
        state.selected = { kind: "card", id: interaction.source };
      }
      if (!interaction.moved && (!target || target.dataset.cardId === interaction.source)) {
        state.connectSource = interaction.source;
        state.tool = "connect";
        clearDraft(); updateToolbar(); updateSelectionVisual();
        showToast("起点已选好，点另一张卡片完成连线");
        return;
      }
      state.connectSource = null;
      state.deferInspector = false;
      state.tool = interaction.returnTool;
      clearDraft();
      renderAll();
      return;
    }
    if (interaction.mode === "draw") {
      if (interaction.points.length) {
        const stroke = { id: `stroke-${crypto.randomUUID()}`, points: interaction.points, pressures:interaction.pressures, width:state.ink.width, brush:state.ink.brush,color:state.ink.color,pressureEnabled:state.ink.pressureEnabled,pressureStrength:state.ink.pressureStrength };
        state.strokes.push(stroke);
        commitHistory(interaction.before);
        state.selected = null;
      }
      clearDraft();
      renderAll();
      return;
    }
    if(interaction.mode==='erase-area'){state.strokes=Ink.eraseRect(state.strokes,interaction.origin,interaction.last);renderStrokes();}
    if(interaction.mode==='erase'||interaction.mode==='erase-area'){state.selected=null;commitHistory(interaction.before);renderInspector();renderStrokes();}
    clearDraft();
    updateStatus();
  }

  function cancelInteraction(event) {
    const interaction = state.interaction;
    if (!interaction || interaction.pointerId !== event.pointerId) return;
    state.interaction = null;
    state.deferInspector = false;
    if (els.viewport.hasPointerCapture(event.pointerId)) els.viewport.releasePointerCapture(event.pointerId);
    if (interaction.mode === "pan") state.viewTransform = { ...interaction.startView };
    if (["move", "resize", "group-move", "group-resize", "draw", "erase", "erase-area"].includes(interaction.mode)) {
      restoreSnapshot(interaction.before);
    } else {
      clearDraft();
      updateTransform();
    }
    state.connectSource = null;
    clearDraft();updateSelectionVisual();renderInspector();
  }

  function finishInterruptedInteraction(event={}) {
    const interaction=state.interaction;
    if(event.pointerId!==undefined&&interaction&&event.pointerId!==interaction.pointerId)return;
    clearTouches();state.spacePan=false;
    if(!interaction)return;
    // Keep completed ink and object positions on browser/OS interruption. Only
    // explicit user cancellation restores interaction.before.
    if(interaction.mode==='edge-drag'){
      state.interaction=null;
      if(els.viewport.hasPointerCapture(interaction.pointerId))els.viewport.releasePointerCapture(interaction.pointerId);
      state.connectSource=null;state.deferInspector=false;state.tool=interaction.returnTool;
      clearDraft();renderAll();return;
    }
    onPointerUp({pointerId:interaction.pointerId,pointerType:interaction.pointerType});
  }

  els.viewport.addEventListener("pointerdown", onPointerDown);
  // Capture loss changes event delivery; it is not pointercancel. In native Chrome a
  // fast mouse release can deliver lostpointercapture before pointerup. Keep the
  // gesture until its real up/cancel, using document delivery after capture loss.
  document.addEventListener("pointermove",event=>{if(state.interaction||touchPoints.has(event.pointerId)||els.viewport.contains(event.target))onPointerMove(event);},{passive:false});
  document.addEventListener("pointerup",event=>{if(state.interaction?.pointerId===event.pointerId||touchPoints.has(event.pointerId))onPointerUp(event);});
  document.addEventListener("pointercancel",event=>{if(state.interaction?.pointerId===event.pointerId||touchPoints.has(event.pointerId))finishInterruptedInteraction(event);});
  els.viewport.addEventListener("lostpointercapture",event=>{if(pinch?.ids.includes(event.pointerId)&&touchPoints.has(event.pointerId)){pinch=null;touchLock=true;}});
  window.addEventListener("blur",()=>finishInterruptedInteraction());
  els.viewport.addEventListener("dblclick", (event) => {
    const hit=document.elementFromPoint(event.clientX,event.clientY),text=hit?.closest('.canvas-text');if(text&&state.tool==='select'){event.preventDefault();editText(text.dataset.textId);return;}if(hit?.closest('.canvas-card,[data-selection-grip]'))return;
    if (state.tool !== "select" || event.target.closest(".canvas-card, .canvas-text, [data-selection-grip], [data-edge-id], [data-stroke-id], .zoom-controls, button, input, select, textarea")) return;
    const point = screenToWorld(event.clientX, event.clientY);
    addCard({ x: point.x - 120, y: point.y - 75 });
  });
  els.viewport.addEventListener("wheel", (event) => {
    event.preventDefault();
    if (event.ctrlKey || event.metaKey) {
      zoomAt(state.viewTransform.scale * Math.exp(-event.deltaY * 0.002), event.clientX, event.clientY);
    } else {
      state.viewTransform.x -= event.deltaX;
      state.viewTransform.y -= event.deltaY;
      updateTransform();
    }
  }, { passive: false });

  $('#textLayer').addEventListener('dblclick',event=>{const node=event.target.closest('[data-text-id]');if(node&&state.tool==='select'){event.stopPropagation();editText(node.dataset.textId);}});
  $('#textLayer').addEventListener('compositionstart',()=>composing=true);
  function textInput(event){const node=event.target.closest('[data-text-id]');if(!node)return;const text=state.texts.find(t=>t.id===node.dataset.textId);if(!text)return;text.text=event.target.textContent.slice(0,24000);node.setAttribute('aria-label','文字：'+(text.text||'空白文字').slice(0,80));const mirror=els.inspectorContent.querySelector('[data-field=text]');if(mirror&&mirror!==document.activeElement)mirror.value=text.text;text.h=Math.max(32,event.target.scrollHeight+8);node.style.minHeight=text.h+'px';if(!composing)emitData();renderSelection();}
  $('#textLayer').addEventListener('input',textInput);
  $('#textLayer').addEventListener('compositionend',event=>{composing=false;textInput(event);});
  $('#textLayer').addEventListener('focusout',event=>{if(event.target.isContentEditable){composing=false;textInput(event);event.target.contentEditable='false';finishEdit();}});
  els.inspectorContent.addEventListener("focusin", (event) => {
    if (event.target.dataset.field && state.editBefore === null) state.editBefore = serialize();
  });
  els.inspectorContent.addEventListener("compositionstart",()=>composing=true);
  els.inspectorContent.addEventListener("compositionend",event=>{composing=false;applyInspectorField(event.target);emitData();});
  els.inspectorContent.addEventListener("input", (event) => {applyInspectorField(event.target);emitData();if(event.target.dataset.field==="sidebarPinned")emit("writer:prototype-sidebar",null);});
  els.inspectorContent.addEventListener("change", (event) => {
    applyInspectorField(event.target);
    if (event.target.matches('select, input[type="range"], input[type="checkbox"], input[type="color"]')) finishEdit();
  });
  els.inspectorContent.addEventListener("focusout", (event) => {
    if (event.target.dataset.field){if(composing){composing=false;applyInspectorField(event.target);emitData();}finishEdit();}
  });

  document.addEventListener('pointerdown',event=>{if(state.menu&&!event.target.closest('.canvas-options,.canvas-select-menu,[data-menu]'))closeOptions();});
  document.addEventListener('input',event=>{const n=event.target;if(n.closest('#drawOptions')){if(n.id==='inkBrush')state.ink.brush=n.value;else if(n.id==='inkWidth')state.ink.width=Number(n.value);else if(n.id==='inkPressure')state.ink.pressureEnabled=n.checked;else if(n.id==='inkStrength')state.ink.pressureStrength=Number(n.value)/100;else if(n.id==='eraserMode')state.ink.eraserMode=n.value;else if(n.id==='eraserSize')state.ink.eraserSize=Number(n.value);else if(n.dataset.inkControl==='color'){state.ink.color=Ink.color(n.value);$$('#inkColors [data-color]').forEach(b=>b.setAttribute('aria-pressed','false'));}$('#inkWidthValue').textContent=state.ink.width;$('#inkPressureValue').textContent=Math.round(state.ink.pressureStrength*100)+'%';$('#inkStrength').disabled=!state.ink.pressureEnabled;$('#eraserSizeValue').textContent=state.ink.eraserSize;$('#eraserPreview').style.width=$('#eraserPreview').style.height=state.ink.eraserSize+'px';updateToolbar();emitUI();}});
  document.addEventListener("click", (event) => {
    if(legacyData)return;
    const menuButton=event.target.closest('[data-menu]');if(menuButton){toggleOptions(menuButton.dataset.menu);return;}
    const inkMode=event.target.closest('[data-ink-mode]');if(inkMode){setTool(inkMode.dataset.inkMode);syncOptions();emitUI();return;}
    const swatch=event.target.closest('[data-color]');if(swatch){if(swatch.dataset.colorTarget==='ink'){state.ink.color=swatch.dataset.color;syncOptions();emitUI();}else{finishEdit();const before=serialize(),selected=selectedCard()||selectedEdge()||selectedStroke()||selectedText();if(selected){selected.color=swatch.dataset.color;commitHistory(before);renderAll();}}return;}
    const viewButton = event.target.closest("button[data-view]");
    if (viewButton) {
      setView(viewButton.dataset.view, viewButton.dataset.view === "writing");
      return;
    }
    const toolButton = event.target.closest("[data-tool]");
    if (toolButton) {
      setTool(toolButton.dataset.tool);
      return;
    }
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const action = button.dataset.action;
    if(action==='toggle-sidebar')toggleSidebar(button.dataset.id);
    else if(action==='close-options')closeOptions(true);
    else if(action==='add-shaped-card'){state.cardShape=button.dataset.shape;closeOptions();addCard(null,null,state.cardShape);emitUI();}
    else if (action === "add-card") addCard();
    else if (action === "add-text") addText();
    else if (action === "add-child") addChild();
    else if (action === "connect-from-card") setTool("connect", selectedCard()?.id);
    else if (action === "delete-selected") deleteSelected();
    else if (action === "undo") undo();
    else if (action === "redo") redo();
    else if (action === "zoom-in") zoomAt(state.viewTransform.scale * 1.15);
    else if (action === "zoom-out") zoomAt(state.viewTransform.scale / 1.15);
    else if (action === "zoom-reset") zoomAt(1);
    else if (action === "fit-content") fitContent();
    else if (action === "select-edge") {
      const edge = edgeById(button.dataset.id);
      if (edge) {
        select("edge", edge.id);
        centerOnEdge(edge);
      }
    } else if (action === "close-inspector") select(null);
  });

  els.themeToggle.addEventListener("click", () => {
    state.theme = state.theme === "light" ? "dark" : "light";
    applyTheme();
    syncUrl();
    emit("writer:prototype-theme",state.theme);
  });

  els.bodyEditor.addEventListener("input", () => {
    state.body = els.bodyEditor.value;
    updateWritingCount();
  });

  document.addEventListener("keydown", (event) => {
    if(event.key==="Tab")delete els.viewport.dataset.pointerFocus;
    if(legacyData)return;
    if(event.key==='Escape'&&state.menu){event.preventDefault();closeOptions(true);return;}
    const editing = event.target.closest('input, textarea, select, [contenteditable="true"], [contenteditable="plaintext-only"], [role="combobox"], [role="listbox"]');
    if(event.isComposing||event.keyCode===229)return;
    if (editing) {
      if (event.key === "Escape") editing.blur();
      return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z" && state.view === "canvas") {
      event.preventDefault();
      if(state.interaction){cancelInteraction({pointerId:state.interaction.pointerId});return;}
      if (event.shiftKey) redo();
      else undo();
      return;
    }
    if(state.view==='canvas'&&(event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='a'){event.preventDefault();setTool('select');setSelection([...state.cards.map(c=>({kind:'card',id:c.id})),...state.texts.map(c=>({kind:'text',id:c.id})),...state.strokes.map(c=>({kind:'stroke',id:c.id})),...state.edges.map(c=>({kind:'edge',id:c.id}))]);return;}
    if (state.view !== "canvas" || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.key === " " && event.target.closest("button,summary"))return;
    if (event.key === " ") {
      state.spacePan = true;
      els.viewport.classList.add("panning");
      event.preventDefault();
      return;
    }
    if (event.key === "Escape") {
      if(state.interaction){event.preventDefault();cancelInteraction({pointerId:state.interaction.pointerId});return;}
      if (state.tool !== "select" || state.connectSource) setTool("select");
      else select(null);
      return;
    }
    const key = event.key.toLowerCase();
    if (key === "v") setTool("select");
    else if (key === "n") addCard();
    else if (key === "t") addText();
    else if (key === "c") setTool("connect");
    else if (key === "d") setTool("draw");
    else if (key === "e") setTool("erase");
    else if (key === "h") setTool("pan");
    else if (key === "f") fitContent();
    else if (key === "+" || key === "=") zoomAt(state.viewTransform.scale * 1.15);
    else if (key === "-") zoomAt(state.viewTransform.scale / 1.15);
    else if (["delete", "backspace"].includes(key)) deleteSelected();
    else if (["arrowleft", "arrowright", "arrowup", "arrowdown"].includes(key)) {
      if(chosen().length>1||selectedText()||selectedStroke()){const before=serialize(),distance=event.shiftKey?25:5;transformGroup({mode:'group-move',items:chosen(),original:JSON.parse(before),bounds:selectionBounds()},key==='arrowleft'?-distance:key==='arrowright'?distance:0,key==='arrowup'?-distance:key==='arrowdown'?distance:0);commitHistory(before);event.preventDefault();return;}
      const card = selectedCard();
      if (!card) return;
      const before = serialize();
      const distance = event.shiftKey ? 25 : 5;
      if (key === "arrowleft") card.x -= distance;
      if (key === "arrowright") card.x += distance;
      if (key === "arrowup") card.y -= distance;
      if (key === "arrowdown") card.y += distance;
      commitHistory(before);
      updateCardDom(card);
      renderEdges();renderSelection();
      event.preventDefault();
    } else if (event.key === "Enter") {
      const text=event.target.closest("[data-text-id]");if(text){editText(text.dataset.textId);return;}
      const card = event.target.closest("[data-card-id]");
      const edge = event.target.closest("[data-edge-id]");
      const stroke = event.target.closest("[data-stroke-id]");
      if (card) select("card", card.dataset.cardId);
      else if (edge) select("edge", edge.dataset.edgeId);
      else if (stroke) select("stroke", stroke.dataset.strokeId);
    }
  });

  document.addEventListener("keyup", (event) => {
    if (event.key === " ") {
      state.spacePan = false;
      els.viewport.classList.remove("panning");
    }
  });

  window.addEventListener("resize", ()=>{closeOptions();updateTransform();});

  window.WriterPrototypeCanvas={
    load(data,ui={},theme="light",session=null){if(window.frameElement&&document.body.dataset.hostBridge!=='2'){legacyData=JSON.parse(JSON.stringify(data));legacyUI=ui;state.theme=theme;applyTheme();closeOptions();$('#app').inert=true;let note=$('#canvasVersionNotice');if(!note){note=document.createElement('div');note.id='canvasVersionNotice';note.className='canvas-version-notice';note.setAttribute('role','alert');note.tabIndex=0;note.textContent='画布已更新。请先点上方“正文”保存正在写的内容，再刷新写作页启用新工具。原资料仍保留。';document.body.append(note);}note.focus({preventScroll:true});return;}legacyData=null;$('#app').inert=false;$('#canvasVersionNotice')?.remove();bridgeLoading=true;clearTouches();closeOptions();state.ink={...defaults,...ui.ink};state.ink.color=Ink.color(state.ink.color);state.ink.brush=['pencil','crayon','brush'].includes(state.ink.brush)?state.ink.brush:'pencil';state.ink.width=clamp(Number(state.ink.width)||3,1,32);state.ink.pressureStrength=clamp(Number(state.ink.pressureStrength)||0,0,1);state.ink.pressureEnabled=state.ink.pressureEnabled!==false;state.ink.eraserMode=['point','stroke','area'].includes(state.ink.eraserMode)?state.ink.eraserMode:'point';state.ink.eraserSize=clamp(Number(state.ink.eraserSize)||24,8,80);state.cardShape=ui.cardShape==='circle'?'circle':'rectangle';state.tool=['select','connect','draw','erase','pan'].includes(ui.tool)?ui.tool:'select';state.deferInspector=false;state.connectSource=null;state.cards=data.cards;state.edges=data.edges;state.strokes=data.strokes;state.texts=data.texts||[];state.history=session?.history?JSON.parse(JSON.stringify(session.history)):{undo:[],redo:[]};state.selected=ui.selected||null;if(state.selected&&!((objectFor(state.selected))))state.selected=null;state.selection=(ui.selection||state.selection).filter(objectFor);if(state.selection.length>1){const items=state.selection;state.selected=null;state.selection=items;}state.view="canvas";state.theme=theme;state.editBefore=null;state.interaction=null;state.viewTransform=ui.viewTransform||{x:40,y:40,scale:1};state.needsFit=false;applyTheme();renderAll();bridgeLoading=false;if(!ui.viewTransform)fitContent(true);emitUI();},
    session(){return {history:JSON.parse(JSON.stringify(state.history))};},
    toggleSidebar,
    checkpoint(){return legacyData?{data:JSON.parse(JSON.stringify(legacyData)),ui:legacyUI}:{data:JSON.parse(serialize()),ui:viewState()};},
    attachRefs(refs){for(const c of state.cards)if(refs[c.id])c.ref=refs[c.id];},
    selectCard(id){const card=cardById(id);if(card){setTool("select");select("card",id);ensureCardVisible(card);}},
    upsertCard(card){if(legacyData)return;finishEdit();const found=cardById(card.id);if(!found){const before=serialize();state.cards.push({...card,...(!Number.isFinite(card.x)||!Number.isFinite(card.y)?vacantPoint(card.w,card.h):{})});commitHistory(before);}state.tool="select";state.selected={kind:"card",id:card.id};renderAll();ensureCardVisible(cardById(card.id));focusInspectorTitle();},
    flush({automatic=false,idleMs=3000}={}){
      if(legacyData)return {data:JSON.parse(JSON.stringify(legacyData)),ui:legacyUI};
      if(composing)return {composing:true,...(!automatic?{draft:JSON.parse(serialize())}:{}),retryAfter:idleMs,ui:viewState()};
      const remaining=Math.max(0,idleMs-(performance.now()-lastActivityAt));
      if(state.interaction||automatic&&remaining>0)return {busy:true,retryAfter:state.interaction?idleMs:Math.max(50,remaining),ui:viewState()};
      if(!automatic)finishEdit();
      return {data:JSON.parse(serialize()),ui:viewState()};
    },
    setTheme(theme){state.theme=theme;applyTheme();},
    showStatus(text){const node=document.getElementById("saveStatus");if(node&&node.textContent!==text)node.textContent=text;},
    error(text){showToast(text);}
  };
  applyTheme();
  updateWritingCount();
  updateHistoryButtons();
  renderAll();
  setView(state.view);
})();
