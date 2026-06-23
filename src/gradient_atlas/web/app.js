const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const palettes = {
  spectrum: ['#3326a8','#126de0','#00c5cf','#56dc75','#f5e94b','#ff8a2b','#e9364f'],
  ocean: ['#152a5b','#175d8d','#2ca6a4','#a7d46f','#f2d15c'],
  magma: ['#251255','#7b1f70','#d33f5f','#f98e52','#f9e784'],
  mono: ['#13283b','#36566e','#7691a3','#c3ced4'],
  aurora: ['#102039','#244c95','#18a7c9','#65f3b5','#f7ff9b'],
  ember: ['#1c1028','#5f1f62','#c22f5d','#ff7a3d','#ffe08a'],
  twilight: ['#111827','#263a8b','#6b49c8','#d45fa3','#ffd6a5'],
  topo: ['#092a36','#0f6f73','#7bc96f','#f4d35e','#f76f53'],
  glacier: ['#081923','#123c69','#2c7da0','#8edce6','#f0fbff']
};
const terrainPresets = [
  {name:'Ngorongoro Crater',lat:-2.687,lon:35.584,radius:18,why:'Near-circular caldera rim surrounding a broad interior basin.'},
  {name:'Bromo–Tengger–Semeru',lat:-7.9425,lon:112.953,radius:22,why:'Nested caldera, volcanic cones, and strongly competing valleys.'},
  {name:'Mount Rinjani',lat:-8.411,lon:116.457,radius:20,why:'Crater lake, asymmetric rim, and a steep volcanic cone.'},
  {name:'Tongariro Volcanic Complex',lat:-39.1573,lon:175.632,radius:22,why:'Several neighbouring cones, saddles, craters, and drainage basins.'},
  {name:'Haleakalā',lat:20.7097,lon:-156.2533,radius:25,why:'A vast eroded summit depression cut by deep radial valleys.'},
  {name:'Crater Lake · Mount Mazama',lat:42.9446,lon:-122.109,radius:18,why:'A clean caldera ring with islands, rim peaks, and outer gullies.'},
  {name:'Mount St Helens',lat:46.1912,lon:-122.1944,radius:18,why:'Breached crater geometry creates a dramatic directional surface.'},
  {name:'Mount Etna',lat:37.751,lon:14.9934,radius:22,why:'Broad cone patterned with summit craters and radial erosion.'},
  {name:'Teide · Tenerife',lat:28.2724,lon:-16.6425,radius:24,why:'Central cone rising from the complex Las Cañadas caldera.'},
  {name:'Mount Fuji',lat:35.3606,lon:138.7274,radius:24,why:'Near-symmetric cone for clean, controlled trajectory comparisons.'},
  {name:'Yosemite Valley',lat:37.745,lon:-119.59,radius:22,why:'Deep glacial trough, sheer walls, domes, and tributary valleys.'},
  {name:'Grand Canyon',lat:36.1069,lon:-112.1129,radius:32,why:'Branching ravines and layered plateaus produce rich local structure.'},
  {name:'Bryce Canyon',lat:37.6283,lon:-112.1677,radius:18,why:'Scalloped amphitheatres divided by ridges and narrow drainages.'},
  {name:'Matterhorn · Zermatt',lat:45.9763,lon:7.6586,radius:18,why:'Pyramidal peak surrounded by glacial valleys and sharp cols.'},
  {name:'Aoraki · Mount Cook',lat:-43.595,lon:170.1418,radius:28,why:'Interlocking alpine ridges, glaciers, and deep troughs.'},
  {name:'Torres del Paine',lat:-50.9423,lon:-73.4068,radius:30,why:'Granite towers, cirques, lakes, and strongly separated valleys.'},
  {name:'Denali',lat:63.0695,lon:-151.0074,radius:35,why:'Huge multi-ridge massif with long glacial drainage systems.'},
  {name:'Machu Picchu · Urubamba',lat:-13.1631,lon:-72.545,radius:20,why:'A tight river meander enclosed by steep, intersecting ridges.'},
  {name:'Yr Wyddfa · Snowdon',lat:53.0685,lon:-4.0763,radius:15,why:'Compact glacial cwms and radiating ridgelines at poster-friendly scale.'},
  {name:'Mount Kilimanjaro',lat:-3.0674,lon:37.3556,radius:30,why:'Isolated massif with multiple summits and broad radial drainage.'}
];
let demFile = null, baseGrid = null, grid = null, starts = [], svgBlob = null, svgUrl = null;
let sourceType = 'map', selectedBounds = null, lastBounds = null, selectedPlace = '';
let naturalVerticalScale = null;
let rotation = 0, renderTimer = null, terrainTimer = null, terrainController = null;
let renderInFlight = false, renderPending = false, renderVersion = 0;
let suggestionController = null, gridVersion = 0;
const canvas = $('#terrainCanvas'), largeCanvas = $('#terrainCanvasLarge');

