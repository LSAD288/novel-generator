/* Small SVG ink/eraser geometry. Pointer pressure follows W3C Pointer Events;
   no hardware pressure is invented for a mouse. All coordinates are world units. */
(function(root,factory){const api=factory(typeof module==='object'&&module.exports?require('./vendor/perfect-freehand.js'):root.PerfectFreehand);if(typeof module==='object'&&module.exports)module.exports=api;else root.WriterCanvasInk=api;})(globalThis,(Freehand)=>{
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)), EPS=1e-7;
 const color=v=>['auto','red','amber','green','blue','violet'].includes(v)||/^#[0-9a-f]{6}$/i.test(v||'')?v:'auto';
 const point=(x,y)=>({x,y});
 function pressure(event){return event.pointerType==='pen'?clamp(Number(event.pressure)||.05,.05,1):1;}
 function outline(stroke){const p=stroke.points,n=p.length;if(!n)return '';const size=Math.max(.5,stroke.width||2.4),left=[],right=[];if(stroke.brush==='crayon')return crayon(stroke);if(stroke.brush==='brush'&&n>1)return brush(stroke);
  for(let i=0;i<n;i++){const before=p[Math.max(0,i-1)],after=p[Math.min(n-1,i+1)],dx=after.x-before.x,dy=after.y-before.y,len=Math.hypot(dx,dy)||1,pr=stroke.pressureEnabled===false?1:1-(stroke.pressureStrength??.75)*(1-clamp(stroke.pressures?.[i]??1,.05,1)),taper=stroke.brush==='brush'?Math.min(1,(i+1)/3,(n-i)/3):1,r=size/2*pr*taper*(stroke.brush==='crayon'?1.25:1);left.push(point(p[i].x-dy/len*r,p[i].y+dx/len*r));right.push(point(p[i].x+dy/len*r,p[i].y-dx/len*r));}
  if(n===1){const pr=stroke.pressureEnabled===false?1:1-(stroke.pressureStrength??.75)*(1-clamp(stroke.pressures?.[0]??1,.05,1)),r=size/2*pr*(stroke.brush==='crayon'?1.25:1);return `M ${p[0].x-r} ${p[0].y} a ${r} ${r} 0 1 0 ${r*2} 0 a ${r} ${r} 0 1 0 ${-r*2} 0`;}
  return 'M '+left.concat(right.reverse()).map(v=>`${v.x} ${v.y}`).join(' L ')+' Z';
 }
 // perfect-freehand supplies only the rendered outline; original points/pressure still own saving and erasing.
 function brush(stroke){
  const size=Math.max(.5,stroke.width||2.4),points=Freehand.getStroke(stroke.points.map((p,i)=>[p.x,p.y,stroke.pressures?.[i]??1]),{size,thinning:stroke.pressureEnabled===false?0:stroke.pressureStrength??.75,simulatePressure:false,smoothing:.65,streamline:.2,start:{cap:true,taper:0},end:{cap:false,taper:size*2},last:true});
  if(!points.length)return '';const f=v=>Number(v.toFixed(2));
  return `M ${f(points[0][0])} ${f(points[0][1])} Q `+points.map((p,i)=>{const next=points[(i+1)%points.length];return `${f(p[0])} ${f(p[1])} ${f((p[0]+next[0])/2)} ${f((p[1]+next[1])/2)}`;}).join(' ')+' Z';
 }
 // SVG particle stamps inspired by fabric-brush's CrayonBrush; no Fabric runtime or upstream code.
 // Stable randomness preserves texture across repaints, theme changes, undo and reload.
 function crayon(stroke){
  const pts=stroke.points,size=Math.max(.5,stroke.width||2.4)*1.25;
  let seed=(Math.round(pts[0].x*100)^Math.round(pts[0].y*100)^Math.round(size*100))>>>0;
  const random=()=>((seed=(Math.imul(seed,1664525)+1013904223)>>>0)/4294967296),length=pts.reduce((s,p,i)=>s+(i?Math.hypot(p.x-pts[i-1].x,p.y-pts[i-1].y):0),0),density=Math.max(3,Math.min(8,Math.ceil(size/3))),step=Math.max(.6,size*.16,length*density/3000),d=[];
  let walked=0,next=0;
  const stamp=(x,y,pressure)=>{
   const radius=size/2*(stroke.pressureEnabled===false?1:1-(stroke.pressureStrength??.75)*(1-pressure));
   for(let k=0;k<density;k++){const angle=random()*Math.PI*2,r=Math.sqrt(random())*radius,w=Math.max(.35,size*(.035+random()*.06)),h=w*(.5+random()),px=x+Math.cos(angle)*r,py=y+Math.sin(angle)*r;d.push(`M ${(px-w/2).toFixed(2)} ${(py-h/2).toFixed(2)} h ${w.toFixed(2)} v ${h.toFixed(2)} h ${(-w).toFixed(2)} Z`);}
  };
  if(pts.length===1)stamp(pts[0].x,pts[0].y,stroke.pressures?.[0]??1);
  for(let i=1;i<pts.length;i++){
   const a=pts[i-1],b=pts[i],len=Math.hypot(b.x-a.x,b.y-a.y);if(!len)continue;
   for(;next<=walked+len;next+=step){const t=clamp((next-walked)/len,0,1),pa=stroke.pressures?.[i-1]??1,pb=stroke.pressures?.[i]??1;stamp(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,pa+(pb-pa)*t);}walked+=len;
  }
  if(!d.length)stamp(pts[0].x,pts[0].y,stroke.pressures?.[0]??1);return d.join(' ');
 }
 function dot(a,b){return a.x*b.x+a.y*b.y;}
 function lerp(a,b,t){return point(a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t);}
 function circleInterval(a,b,c,r){const d=point(b.x-a.x,b.y-a.y),f=point(a.x-c.x,a.y-c.y),A=dot(d,d);if(A<EPS)return dot(f,f)<=r*r?[0,1]:null;const B=2*dot(f,d),C=dot(f,f)-r*r,D=B*B-4*A*C;if(D<0)return null;const lo=Math.max(0,(-B-Math.sqrt(D))/(2*A)),hi=Math.min(1,(-B+Math.sqrt(D))/(2*A));return lo<=hi?[lo,hi]:null;}
 function rectInterval(a,b,rect){let lo=0,hi=1;for(const [start,delta,min,max]of [[a.x,b.x-a.x,rect.x1,rect.x2],[a.y,b.y-a.y,rect.y1,rect.y2]]){if(Math.abs(delta)<EPS){if(start<min||start>max)return null;}else{const t1=(min-start)/delta,t2=(max-start)/delta;lo=Math.max(lo,Math.min(t1,t2));hi=Math.min(hi,Math.max(t1,t2));if(lo>hi)return null;}}return [lo,hi];}
 function capsuleInterval(a,b,c,d,r){const dx=d.x-c.x,dy=d.y-c.y,L=Math.hypot(dx,dy);if(L<EPS)return circleInterval(a,b,c,r);const local=p=>point(((p.x-c.x)*dx+(p.y-c.y)*dy)/L,(-(p.x-c.x)*dy+(p.y-c.y)*dx)/L),parts=[circleInterval(a,b,c,r),circleInterval(a,b,d,r),rectInterval(local(a),local(b),{x1:0,x2:L,y1:-r,y2:r})].filter(Boolean);return parts.length?[Math.min(...parts.map(p=>p[0])),Math.max(...parts.map(p=>p[1]))]:null;}
 function hit(stroke,a,b,r){if(stroke.points.length===1)return !!capsuleInterval(stroke.points[0],stroke.points[0],a,b,r+(stroke.width||2)/2);return stroke.points.some((p,i)=>i&&capsuleInterval(stroke.points[i-1],p,a,b,r+(stroke.width||2)/2));}
 function split(stroke,a,b,r,idFactory){const pts=stroke.points,ps=stroke.pressures||pts.map(()=>1),chunks=[];let current=[],pressures=[];const append=(p,pr)=>{const last=current.at(-1);if(!last||Math.hypot(last.x-p.x,last.y-p.y)>EPS){current.push({...p});pressures.push(pr);}};const finish=()=>{if(current.length)chunks.push({points:current,pressures});current=[];pressures=[];};
  if(pts.length===1)return hit(stroke,a,b,r)?[]:[stroke];
  for(let i=1;i<pts.length;i++){const x=pts[i-1],y=pts[i],cut=capsuleInterval(x,y,a,b,r+(stroke.width||2)/2),pr=t=>(ps[i-1]??1)+((ps[i]??1)-(ps[i-1]??1))*t;if(!cut){append(x,pr(0));append(y,pr(1));continue;}if(cut[0]>EPS){append(x,pr(0));append(lerp(x,y,cut[0]),pr(cut[0]));}finish();if(cut[1]<1-EPS){append(lerp(x,y,cut[1]),pr(cut[1]));append(y,pr(1));}}
  finish();return chunks.map((c,i)=>({...stroke,id:i===0?stroke.id:idFactory(),...c}));
 }
 function erase(strokes,a,b,r,mode,idFactory=()=>`stroke-${crypto.randomUUID()}`){const out=[];for(const stroke of strokes){if(!hit(stroke,a,b,r)){out.push(stroke);continue;}if(mode==='point')out.push(...split(stroke,a,b,r,idFactory));}return out;}
 function eraseRect(strokes,a,b){const rect={x1:Math.min(a.x,b.x),x2:Math.max(a.x,b.x),y1:Math.min(a.y,b.y),y2:Math.max(a.y,b.y)};return strokes.filter(s=>!s.points.some((p,i)=>rectInterval(i?s.points[i-1]:p,p,rect)));}
 return {color,pressure,outline,capsuleInterval,erase,eraseRect};
});
