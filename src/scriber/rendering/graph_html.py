"""Interactive HTML graph renderer (audit-contract implementation).

Implements the full vision from audit.html:
- Multiple gravitational centers: per-component gravity (union-find) +
  forceCluster per top-level directory, NO global center force → uncorrelated
  components (e.g. Rust vs Python) separate naturally.
- Radial/hierarchical layout: hub nodes (max in-degree) sit at the cloud
  center, leaves (entrypoints) at the periphery; dependency depth drives the
  initial radius.
- Weight/confidence-aware springs (weak relations = looser).
- Map-class UI: inertial panning, zoom %, search, minimap, keyboard nav,
  hover tooltip.

Self-contained, dependency-free, works offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scriber.graph.model import RelationGraph


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #060814;
  --panel: rgba(13, 20, 38, 0.78);
  --border: rgba(255, 255, 255, 0.08);
  --border-focus: rgba(94, 234, 212, 0.4);
  --txt: #f1f5f9;
  --txt-mute: #94a3b8;
  --txt-dark: #0f172a;
  --acc: #2dd4bf;
  --acc-glow: rgba(45, 212, 191, 0.25);
  --acc2: #38bdf8;
  --acc2-glow: rgba(56, 189, 248, 0.25);
  --good: #4ade80;
  --good-glow: rgba(74, 222, 128, 0.2);
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:var(--font-sans);background:var(--bg);color:var(--txt);overflow:hidden}
/* Themed scrollbars */
*{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,0.15) transparent}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.15);border-radius:4px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,0.3)}

canvas#main{position:fixed;inset:0;display:block;width:100vw;height:100vh;cursor:grab;z-index:1}
canvas#main.dragging{cursor:grabbing}
canvas#main.panning{cursor:grabbing}

.sidebar {
  position: fixed;
  top: 20px;
  left: 20px;
  bottom: 20px;
  width: 350px;
  z-index: 20;
  background: var(--panel);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0,0,0,0.55);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  pointer-events: auto;
}

.brand-section {
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  gap: 14px;
}
.brand-logo {
  height: 80px;
  width: auto;
  filter: drop-shadow(0 0 12px var(--acc-glow));
}
.brand-name-svg {
  height: 28px;
  width: auto;
  margin-bottom: 2px;
}
.brand-text h1 {
  font-size: 16px;
  font-weight: 700;
  color: var(--txt);
  letter-spacing: -0.01em;
}
.brand-text .sub {
  font-size: 10px;
  color: var(--txt-mute);
  font-family: var(--font-mono);
  margin-top: 1px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  border-bottom: 1px solid var(--border);
  background: rgba(0,0,0,0.15);
}
.stat-box {
  padding: 10px 4px;
  text-align: center;
  border-right: 1px solid var(--border);
}
.stat-box:last-child {
  border-right: none;
}
.stat-box .lbl {
  font-size: 8px;
  color: var(--txt-mute);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
}
.stat-box .v {
  font-size: 14px;
  font-weight: 700;
  color: var(--txt);
  font-family: var(--font-mono);
  margin-top: 2px;
}
.stat-box .v.good {
  color: var(--good);
  text-shadow: 0 0 8px var(--good-glow);
}

.controls-section {
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.search-wrapper {
  position: relative;
}
.search-input {
  width: 100%;
  background: rgba(0,0,0,0.25);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--txt);
  padding: 8px 12px;
  font-size: 12px;
  font-family: var(--font-mono);
  transition: all 0.2s ease;
}
.search-input:focus {
  outline: none;
  border-color: var(--acc);
  box-shadow: 0 0 0 2px var(--acc-glow);
  background: rgba(0,0,0,0.35);
}

.search-suggestions {
  position: absolute;
  top: 105%;
  left: 0;
  right: 0;
  background: #0d1222;
  border: 1px solid var(--border);
  border-radius: 8px;
  max-height: 180px;
  overflow-y: auto;
  z-index: 30;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
  display: none;
}
.suggestion-item {
  padding: 8px 12px;
  font-size: 11px;
  font-family: var(--font-mono);
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.03);
  color: var(--txt-mute);
  transition: all 0.15s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.suggestion-item:hover {
  background: rgba(45, 212, 191, 0.15);
  color: var(--acc);
}

.btn-row {
  display: flex;
  gap: 6px;
}
.btn {
  flex: 1;
  font-size: 10.5px;
  font-family: var(--font-mono);
  font-weight: 500;
  background: rgba(255,255,255,0.04);
  border: 1px solid var(--border);
  color: var(--txt-mute);
  padding: 8px 6px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.btn:hover {
  color: var(--txt);
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.2);
}
.btn.active {
  background: var(--acc-glow);
  color: var(--acc);
  border-color: var(--acc);
}

.inspector-section {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.inspector-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--txt-mute);
  text-align: center;
  font-size: 11.5px;
  gap: 12px;
  padding: 40px 0;
  opacity: 0.85;
}
.inspector-placeholder svg {
  opacity: 0.35;
  width: 36px;
  height: 36px;
  stroke: var(--txt-mute);
}

.node-title {
  font-size: 15px;
  font-weight: 700;
  word-break: break-all;
  color: var(--txt);
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.node-title .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}
.badge {
  display: inline-block;
  font-size: 8.5px;
  font-family: var(--font-mono);
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
  margin-bottom: 12px;
}
.badge.in-pack {
  background: rgba(74, 222, 128, 0.1);
  color: var(--good);
  border: 1px solid rgba(74, 222, 128, 0.2);
}
.badge.out-pack {
  background: rgba(148, 163, 184, 0.15);
  color: var(--txt-mute);
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.info-row {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  padding: 6px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}
.info-row .lbl {
  color: var(--txt-mute);
}
.info-row .v {
  font-family: var(--font-mono);
  color: var(--txt);
}
.inspector-subtitle {
  font-size: 9px;
  color: var(--acc);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
  margin-top: 18px;
  margin-bottom: 6px;
}
.inspector-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-family: var(--font-mono);
  font-size: 11px;
}
.inspector-link {
  color: var(--txt-mute);
  text-decoration: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border-radius: 6px;
  transition: all 0.15s ease;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.inspector-link:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--acc2);
}
.inspector-link .arrow-icon {
  opacity: 0.5;
  font-size: 10px;
}
.inspector-link .kind-badge {
  font-size: 8px;
  opacity: 0.5;
  background: rgba(255,255,255,0.08);
  padding: 1px 4px;
  border-radius: 3px;
}

.legend-section {
  padding: 14px 20px;
  border-top: 1px solid var(--border);
  background: rgba(0,0,0,0.15);
}
.legend-title {
  font-size: 9px;
  color: var(--txt-mute);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 600;
  margin-bottom: 8px;
}
.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-family: var(--font-mono);
  color: var(--txt-mute);
}
.legend-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1px solid rgba(255,255,255,0.1);
}

.minimap-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  width: 200px;
  height: 140px;
  z-index: 20;
  background: rgba(8, 12, 24, 0.8);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px rgba(0,0,0,0.4);
}
canvas#minimap {
  width: 100%;
  height: 100%;
  display: block;
  cursor: crosshair;
}

.hint {
  position: fixed;
  bottom: 170px;
  right: 20px;
  font-size: 9.5px;
  color: var(--txt-mute);
  font-family: var(--font-mono);
  text-align: right;
  line-height: 1.5;
  z-index: 20;
  background: rgba(13, 20, 38, 0.6);
  padding: 6px 10px;
  border-radius: 8px;
  backdrop-filter: blur(8px);
  border: 1px solid var(--border);
  pointer-events: none;
}

.tooltip {
  position: fixed;
  background: rgba(8, 12, 24, 0.95);
  backdrop-filter: blur(6px);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--txt-mute);
  pointer-events: none;
  z-index: 40;
  display: none;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
}
.tooltip b {
  color: var(--acc);
  font-family: var(--font-sans);
  font-size: 12px;
  display: block;
  margin-bottom: 3px;
}

@media(max-width:768px){
  .sidebar {
    top: auto;
    left: 10px;
    right: 10px;
    bottom: 10px;
    width: auto;
    height: 45vh;
    border-radius: 12px;
  }
  .minimap-container, .hint {
    display: none;
  }
}
</style>
__FAVICON__
</head>
<body>
<canvas id="main"></canvas>

<div class="sidebar">
  <div class="brand-section">
    __LOGO__
  </div>

  <div class="stats-grid">
    <div class="stat-box">
      <div class="lbl">nodes</div>
      <div class="v" id="statNodes">—</div>
    </div>
    <div class="stat-box">
      <div class="lbl">edges</div>
      <div class="v" id="statEdges">—</div>
    </div>
    <div class="stat-box">
      <div class="lbl">clouds</div>
      <div class="v" id="statClouds">—</div>
    </div>
    <div class="stat-box">
      <div class="lbl">in pack</div>
      <div class="v good" id="statInPack">—</div>
    </div>
  </div>

  <div class="controls-section">
    <div class="search-wrapper">
      <input class="search-input" id="search" placeholder="🔍 Search file..." autocomplete="off">
      <div class="search-suggestions" id="suggestions"></div>
    </div>
    <div class="btn-row">
      <button class="btn" id="btnFit">
        <svg style="width:11px;height:11px;" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75v4.5m0-4.5h-4.5m4.5 0L15 9m5.25 11.25v-4.5m0 4.5h-4.5m4.5 0L15 15" /></svg>
        Fit
      </button>
      <button class="btn" id="btnRelayout">
        <svg style="width:11px;height:11px;" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>
        Relayout
      </button>
      <button class="btn" id="btnInOnly">In-pack</button>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:2px;">
      <span style="font-size:9px;color:var(--txt-mute);font-family:var(--font-mono);font-weight:600;">ZOOM</span>
      <span style="font-size:11px;color:var(--acc);font-family:var(--font-mono);font-weight:600;" id="zoomPct">100%</span>
    </div>
  </div>

  <div class="inspector-section" id="info">
    <div class="inspector-placeholder">
      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 111.063.852l-.708 2.836a.75.75 0 001.063.852l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
      </svg>
      <span>Click a node in the graph to inspect details.</span>
    </div>
  </div>

  <div class="legend-section">
    <div class="legend-title">Legend</div>
    <div class="legend-items" id="legendItems"></div>
  </div>
</div>

<div class="minimap-container">
  <canvas id="minimap"></canvas>
</div>

<div class="hint">drag = pan · wheel = zoom<br>arrows/F = keys · hover = info</div>
<div class="tooltip" id="tooltip"></div>

<script>
const DATA = __DATA__;
DATA.included = new Set(DATA.included);
const LANG_COLORS = __LANG_COLORS__;

const getLangMeta = (lang) => {
  const l = (lang || 'unknown').toLowerCase();
  const baseColor = LANG_COLORS[l] || LANG_COLORS.default || '#cbd5e1';
  if (l.includes('python')) return { icon: '🐍', color: baseColor, label: 'Python' };
  if (l.includes('rust')) return { icon: '🦀', color: baseColor, label: 'Rust' };
  if (l.includes('javascript') || l === 'js') return { icon: '🟨', color: baseColor, label: 'JS' };
  if (l.includes('typescript') || l === 'ts') return { icon: '🟦', color: baseColor, label: 'TS' };
  if (l.includes('go')) return { icon: '🐹', color: baseColor, label: 'Go' };
  if (l.includes('c++')) return { icon: '⚙️', color: baseColor, label: 'C++' };
  if (l.includes('c')) return { icon: '🔧', color: baseColor, label: 'C' };
  if (l.includes('markdown') || l === 'md') return { icon: '📝', color: baseColor, label: 'MD' };
  if (l.includes('toml')) return { icon: '⚙️', color: baseColor, label: 'TOML' };
  return { icon: '📁', color: baseColor, label: lang };
};

const DEVICON_URLS = {
  'python': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/python/python-original.svg',
  'rust': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/rust/rust-original.svg',
  'javascript': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/javascript/javascript-original.svg',
  'js': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/javascript/javascript-original.svg',
  'typescript': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/typescript/typescript-original.svg',
  'ts': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/typescript/typescript-original.svg',
  'go': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/go/go-original.svg',
  'c++': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/cplusplus/cplusplus-original.svg',
  'cplusplus': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/cplusplus/cplusplus-original.svg',
  'c': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/c/c-original.svg',
  'markdown': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/markdown/markdown-original.svg',
  'md': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/markdown/markdown-original.svg',
  'html': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/html5/html5-original.svg',
  'css': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/css3/css3-original.svg',
  'toml': 'https://cdn.jsdelivr.net/gh/devicons/devicon@latest/icons/rust/rust-original.svg'
};

const iconCache = {};
const getIconImage = (lang) => {
  const l = (lang || 'unknown').toLowerCase();
  const url = DEVICON_URLS[l];
  if (!url) return null;

  if (iconCache[url]) {
    return iconCache[url].loaded ? iconCache[url].img : null;
  }

  const img = new Image();
  img.src = url;
  iconCache[url] = { img: img, loaded: false };
  img.onload = () => {
    iconCache[url].loaded = true;
  };
  img.onerror = () => {
    iconCache[url].failed = true;
  };
  return null;
};

const STRUCTURAL = new Set(['import','reexport','inherits','type_reference','implements','call']);
const isStructural = k => STRUCTURAL.has(k);

const canvas=document.getElementById('main'), ctx=canvas.getContext('2d');
const mm=document.getElementById('minimap'), mmx=mm.getContext('2d');
let W,H,dpr=Math.max(1,window.devicePixelRatio||1);
let nodes=[], edges=[], compOf={}, comps=[];
let dirAnchors=[], dirMap={};
let selected=null, hover=null, dragNode=null, panDrag=false; const selectedSet = new Set();
let panLast={x:0,y:0};
let scale=1, offX=0, offY=0;
let panVX=0, panVY=0, panning=false;
let searchQuery='';
let inPackOnly=false;
let activeLangs=new Set();
let forceAlpha=1.0;

function resize(){
  const r=canvas.getBoundingClientRect(); W=r.width; H=r.height;
  canvas.width=W*dpr; canvas.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  const mr=mm.getBoundingClientRect();
  mm.width=mr.width*dpr; mm.height=mr.height*dpr; mmx.setTransform(dpr,0,0,dpr,0,0);
}
window.addEventListener('resize',()=>{resize(); if(nodes.length){fitView(); drawMinimap();}});

function langOf(n){return n.lang||'unknown';}
function baseColor(n){return LANG_COLORS[langOf(n)]||LANG_COLORS.default;}
function getDirOf(path) {
  const parts = path.split('/');
  return parts.length > 1 ? parts.slice(0, parts.length - 1).join('/') : '.';
}

function analyzeTopology(){
  const parent={};
  const find=x=>{while(parent[x]!==x){parent[x]=parent[parent[x]];x=parent[x];}return x;};
  nodes.forEach(n=>parent[n.id]=n.id);
  edges.forEach(e=>{if(isStructural(e.kind)&&parent[e.source.id]&&parent[e.target.id]){const ra=find(e.source.id),rb=find(e.target.id);if(ra!==rb)parent[ra]=rb;}});
  nodes.forEach(n=>{n.comp=find(n.id);});
  const indeg={}, outdeg={};
  edges.forEach(e=>{if(isStructural(e.kind)){outdeg[e.source.id]=(outdeg[e.source.id]||0)+1; indeg[e.target.id]=(indeg[e.target.id]||0)+1;}});
  nodes.forEach(n=>{n.indeg=indeg[n.id]||0; n.outdeg=outdeg[n.id]||0;});
  const cm={};
  nodes.forEach(n=>{(cm[n.comp]=cm[n.comp]||[]).push(n);});
  comps=Object.values(cm).sort((a,b)=>b.length-a.length);
  compOf={};
  comps.forEach((c,i)=>c.forEach(n=>compOf[n.id]=i));
  nodes.forEach(n=>{
    const parts=n.id.split('/');
    n.cluster = parts.length>1 ? parts.slice(0,Math.min(2,parts.length-1)).join('/') : (n.lang||'misc');
  });
}

const FORCES={
  linkDistance:165, linkBase:0.08,
  charge:5500,
  collidePad:40, collideStr:0.9,
  compGravity:0.006,
  clusterGravity:0.012,
  damping:0.84, maxSpeed:11,
  alphaDecay:0.0228, alphaMin:0.004,
};

function sim(){
  forceAlpha += (0 - forceAlpha)*FORCES.alphaDecay;
  if(forceAlpha<FORCES.alphaMin && !dragNode) return;
  const heat=forceAlpha;
  const vis=nodes.filter(visible);
  if(!vis.length) return;

  // Handle dragging containment for file nodes dragging anchors
  if (dragNode && !dragNode.isAnchor) {
    const anchor = dirMap[dragNode.dir];
    if (anchor) {
      const dx = dragNode.x - anchor.x;
      const dy = dragNode.y - anchor.y;
      const d = Math.sqrt(dx*dx + dy*dy) || 0.1;
      const maxR = anchor.boundaryR - dragNode.r - 8;
      if (d > maxR) {
        anchor.x = dragNode.x - (dx / d) * maxR;
        anchor.y = dragNode.y - (dy / d) * maxR;
      }
    }
  }

  vis.forEach(n=>{n.fx=0;n.fy=0;});
  dirAnchors.forEach(n=>{n.fx=0;n.fy=0;});

  const allObjects = [...vis, ...dirAnchors];

  // 1) Charge-based repulsion (only between matching types)
  for(let i=0;i<allObjects.length;i++){const a=allObjects[i];
    for(let j=i+1;j<allObjects.length;j++){const b=allObjects[j];
      if (a.isAnchor !== b.isAnchor) continue;
      let dx=b.x-a.x,dy=b.y-a.y;let d2=dx*dx+dy*dy;

      // Limit range of charge-based repulsion to keep layout stable and prevent jiggling
      if (a.isAnchor && d2 > 350*350) continue;
      if (!a.isAnchor && d2 > 120*120) continue;

      if(d2<1){d2=1;dx=(Math.random()-.5);dy=(Math.random()-.5);}
      const d=Math.sqrt(d2);

      const chargeA = a.isAnchor ? 12000 : FORCES.charge;
      const chargeB = b.isAnchor ? 12000 : FORCES.charge;
      const f = Math.sqrt(chargeA * chargeB)/d2;
      const fx=dx/d*f,fy=dy/d*f;
      a.fx-=fx;a.fy-=fy;b.fx+=fx;b.fy+=fy;
    }
  }

  // 1.5) Pull directory anchors gently to their respective language centers to group them
  const uniqueLangs = Array.from(new Set(dirAnchors.map(a => a.primaryLang).filter(l => l && l !== 'unknown')));
  const langCenters = {};
  if (uniqueLangs.length > 1) {
    uniqueLangs.forEach((lang, idx) => {
      const angle = (idx / uniqueLangs.length) * Math.PI * 2;
      const dist = 320;
      langCenters[lang] = {
        x: W / 2 + Math.cos(angle) * dist,
        y: H / 2 + Math.sin(angle) * dist
      };
    });
  }

  dirAnchors.forEach(anchor => {
    const lang = anchor.primaryLang;
    const center = (lang && langCenters[lang]) ? langCenters[lang] : { x: W/2, y: H/2 };

    const dx = center.x - anchor.x;
    const dy = center.y - anchor.y;
    const k = 0.007; // Gentle center gravity force to cluster by language
    anchor.fx += dx * k;
    anchor.fy += dy * k;
  });

  // 2) Anchor attraction (linear spring pull to center, targetDist = 0)
  vis.forEach(n => {
    const anchor = dirMap[n.dir];
    if (!anchor) return;
    const dx = anchor.x - n.x;
    const dy = anchor.y - n.y;
    const k = 0.05;
    const fx = dx * k;
    const fy = dy * k;

    n.fx += fx;
    n.fy += fy;
    anchor.fx -= fx * 0.4;
    anchor.fy -= fy * 0.4;
  });

  // 3) Structural edge spring forces
  edges.forEach(e=>{
    if(!isStructural(e.kind))return;
    if(!visible(e.source)||!visible(e.target))return;
    let dx=e.target.x-e.source.x,dy=e.target.y-e.source.y;
    let d=Math.sqrt(dx*dx+dy*dy)||0.01;
    const k=FORCES.linkBase*(e.conf||1);
    const diff=(d-FORCES.linkDistance)*k;
    const fx=dx/d*diff,fy=dy/d*diff;
    e.source.fx+=fx;e.source.fy+=fy;e.target.fx-=fx;e.target.fy-=fy;
  });

  // 4) Position integration & containment constraint
  allObjects.forEach(n=>{
    if(dragNode===n){n.vx=0;n.vy=0;return;}
    const damping = n.isAnchor ? 0.76 : FORCES.damping;
    const maxSp = n.isAnchor ? 5 : FORCES.maxSpeed;
    n.vx=(n.vx+n.fx*heat)*damping;
    n.vy=(n.vy+n.fy*heat)*damping;
    const sp=Math.sqrt(n.vx*n.vx+n.vy*n.vy);
    if(sp>maxSp){n.vx=n.vx/sp*maxSp;n.vy=n.vy/sp*maxSp;}
    n.x+=n.vx;n.y+=n.vy;

    if (!n.isAnchor) {
      const anchor = dirMap[n.dir];
      if (anchor) {
        const dx = n.x - anchor.x;
        const dy = n.y - anchor.y;
        const d = Math.sqrt(dx*dx + dy*dy) || 0.1;
        const maxR = anchor.boundaryR - n.r - 8;
        if (d > maxR) {
          n.x = anchor.x + (dx / d) * maxR;
          n.y = anchor.y + (dy / d) * maxR;

          const ux = dx / d, uy = dy / d;
          const dot = n.vx * ux + n.vy * uy;
          if (dot > 0) {
            n.vx -= 2 * dot * ux * 0.8;
            n.vy -= 2 * dot * uy * 0.8;
          }
        }
      }
    }
  });

  // 5) Collision pass (only between matching types)
  const pad=FORCES.collidePad;
  for(let pass=0;pass<2;pass++)for(let i=0;i<allObjects.length;i++){const a=allObjects[i];
    for(let j=i+1;j<allObjects.length;j++){const b=allObjects[j];
      if (a.isAnchor !== b.isAnchor) continue;
      let dx=b.x-a.x,dy=b.y-a.y;let d=Math.sqrt(dx*dx+dy*dy);
      const rA = a.isAnchor ? a.boundaryR : a.r;
      const rB = b.isAnchor ? b.boundaryR : b.r;
      const extraPad = (a.isAnchor && b.isAnchor) ? 25 : 10;
      const minD=rA+rB+extraPad;
      if(d<minD){if(d<0.01){d=0.01;dx=(Math.random()-.5);dy=(Math.random()-.5);}
        const ov=(minD-d)*0.75;const ux=dx/d,uy=dy/d;
        if(dragNode!==a){a.x-=ux*ov*0.5;a.y-=uy*ov*0.5;}
        if(dragNode!==b){b.x+=ux*ov*0.5;b.y+=uy*ov*0.5;}
      }
    }
  }
}

function build(){
  nodes=[]; const map={};
  DATA.nodes.forEach(n=>{
    const node={id:n.id,label:n.label,lang:n.lang||'unknown',weight:n.weight||1,
      conf:n.conf||1,inPack:DATA.included.has(n.id),x:0,y:0,vx:0,vy:0,fx:0,fy:0,
      r:10+Math.min(16,Math.sqrt(n.weight||1)*3.2)};
    map[n.id]=node;nodes.push(node);
  });
  edges=DATA.edges.map(e=>({source:map[e.s],target:map[e.t],kind:e.k,conf:e.conf||1})).filter(e=>e.source&&e.target);
  analyzeTopology();

  const dirSet = new Set();
  nodes.forEach(n => {
    n.dir = getDirOf(n.id);
    dirSet.add(n.dir);
  });

  // Pre-calculate primary programming language for each directory
  const dirLangs = {};
  dirSet.forEach(d => {
    const nodesInDir = nodes.filter(n => n.dir === d);
    const counts = {};
    nodesInDir.forEach(n => {
      const l = n.lang || 'unknown';
      counts[l] = (counts[l] || 0) + 1;
    });
    let maxL = 'unknown', maxC = 0;
    for (const l in counts) {
      if (counts[l] > maxC) { maxC = counts[l]; maxL = l; }
    }
    dirLangs[d] = maxL;
  });

  // Sort directories by primary language so they are grouped together in adjacent initial angles
  const sortedDirs = Array.from(dirSet).sort((a, b) => {
    const la = dirLangs[a], lb = dirLangs[b];
    if (la < lb) return -1;
    if (la > lb) return 1;
    return 0;
  });

  dirAnchors = [];
  dirMap = {};
  let index = 0;
  const totalDirs = sortedDirs.length;
  sortedDirs.forEach(d => {
    const angle = (index / Math.max(1, totalDirs)) * Math.PI * 2;
    const r = 240;
    const nodesInDir = nodes.filter(n => n.dir === d);
    const boundaryR = 40 + Math.sqrt(nodesInDir.length) * 24;
    const anchor = {
      id: 'dir::' + d,
      label: d,
      isAnchor: true,
      x: W/2 + Math.cos(angle) * r,
      y: H/2 + Math.sin(angle) * r,
      vx: 0, vy: 0, fx: 0, fy: 0,
      r: 35,
      boundaryR: boundaryR,
      primaryLang: dirLangs[d]
    };
    dirAnchors.push(anchor);
    dirMap[d] = anchor;
    index++;
  });

  nodes.forEach(n => {
    const anchor = dirMap[n.dir];
    if (anchor) {
      const angle = Math.random() * Math.PI * 2;
      const dist = 40 + Math.random() * 50;
      n.x = anchor.x + Math.cos(angle) * dist;
      n.y = anchor.y + Math.sin(angle) * dist;
    } else {
      n.x = W/2 + (Math.random() - 0.5) * 100;
      n.y = H/2 + (Math.random() - 0.5) * 100;
    }
  });

  const langs={};nodes.forEach(n=>{langs[n.lang||'unknown']=1;});activeLangs=new Set(Object.keys(langs));
  buildLegend();
  updateStats();
}

function visible(n){
  if(inPackOnly&&!n.inPack)return false;
  if(!activeLangs.has(n.lang||'unknown'))return false;
  if(searchQuery&&!(n.label.toLowerCase().includes(searchQuery)||n.id.toLowerCase().includes(searchQuery)))return n._searchHit?true:false;
  return true;
}

function buildLegend(){
  const ls={};nodes.forEach(n=>{ls[n.lang||'unknown']=(ls[n.lang||'unknown']||0)+1;});
  let h=Object.entries(ls).sort((a,b)=>b[1]-a[1]).map(([l,c])=>{
    const col=LANG_COLORS[l]||LANG_COLORS.default;
    return `<div class="legend-item"><span class="legend-color-dot" style="background:${col}"></span>${l} <span style="opacity:.5">(${c})</span></div>`;
  }).join('');
  h+=`<div class="legend-item" style="border-left:1px solid var(--border);padding-left:8px;"><span class="legend-color-dot" style="background:${LANG_COLORS.in_pack};box-shadow:0 0 4px ${LANG_COLORS.in_pack}88"></span>in pack (${nodes.filter(n=>n.inPack).length})</div>`;
  document.getElementById('legendItems').innerHTML=h;
}

function updateStats(){
  document.getElementById('statNodes').textContent=nodes.length;
  document.getElementById('statEdges').textContent=edges.length;
  document.getElementById('statClouds').textContent=comps.length;
  document.getElementById('statInPack').textContent=nodes.filter(n=>n.inPack).length;
}

function matchesSearch(n){return searchQuery&&(n.label.toLowerCase().includes(searchQuery)||n.id.toLowerCase().includes(searchQuery));}

function getGuessedPurpose(clusterName, nodes) {
  let hasTest = false, hasRender = false, hasCli = false, hasModels = false;
  let hasPack = false, hasNetwork = false, hasGpu = false;
  nodes.forEach(n => {
    const name = n.label.toLowerCase();
    const id = n.id.toLowerCase();
    if (name.includes('test') || id.includes('tests/')) hasTest = true;
    if (name.includes('render') || name.includes('html') || name.includes('draw') || name.includes('canvas')) hasRender = true;
    if (name.includes('cli') || name.includes('main') || name.includes('app') || name.includes('launcher')) hasCli = true;
    if (name.includes('model') || name.includes('db') || name.includes('schema') || name.includes('cache')) hasModels = true;
    if (name.includes('pack') || name.includes('scriber')) hasPack = true;
    if (id.includes('network') || id.includes('async')) hasNetwork = true;
    if (id.includes('gpu') || id.includes('render/')) hasGpu = true;
  });
  if (hasTest) return "Testing & Verification";
  if (hasGpu) return "GPU & Render Engine";
  if (hasRender) return "Rendering & Visuals";
  if (hasCli) return "Application CLI & Entrypoints";
  if (hasModels) return "Data Models & Cache";
  if (hasPack) return "Packaging & Assembly";
  if (hasNetwork) return "Networking & Async IO";
  const parts = clusterName.split('/');
  const folder = parts[parts.length - 1];
  return folder.charAt(0).toUpperCase() + folder.slice(1) + " Modules";
}

function drawPlacard(ctx, anchor, name, purpose, col, baseAlpha) {
  ctx.save();
  ctx.globalAlpha = baseAlpha;

  const isSelected = selected === anchor;
  const isHovered = hover === anchor;

  const labelTop = name.toUpperCase();
  const labelBot = purpose.toUpperCase();

  const meta = getLangMeta(anchor.primaryLang);
  const icon = meta.icon;
  const placardColor = meta.color;

  ctx.font = 'bold 8.5px JetBrains Mono, monospace';
  const wTop = ctx.measureText(labelTop).width;
  ctx.font = 'bold 10.5px Inter, sans-serif';
  const wBot = ctx.measureText(labelBot).width;

  const textWidth = Math.max(wTop, wBot);
  const w = textWidth + 40;
  const h = 36;
  const rx = anchor.x - w / 2;
  const ry = anchor.y - anchor.boundaryR - h - 8;
  const rad = 8;

  ctx.beginPath();
  ctx.moveTo(rx + rad, ry);
  ctx.lineTo(rx + w - rad, ry);
  ctx.quadraticCurveTo(rx + w, ry, rx + w, ry + rad);
  ctx.lineTo(rx + w, ry + h - rad);
  ctx.quadraticCurveTo(rx + w, ry + h, rx + w - rad, ry + h);
  ctx.lineTo(rx + rad, ry + h);
  ctx.quadraticCurveTo(rx, ry + h, rx, ry + h - rad);
  ctx.lineTo(rx, ry + rad);
  ctx.quadraticCurveTo(rx, ry, rx + rad, ry);
  ctx.closePath();

  ctx.fillStyle = isSelected ? 'rgba(15, 23, 42, 0.96)' : 'rgba(8, 12, 24, 0.90)';
  ctx.fill();

  ctx.strokeStyle = isSelected ? '#2dd4bf' : (isHovered ? placardColor + 'aa' : placardColor + '44');
  ctx.lineWidth = isSelected ? 2.0 : 1.2;
  ctx.stroke();

  // Draw left vertical color accent bar
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(rx + rad, ry);
  ctx.lineTo(rx + 24, ry);
  ctx.lineTo(rx + 24, ry + h);
  ctx.lineTo(rx + rad, ry + h);
  ctx.quadraticCurveTo(rx, ry + h, rx, ry + h - rad);
  ctx.lineTo(rx, ry + rad);
  ctx.quadraticCurveTo(rx, ry, rx + rad, ry);
  ctx.closePath();
  ctx.fillStyle = placardColor + '1e';
  ctx.fill();
  ctx.restore();

  // Draw icon (try Devicon CDN, fallback to emoji)
  const img = getIconImage(anchor.primaryLang);
  if (img) {
    const isDarkIcon = (anchor.primaryLang === 'rust' || anchor.primaryLang === 'markdown' || anchor.primaryLang === 'md' || anchor.primaryLang === 'toml');
    if (isDarkIcon) {
      ctx.filter = 'invert(1) brightness(1.5)';
    }
    ctx.drawImage(img, rx + 4, ry + h / 2 - 8, 16, 16);
    if (isDarkIcon) {
      ctx.filter = 'none';
    }
  } else {
    ctx.font = '13px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(icon, rx + 12, ry + h / 2 + 0.5);
  }

  // Draw text
  ctx.textAlign = 'left';
  ctx.textBaseline = 'middle';

  ctx.fillStyle = isSelected ? '#2dd4bfcc' : 'rgba(148, 163, 184, 0.7)';
  ctx.font = 'bold 8px JetBrains Mono, monospace';
  ctx.fillText(labelTop, rx + 30, ry + 12);

  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 10px Inter, sans-serif';
  ctx.fillText(labelBot, rx + 30, ry + 24);

  ctx.restore();
}

function drawGroupBoundaries() {
  const baseAlpha = 0.85;

  const drawAnchors = dirAnchors.slice().sort((a, b) => {
    const aVal = (a === selected) ? 2 : ((a === hover) ? 1 : 0);
    const bVal = (b === selected) ? 2 : ((b === hover) ? 1 : 0);
    return aVal - bVal;
  });
  drawAnchors.forEach(anchor => {
    const arr = nodes.filter(n => n.dir === anchor.label && visible(n));
    const meta = getLangMeta(anchor.primaryLang);
    const col = meta.color;

    const isSelected = selectedSet.has(anchor);
    const isHovered = hover === anchor;
    const isTargetDir = (selectedSet.size > 0 && Array.from(selectedSet).some(s => s.dir === anchor.label)) || (hover && hover.dir === anchor.label);
    const isSelfActive = isSelected || isHovered || isTargetDir;

    let alpha = baseAlpha;
    if (selectedSet.size > 0 || hover) {
      alpha = isSelfActive ? baseAlpha : baseAlpha * 0.12;
    }

    ctx.save();
    ctx.globalAlpha = alpha;

    ctx.beginPath();
    ctx.arc(anchor.x, anchor.y, anchor.boundaryR, 0, Math.PI * 2);

    ctx.fillStyle = isSelected ? 'rgba(45, 212, 191, 0.03)' : col + '04';
    ctx.fill();

    ctx.strokeStyle = isSelected ? '#2dd4bf' : (isHovered ? col + '66' : col + '1e');
    ctx.lineWidth = isSelected ? 2.5 : 1.6;
    ctx.stroke();

    if (isSelected) {
      ctx.strokeStyle = 'rgba(45, 212, 191, 0.2)';
      ctx.lineWidth = 6;
      ctx.stroke();
    }

    ctx.restore();

    if (arr.length > 0) {
      const purpose = getGuessedPurpose(anchor.label, arr);
      drawPlacard(ctx, anchor, anchor.label, purpose, col, alpha);
    }
  });
}

function isActive(n) {
  if (selectedSet.size === 0 && !hover) return true;
  const target = hover;
  if (target) {
    if (target.isAnchor) {
      if (n.isAnchor) return n === target;
      if (n.dir === target.label) return true;
      return edges.some(e =>
        isStructural(e.kind) &&
        ((e.source === n && e.target.dir === target.label) ||
         (e.target === n && e.source.dir === target.label))
      );
    }
    if (n === target) return true;
    return edges.some(e =>
      isStructural(e.kind) &&
      ((e.source === n && e.target === target) || (e.target === n && e.source === target))
    );
  }

  if (selectedSet.has(n)) return true;
  if (n.isAnchor) {
    return Array.from(selectedSet).some(s => s.dir === n.label);
  } else {
    return Array.from(selectedSet).some(s => {
      if (s.isAnchor) {
        return n.dir === s.label;
      }
      return n === s || edges.some(e =>
        isStructural(e.kind) &&
        ((e.source === s && e.target === n) || (e.target === s && e.source === n))
      );
    });
  }
}

function isEdgeActive(e) {
  if (selectedSet.size === 0 && !hover) return true;
  const target = hover;
  if (target) {
    if (target.isAnchor) {
      return e.source.dir === target.label || e.target.dir === target.label;
    }
    return e.source === target || e.target === target;
  }

  return Array.from(selectedSet).some(s => {
    if (s.isAnchor) {
      return e.source.dir === s.label || e.target.dir === s.label;
    }
    return e.source === s || e.target === s;
  });
}

function draw(){
  ctx.clearRect(0,0,W,H);
  ctx.save();ctx.translate(offX,offY);ctx.scale(scale,scale);

  // 1) Draw group background blobs
  drawGroupBoundaries();

  // 2) Draw edges
  edges.forEach(e=>{
    if(!visible(e.source)||!visible(e.target))return;
    const touch = selectedSet.has(e.source) || selectedSet.has(e.target) || (hover && (e.source === hover || e.target === hover));
    if(!isStructural(e.kind)&&!touch)return;

    const active = isEdgeActive(e);
    const both=e.source.inPack&&e.target.inPack;
    const isInternal = e.source.dir === e.target.dir;

    // Curved Bezier line
    const dx = e.target.x - e.source.x;
    const dy = e.target.y - e.source.y;
    const len = Math.sqrt(dx*dx + dy*dy) || 0.01;
    const nx = -dy / len;
    const ny = dx / len;
    const curv = 16;
    const mx = (e.source.x + e.target.x)/2 + nx * curv;
    const my = (e.source.y + e.target.y)/2 + ny * curv;

    ctx.save();
    if (!active) {
      ctx.globalAlpha = 0.04;
    }

    ctx.beginPath();
    ctx.moveTo(e.source.x,e.source.y);
    ctx.quadraticCurveTo(mx,my,e.target.x,e.target.y);

    if(touch) {
      ctx.strokeStyle='rgba(45,212,191,0.85)';
      ctx.lineWidth=2.8;
      ctx.stroke();

      ctx.strokeStyle='#ffffff';
      ctx.lineWidth=1.5;
      ctx.setLineDash([5, 5]);
      ctx.lineDashOffset = - (Date.now() / 25) % 10;
      ctx.stroke();
      ctx.setLineDash([]);
    } else {
      if (isInternal) {
        ctx.strokeStyle = baseColor(e.source) + '22';
        ctx.lineWidth = 1.0;
        ctx.setLineDash(e.kind==='import'?[]:[3,2]);
      } else {
        ctx.strokeStyle = 'rgba(148,163,184,0.12)';
        ctx.setLineDash([3, 4]);
        ctx.lineWidth = 0.8;
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.restore();

    // Draw arrowhead
    if (isStructural(e.kind) && active) {
      const adx = e.target.x - mx;
      const ady = e.target.y - my;
      const alen = Math.sqrt(adx*adx + ady*ady) || 0.01;
      const aux = adx / alen;
      const auy = ady / alen;
      const offset = e.target.r + 2;
      const arrowTipX = e.target.x - aux * offset;
      const arrowTipY = e.target.y - auy * offset;

      const arrowSize = 6;
      const arrowAngle = Math.PI / 6;
      const x1 = arrowTipX - aux * arrowSize + auy * arrowSize * Math.tan(arrowAngle);
      const y1 = arrowTipY - auy * arrowSize - aux * arrowSize * Math.tan(arrowAngle);
      const x2 = arrowTipX - aux * arrowSize - auy * arrowSize * Math.tan(arrowAngle);
      const y2 = arrowTipY - auy * arrowSize + aux * arrowSize * Math.tan(arrowAngle);

      ctx.save();
      if (!active) ctx.globalAlpha = 0.04;
      ctx.beginPath();
      ctx.moveTo(arrowTipX, arrowTipY);
      ctx.lineTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.closePath();
      ctx.fillStyle = touch ? '#2dd4bf' : 'rgba(148, 163, 184, 0.4)';
      ctx.fill();
      ctx.restore();
    }
  });

  // 3) Draw nodes
  const anySearch=searchQuery.length>0;
  const drawNodes = nodes.filter(visible).sort((a, b) => {
    const aVal = selectedSet.has(a) ? 2 : ((a === hover) ? 1 : 0);
    const bVal = selectedSet.has(b) ? 2 : ((b === hover) ? 1 : 0);
    return aVal - bVal;
  });
  drawNodes.forEach(n=>{
    const hl=selectedSet.has(n)||(hover===n);
    const hit=matchesSearch(n);
    const active = isActive(n);
    const dim = !active || (anySearch && !hit);
    const r=n.r;

    ctx.save();
    if (!active) {
      ctx.globalAlpha = 0.05;
    }

    // Glow ring for in-pack nodes
    if(n.inPack){
      ctx.beginPath();ctx.arc(n.x,n.y,r+4,0,Math.PI*2);
      ctx.strokeStyle='rgba(74,222,128,.4)';ctx.lineWidth=1.5;ctx.stroke();
    }

    // Selection glow
    if(hl||hit){
      ctx.beginPath();ctx.arc(n.x,n.y,r+6,0,Math.PI*2);
      ctx.fillStyle=baseColor(n)+'16';ctx.fill();
      ctx.strokeStyle=baseColor(n)+'55';ctx.lineWidth=1;ctx.stroke();
    }

    // Shadow
    ctx.beginPath();ctx.arc(n.x,n.y,r+2,0,Math.PI*2);
    ctx.fillStyle='rgba(0,0,0,.35)';ctx.fill();

    // Fill circle
    ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);
    ctx.fillStyle=dim?'#1e293b':(n.inPack?LANG_COLORS.in_pack:baseColor(n));
    ctx.fill();
    ctx.lineWidth=hl?2:1.2;ctx.strokeStyle=hl?'#fff':'rgba(0,0,0,0.35)';ctx.stroke();

    // Draw initials inside node when zoomed in
    if (scale > 1.2 && r > 12 && !dim) {
      ctx.save();
      ctx.fillStyle = '#ffffffcc';
      ctx.font = 'bold 8px JetBrains Mono,Consolas,monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      const langAbbr = n.lang ? n.lang.substring(0, 2).toUpperCase() : '';
      ctx.fillText(langAbbr, n.x, n.y);
      ctx.restore();
    }

    // Node label text
    const isHub=n.indeg>=6;
    const showLabel = (scale > 0.95 && active) || hl || hit || isHub || n.inPack;
    if(showLabel){
      const fs = hl?12.5 : (isHub?11.5:10.5);
      ctx.font=(hl||isHub?'bold ':'')+fs+'px JetBrains Mono,Consolas,monospace';
      const ly=n.y+r+ (isHub?15:13);

      // Draw label pill background envelope
      ctx.save();
      const textWidth = ctx.measureText(n.label).width;
      const textHeight = fs;
      const px = 6, py = 3;
      const bx = n.x - textWidth/2 - px;
      const by = ly - textHeight/2 - py;
      const bw = textWidth + px*2;
      const bh = textHeight + py*2;
      const br = 4;

      ctx.beginPath();
      ctx.moveTo(bx + br, by);
      ctx.lineTo(bx + bw - br, by);
      ctx.quadraticCurveTo(bx + bw, by, bx + bw, by + br);
      ctx.lineTo(bx + bw, by + bh - br);
      ctx.quadraticCurveTo(bx + bw, by + bh, bx + bw - br, by + bh);
      ctx.lineTo(bx + br, by + bh);
      ctx.quadraticCurveTo(bx, by + bh, bx, by + bh - br);
      ctx.lineTo(bx, by + br);
      ctx.quadraticCurveTo(bx, by, bx + br, by);
      ctx.closePath();

      ctx.fillStyle = 'rgba(8, 12, 24, 0.85)';
      ctx.fill();
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle='rgba(0,0,0,.6)';ctx.textAlign='center';ctx.fillText(n.label,n.x+0.6,n.y+0.6+r+13);
      ctx.fillStyle=dim?'#334155':(hl?'#fff':(n.inPack?'#bbf7d0':(isHub?'#f1f5f9':'#cbd5e1')));
      ctx.fillText(n.label,n.x,ly);
    }
    ctx.restore();
  });

  ctx.restore();
  drawMinimap();
}

function drawMinimap(){
  const mw=mm.getBoundingClientRect().width, mh=mm.getBoundingClientRect().height;
  mmx.clearRect(0,0,mw,mh);
  if(!nodes.length)return;

  let mnx=1e9,mny=1e9,mxx=-1e9,mxy=-1e9;
  nodes.forEach(n=>{mnx=Math.min(mnx,n.x);mny=Math.min(mny,n.y);mxx=Math.max(mxx,n.x);mxy=Math.max(mxy,n.y);});
  const gw=(mxx-mnx)||1, gh=(mxy-mny)||1;
  const padMM=8;
  const mmS=Math.min((mw-2*padMM)/gw,(mh-2*padMM)/gh);
  const mmOX=(mw-gw*mmS)/2 - mnx*mmS;
  const mmOY=(mh-gh*mmS)/2 - mny*mmS;

  // Draw subtle module circles on the minimap
  dirAnchors.forEach(anchor => {
    const arr = nodes.filter(n => n.dir === anchor.label && visible(n));
    if (arr.length === 0) return;
    const firstNode = arr[0];
    const col = baseColor(firstNode) || LANG_COLORS.default;

    mmx.beginPath();
    mmx.arc(anchor.x * mmS + mmOX, anchor.y * mmS + mmOY, anchor.boundaryR * mmS, 0, Math.PI * 2);
    mmx.fillStyle = col + '02'; // Extremely faint fill (0.008 opacity)
    mmx.fill();
    mmx.strokeStyle = col + '15'; // Subtle outline (0.08 opacity)
    mmx.lineWidth = 0.7;
    mmx.stroke();
  });

  // Draw subtle active edges on the minimap
  if (selectedSet.size > 0 || hover) {
    edges.forEach(e => {
      if (!visible(e.source) || !visible(e.target)) return;
      if (!isStructural(e.kind)) return;
      if (!isEdgeActive(e)) return;

      mmx.beginPath();
      mmx.moveTo(e.source.x * mmS + mmOX, e.source.y * mmS + mmOY);
      mmx.lineTo(e.target.x * mmS + mmOX, e.target.y * mmS + mmOY);

      const isTouch = (selectedSet.has(e.source) || selectedSet.has(e.target) || hover === e.source || hover === e.target);
      mmx.strokeStyle = isTouch ? 'rgba(45, 212, 191, 0.35)' : 'rgba(148, 163, 184, 0.12)';
      mmx.lineWidth = isTouch ? 0.8 : 0.4;
      mmx.stroke();
    });
  }

  // Draw node dots (with active highlighting/dimming)
  nodes.forEach(n=>{
    if(!visible(n)) return;
    const active = isActive(n);
    const isSel = selectedSet.has(n) || (hover === n);

    mmx.beginPath();
    mmx.arc(n.x*mmS+mmOX, n.y*mmS+mmOY, isSel ? 2.5 : 1.5, 0, Math.PI*2);

    if (selectedSet.size > 0 || hover) {
      if (isSel) {
        mmx.fillStyle = '#2dd4bf'; // Highlight selected node in teal
      } else if (active) {
        mmx.fillStyle = baseColor(n) + 'bb'; // Highlight connected nodes in their language color
      } else {
        mmx.fillStyle = 'rgba(148, 163, 184, 0.08)'; // Dim unrelated nodes
      }
    } else {
      mmx.fillStyle = 'rgba(148, 163, 184, 0.4)'; // Default: uniform soft grey
    }
    mmx.fill();
  });

  const vc0=screenToWorld(0,0), vc1=screenToWorld(W,H);
  const rx=vc0.x*mmS+mmOX, ry=vc0.y*mmS+mmOY;
  const rw=(vc1.x-vc0.x)*mmS, rh=(vc1.y-vc0.y)*mmS;
  mmx.strokeStyle='rgba(45,212,191,.85)';mmx.lineWidth=1.2;
  mmx.fillStyle='rgba(45,212,191,.04)';
  mmx.fillRect(rx,ry,rw,rh);
  mmx.strokeRect(rx,ry,rw,rh);

  mm._mmS=mmS; mm._mmOX=mmOX; mm._mmOY=mmOY;
}

function loop(){
  sim();
  if(!panning&&(Math.abs(panVX)>0.05||Math.abs(panVY)>0.05)){offX+=panVX;offY+=panVY;panVX*=0.92;panVY*=0.92;}
  draw();
  requestAnimationFrame(loop);
}

function screenToWorld(x,y){return {x:(x-offX)/scale,y:(y-offY)/scale};}
function pick(sx,sy){
  const p=screenToWorld(sx,sy);
  // 1) First check file nodes (smaller, on top)
  for(let i=nodes.length-1;i>=0;i--){
    const n=nodes[i];
    if(!visible(n))continue;
    if((p.x-n.x)**2+(p.y-n.y)**2<=(n.r+4)**2)return n;
  }
  // 2) Then check directory anchors (placards or boundaries)
  for(let i=dirAnchors.length-1;i>=0;i--){
    const anchor=dirAnchors[i];
    const dx = Math.abs(p.x - anchor.x);
    // Placard center Y: anchor.y - anchor.boundaryR - 17 - 8 = anchor.y - anchor.boundaryR - 25
    const placardCenterY = anchor.y - anchor.boundaryR - 25;
    const dyPlacard = Math.abs(p.y - placardCenterY);
    const dyCenter = Math.abs(p.y - anchor.y);

    // Pick if click within the placard bounding box (140x40) or inside the anchor center circle (radius 35)
    if ((dx <= 70 && dyPlacard <= 20) || (dx*dx + dyCenter*dyCenter <= 35*35)) {
      return anchor;
    }
  }
  return null;
}

function fitView(){
  if(!nodes.length)return;let mnx=1e9,mny=1e9,mxx=-1e9,mxy=-1e9;
  nodes.filter(visible).forEach(n=>{mnx=Math.min(mnx,n.x);mny=Math.min(mny,n.y);mxx=Math.max(mxx,n.x);mxy=Math.max(mxy,n.y);});
  dirAnchors.forEach(n=>{mnx=Math.min(mnx,n.x);mny=Math.min(mny,n.y);mxx=Math.max(mxx,n.x);mxy=Math.max(mxy,n.y);});

  if(!isFinite(mnx))return;const pad=70,w=(mxx-mnx)||1,h=(mxy-mny)||1;
  scale=Math.max(0.2,Math.min(3,Math.min((W-pad*2)/w,(H-pad*2)/h)));
  offX=W/2-(mnx+w/2)*scale;offY=H/2-(mny+h/2)*scale;updateZoom();
}
function updateZoom(){document.getElementById('zoomPct').textContent=Math.round(scale*100)+'%';}
function focusNode(n){
  selectedSet.clear();
  selectedSet.add(n);
  selected=n;
  updInfo();
  fitToNode(n);
}
window.focusNodeById = function(id) {
  if (id.startsWith('dir::')) {
    const a = dirAnchors.find(x => x.id === id);
    if (a) {
      selectedSet.clear();
      selectedSet.add(a);
      selected = a;
      updInfo();
      fitToNode(a);
    }
    return;
  }
  const n = nodes.find(x => x.id === id);
  if (n) { focusNode(n); }
};
window.clearMultiSelection = function() {
  selectedSet.clear();
  selected = null;
  updInfo();
};
function fitToNode(n){scale=Math.max(scale,1.4);offX=W/2-n.x*scale;offY=H/2-n.y*scale;updateZoom();}

function updInfo(){
  const info=document.getElementById('info');
  if(selectedSet.size === 0){
    info.innerHTML=`
      <div class="inspector-placeholder">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 111.063.852l-.708 2.836a.75.75 0 001.063.852l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
        </svg>
        <span>Click a node or module to inspect details. Use Ctrl+Click to select multiple.</span>
      </div>
    `;
    return;
  }

  if (selectedSet.size > 1) {
    const items = Array.from(selectedSet);
    const files = items.filter(n => !n.isAnchor);
    const modules = items.filter(n => n.isAnchor);

    const langCounts = {};
    files.forEach(f => {
      langCounts[f.lang] = (langCounts[f.lang] || 0) + 1;
    });
    const langSummary = Object.entries(langCounts)
      .sort((a,b)=>b[1]-a[1])
      .map(([lang, count]) => {
        const meta = getLangMeta(lang);
        return `<span class="badge" style="background:${meta.color}22;color:${meta.color};border:1px solid ${meta.color}33;margin-right:4px;margin-bottom:4px;white-space:nowrap;">${meta.icon} ${lang} (${count})</span>`;
      }).join('');

    let html = `
      <div class="node-title">
        <span class="dot" style="background:#2dd4bf;box-shadow:0 0 8px #2dd4bf66;border-radius:2px;width:12px;height:12px;"></span>
        <span>Multiple Selection</span>
      </div>
      <div style="margin-bottom:10px;">
        <span class="badge" style="background:rgba(45,212,191,0.15);color:#2dd4bf;border:1px solid rgba(45,212,191,0.3);">${selectedSet.size} SELECTED</span>
      </div>

      <div class="info-row"><span class="lbl">Modules Selected</span><span class="v">${modules.length}</span></div>
      <div class="info-row"><span class="lbl">Files Selected</span><span class="v">${files.length}</span></div>
    `;

    if (langSummary) {
      html += `
        <div class="inspector-subtitle" style="margin-top:16px;">Languages represented</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:6px;">
          ${langSummary}
        </div>
      `;
    }

    html += `
      <div class="inspector-subtitle" style="margin-top:16px;">Items in selection</div>
      <div style="max-height:220px;overflow-y:auto;border:1px solid var(--border);border-radius:6px;background:rgba(255,255,255,0.01);margin-top:6px;padding:2px 0;">
    `;

    items.forEach(item => {
      const meta = item.isAnchor ? getLangMeta(item.primaryLang) : getLangMeta(item.lang);
      html += `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 10px;border-bottom:1px solid var(--border);font-size:11px;">
          <div style="display:flex;align-items:center;gap:6px;cursor:pointer;" onclick="focusNodeById('${item.id}')">
            <span>${meta.icon}</span>
            <span style="font-weight:600;color:var(--txt);text-decoration:underline;">${item.label}</span>
          </div>
          <span style="font-size:9px;color:var(--txt-mute);">${item.isAnchor ? 'Module' : 'File'}</span>
        </div>
      `;
    });

    html += `
      </div>
      <div style="margin-top:16px;text-align:center;">
        <button onclick="clearMultiSelection()" style="background:rgba(239,68,68,0.1);color:#f87171;border:1px solid rgba(239,68,68,0.2);padding:6px 12px;border-radius:4px;font-size:10px;font-weight:600;cursor:pointer;transition:all 0.2s;" onmouseover="this.style.background='rgba(239,68,68,0.2)'" onmouseout="this.style.background='rgba(239,68,68,0.1)'">Clear Selection</button>
      </div>
    `;

    info.innerHTML = html;
    return;
  }

  // Handle selected directory/module
  if (selected.isAnchor) {
    const files = nodes.filter(n => n.dir === selected.label && visible(n));
    const firstNode = files.length > 0 ? files[0] : null;
    const col = firstNode ? baseColor(firstNode) : LANG_COLORS.default;
    const purpose = getGuessedPurpose(selected.label, files);

    // Find cross-module links
    const outEdges = edges.filter(e => e.source.dir === selected.label && e.target.dir !== selected.label);
    const incEdges = edges.filter(e => e.target.dir === selected.label && e.source.dir !== selected.label);

    let html = `
      <div class="node-title">
        <span class="dot" style="background:${col};box-shadow: 0 0 8px ${col}66;border-radius: 2px;width:12px;height:12px;"></span>
        <span>${selected.label}</span>
      </div>
      <div style="margin-bottom: 10px;">
        <span class="badge" style="background:${col}22;color:${col};border:1px solid ${col}44;">MODULE / CLOUD</span>
      </div>
      <div class="info-row"><span class="lbl">Purpose</span><span class="v" style="font-weight:600;color:#fff;">${purpose}</span></div>
      <div class="info-row"><span class="lbl">Files Count</span><span class="v">${files.length}</span></div>
      <div class="info-row"><span class="lbl">In Pack</span><span class="v">${files.filter(n => n.inPack).length}</span></div>
      <div class="info-row"><span class="lbl">Membrane Radius</span><span class="v">${Math.round(selected.boundaryR)}px</span></div>
    `;

    html += `<div class="inspector-subtitle">Files in Module (${files.length})</div>`;
    html += `<div class="inspector-list" style="max-height: 150px; overflow-y: auto;">`;
    if (files.length) {
      html += files.map(f => `
        <div class="inspector-link" onclick="focusNodeById('${f.id}')">
          <span class="dot" style="background:${f.inPack ? LANG_COLORS.in_pack : baseColor(f)};width:6px;height:6px;margin-right:6px;"></span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;" title="${f.id}">${f.label}</span>
          ${f.inPack ? '<span class="kind-badge" style="background:rgba(74,222,128,0.1);color:#4ade80;">pack</span>' : ''}
        </div>
      `).join('');
    } else {
      html += `<span style="opacity:0.4;font-style:italic;padding-left:6px;">No visible files</span>`;
    }
    html += `</div>`;

    html += `<div class="inspector-subtitle">External Dependencies (${outEdges.length})</div>`;
    html += `<div class="inspector-list" style="max-height: 150px; overflow-y: auto;">`;
    if (outEdges.length) {
      const uniqueTargets = [];
      const seen = new Set();
      outEdges.forEach(e => {
        if (!seen.has(e.target.id)) {
          seen.add(e.target.id);
          uniqueTargets.push(e.target);
        }
      });
      html += uniqueTargets.map(t => `
        <div class="inspector-link" onclick="focusNodeById('${t.id}')">
          <span class="arrow-icon">→</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;" title="${t.id}">${t.label}</span>
          <span class="kind-badge" style="font-size: 8px; opacity:0.6;">${t.dir}</span>
        </div>
      `).join('');
    } else {
      html += `<span style="opacity:0.4;font-style:italic;padding-left:6px;">No external dependencies</span>`;
    }
    html += `</div>`;

    html += `<div class="inspector-subtitle">External Dependents (${incEdges.length})</div>`;
    html += `<div class="inspector-list" style="max-height: 150px; overflow-y: auto;">`;
    if (incEdges.length) {
      const uniqueSources = [];
      const seen = new Set();
      incEdges.forEach(e => {
        if (!seen.has(e.source.id)) {
          seen.add(e.source.id);
          uniqueSources.push(e.source);
        }
      });
      html += uniqueSources.map(s => `
        <div class="inspector-link" onclick="focusNodeById('${s.id}')">
          <span class="arrow-icon">←</span>
          <span style="flex:1;overflow:hidden;text-overflow:ellipsis;" title="${s.id}">${s.label}</span>
          <span class="kind-badge" style="font-size: 8px; opacity:0.6;">${s.dir}</span>
        </div>
      `).join('');
    } else {
      html += `<span style="opacity:0.4;font-style:italic;padding-left:6px;">No external dependents</span>`;
    }
    html += `</div>`;

    info.innerHTML = html;
    return;
  }

  // Handle selected file node
  const out=edges.filter(e=>e.source===selected).map(e=>({n:e.target,k:e.kind}));
  const inc=edges.filter(e=>e.target===selected).map(e=>({n:e.source,k:e.kind}));
  const col=selected.inPack?LANG_COLORS.in_pack:baseColor(selected);

  let html = `
    <div class="node-title">
      <span class="dot" style="background:${col};box-shadow: 0 0 8px ${col}66"></span>
      <span>${selected.label}</span>
    </div>
    <div style="margin-bottom: 10px;">
      ${selected.inPack ? '<span class="badge in-pack">IN PACK</span>' : '<span class="badge out-pack">EXTERNAL</span>'}
    </div>
    <div class="info-row"><span class="lbl">Path</span><span class="v" style="word-break:break-all;font-size:10px;text-align:right;">${selected.id}</span></div>
    <div class="info-row"><span class="lbl">Language</span><span class="v">${selected.lang}</span></div>
    <div class="info-row"><span class="lbl">Module</span><span class="v" style="cursor:pointer;color:#2dd4bf;text-decoration:underline;" onclick="focusNodeById('dir::${selected.dir}')">${selected.dir}</span></div>
    <div class="info-row"><span class="lbl">Links (In/Out)</span><span class="v">${selected.indeg} / ${selected.outdeg}</span></div>
  `;

  html += `<div class="inspector-subtitle">Dependencies (${out.length})</div>`;
  html += `<div class="inspector-list">`;
  if (out.length) {
    html += out.map(o => `
      <div class="inspector-link" onclick="focusNodeById('${o.n.id}')">
        <span class="arrow-icon">→</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;" title="${o.n.id}">${o.n.label}</span>
        <span class="kind-badge">${o.k}</span>
      </div>
    `).join('');
  } else {
    html += `<span style="opacity:0.4;font-style:italic;padding-left:6px;">No dependencies</span>`;
  }
  html += `</div>`;

  html += `<div class="inspector-subtitle">Dependents (${inc.length})</div>`;
  html += `<div class="inspector-list">`;
  if (inc.length) {
    html += inc.map(i => `
      <div class="inspector-link" onclick="focusNodeById('${i.n.id}')">
        <span class="arrow-icon">←</span>
        <span style="flex:1;overflow:hidden;text-overflow:ellipsis;" title="${i.n.id}">${i.n.label}</span>
        <span class="kind-badge">${i.k}</span>
      </div>
    `).join('');
  } else {
    html += `<span style="opacity:0.4;font-style:italic;padding-left:6px;">No dependents</span>`;
  }
  html += `</div>`;

  info.innerHTML = html;
}

canvas.addEventListener('mousedown',e=>{
  const r=canvas.getBoundingClientRect();const sx=e.clientX-r.left,sy=e.clientY-r.top;
  const n=pick(sx,sy);
  if(n){
    dragNode=n;
    const isCtrl = e.ctrlKey || e.metaKey;
    if (isCtrl) {
      if (selectedSet.has(n)) {
        selectedSet.delete(n);
        selected = selectedSet.size > 0 ? Array.from(selectedSet)[selectedSet.size - 1] : null;
      } else {
        selectedSet.add(n);
        selected = n;
      }
    } else {
      selectedSet.clear();
      selectedSet.add(n);
      selected = n;
    }
    updInfo();
  }
  else{
    const isCtrl = e.ctrlKey || e.metaKey;
    if (!isCtrl) {
      selectedSet.clear();
      selected = null;
      updInfo();
    }
    panDrag=true;panLast={x:sx,y:sy};panning=true;panVX=0;panVY=0;canvas.classList.add('dragging');
  }
});
canvas.addEventListener('mousemove',e=>{
  const r=canvas.getBoundingClientRect();const sx=e.clientX-r.left,sy=e.clientY-r.top;
  if(dragNode){const p=screenToWorld(sx,sy);dragNode.x=p.x;dragNode.y=p.y;forceAlpha=Math.max(forceAlpha,0.4);}
  else if(panDrag){const dx=sx-panLast.x,dy=sy-panLast.y;offX+=dx;offY+=dy;panVX=dx*0.6;panVY=dy*0.6;panLast={x:sx,y:sy};updateZoom();}
  else{const nh=pick(sx,sy);if(nh!==hover){hover=nh;canvas.style.cursor=hover?'pointer':'grab';}
    const tt=document.getElementById('tooltip');
    if(hover){tt.style.display='block';tt.style.left=(sx+14)+'px';tt.style.top=(sy+14)+'px';tt.innerHTML=`<b>${hover.label}</b>${hover.lang} · cloud #${(compOf[hover.id]??0)+1}<br>${hover.indeg}← ${hover.outdeg}→`;}
    else tt.style.display='none';
  }
});
window.addEventListener('mouseup',()=>{if(dragNode){dragNode=null;}panDrag=false;panning=false;canvas.classList.remove('dragging');});
canvas.addEventListener('wheel',e=>{
  e.preventDefault();const r=canvas.getBoundingClientRect();const mx=e.clientX-r.left,my=e.clientY-r.top;
  const b=screenToWorld(mx,my);scale=Math.max(0.15,Math.min(5,scale*(e.deltaY<0?1.12:0.89)));
  const a=screenToWorld(mx,my);offX+=(a.x-b.x)*scale;offY+=(a.y-b.y)*scale;updateZoom();
},{passive:false});

mm.addEventListener('mousedown',e=>{
  const r=mm.getBoundingClientRect();
  const mx=e.clientX-r.left, my=e.clientY-r.top;
  const s=mm._mmS, ox=mm._mmOX, oy=mm._mmOY;
  if(!s) return;
  const wx=(mx-ox)/s, wy=(my-oy)/s;
  offX = W/2 - wx*scale;
  offY = H/2 - wy*scale;
});

document.addEventListener('keydown',e=>{
  if(e.target.tagName==='INPUT')return;
  const step=40;
  if(e.key==='ArrowLeft'){offX+=step;}
  else if(e.key==='ArrowRight'){offX-=step;}
  else if(e.key==='ArrowUp'){offY+=step;}
  else if(e.key==='ArrowDown'){offY-=step;}
  else if(e.key==='+'||e.key==='='){scale=Math.min(5,scale*1.15);updateZoom();}
  else if(e.key==='-'||e.key==='_'){scale=Math.max(0.15,scale*0.87);updateZoom();}
  else if(e.key==='f'||e.key==='F'){fitView();}
  else if(e.key==='Escape'){selectedSet.clear();selected=null;updInfo();}
  else return;
  e.preventDefault();
});

const searchInput = document.getElementById('search');
const suggestionsDiv = document.getElementById('suggestions');

searchInput.addEventListener('input', e => {
  searchQuery = e.target.value.toLowerCase().trim();
  showSuggestions();
});

searchInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') {
    const m = nodes.find(n => matchesSearch(n));
    if (m) {
      focusNode(m);
      suggestionsDiv.style.display = 'none';
    }
  }
});

function showSuggestions() {
  if (!searchQuery) {
    suggestionsDiv.style.display = 'none';
    return;
  }
  const matches = nodes.filter(n =>
    n.label.toLowerCase().includes(searchQuery) ||
    n.id.toLowerCase().includes(searchQuery)
  ).slice(0, 8);

  if (matches.length === 0) {
    suggestionsDiv.style.display = 'none';
    return;
  }
  suggestionsDiv.innerHTML = matches.map(n => `
    <div class="suggestion-item" data-id="${n.id}">
      <span style="color:var(--txt);font-weight:600;">${n.label}</span>
      <span style="opacity:0.5;font-size:9px;margin-left:5px;">(${n.lang})</span>
      <div style="font-size:9px;opacity:0.4;overflow:hidden;text-overflow:ellipsis;">${n.id}</div>
    </div>
  `).join('');
  suggestionsDiv.style.display = 'block';
}

suggestionsDiv.addEventListener('click', e => {
  const item = e.target.closest('.suggestion-item');
  if (item) {
    const id = item.getAttribute('data-id');
    const n = nodes.find(x => x.id === id);
    if (n) {
      focusNode(n);
      searchInput.value = n.label;
      searchQuery = n.label.toLowerCase();
      suggestionsDiv.style.display = 'none';
    }
  }
});

document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrapper')) {
    suggestionsDiv.style.display = 'none';
  }
});

document.getElementById('btnFit').addEventListener('click',()=>{fitView();});
document.getElementById('btnRelayout').addEventListener('click',()=>{build();forceAlpha=1.0;fitView();});
document.getElementById('btnInOnly').addEventListener('click',function(){inPackOnly=!inPackOnly;this.classList.toggle('active',inPackOnly);updateStats();});

resize();build();forceAlpha=1.0;fitView();loop();
</script>
</body>
</html>
"""