function setStatus(text, error=false) {
  $('#status').textContent = text;
  $('#status').classList.toggle('error', error);
}

function rotateGrid(source, turns) {
  let result=source;
  for(let turn=0;turn<turns;turn++) result=Array.from({length:result[0].length},(_,y)=>Array.from({length:result.length},(_,x)=>result[result.length-1-x][y]));
  return result;
}

function rotatePoint(point, turns) {
  let [u,v]=point;
  for(let turn=0;turn<turns;turn++) [u,v]=[1-v,u];
  return [u,v];
}

function setGrid(source, resetStarts=true) {
  baseGrid=source;gridVersion++;
  grid=rotateGrid(baseGrid,rotation/90);
  if(resetStarts) starts=[[.5,.5]];
  drawTerrain();
  $('#terrainShell').classList.remove('empty');
  $('.large-terrain-shell').classList.add('ready');
  $('#generate').disabled=false;
  $('#suggestStarts').disabled=false;
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

function applyTheme() {
  document.body.dataset.theme = $('#theme').value;
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

function aspectLabel(width,height) {
  const ratio=width/height,common=[[1,1],[2,3],[3,4],[4,5],[1,Math.SQRT2],[3,2],[4,3],[5,4]];
  const match=common.find(([a,b])=>Math.abs(ratio-a/b)<.012);
  return match?`${match[0]}:${match[1]}`:`${ratio.toFixed(2)}:1`;
}

function updatePrintHint() {
  const width=+$('#printWidth').value,height=+$('#printHeight').value;
  if(!width||!height)return;const format=value=>Number.isInteger(value)?String(value):value.toFixed(2).replace(/0+$/,'').replace(/\.$/,'');
  $('#printHint').textContent=`${format(width)} × ${format(height)} in · ${aspectLabel(width,height)} ${width>height?'landscape':width===height?'square':'portrait'} · vector SVG`;
}

function applyPrintPreset() {
  const value=$('#printPreset').value;if(value==='custom'){updatePrintHint();return}
  let [width,height]=value.split(',').map(Number);const landscape=$('#printOrientation').value==='landscape';
  if((landscape&&height>width)||(!landscape&&width>height))[width,height]=[height,width];
  $('#printWidth').value=width;$('#printHeight').value=height;updatePrintHint();scheduleRender(180);
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
  const dark=$('#theme').value==='dark';
  context.putImageData(image,0,0); context.fillStyle=dark?'rgba(7,16,25,.08)':'rgba(248,245,238,.08)';context.fillRect(0,0,w,h);
  context.strokeStyle=dark?'rgba(237,248,255,.42)':'rgba(255,255,255,.22)'; context.lineWidth=1;
  for(let i=0;i<=16;i++) {
    context.beginPath();context.moveTo(i*w/16,0);context.lineTo(i*w/16,h);context.stroke();
    context.beginPath();context.moveTo(0,i*h/16);context.lineTo(w,i*h/16);context.stroke();
  }
  starts.forEach((p,i) => {
    const scale=Math.max(1,w/800),x=p[0]*w,y=p[1]*h;context.beginPath();context.arc(x,y,12*scale,0,Math.PI*2);context.fillStyle=dark?'#071019':'#f8f5ee';context.fill();
    context.lineWidth=4*scale;context.strokeStyle=dark?'#edf8ff':'#17324d';context.stroke();context.fillStyle=dark?'#edf8ff':'#17324d';context.font=`bold ${13*scale}px ui-monospace`;context.fillText(String(i+1),x+18*scale,y+5*scale);
  });
}

function drawTerrain() {
  if (!grid) return;
  drawTerrainCanvas(canvas); drawTerrainCanvas(largeCanvas);
  $('#pointCount').textContent=`${starts.length} start point${starts.length===1?'':'s'}`;
  $('#largePointCount').textContent=$('#pointCount').textContent;
}

function acceptGrid(data, title, message) {
  demFile=null;setGrid(data.grid);if(title)$('#title').value=title.toUpperCase();setStatus(message);scheduleRender(120);
}

async function analyze(file) {
  demFile=file; sourceType='upload'; naturalVerticalScale=null; applyReliefMode(); $('#fileName').textContent=file.name;
  $('#title').value=file.name.replace(/\.[^.]+$/,'').replace(/[-_]+/g,' ').toUpperCase();
  $('#loading').classList.add('show'); $('#terrainShell').classList.remove('empty'); setStatus('Reading and normalizing the DEM…');
  terrainController?.abort();const controller=new AbortController();terrainController=controller;
  const form=new FormData();form.append('file',file);form.append('smoothing',$('#smoothing').value);form.append('resolution','96');
  try { const r=await fetch('/api/preview',{method:'POST',body:form,signal:controller.signal}), data=await r.json(); if(!r.ok)throw new Error(data.error);
    if(controller!==terrainController)return;setGrid(data.grid);setStatus('DEM ready · drag the centre start point or click to add another.');scheduleRender(120);
  } catch(e) { if(e.name==='AbortError')return;grid=null;baseGrid=null;$('#terrainShell').classList.add('empty');$('.large-terrain-shell').classList.remove('ready');$('#generate').disabled=true;$('#suggestStarts').disabled=true;setStatus(e.message,true); }
  finally { if(controller===terrainController)$('#loading').classList.remove('show'); }
}

async function fetchTerrain(bounds, title='') {
  lastBounds=bounds; sourceType='remote'; demFile=null; $('#loading').classList.add('show'); $('#terrainShell').classList.remove('empty');
  setStatus('Fetching and stitching global elevation tiles…');
  terrainController?.abort();const controller=new AbortController();terrainController=controller;
  try {
    const r=await fetch('/api/terrain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...bounds,smoothing:+$('#smoothing').value,resolution:96}),signal:controller.signal});
    const data=await r.json(); if(!r.ok)throw new Error(data.error);
    if(controller!==terrainController)return;
    naturalVerticalScale=data.metadata.natural_vertical_scale;applyReliefMode();
    acceptGrid(data,title,`Terrain ready · ${data.metadata.elevation_min}–${data.metadata.elevation_max} m · ${data.metadata.width_km}×${data.metadata.height_km} km · ${data.metadata.tiles} tile(s)`);
  } catch(e) { if(e.name==='AbortError')return;if(!grid)$('#terrainShell').classList.add('empty');setStatus(e.message,true); }
  finally { if(controller===terrainController)$('#loading').classList.remove('show'); }
}

function boundsObject(bounds) {return{north:bounds.getNorth(),south:bounds.getSouth(),east:bounds.getEast(),west:bounds.getWest()}}
function scheduleRegionFetch(delay=650) {
  clearTimeout(terrainTimer);terrainTimer=setTimeout(()=>{if(selectedBounds)fetchTerrain(boundsObject(selectedBounds),selectedPlace||'SELECTED TERRAIN')},delay);
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
  function useLayer(layer) { drawn.clearLayers(); drawn.addLayer(layer); selectedBounds=layer.getBounds(); $('#fetchMap').disabled=false;scheduleRegionFetch(); }
  terrainMap.on(L.Draw.Event.CREATED,e=>useLayer(e.layer));
  terrainMap.on(L.Draw.Event.EDITED,e=>e.layers.eachLayer(layer=>{selectedBounds=layer.getBounds();scheduleRegionFetch()}));
  terrainMap.on(L.Draw.Event.DELETED,()=>{selectedBounds=null;clearTimeout(terrainTimer);terrainController?.abort();$('#fetchMap').disabled=true});
  window.showPlace=(place)=>{
    selectedPlace=place.name.split(',')[0]; const lat=place.lat,lon=place.lon,dLat=.16,dLon=.16/Math.max(.25,Math.cos(lat*Math.PI/180));
    const layer=L.rectangle([[lat-dLat,lon-dLon],[lat+dLat,lon+dLon]],{color:'#e14b43',weight:2,fillOpacity:.12});useLayer(layer);
    terrainMap.fitBounds(layer.getBounds(),{padding:[12,12]});$('#searchResults').classList.remove('show');$('#title').value=selectedPlace.toUpperCase();
  };
  terrainPresets.forEach((preset,index)=>{const option=document.createElement('option');option.value=String(index);option.textContent=preset.name;$('#terrainPreset').appendChild(option)});
  $('#terrainPreset').onchange=()=>{
    if($('#terrainPreset').value==='')return;const preset=terrainPresets[+$('#terrainPreset').value];
    selectedPlace=preset.name;$('#title').value=preset.name.toUpperCase();$('#latitude').value=preset.lat;$('#longitude').value=preset.lon;$('#radius').value=preset.radius;$('#radiusOut').textContent=`${preset.radius} km`;$('#presetHint').textContent=preset.why;
    const dLat=preset.radius/111.32,dLon=preset.radius/(111.32*Math.max(.15,Math.cos(preset.lat*Math.PI/180)));
    const layer=L.rectangle([[preset.lat-dLat,preset.lon-dLon],[preset.lat+dLat,preset.lon+dLon]],{color:'#e14b43',weight:2,fillOpacity:.12});
    useLayer(layer);terrainMap.fitBounds(layer.getBounds(),{padding:[12,12]});
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
$('#fetchMap').onclick=()=>{if(!selectedBounds)return;clearTimeout(terrainTimer);fetchTerrain(boundsObject(selectedBounds),selectedPlace||'SELECTED TERRAIN')};

// Direct coordinate acquisition
$('#radius').oninput=e=>$('#radiusOut').textContent=`${e.target.value} km`;
$('#fetchCoords').onclick=()=>{
  const lat=+$('#latitude').value,lon=+$('#longitude').value,radius=+$('#radius').value;
  if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>85||Math.abs(lon)>180){setStatus('Enter valid latitude and longitude.',true);return}
  const dLat=radius/111.32,dLon=radius/(111.32*Math.max(.15,Math.cos(lat*Math.PI/180)));
  fetchTerrain({north:lat+dLat,south:lat-dLat,east:lon+dLon,west:lon-dLon},`TERRAIN ${lat.toFixed(3)}, ${lon.toFixed(3)}`);
};
let coordinateTimer=null;
['latitude','longitude','radius'].forEach(id=>$('#'+id).addEventListener('input',()=>{clearTimeout(coordinateTimer);coordinateTimer=setTimeout(()=>$('#fetchCoords').click(),700)}));

// Local upload
$('#demFile').addEventListener('change',e=>e.target.files[0]&&analyze(e.target.files[0]));
const dz=$('#dropzone');['dragenter','dragover'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.add('drag')}));
['dragleave','drop'].forEach(n=>dz.addEventListener(n,e=>{e.preventDefault();dz.classList.remove('drag')}));
dz.addEventListener('drop',e=>e.dataTransfer.files[0]&&analyze(e.dataTransfer.files[0]));

function addStartFromCanvas(e){if(!grid)return;const r=e.currentTarget.getBoundingClientRect();starts.push([(e.clientX-r.left)/r.width,(e.clientY-r.top)/r.height]);drawTerrain();scheduleRender()}
canvas.addEventListener('click',addStartFromCanvas);largeCanvas.addEventListener('click',addStartFromCanvas);
$('#undoStart').onclick=()=>{starts.pop();drawTerrain();scheduleRender()};$('#clearStarts').onclick=()=>{starts=[];drawTerrain();scheduleRender()};
$('#largeUndo').onclick=$('#undoStart').onclick;$('#largeClear').onclick=$('#clearStarts').onclick;

$('#suggestStarts').onclick=async()=>{
  if(!grid)return;const methods=$$('#optimizers input:checked').map(input=>input.value);
  if(methods.length<2){setStatus('Select at least two optimizers to find disagreement.',true);return}
  suggestionController?.abort();const controller=new AbortController();suggestionController=controller;const version=gridVersion;
  const button=$('#suggestStarts');button.disabled=true;button.textContent='Scanning terrain…';setStatus('Finding starts where optimizer paths diverge most…');
  try {
    const response=await fetch('/api/suggest-starts',{method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,body:JSON.stringify({grid,optimizers:methods,steps:+$('#steps').value,step_length:+$('#stepLength').value,objective:$('#objective').value,count:+$('#suggestCount').value})});
    const data=await response.json();if(!response.ok)throw new Error(data.error);if(version!==gridVersion||controller!==suggestionController)return;
    starts=data.starts;drawTerrain();setStatus(`Placed ${starts.length} high-disagreement start point${starts.length===1?'':'s'}.`);scheduleRender(80);
  } catch(error){if(error.name!=='AbortError')setStatus(error.message,true)}
  finally{if(controller===suggestionController){button.disabled=false;button.textContent='Find high-disagreement starts'}}
};

$('#expandTerrain').onclick=()=>{const dialog=$('#terrainDialog');dialog.showModal();requestAnimationFrame(drawTerrain)};
$('#expandArtwork').onclick=()=>{if(!svgUrl)return;$('#largeArtworkTitle').textContent=$('#title').value||'Generated artwork';$('#artDialog').showModal()};
$$('[data-close]').forEach(button=>button.onclick=()=>$('#'+button.dataset.close).close());
$('#steps').oninput=e=>{$('#stepsOut').value=e.target.value;scheduleRender()};
$('#stepLength').oninput=e=>{$('#stepLengthOut').value=`${(+e.target.value).toFixed(2)}×`;scheduleRender()};
$('#palette').onchange=()=>{updateStrip();scheduleRender()};updateStrip();
$('#theme').onchange=()=>{applyTheme();scheduleRender(120)};applyTheme();
$('#reliefMode').onchange=()=>{applyReliefMode();scheduleRender()};
$('#heightScale').oninput=()=>{$('#reliefMode').value='manual';applyReliefMode();scheduleRender()};applyReliefMode();
$('#objective').onchange=()=>{const mode=$('#objective').value;$('#generate span').textContent=`Generate ${mode} artwork`;scheduleRender(120)};
$('#smoothing').addEventListener('change',()=>{clearTimeout(terrainTimer);terrainTimer=setTimeout(()=>{if(demFile)analyze(demFile);else if(lastBounds)fetchTerrain(lastBounds,$('#title').value)},450)});
$('#tileRotation').onchange=()=>{const next=+$('#tileRotation').value,turns=((next-rotation)/90+4)%4;rotation=next;starts=starts.map(point=>rotatePoint(point,turns));if(baseGrid){grid=rotateGrid(baseGrid,rotation/90);gridVersion++}drawTerrain();scheduleRender(120)};
$('#printPreset').onchange=applyPrintPreset;
$('#printOrientation').onchange=()=>{let width=+$('#printWidth').value,height=+$('#printHeight').value;const landscape=$('#printOrientation').value==='landscape';if((landscape&&height>width)||(!landscape&&width>height)){[$('#printWidth').value,$('#printHeight').value]=[height,width]}updatePrintHint();scheduleRender(180)};
['printWidth','printHeight'].forEach(id=>$('#'+id).addEventListener('input',()=>{$('#printPreset').value='custom';updatePrintHint();scheduleRender()}));
['trajectoryStyle','lines','fillOpacity'].forEach(id=>$('#'+id).addEventListener('input',()=>scheduleRender()));
$('#title').addEventListener('input',()=>scheduleRender(500));
$$('#optimizers input').forEach(input=>input.addEventListener('change',()=>scheduleRender(120)));

function config(){return{title:$('#title').value||'UNTITLED DEM',objective:$('#objective').value,steps:+$('#steps').value,step_length:+$('#stepLength').value,trajectory_style:$('#trajectoryStyle').value,theme:$('#theme').value,print_width:+$('#printWidth').value,print_height:+$('#printHeight').value,start_points:starts.length?starts:[[.5,.5]],optimizers:$$('#optimizers input:checked').map(x=>x.value),palette:$('#palette').value,smoothing:+$('#smoothing').value,grid_lines:+$('#lines').value,vertical_scale:+$('#heightScale').value,fill_opacity:+$('#fillOpacity').value,auto_fit:true,surface_top:90}}

function scheduleRender(delay=320) {
  if(!grid)return;renderVersion++;clearTimeout(renderTimer);
  if(renderInFlight){renderPending=true;return}
  const version=renderVersion;renderTimer=setTimeout(()=>renderArtwork(version),delay);
}

async function renderArtwork(version=++renderVersion){
  if(!grid)return;if(!$$('#optimizers input:checked').length){setStatus('Select at least one optimizer.',true);return}
  if(renderInFlight){renderPending=true;return}clearTimeout(renderTimer);renderInFlight=true;
  const button=$('#generate');button.disabled=true;button.querySelector('span').textContent='Generating…';setStatus('Projecting terrain and tracing optimizer paths…');
  const form=new FormData();form.append('grid',JSON.stringify(grid));form.append('config',JSON.stringify(config()));
  try {const r=await fetch('/api/render',{method:'POST',body:form});if(!r.ok){const d=await r.json();throw new Error(d.error)}const blob=await r.blob();if(version!==renderVersion)return;svgBlob=blob;if(svgUrl)URL.revokeObjectURL(svgUrl);svgUrl=URL.createObjectURL(svgBlob);$('#artPreview').src=svgUrl;$('#artPreviewLarge').src=svgUrl;$('#artShell').classList.remove('empty');$('.large-art-shell').classList.add('ready');$('#downloadSvg').disabled=$('#downloadPng').disabled=$('#expandArtwork').disabled=false;setStatus('Artwork updated automatically. SVG is print-ready and fully editable.')}
  catch(e){setStatus(e.message,true)}finally{renderInFlight=false;button.disabled=false;button.querySelector('span').textContent=`Generate ${$('#objective').value} artwork`;if(renderPending||version!==renderVersion){renderPending=false;const latest=renderVersion;renderTimer=setTimeout(()=>renderArtwork(latest),80)}}
}
$('#generate').onclick=()=>{clearTimeout(renderTimer);renderVersion++;renderArtwork(renderVersion)};

function download(blob,name){const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
function slug(){return($('#title').value||'dem-art').toLowerCase().replace(/[^a-z0-9]+/g,'-')}
$('#downloadSvg').onclick=()=>svgBlob&&download(svgBlob,`${slug()}.svg`);
$('#downloadPng').onclick=()=>{if(!svgUrl)return;const img=new Image();img.onload=()=>{const dpi=200,maxPixels=40_000_000,width=+$('#printWidth').value,height=+$('#printHeight').value;let pixelWidth=Math.round(width*dpi),pixelHeight=Math.round(height*dpi);const scale=Math.min(1,Math.sqrt(maxPixels/(pixelWidth*pixelHeight)));pixelWidth=Math.round(pixelWidth*scale);pixelHeight=Math.round(pixelHeight*scale);const c=document.createElement('canvas');c.width=pixelWidth;c.height=pixelHeight;c.getContext('2d').drawImage(img,0,0,c.width,c.height);c.toBlob(b=>download(b,`${slug()}-${width}x${height}in.png`),'image/png')};img.src=svgUrl};
$('#largeDownloadSvg').onclick=$('#downloadSvg').onclick;$('#largeDownloadPng').onclick=$('#downloadPng').onclick;
