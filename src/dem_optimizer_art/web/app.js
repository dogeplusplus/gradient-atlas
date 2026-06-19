const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const palettes = {
  spectrum: ['#3326a8','#126de0','#00c5cf','#56dc75','#f5e94b','#ff8a2b','#e9364f'],
  ocean: ['#152a5b','#175d8d','#2ca6a4','#a7d46f','#f2d15c'],
  magma: ['#251255','#7b1f70','#d33f5f','#f98e52','#f9e784'],
  mono: ['#13283b','#36566e','#7691a3','#c3ced4']
};
let demFile = null, grid = null, starts = [], svgBlob = null, svgUrl = null;
let sourceType = 'map', selectedBounds = null, lastBounds = null, selectedPlace = '';
let naturalVerticalScale = null;
const canvas = $('#terrainCanvas'), largeCanvas = $('#terrainCanvasLarge');

function setStatus(text, error=false) {
  $('#status').textContent = text;
  $('#status').classList.toggle('error', error);
}

function paletteColor(t) {
  const p = palettes[$('#palette').value], v = Math.max(0, Math.min(.9999, t)) * (p.length - 1);
  const i = Math.floor(v), f = v - i;
  const a = p[i].match(/\w\w/g).map(x => parseInt(x, 16));
  const b = p[i+1].match(/\w\w/g).map(x => parseInt(x, 16));
  return `rgb(${a.map((x,k) => Math.round(x + (b[k]-x)*f)).join(',')})`;
}

function updateStrip() {
  $('#paletteStrip').style.background = `linear-gradient(90deg,${palettes[$('#palette').value].join(',')})`;
  if (grid) drawTerrain();
}

function applyReliefMode() {
  const mode=$('#reliefMode').value, base=naturalVerticalScale ?? .31;
  if(mode==='natural') $('#heightScale').value=base.toFixed(2);
  if(mode==='subtle') $('#heightScale').value=Math.min(1.2,base*1.45).toFixed(2);
  if(mode==='dramatic') $('#heightScale').value=Math.min(1.6,base*3).toFixed(2);
  const labels={natural:'Natural aspect uses measured elevation relative to map width.',subtle:'Subtle boost uses 1.45× the terrain\'s physical relief.',dramatic:'Dramatic uses 3× physical relief.',manual:'Manual keeps the height scale you enter.'};
  $('#reliefHint').textContent=labels[mode];
}

function drawTerrainCanvas(target) {
  const context=target.getContext('2d'), w=target.width, h=target.height, gh=grid.length, gw=grid[0].length, image=context.createImageData(w,h);
  for (let y=0; y<h; y++) {
    const row=grid[Math.floor(y/h*gh)];
    for (let x=0; x<w; x++) {
      const z=row[Math.floor(x/w*gw)], rgb=paletteColor((z+1.8)/3.6).match(/\d+/g).map(Number), o=(y*w+x)*4;
      image.data[o]=rgb[0]; image.data[o+1]=rgb[1]; image.data[o+2]=rgb[2]; image.data[o+3]=210;
    }
  }
  context.putImageData(image,0,0); context.strokeStyle='rgba(255,255,255,.22)'; context.lineWidth=1;
  for(let i=0;i<=16;i++) {
    context.beginPath();context.moveTo(i*w/16,0);context.lineTo(i*w/16,h);context.stroke();
    context.beginPath();context.moveTo(0,i*h/16);context.lineTo(w,i*h/16);context.stroke();
  }
  starts.forEach((p,i) => {
    const scale=Math.max(1,w/800),x=p[0]*w,y=p[1]*h;context.beginPath();context.arc(x,y,12*scale,0,Math.PI*2);context.fillStyle='#f8f5ee';context.fill();
    context.lineWidth=4*scale;context.strokeStyle='#17324d';context.stroke();context.fillStyle='#17324d';context.font=`bold ${13*scale}px ui-monospace`;context.fillText(String(i+1),x+18*scale,y+5*scale);
  });
}

function drawTerrain() {
  if (!grid) return;
  drawTerrainCanvas(canvas); drawTerrainCanvas(largeCanvas);
  $('#pointCount').textContent=`${starts.length} start point${starts.length===1?'':'s'}`;
  $('#largePointCount').textContent=$('#pointCount').textContent;
}

function acceptGrid(data, title, message) {
  grid=data.grid; demFile=null; starts=[]; drawTerrain(); $('#terrainShell').classList.remove('empty');
  $('.large-terrain-shell').classList.add('ready');
  $('#generate').disabled=false; if(title) $('#title').value=title.toUpperCase(); setStatus(message);
}