_DEFAULT_LANG_COLORS = {
    "python": "#3b82f6",
    "typescript": "#38bdf8",
    "javascript": "#eab308",
    "rust": "#f97316",
    "go": "#06b6d4",
    "java": "#ef4444",
    "c": "#a78bfa",
    "cpp": "#8b5cf6",
    "kotlin": "#f472b6",
    "markdown": "#9aa8c2",
    "json": "#fbbf24",
    "toml": "#fb923c",
    "yaml": "#94a3b8",
    "text": "#9aa8c2",
    "in_pack": "#4ade80",
    "default": "#64748b",
}


def _path_id(path: Path) -> str:
    return path.as_posix()


def _load_asset_as_data_uri(path: Path) -> str | None:
    """Read an SVG/PNG asset and return a base64 data URI (None if missing).

    The generated graph.html is self-contained and often viewed outside the
    project tree, so we embed branding assets inline rather than referencing
    relative paths that would break.
    """
    import base64

    try:
        raw = path.read_bytes()
    except OSError:
        return None
    suffix = path.suffix.lower()
    if suffix == ".svg":
        mime = "image/svg+xml"
    elif suffix == ".png":
        mime = "image/png"
    else:
        mime = "application/octet-stream"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def render_graph_html(
    graph: RelationGraph,
    title: str = "Scriber Relation Graph",
    lang_colors: dict[str, str] | None = None,
    included_paths: set[Path] | None = None,
    assets_dir: Path | None = None,
) -> str:
    """Render the graph as a self-contained interactive HTML file.

    Implements the audit-contract vision: multiple gravitational centers (per
    connected component + per top-level dir), radial/hierarchical init from
    dependency depth, weighted springs, and map-class navigation.

    ``assets_dir`` (project ``assets/``) is used to inline the Scriber icon
    (favicon) and logo (topbar) so the visualization carries the brand even
    when viewed outside the project tree.
    """
    palette = lang_colors or _DEFAULT_LANG_COLORS
    included = {_path_id(p) for p in (included_paths or set())}

    # Inline branding assets (favicon + topbar logo + name logo) as data URIs.
    icon_uri: str | None = None
    logo_uri: str | None = None
    name_xml: str | None = None
    if assets_dir is not None:
        icon_uri = _load_asset_as_data_uri(assets_dir / "scriber_icon.svg")
        logo_uri = _load_asset_as_data_uri(assets_dir / "scriber_logo.svg")
        name_path = assets_dir / "scriber_name.svg"
        if name_path.exists():
            try:
                with open(name_path, "r", encoding="utf-8") as f:
                    xml_content = f.read()
                # Recolor text for dark mode readability: "Project" -> white, "Scriber" -> teal theme accent
                xml_content = xml_content.replace('fill="dimgray"', 'fill="#f8fafc"')
                xml_content = xml_content.replace('fill="dodgerblue"', 'fill="#2dd4bf"')
                # Set responsive viewBox to trim empty padding (starts at x=10, width=220)
                xml_content = xml_content.replace(
                    '<svg width="250" height="40" ',
                    '<svg viewBox="10 0 220 36" class="brand-name-svg" ',
                )
                name_xml = xml_content
            except Exception:
                name_xml = None

    degree: dict[str, int] = {}
    for edge in graph.edges:
        s = _path_id(edge.source)
        t = _path_id(edge.target)
        degree[s] = degree.get(s, 0) + 1
        degree[t] = degree.get(t, 0) + 1

    nodes_data = []
    for node in graph.nodes:
        nid = _path_id(node)
        suffix = node.suffix.lower().lstrip(".") if node.suffix else ""
        nodes_data.append(
            {
                "id": nid,
                "label": node.name,
                "lang": _lang_from_suffix(suffix),
                "weight": degree.get(nid, 1),
            }
        )

    edges_data = [
        {
            "s": _path_id(edge.source),
            "t": _path_id(edge.target),
            "k": edge.kind,
            "conf": float(edge.confidence),
        }
        for edge in graph.edges
    ]

    data_json = json.dumps(
        {"nodes": nodes_data, "edges": edges_data, "included": sorted(included)}
    )
    # Favicon + topbar logo as inline data URIs (graceful no-op if assets missing).
    favicon_tag = (
        f'<link rel="icon" type="image/svg+xml" href="{icon_uri}">' if icon_uri else ""
    )
    logo_tag = ""
    if logo_uri:
        name_tag = name_xml if name_xml else f"<h1>{title}</h1>"
        logo_tag = f"""<img class="brand-logo" alt="Scriber" src="{logo_uri}">
    <div class="brand-text">
      {name_tag}
      <div class="sub">dependency graph</div>
    </div>"""
    else:
        logo_tag = f"""<div class="brand-text">
      <h1>{title}</h1>
      <div class="sub">dependency graph</div>
    </div>"""

    return (
        _HTML_TEMPLATE.replace("__FAVICON__", favicon_tag)
        .replace("__LOGO__", logo_tag)
        .replace("__TITLE__", title.replace('"', "&quot;"))
        .replace("__DATA__", data_json)
        .replace("__LANG_COLORS__", json.dumps(palette))
    )


def _lang_from_suffix(suffix: str) -> str:
    mapping = {
        "py": "python",
        "pyi": "python",
        "ts": "typescript",
        "tsx": "typescript",
        "js": "javascript",
        "jsx": "javascript",
        "rs": "rust",
        "go": "go",
        "java": "java",
        "kt": "kotlin",
        "c": "c",
        "h": "c",
        "cpp": "cpp",
        "hpp": "cpp",
        "cc": "cpp",
        "md": "markdown",
        "json": "json",
        "toml": "toml",
        "yaml": "yaml",
        "yml": "yaml",
        "txt": "text",
    }
    return mapping.get(suffix, "unknown")
