/* Canvas-scoped adaptation of market/rank-select.js: same native value/change contract,
   one bounded portal shared by menus, keyboard focus returned to its trigger. */
(() => {
  'use strict';
  let opened=null, sequence=0;
  const controls=new WeakMap(),menu=document.createElement('div');
  menu.className='canvas-select-menu';menu.id='canvas-select-options';menu.setAttribute('role','listbox');menu.hidden=true;document.body.append(menu);
  function close(restore=false){const previous=opened;opened=null;menu.hidden=true;menu.replaceChildren();if(previous){previous.trigger.setAttribute('aria-expanded','false');if(restore&&previous.trigger.isConnected)previous.trigger.focus();}}
  function focus(index){const options=[...menu.children];options[Math.max(0,Math.min(options.length-1,index))]?.focus();}
  function open(control,last=false){if(control.select.disabled)return;close();opened=control;const {select,trigger}=control;menu.setAttribute('aria-label',trigger.getAttribute('aria-label'));menu.replaceChildren(...[...select.options].map(option=>{const row=document.createElement('div');row.setAttribute('role','option');row.setAttribute('aria-selected',String(option.selected));row.tabIndex=-1;row.textContent=option.textContent;row.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));control.sync();close(true);};return row;}));menu.hidden=false;trigger.setAttribute('aria-expanded','true');const r=trigger.getBoundingClientRect(),below=innerHeight-r.bottom-12,above=r.top-12,height=Math.min(menu.scrollHeight,208,Math.max(above,below));menu.style.width=Math.min(Math.min(Math.max(r.width,160),216),innerWidth-16)+'px';menu.style.maxHeight=height+'px';menu.style.left=Math.max(8,Math.min(r.left,innerWidth-menu.offsetWidth-8))+'px';menu.style.top=(below>=Math.min(menu.scrollHeight,208)||below>=above?r.bottom+6:Math.max(8,r.top-height-6))+'px';focus(last?menu.children.length-1:Math.max(0,select.selectedIndex));}
  function enhance(root){for(const select of root.querySelectorAll('select')){
    const existing=controls.get(select);if(existing){existing.sync();continue;}
    const label=select.getAttribute('aria-label')||select.closest('label')?.querySelector('span')?.textContent||'选项';
    select.hidden=true;select.tabIndex=-1;select.setAttribute('aria-hidden','true');
    if(select.dataset.field==='shape'){
      const group=document.createElement('div');group.className='canvas-segments';group.setAttribute('role','group');group.setAttribute('aria-label',label);
      const sync=()=>{for(const button of group.children){button.setAttribute('aria-pressed',String(button.dataset.value===select.value));button.disabled=select.disabled;}};
      for(const option of select.options){const button=document.createElement('button');button.type='button';button.textContent=option.textContent;button.dataset.value=option.value;button.onclick=()=>{select.value=option.value;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));sync();};group.append(button);}
      select.after(group);controls.set(select,{sync});sync();continue;
    }
    if(select.dataset.editable==='true'){
      const wrap=document.createElement('span'),input=document.createElement('input'),toggle=document.createElement('button');wrap.className='canvas-type-control';input.type='text';input.className='canvas-select-trigger canvas-type-input';input.value=select.value;input.maxLength=60;input.dataset.field=select.dataset.field;input.placeholder='手写或选择类型';input.setAttribute('role','combobox');input.setAttribute('aria-label',label);input.setAttribute('aria-haspopup','listbox');input.setAttribute('aria-expanded','false');input.setAttribute('aria-controls',menu.id);input.setAttribute('aria-autocomplete','list');toggle.type='button';toggle.className='canvas-type-toggle';toggle.setAttribute('aria-label','选择常用类型');
      const control={select,trigger:input,sync(){input.value=select.selectedOptions[0]?.value||input.value;input.disabled=toggle.disabled=select.disabled;}};controls.set(select,control);wrap.append(input,toggle);select.after(wrap);select.addEventListener('change',control.sync);input.addEventListener('input',()=>{select.value=input.value;close();});input.addEventListener('keydown',e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();e.stopPropagation();open(control,e.key==='ArrowUp');}});toggle.onclick=e=>{e.preventDefault();opened===control?close(true):open(control);};control.sync();continue;
    }
    const trigger=document.createElement('button');trigger.type='button';trigger.className='canvas-select-trigger';trigger.id='canvas-select-'+(++sequence);trigger.setAttribute('role','combobox');trigger.setAttribute('aria-label',label);trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-controls',menu.id);trigger.setAttribute('aria-expanded','false');
    const control={select,trigger,sync(){trigger.textContent=select.selectedOptions[0]?.textContent||'暂无选项';trigger.disabled=select.disabled;}};controls.set(select,control);select.after(trigger);select.addEventListener('change',control.sync);trigger.onclick=e=>{e.preventDefault();opened===control?close():open(control);};trigger.onkeydown=e=>{if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();e.stopPropagation();open(control,e.key==='ArrowUp');}};control.sync();
  }}
  menu.addEventListener('keydown',e=>{const index=[...menu.children].indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();focus(e.key==='Home'?0:e.key==='End'?menu.children.length-1:index+(e.key==='ArrowDown'?1:-1));}else if(e.key==='Enter'||e.key===' '){e.preventDefault();document.activeElement.click();}else if(e.key==='Escape'){e.preventDefault();close(true);}else if(e.key==='Tab')close(true);e.stopPropagation();});
  document.addEventListener('pointerdown',e=>{if(opened&&!menu.contains(e.target)&&!opened.trigger.contains(e.target)&&!opened.trigger.closest('.canvas-type-control')?.contains(e.target))close();});
  window.addEventListener('resize',()=>close());document.addEventListener('scroll',e=>{if(opened&&!menu.contains(e.target))close();},true);
  window.WriterCanvasControls={enhance,close};
})();