async function analyze(file) {
  demFile=file; sourceType='upload'; naturalVerticalScale=null; applyReliefMode(); $('#fileName').textContent=file.name;
  $('#title').value=file.name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' ').toUpperCase();
  $('#loading').classList.add('show'); $('#terrainShell').classList.remove('empty'); setStatus('Reading and normalizing the DEM…');
  const form=new FormData();form.append('file',file);form.append('smoothing',$('#smoothing').value);form.append('resolution','96');
  try { const r=await fetch('/api/preview',{method:'POST',body:form}), data=await r.json(); if(!r.ok)throw new Error(data.error);
    grid=data.grid;starts=[];drawTerrain();$('.large-terrain-shell').classList.add('ready');$('#generate').disabled=false;setStatus('DEM ready. Click the terrain to place a start point.');
  } catch(e) { grid=null;$('#terrainShell').classList.add('empty');$('.large-terrain-shell').classList.remove('ready');$('#generate').disabled=true;setStatus(e.message,true); }
  finally { $('#loading').classList.remove('show'); }
}

async function fetchTerrain(bounds, title='') {
  lastBounds=bounds; sourceType='remote'; demFile=null; $('#loading').classList.add('show'); $('#terrainShell').classList.remove('empty');
  setStatus('Fetching and stitching global elevation tiles…');
  try {
    const r=await fetch('/api/terrain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...bounds,smoothing:+$('#smoothing').value,resolution:96})});
    const data=await r.json(); if(!r.ok)throw new Error(data.error);
    naturalVerticalScale=data.metadata.natural_vertical_scale;applyReliefMode();
    acceptGrid(data,title,`Terrain ready · ${data.metadata.elevation_min}–${data.metadata.elevation_max} m · ${data.metadata.width_km}×${data.metadata.height_km} km · ${data.metadata.tiles} tile(s)`);
  } catch(e) { if(!grid)$('#terrainShell').classList.add('empty');setStatus(e.message,true); }
  finally { $('#loading').classList.remove('show'); }
}

// Source selector
$$('.source-tabs button').forEach(button => button.addEventListener('click', () => {
  sourceType=button.dataset.source; $$('.source-tabs button').forEach(x=>x.classList.toggle('active',x===button));
  $$('.source-panel').forEach(x=>x.classList.toggle('active',x.id===`source-${sourceType}`));
  if(sourceType==='map' && window.terrainMap)setTimeout(()=>terrainMap.invalidateSize(),0);
}));

// Leaflet place search and rectangle selection
if (window.L) {
  window.terrainMap=L.map('map',{zoomControl:true}).setView([20,0],2);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'© OpenStreetMap contributors'}).addTo(terrainMap);
  const drawn=new L.FeatureGroup().addTo(terrainMap);
  terrainMap.addControl(new L.Control.Draw({position:'topright',edit:{featureGroup:drawn,remove:true},draw:{polyline:false,polygon:false,circle:false,circlemarker:false,marker:false,rectangle:{shapeOptions:{color:'#e14b43',weight:2,fillOpacity:.12}}}}));
  function useLayer(layer) { drawn.clearLayers(); drawn.addLayer(layer); selectedBounds=layer.getBounds(); $('#fetchMap').disabled=false; }
  terrainMap.on(L.Draw.Event.CREATED,e=>useLayer(e.layer));
  terrainMap.on(L.Draw.Event.EDITED,e=>e.layers.eachLayer(layer=>{selectedBounds=layer.getBounds()}));
  terrainMap.on(L.Draw.Event.DELETED,()=>{selectedBounds=null;$('#fetchMap').disabled=true});
  window.showPlace=(place)=>{
    selectedPlace=place.name.split(',')[0]; const lat=place.lat,lon=place.lon,dLat=.16,dLon=.16/Math.max(.25,Math.cos(lat*Math.PI/180));
    const layer=L.rectangle([[lat-dLat,lon-dLon],[lat+dLat,lon+dLon]],{color:'#e14b43',weight:2,fillOpacity:.12});useLayer(layer);
    terrainMap.fitBounds(layer.getBounds(),{padding:[12,12]});$('#searchResults').classList.remove('show');$('#title').value=selectedPlace.toUpperCase();
  };
}

$('#searchPlace').onclick=async()=>{
  const q=$('#placeSearch').value.trim();if(!q)return;const box=$('#searchResults');box.innerHTML='<button disabled>Searching…</button>';box.classList.add('show');
  try {const r=await fetch(`/api/search?q=${encodeURIComponent(q)}`),data=await r.json();if(!r.ok)throw new Error(data.error);
    box.innerHTML=data.results.length?'':'<button disabled>No places found</button>';
    data.results.forEach(place=>{const b=document.createElement('button');b.textContent=place.name;b.onclick=()=>showPlace(place);box.appendChild(b)});
  } catch(e){box.innerHTML=`<button disabled>${e.message}</button>`}
};
$('#placeSearch').addEventListener('keydown',e=>{if(e.key==='Enter')$('#searchPlace').click()});
$('#fetchMap').onclick=()=>{if(!selectedBounds)return;fetchTerrain({north:selectedBounds.getNorth(),south:selectedBounds.getSouth(),east:selectedBounds.getEast(),west:selectedBounds.getWest()},selectedPlace||'SELECTED TERRAIN')};

// Direct coordinate acquisition
$('#radius').oninput=e=>$('#radiusOut').textContent=`${e.target.value} km`;
$('#fetchCoords').onclick=()=>{
  const lat=+$('#latitude').value,lon=+$('#longitude').value,radius=+$('#radius').value;
  if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>85||Math.abs(lon)>180){setStatus('Enter valid latitude and longitude.',true);return}
  const dLat=radius/111.32,dLon=radius/(111.32*Math.max(.15,Math.cos(lat*Math.PI/180)));
  fetchTerrain({north:lat+dLat,south:lat-dLat,east:lon+dLon,west:lon-dLon},`TERRAIN ${lat.toFixed(3)}, ${lon.toFixed(3)}`);
};

// Local upload
$('#demFile').addEventListener('change',e=>e.target.files[0]&&analyze(e.target.files[0]));
const dz=$('#dropzone');['dragenter','dragover'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.add('drag')}));
['dragleave','drop'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.remove('drag')}));
dz.addEventListener('drop',e=>e.dataTransfer.files[0]&&analyze(e.dataTransfer.files[0]));

function addStartFromCanvas(e){if(!grid)return;const r=e.currentTarget.getBoundingClientRect();starts.push([(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]);drawTerrain()}
canvas.addEventListener('click',addStartFromCanvas);largeCanvas.addEventListener('click',addStartFromCanvas);
$('#undoStart').onclick=()=>{starts.pop();drawTerrain()};$('#clearStarts').onclick=()=>{starts=[];drawTerrain()};
$('#largeUndo').onclick=$('#undoStart').onclick;$('#largeClear').onclick=$('#clearStarts').onclick;

$('#expandTerrain').onclick=()=>{const dialog=$('#terrainDialog');dialog.showModal();requestAnimationFrame(drawTerrain)};
$('#expandArtwork').onclick=()=>{if(!svgUrl)return;$('#largeArtworkTitle').textContent=$('#title').value||'Generated artwork';$('#artDialog').showModal()};
$$('[data-close]').forEach(button=>button.onclick=()=>$('#'+button.dataset.close).close());
$('#steps').oninput=e=>$('#stepsOut').value=e.target.value;$('#palette').onchange=updateStrip;updateStrip();
$('#reliefMode').onchange=applyReliefMode;$('#heightScale').oninput=()=>{$('#reliefMode').value='manual';applyReliefMode()};applyReliefMode();
$('#smoothing').addEventListener('change',()=>{if(demFile)analyze(demFile);else if(lastBounds)fetchTerrain(lastBounds,$('#title').value)});

function config(){return{title:$('#title').value||'UNTITLED DEM',steps:+$('#steps').value,start_points:starts.length?starts:[[.5,.5]],optimizers:$$('#optimizers input:checked').map(x=>x.value),palette:$('#palette').value,smoothing:+$('#smoothing').value,grid_lines:+$('#lines').value,vertical_scale:+$('#heightScale').value,fill_opacity:+$('#fillOpacity').value,auto_fit:true,surface_top:90,surface_bottom:1185}}

$('#generate').onclick=async()=>{
  if(!grid)return;if(!$$('#optimizers input:checked').length){setStatus('Select at least one optimizer.',true);return}
  const button=$('#generate');button.disabled=true;button.querySelector('span').textContent='Generating…';setStatus('Projecting terrain and tracing optimizer paths…');
  const form=new FormData();if(demFile){form.append('file',demFile);form.append('smoothing',$('#smoothing').value);form.append('resolution','96')}else form.append('grid',JSON.stringify(grid));form.append('config',JSON.stringify(config()));
  try {const r=await fetch('/api/render',{method:'POST',body:form});if(!r.ok){const d=await r.json();throw new Error(d.error)}svgBlob=await r.blob();if(svgUrl)URL.revokeObjectURL(svgUrl);svgUrl=URL.createObjectURL(svgBlob);$('#artPreview').src=svgUrl;$('#artPreviewLarge').src=svgUrl;$('#artShell').classList.remove('empty');$('.large-art-shell').classList.add('ready');$('#downloadSvg').disabled=$('#downloadPng').disabled=$('#expandArtwork').disabled=false;setStatus('Artwork generated. SVG is print-ready and fully editable.')}
  catch(e){setStatus(e.message,true)}finally{button.disabled=false;button.querySelector('span').textContent='Generate artwork'}
};

function download(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function slug(){return($('#title').value||'dem-art').toLowerCase().replace(/[^a-z0-9]+/g,'-')}
$('#downloadSvg').onclick=()=>svgBlob&&download(svgBlob,`${slug()}.svg`);
$('#downloadPng').onclick=()=>{if(!svgUrl)return;const img=new Image();img.onload=()=>{const c=document.createElement('canvas');c.width=2400;c.height=3200;c.getContext('2d').drawImage(img,0,0,c.width,c.height);c.toBlob(b=>download(b,`${slug()}.png`),'image/png')};img.src=svgUrl};
$('#largeDownloadSvg').onclick=$('#downloadSvg').onclick;$('#largeDownloadPng').onclick=$('#downloadPng').onclick;
