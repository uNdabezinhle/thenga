/* Northbound client — talks to the Reka DRF API */
(() => {
'use strict';

const API_BASE = (window.REKA_API_BASE ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
const APP_VERSION = '1.0.0 (build 1)';

const I = (d) => `<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICO = {
  shop: I('<path d="M3 9l1-4h16l1 4"/><path d="M4 9v11h16V9"/><path d="M9 13h6"/>'),
  search: I('<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/>'),
  cart: I('<path d="M6 6h15l-1.5 9h-12z"/><circle cx="9" cy="20" r="1"/><circle cx="18" cy="20" r="1"/><path d="M6 6L5 3H2"/>'),
  saved: I('<path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z"/>'),
  user: I('<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
  back: I('<path d="M15 18l-6-6 6-6"/>'),
  plus: I('<path d="M12 5v14M5 12h14"/>'),
  minus: I('<path d="M5 12h14"/>'),
  trash: I('<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>'),
  star: I('<path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7-6.3-4.6L5.7 21l2.3-7-6-4.6h7.6z" fill="currentColor" stroke="none"/>'),
  check: I('<path d="M20 6L9 17l-5-5"/>'),
  close: I('<path d="M18 6L6 18M6 6l12 12"/>'),
  logout: I('<path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>'),
  shield: I('<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'),
  key: I('<path d="M21 2l-2 2m-7.6 7.6a5 5 0 11-7.07 7.07 5 5 0 017.07-7.07zM15 7l3 3"/><circle cx="7.5" cy="16.5" r="1" fill="currentColor"/>'),
  tag: I('<path d="M20.6 13.4L12 22l-9-9V3h10l7.6 7.6a2 2 0 010 2.8z"/><circle cx="7.5" cy="7.5" r="1.2" fill="currentColor" stroke="none"/>'),
  truck: I('<path d="M1 3h15v13H1zM16 8h4l3 4v4h-7V8z"/><circle cx="5.5" cy="18.5" r="2"/><circle cx="18.5" cy="18.5" r="2"/>'),
  box: I('<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><path d="M3.3 7L12 12l8.7-5M12 22V12"/>'),
  chev: I('<path d="M9 18l6-6-6-6"/>'),
  staff: I('<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>'),
};

const ENDPOINTS = [
  {m:'POST',  p:'/api/v1/auth/users/', g:'Authentication'},
  {m:'POST',  p:'/api/v1/auth/token/', g:'Authentication'},
  {m:'POST',  p:'/api/v1/auth/token/refresh/', g:'Authentication'},
  {m:'POST',  p:'/api/v1/auth/mfa/verify/', g:'Authentication'},
  {m:'POST',  p:'/api/v1/auth/mfa/setup/', g:'Authentication'},
  {m:'POST',  p:'/api/v1/auth/mfa/generate_backup_codes/', g:'Authentication'},
  {m:'DELETE',p:'/api/v1/auth/mfa/disable/', g:'Authentication'},
  {m:'GET',   p:'/api/v1/auth/profiles/', g:'Authentication'},
  {m:'GET',   p:'/api/v1/cart/cart/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/add_item/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/items/{id}/update/', g:'Cart'},
  {m:'DELETE',p:'/api/v1/cart/cart/items/{id}/remove/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/apply_discount/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/select_shipping/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/transfer_cart/', g:'Cart'},
  {m:'POST',  p:'/api/v1/cart/cart/clear/', g:'Cart'},
  {m:'GET',   p:'/api/v1/cart/saved-items/', g:'Cart'},
  {m:'GET',   p:'/api/v1/products/', g:'Products'},
  {m:'GET',   p:'/api/v1/products/{id}/', g:'Products'},
  {m:'POST',  p:'/api/v1/orders/', g:'Orders'},
  {m:'GET',   p:'/api/v1/orders/{id}/tracking/', g:'Orders'},
  {m:'GET',   p:'/api/v1/orders/{id}/invoice/', g:'Orders'},
  {m:'POST',  p:'/api/v1/orders/{id}/cooling-off/exercise/', g:'Orders'},
  {m:'POST',  p:'/api/v1/payments/sandbox/complete/', g:'Payments'},
  {m:'POST',  p:'/api/v1/payments/webhooks/sandbox/', g:'Payments'},
  {m:'GET',   p:'/api/v1/orders/staff/', g:'Staff'},
  {m:'POST',  p:'/api/v1/payments/refunds/', g:'Staff'},
  {m:'GET',   p:'/api/v1/payments/reconciliation/', g:'Staff'},
];

const uuid = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
  const r = Math.random()*16|0, v = c === 'x' ? r : (r&0x3|0x8);
  return v.toString(16);
});

const store = {
  get(k, d=null){ try { const v = localStorage.getItem('nb_'+k); return v ? JSON.parse(v) : d; } catch { return d; } },
  set(k, v){ localStorage.setItem('nb_'+k, JSON.stringify(v)); },
  del(k){ localStorage.removeItem('nb_'+k); },
};

const S = {
  screen:'shop', tab:'shop', authView:'login', ctab:'log',
  user: store.get('user'),
  tokens: store.get('tokens'),
  mfaPending: null,
  preAuthToken: null,
  cartSession: store.get('cartSession') || uuid(),
  promos: [],
  ads: [],
  inbox: [],
  profile: null,
  prefs: null,
  shippingRates: [],
  staffAds: [],
  staffPromos: [],
  bundles: [],
  loyalty: null,
  loyaltyNote: '',
  staffFlashes: [],
  staffBundles: [],
  recent: store.get('recent') || [],
  products: [],
  categories: [{id:'all', label:'Everything'}],
  cart: null,
  saved: [],
  orders: [],
  wishlist: store.get('wishlist') || [],
  product: null,
  variant: null,
  filters:{q:'', cat:'all', sort:'featured'},
  form:{email:'jordan@northbound.test', password:'correct-horse-42',
        username:'jordan.m', password2:'correct-horse-42', mfacode:'', code:'', referral:''},
  log:[], hits:new Set(), busy:false, snack:null, formErr:null,
  flags:{slow:false},
  checkout:{addr:'14 Harbour Lane, Cape Town 8001', pay:'card'},
  expanded:new Set(),
  ready:false,
  lastMs: 0,
  staffOrders: [],
  recon: null,
  staffFilter: '',
};

store.set('cartSession', S.cartSession);

const money = n => {
  const num = typeof n === 'string' ? parseFloat(n) : Number(n || 0);
  return 'R ' + num.toLocaleString('en-ZA',{minimumFractionDigits:2, maximumFractionDigits:2});
};
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const byId = id => S.products.find(p => p.id === id || p.id === +id);

function topo(hue, seed){
  let rings = '';
  for (let k = 0; k < 7; k++){
    const base = 12 + k * 11;
    let pts = [];
    for (let a = 0; a <= 360; a += 12){
      const t = a * Math.PI / 180;
      const r = base * (1 + 0.10*Math.sin(3*t + seed) + 0.07*Math.sin(5*t + seed*1.7) + 0.04*Math.sin(7*t + k));
      pts.push((100 + r*Math.cos(t)).toFixed(1) + ',' + (100 + r*Math.sin(t)).toFixed(1));
    }
    const op = 0.10 + k*0.035;
    rings += `<polygon points="${pts.join(' ')}" fill="none" stroke="hsl(${hue} 42% 26%)" stroke-width="1.1" opacity="${op.toFixed(2)}"/>`;
  }
  return `<svg viewBox="0 0 200 200" style="width:100%;height:100%;display:block;background:hsl(${hue} 34% 93%)">${rings}
    <circle cx="100" cy="100" r="7" fill="hsl(${hue} 46% 30%)" opacity=".5"/></svg>`;
}

function cartItems(){ return (S.cart && S.cart.items) || []; }
function cartCount(){ return cartItems().reduce((n,i) => n + i.quantity, 0); }
function cartTotals(){ return (S.cart && S.cart.totals) || {subtotal:'0.00', discount_total:'0.00', shipping_total:'0.00', grand_total:'0.00'}; }
function selectedShip(){
  const list = (S.cart && S.cart.shipping_estimates) || [];
  return list.find(s => s.is_selected) || list[0] || null;
}
function activeDiscount(){ return ((S.cart && S.cart.discounts) || [])[0] || null; }

function snack(msg){
  S.snack = msg;
  render();
  clearTimeout(snack._t);
  snack._t = setTimeout(() => { S.snack = null; render(); }, 2600);
}
function go(screen, tab){
  S.screen = screen;
  if (tab) S.tab = tab;
  S.formErr = null;
  render();
  const vp = document.getElementById('viewport');
  if (vp) vp.scrollTop = 0;
}

function persistAuth(){
  if (S.user) store.set('user', S.user); else store.del('user');
  if (S.tokens) store.set('tokens', S.tokens); else store.del('tokens');
  store.set('wishlist', S.wishlist);
  store.set('cartSession', S.cartSession);
}

/* ---------- API layer ---------- */
let reqId = 0;

async function api(method, route, opts = {}){
  const { body = null, path = route, headers = {} } = opts;
  const id = ++reqId;
  const url = API_BASE + path;
  const h = {
    'Accept': 'application/json',
    'X-App-Version': APP_VERSION,
    'X-Request-ID': uuid(),
    'X-Cart-Session': S.cartSession,
    ...headers,
  };
  if (S.tokens && S.tokens.access) h['Authorization'] = 'Bearer ' + S.tokens.access;
  if (body !== null) h['Content-Type'] = 'application/json';

  const t0 = performance.now();
  if (S.flags.slow) await new Promise(r => setTimeout(r, 900 + Math.random()*400));

  let res, data, status;
  try {
    res = await fetch(url, {
      method,
      headers: h,
      body: body !== null ? JSON.stringify(body) : undefined,
    });
    status = res.status;
    const text = await res.text();
    try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }
  } catch (err) {
    status = 0;
    data = { error: { code: 'network_error', message: String(err.message || err) } };
  }

  // Silent refresh on 401
  if (status === 401 && S.tokens && S.tokens.refresh && !path.includes('/token/')) {
    const refreshed = await tryRefresh();
    if (refreshed) return api(method, route, opts);
  }

  const ms = Math.round(performance.now() - t0);
  S.lastMs = ms;
  S.log.unshift({id, method, route, path, status, ms, body, res: data});
  if (S.log.length > 40) S.log.pop();
  S.hits.add(method + ' ' + route);
  renderConsole();
  return { status, data, ms, ok: status >= 200 && status < 300 };
}

async function tryRefresh(){
  if (!S.tokens || !S.tokens.refresh) return false;
  const t0 = performance.now();
  try {
    const res = await fetch(API_BASE + '/api/v1/auth/token/refresh/', {
      method: 'POST',
      headers: {'Content-Type':'application/json', 'X-App-Version': APP_VERSION},
      body: JSON.stringify({ refresh: S.tokens.refresh }),
    });
    const data = await res.json().catch(() => ({}));
    const ms = Math.round(performance.now() - t0);
    S.log.unshift({id: 'r'+Date.now(), method:'POST', route:'/api/v1/auth/token/refresh/', path:'/api/v1/auth/token/refresh/', status:res.status, ms, body:{refresh:'…'}, res:data});
    if (!res.ok) {
      S.tokens = null; S.user = null; persistAuth();
      return false;
    }
    S.tokens.access = data.access;
    if (data.refresh) S.tokens.refresh = data.refresh;
    persistAuth();
    return true;
  } catch {
    return false;
  }
}

function errMsg(data, fallback='Something went wrong.'){
  if (!data) return fallback;
  if (data.error) {
    if (data.error.message) return data.error.message;
    if (data.error.errors && data.error.errors[0]) return data.error.errors[0].message;
  }
  if (data.detail) return typeof data.detail === 'string' ? data.detail : fallback;
  return fallback;
}

/* ---------- data loaders ---------- */
function remember(id){
  const n = +id;
  if (!n) return;
  S.recent = [n, ...S.recent.filter(x => +x !== n)].slice(0, 8);
  store.set('recent', S.recent);
}

async function loadMerch(){
  const promos = await api('GET', '/api/v1/promotions/', { path: '/api/v1/promotions/' });
  if (promos.ok) S.promos = (promos.data && promos.data.results) || [];
  const ads = await api('GET', '/api/v1/ads/', { path: '/api/v1/ads/?placement=shop_top' });
  if (ads.ok) S.ads = (ads.data && ads.data.results) || [];
  const bundles = await api('GET', '/api/v1/promotions/bundles/', { path: '/api/v1/promotions/bundles/' });
  if (bundles.ok) S.bundles = (bundles.data && bundles.data.results) || [];
}

async function loadLoyalty(){
  if (!S.tokens) { S.loyalty = null; return; }
  const r = await api('GET', '/api/v1/promotions/loyalty/', { path: '/api/v1/promotions/loyalty/' });
  if (r.ok) S.loyalty = r.data;
}

function val(id){
  const el = document.getElementById(id);
  return el ? el.value : '';
}

async function loadSettings(){
  const prof = await api('GET', '/api/v1/auth/profiles/', { path: '/api/v1/auth/profiles/' });
  const rows = prof.data && (prof.data.results || prof.data);
  S.profile = Array.isArray(rows) ? (rows[0] || null) : null;
  const prefs = await api('GET', '/api/v1/notifications/preferences/', { path: '/api/v1/notifications/preferences/' });
  if (prefs.ok) S.prefs = prefs.data;
  await loadLoyalty();
}

async function loadStore(){
  const rates = await api('GET', '/api/v1/orders/staff/shipping-rates/', { path: '/api/v1/orders/staff/shipping-rates/' });
  S.shippingRates = (rates.data && rates.data.results) || [];
  const ads = await api('GET', '/api/v1/ads/staff/', { path: '/api/v1/ads/staff/' });
  S.staffAds = (ads.data && ads.data.results) || [];
  const promos = await api('GET', '/api/v1/promotions/staff/', { path: '/api/v1/promotions/staff/' });
  S.staffPromos = (promos.data && promos.data.results) || [];
  const flashes = await api('GET', '/api/v1/promotions/staff/flashes/', { path: '/api/v1/promotions/staff/flashes/' });
  S.staffFlashes = (flashes.data && flashes.data.results) || [];
  const bundles = await api('GET', '/api/v1/promotions/staff/bundles/', { path: '/api/v1/promotions/staff/bundles/' });
  S.staffBundles = (bundles.data && bundles.data.results) || [];
}

async function loadInbox(){
  if (!S.tokens) { S.inbox = []; return; }
  const r = await api('GET', '/api/v1/notifications/inbox/', { path: '/api/v1/notifications/inbox/' });
  if (r.ok) S.inbox = (r.data && r.data.results) || [];
}

async function loadProducts(){
  const q = new URLSearchParams();
  if (S.filters.cat && S.filters.cat !== 'all') q.set('category', S.filters.cat);
  if (S.filters.q) q.set('q', S.filters.q);
  if (S.filters.sort && S.filters.sort !== 'featured') q.set('sort', S.filters.sort);
  q.set('page_size', '100');
  const { ok, data } = await api('GET', '/api/v1/products/', { path: '/api/v1/products/?' + q.toString() });
  if (ok) {
    // cursor or plain results
    S.products = data.results || data || [];
  }
}

async function loadCart(){
  const { ok, data } = await api('GET', '/api/v1/cart/cart/');
  if (ok) S.cart = data;
}

async function loadSaved(){
  if (!S.user) { S.saved = []; return; }
  const { ok, data } = await api('GET', '/api/v1/cart/saved-items/');
  if (ok) S.saved = Array.isArray(data) ? data : (data.results || []);
}

async function loadOrders(){
  if (!S.user) { S.orders = []; return; }
  const { ok, data } = await api('GET', '/api/v1/orders/');
  if (ok) S.orders = data.results || data || [];
}

async function loadStaffOrders(){
  if (!S.user || !S.user.is_staff_ops) { S.staffOrders = []; return; }
  const q = S.staffFilter ? ('?status=' + encodeURIComponent(S.staffFilter)) : '';
  const { ok, data } = await api('GET', '/api/v1/orders/staff/', {
    path: '/api/v1/orders/staff/' + q,
  });
  if (ok) S.staffOrders = data.results || [];
}

async function loadRecon(){
  if (!S.user || !S.user.is_staff_ops) { S.recon = null; return; }
  const { ok, data } = await api('GET', '/api/v1/payments/reconciliation/', {
    path: '/api/v1/payments/reconciliation/',
  });
  if (ok) S.recon = data;
}

async function loadProduct(id){
  const { ok, data } = await api('GET', '/api/v1/products/{id}/', { path: `/api/v1/products/${id}/` });
  if (ok) {
    S.product = data;
    S.variant = (data.variants || []).find(v => +v.stock > 0) || null;
  }
}

/* ---------- screens ---------- */
function scShop(){
  const list = S.products;
  return `
  <div class="screen">
    <div class="appbar">
      <div style="flex:1">
        <h1>Northbound</h1>
        <div class="sub">${S.user ? 'Welcome back, ' + esc((S.user.name||'').split(' ')[0] || S.user.username) : 'Browsing as a guest'}</div>
      </div>
      <button class="iconbtn" data-act="tab" data-v="search" aria-label="Search">${ICO.search}</button>
      <button class="iconbtn" data-act="tab" data-v="cart" aria-label="Cart" style="position:relative">
        ${ICO.cart}${cartCount() ? `<i class="badge">${cartCount()}</i>` : ''}
      </button>
    </div>
    <div class="body">
      <div class="chips">
        ${S.categories.map(c => `<button class="chip ${S.filters.cat===c.id?'on':''}" data-act="cat" data-v="${c.id}">${c.label}</button>`).join('')}
      </div>
      ${(S.ads||[]).slice(0,1).map(ad => `<button class="card" style="width:100%;text-align:left;margin-bottom:10px;background:var(--forest);color:#fff" data-act="open" data-v="${ad.product_id||''}">
        <b style="color:var(--lime)">${esc(ad.title)}</b>
        ${ad.body ? `<div style="font-size:12.5px;margin-top:4px">${esc(ad.body)}</div>` : ''}
      </button>`).join('')}
      ${(S.promos||[]).slice(0,1).map(p => `<p style="font-size:13px;font-weight:700;margin:0 0 10px">${esc(p.title)} · code <span class="mono">${esc(p.code)}</span></p>`).join('')}
      ${(S.bundles||[]).map(b => `<div class="card" style="margin-bottom:10px">
        <b style="font-size:14px">${esc(b.title)}</b>
        <div class="muted" style="font-size:12px;margin-top:4px">${(b.items||[]).map(i => esc(i.name)).join(' + ')}</div>
        <div class="pr" style="margin:8px 0">${money(b.price)}${b.compare_at && b.compare_at !== b.price ? `<span style="text-decoration:line-through;color:#8E998F;font-size:12px;margin-left:6px">${money(b.compare_at)}</span>` : ''}</div>
        <button class="btn sm" data-act="addbundle" data-v="${b.id}">Add bundle</button>
      </div>`).join('')}
      ${(() => {
        const seen = (S.recent||[]).map(id => list.find(p => p.id === id || p.id === +id)).filter(Boolean);
        if (!seen.length) return '';
        return `<div class="h2">Recently viewed</div><div class="grid">${seen.map(cardHTML).join('')}</div>`;
      })()}
      ${list.length ? `<div class="grid">${list.map(cardHTML).join('')}</div>`
        : `<div class="empty"><h3>Loading catalogue…</h3><p class="muted">Connecting to ${esc(API_BASE)}</p></div>`}
      <p class="muted" style="margin-top:18px;text-align:center">${list.length} items · prices include VAT · live API</p>
    </div>
  </div>`;
}

function cardHTML(p){
  const out = p.sold_out || (p.variants && p.variants.every(v => +v.stock === 0));
  return `<button class="pcard" data-act="open" data-v="${p.id}">
    <div class="art">${topo(p.hue||150, p.id)}${out ? '<span class="tagsold">Sold out</span>' : ''}</div>
    <div class="meta">
      <div class="br">${esc(p.brand)}</div>
      <div class="nm">${esc(p.name)}</div>
      <div class="row" style="gap:4px;margin-top:5px;color:#C99A2E">${ICO.star}<span style="font-size:11px;color:#6E7B72">${p.rating||0} (${p.reviews||0})</span></div>
      <div class="pr">${money(p.price)}${p.compare_at && p.compare_at !== p.price ? `<span style="text-decoration:line-through;color:#8E998F;font-size:11px;margin-left:6px;font-weight:500">${money(p.compare_at)}</span>` : ''}</div>
    </div>
  </button>`;
}

function scSearch(){
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Search</h1></div></div>
    <div class="body">
      <div class="searchfield">
        ${ICO.search}
        <input id="q" placeholder="Search packs, shells, stoves…" value="${esc(S.filters.q)}" autocomplete="off">
        ${S.filters.q ? '<button class="iconbtn" style="width:26px;height:26px" data-act="clearq">'+ICO.close+'</button>' : ''}
      </div>
      <div class="chips">
        ${[['featured','Featured'],['low','Price ↑'],['high','Price ↓'],['rated','Top rated']]
          .map(([k,l]) => `<button class="chip ${S.filters.sort===k?'on':''}" data-act="sort" data-v="${k}">${l}</button>`).join('')}
      </div>
      <div class="chips">
        ${S.categories.map(c => `<button class="chip ${S.filters.cat===c.id?'on':''}" data-act="cat" data-v="${c.id}">${c.label}</button>`).join('')}
      </div>
      ${S.products.length ? `<div class="grid">${S.products.map(cardHTML).join('')}</div>`
        : `<div class="empty"><h3>Nothing matched “${esc(S.filters.q)}”</h3><p class="muted">Try a broader term, or clear the category filter.</p></div>`}
    </div>
  </div>`;
}

function scProduct(){
  const p = S.product;
  if (!p) return `<div class="screen"><div class="empty"><h3>Loading…</h3></div></div>`;
  const v = S.variant;
  const stock = v ? +v.stock : null;
  const specs = p.specs || [];
  const reviews = p.review_list || [];
  return `
  <div class="screen">
    <div class="appbar">
      <button class="iconbtn" data-act="back">${ICO.back}</button>
      <div style="flex:1"><div class="sub mono" style="font-size:11px">${esc(p.sku)}</div></div>
      <button class="iconbtn" data-act="wish" data-v="${p.id}" style="color:${S.wishlist.includes(p.id)?'#0E2A22':'#8E998F'}">${ICO.saved}</button>
    </div>
    <div class="body">
      <div style="border-radius:var(--r);overflow:hidden;border:1px solid var(--hair);aspect-ratio:4/3">${topo(p.hue||150, p.id)}</div>
      <div class="br" style="font-size:11px;color:var(--mute);letter-spacing:.06em;text-transform:uppercase;margin-top:16px">${esc(p.brand)}</div>
      <h2 style="font-family:'Archivo';font-size:23px;font-weight:800;letter-spacing:-.02em;line-height:1.15;margin:4px 0 8px">${esc(p.name)}</h2>
      <div class="row" style="gap:6px;color:#C99A2E">${ICO.star}<span style="font-size:12.5px;color:var(--ink);font-weight:600">${p.rating||0}</span>
        <span class="muted">${p.reviews||0} reviews</span></div>
      <div class="mono" style="font-size:24px;font-weight:600;color:var(--forest);margin:12px 0 4px">${money(p.price)}${p.compare_at && p.compare_at !== p.price ? `<span style="text-decoration:line-through;color:var(--mute);font-size:14px;margin-left:8px;font-weight:500">${money(p.compare_at)}</span>` : ''}</div>
      <p class="muted" style="margin-top:10px">${esc(p.description||'')}</p>

      <div class="h2">Choose an option</div>
      <div class="row" style="flex-wrap:wrap;gap:8px">
        ${(p.variants||[]).map(x => `<button class="varbtn ${v && v.id===x.id?'on':''}" data-act="variant" data-v="${x.id}" ${+x.stock===0?'disabled':''}>${esc(x.label)}</button>`).join('')}
      </div>
      ${v ? `<p class="muted" style="margin-top:9px">${stock > 0
          ? (stock <= 3 ? `Only <b style="color:#9B3B1E">${stock} left</b> in stock` : `${stock} in stock`)
          : 'Out of stock'}</p>` : '<p class="muted" style="margin-top:9px">Select an option to see stock.</p>'}

      <div class="h2">Specification</div>
      <div class="card">
        ${specs.map((s,i) => `<div class="between" style="padding:7px 0;${i?'border-top:1px solid var(--hair)':''}">
          <span class="muted">${esc(s.key)}</span><span class="mono" style="font-size:12.5px;font-weight:500">${esc(s.value)}</span></div>`).join('') || '<p class="muted">No specs listed.</p>'}
      </div>

      <div class="h2">What buyers say</div>
      ${reviews.length ? reviews.map(r => `<div class="card" style="margin-bottom:8px">
        <div class="between"><b style="font-size:13px">${esc(r.who)}</b>
          <span style="color:#C99A2E;font-size:11px">${'★'.repeat(r.rating)}</span></div>
        <p class="muted" style="margin-top:6px">${esc(r.body)}</p></div>`).join('')
        : '<p class="muted">No reviews yet.</p>'}
      ${S.user ? `<div class="card" style="margin-top:10px">
        <div class="field"><label>Stars</label><input id="review-rating" inputmode="numeric" value="5"></div>
        <div class="field"><label>Your review</label><textarea id="review-body" rows="3"></textarea></div>
        <button class="btn sm" data-act="review">Post review</button>
      </div>` : '<p class="muted" style="margin-top:8px">Sign in to review this product.</p>'}

      <div style="height:14px"></div>
      <button class="btn" data-act="add" ${!v || +v.stock===0 || S.busy ? 'disabled':''}>
        ${S.busy ? '<span class="spinner"></span> Adding' : (v && +v.stock===0 ? 'Out of stock' : 'Add to cart')}
      </button>
      <button class="btn ghost" style="margin-top:8px" data-act="wish" data-v="${p.id}">
        ${S.wishlist.includes(p.id) ? 'Saved to wishlist' : 'Save to wishlist'}
      </button>
    </div>
  </div>`;
}

function scCart(){
  const items = cartItems();
  const t = cartTotals();
  const disc = activeDiscount();
  const ships = (S.cart && S.cart.shipping_estimates) || [];
  if (!items.length) return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Cart</h1></div></div>
    <div class="empty">${ICO.cart}<h3 style="margin-top:12px">Your cart is empty</h3>
      <p class="muted" style="margin-bottom:18px">Everything you add stays here, whether or not you sign in.</p>
      <button class="btn sm lime" style="margin:0 auto" data-act="tab" data-v="shop">Browse the shop</button></div>
  </div>`;

  return `
  <div class="screen">
    <div class="appbar">
      <div style="flex:1"><h1>Cart</h1><div class="sub">${cartCount()} item${cartCount()===1?'':'s'}</div></div>
      <button class="linkbtn" data-act="clear">Clear all</button>
    </div>
    <div class="body">
      ${items.map(i => `<div class="citem">
          <div class="thumb">${topo(i.hue||150, i.product_id)}</div>
          <div style="flex:1;min-width:0">
            <div class="between" style="align-items:flex-start">
              <div style="min-width:0">
                <div style="font-size:13.5px;font-weight:600;line-height:1.3">${esc(i.product_name)}</div>
                <div class="muted" style="font-size:11.5px">${esc(i.variant_label||'')}</div>
              </div>
              <div class="mono" style="font-size:13px;font-weight:600;white-space:nowrap">${money(i.line_total)}</div>
            </div>
            <div class="between" style="margin-top:9px">
              <div class="stepper">
                <button data-act="qty" data-v="${i.id}" data-d="-1">${ICO.minus}</button>
                <span class="q">${i.quantity}</span>
                <button data-act="qty" data-v="${i.id}" data-d="1">${ICO.plus}</button>
              </div>
              <div class="row" style="gap:12px">
                <button class="linkbtn" data-act="savelater" data-v="${i.id}">Save for later</button>
                <button class="iconbtn" style="width:30px;height:30px;color:#9B3B1E" data-act="remove" data-v="${i.id}">${ICO.trash}</button>
              </div>
            </div>
          </div>
        </div>`).join('')}

      <div class="h2">Discount code</div>
      ${disc ? `<div class="card between" style="background:#F7FBEE;border-color:#CFE39A">
          <div class="row" style="gap:9px;color:var(--forest)">${ICO.tag}
            <div><b class="mono" style="font-size:13px">${esc(disc.code)}</b>
            <div class="muted" style="font-size:11.5px">${disc.discount_type==='percentage'?disc.amount+'% off':'R '+disc.amount+' off'}</div></div></div>
          <button class="linkbtn" data-act="undiscount">Remove</button></div>`
        : `<div class="row" style="gap:8px">
            <input id="code" placeholder="Enter code" value="${esc(S.form.code)}" style="flex:1;padding:13px 14px;border:1px solid var(--hair);border-radius:11px;font:inherit;font-size:14px;text-transform:uppercase" autocomplete="off">
            <button class="btn sm" data-act="discount" style="padding:13px 18px">Apply</button>
          </div>
          <p class="muted" style="margin-top:7px;font-size:11.5px">Try <b class="mono">DISCOUNT20</b></p>`}

      <div class="h2">Delivery</div>
      ${ships.map(s => `<button class="ship ${s.is_selected?'on':''}" data-act="ship" data-v="${s.id}">
        <span class="radio"></span>
        <span style="flex:1"><b style="font-size:13.5px">${esc(s.method_name)}</b>
          <span class="muted" style="display:block;font-size:11.5px">${esc(s.estimated_days)}</span></span>
        <span class="mono" style="font-size:13px;font-weight:600">${+s.price ? money(s.price) : 'Free'}</span>
      </button>`).join('')}

      <div class="hr"></div>
      <div class="totals">
        <div class="ln"><span>Subtotal</span><span>${money(t.subtotal)}</span></div>
        ${+t.discount_total > 0 ? `<div class="ln disc"><span>Discount</span><span>− ${money(t.discount_total)}</span></div>` : ''}
        <div class="ln"><span>Delivery</span><span>${+t.shipping_total ? money(t.shipping_total) : 'Free'}</span></div>
        <div class="ln big"><span>Total</span><span>${money(t.grand_total)}</span></div>
      </div>
      <div style="height:14px"></div>
      <button class="btn" data-act="checkout">Checkout · ${money(t.grand_total)}</button>
      ${!S.user ? `<p class="muted" style="text-align:center;margin-top:10px;font-size:11.5px">
        Signing in will merge this guest cart into your account.</p>` : ''}
    </div>
  </div>`;
}

function scSaved(){
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Saved</h1><div class="sub">${S.saved.length} put aside</div></div></div>
    <div class="body">
      ${S.saved.length ? S.saved.map(i => `<div class="citem">
          <div class="thumb">${topo(i.hue||150, i.product_id)}</div>
          <div style="flex:1;min-width:0">
            <div style="font-size:13.5px;font-weight:600">${esc(i.product_name)}</div>
            <div class="muted" style="font-size:11.5px">${esc(i.variant_label||'')}</div>
            <div class="between" style="margin-top:10px">
              <span class="mono" style="font-size:13px;font-weight:600">${money(i.unit_price)}</span>
              <button class="btn sm lime" data-act="movecart" data-v="${i.id}">Move to cart</button>
            </div>
          </div></div>`).join('') : `<div class="empty">${ICO.saved}<h3 style="margin-top:12px">Nothing saved yet</h3>
        <p class="muted">Use “Save for later” in the cart (requires sign-in).</p></div>`}

      ${S.wishlist.length ? `<div class="h2">Wishlist</div>
        <div class="grid">${S.wishlist.map(id => { const p = byId(id); return p ? cardHTML(p) : ''; }).join('')}</div>` : ''}
    </div>
  </div>`;
}

function scCheckout(){
  const t = cartTotals();
  const items = cartItems();
  return `
  <div class="screen">
    <div class="appbar"><button class="iconbtn" data-act="tab" data-v="cart">${ICO.back}</button>
      <div style="flex:1"><h1 style="font-size:22px">Checkout</h1></div></div>
    <div class="body">
      ${!S.user ? `<div class="card" style="background:var(--forest);border-color:var(--forest);color:var(--paper);margin-bottom:14px">
        <b style="font-size:13.5px">Sign in to place this order</b>
        <p style="font-size:12.5px;color:#A9C2B4;margin:6px 0 12px;line-height:1.5">Your cart moves across with you — nothing is lost.</p>
        <button class="btn lime" data-act="tab" data-v="profile">Sign in</button></div>` : ''}

      <div class="h2" style="margin-top:0">Deliver to</div>
      <div class="card">
        <div class="row" style="gap:10px;color:var(--forest)">${ICO.truck}
          <div style="flex:1"><b style="font-size:13.5px">${S.user ? esc(S.user.name||S.user.username) : 'Guest'}</b>
          <div class="muted" style="font-size:12.5px">${esc(S.checkout.addr)}</div></div></div>
      </div>

      <div class="h2">Payment</div>
      ${[['card','Card','Sandbox Visa •••• 4242'],['eft','Instant EFT','Bank transfer'],['cod','Cash on delivery','Pay the courier']]
        .map(([k,l,sub]) => `<button class="ship ${S.checkout.pay===k?'on':''}" data-act="pay" data-v="${k}">
          <span class="radio"></span><span style="flex:1"><b style="font-size:13.5px">${l}</b>
          <span class="muted" style="display:block;font-size:11.5px">${sub}</span></span></button>`).join('')}

      <div class="h2">Order summary</div>
      <div class="card totals">
        ${items.map(i => `<div class="ln"><span style="max-width:190px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(i.product_name)} × ${i.quantity}</span><span>${money(i.line_total)}</span></div>`).join('')}
        ${+t.discount_total > 0 ? `<div class="ln disc"><span>Discount</span><span>− ${money(t.discount_total)}</span></div>` : ''}
        <div class="ln"><span>Delivery</span><span>${+t.shipping_total?money(t.shipping_total):'Free'}</span></div>
        <div class="ln big"><span>Total</span><span>${money(t.grand_total)}</span></div>
      </div>
      <p class="muted" style="margin-top:12px;font-size:11.5px">By placing this order you agree to our terms. Cooling-off rights apply per ECTA s44 where eligible.</p>
      <div style="height:16px"></div>
      <button class="btn" data-act="placeorder" ${!S.user||S.busy||!items.length?'disabled':''}>
        ${S.busy ? '<span class="spinner"></span> Placing order' : 'Place order · ' + money(t.grand_total)}</button>
    </div>
  </div>`;
}

function shipmentLine(o){
  const ship = o.shipment;
  if (ship && ship.tracking_number) {
    const events = (ship.events || []).map(ev =>
      `<div class="muted" style="font-size:11px">${esc(ev.status)}${ev.note ? ' · ' + esc(ev.note) : ''}</div>`
    ).join('');
    return `<p style="font-size:12.5px;margin:8px 0 0"><b>${esc(ship.carrier || 'Courier')}</b> · <span class="mono">${esc(ship.tracking_number)}</span></p>${events}`;
  }
  if (o.status === 'packed') {
    return `<p class="muted" style="font-size:12px;margin:8px 0 0">Waiting for the courier</p>`;
  }
  return '';
}

function scOrders(){
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Orders</h1><div class="sub">${S.orders.length} placed</div></div></div>
    <div class="body">
      ${S.orders.length ? S.orders.map(o => {
        const stage = o.tracking_stage ?? 0;
        const awaiting = o.status === 'awaiting_payment';
        const date = o.placed_at ? new Date(o.placed_at).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}) : '';
        return `<div class="card" style="margin-bottom:10px">
        <div class="between"><b class="mono" style="font-size:12.5px">${esc(o.reference)}</b>
          <span class="mono" style="font-size:12.5px;font-weight:600">${money(o.grand_total)}</span></div>
        <div class="muted" style="font-size:11.5px;margin:3px 0 12px">${date} · ${o.item_count||0} items · ${esc(o.shipping_method||'')} · <span class="mono">${esc(o.status)}</span></div>
        <div class="track">
          ${['Order placed','Payment confirmed','Packed','Out for delivery','Delivered']
            .map((s,ix) => `<div class="stp ${ix<=stage?'done':''}">
              <b style="font-size:12.5px;color:${ix<=stage?'var(--ink)':'var(--mute)'}">${s}</b>
              ${ix===stage?`<div class="muted" style="font-size:11px">Current status</div>`:''}
            </div>`).join('')}
        </div>
        ${shipmentLine(o)}
        ${awaiting ? `<button class="btn sm lime" style="width:100%;margin-bottom:8px" data-act="payorder" data-v="${esc(o.reference)}">Complete sandbox payment</button>` : ''}
        ${!awaiting && o.status !== 'cancelled' && o.status !== 'refunded' ? `<button class="btn ghost sm" style="width:100%;margin-bottom:8px" data-act="invoice" data-v="${esc(o.reference)}">View tax invoice</button>` : ''}
        ${o.cooling_off && o.cooling_off.eligible ? `<button class="btn ghost sm" style="width:100%;margin-bottom:8px;color:#9B3B1E" data-act="coolingoff" data-v="${esc(o.reference)}">Exercise 7-day cooling-off</button>
          <p class="muted" style="font-size:11px;margin:-4px 0 10px">ECTA s44 · ${o.cooling_off.days_remaining} day(s) left · full refund</p>` : ''}
        ${stage < 4 && !awaiting && o.status !== 'cancelled' && o.status !== 'refunded' ? `<button class="btn ghost sm" style="width:100%" data-act="advance" data-v="${esc(o.reference)}">Advance fulfilment</button>` : ''}
      </div>`;
      }).join('')
      : `<div class="empty">${ICO.box}<h3 style="margin-top:12px">No orders yet</h3>
         <p class="muted">Place one from the cart to see live tracking here.</p></div>`}
    </div>
  </div>`;
}

function scProfile(){
  if (!S.user) return scAuth();
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Account</h1></div>
      <button class="iconbtn" data-act="logout">${ICO.logout}</button></div>
    <div class="body">
      <div class="card row" style="gap:13px">
        <div style="width:52px;height:52px;border-radius:50%;background:var(--forest);color:var(--lime);display:grid;place-items:center;
          font-family:'Archivo';font-weight:800;font-size:18px">${esc((S.user.name||S.user.username||'?')[0])}</div>
        <div style="flex:1;min-width:0">
          <b style="font-size:15px">${esc(S.user.name||S.user.username)}</b>
          <div class="muted" style="font-size:12.5px;overflow:hidden;text-overflow:ellipsis">${esc(S.user.email)}</div>
          <div class="row" style="gap:6px;margin-top:6px;color:#2F7A4F;font-size:11.5px">${ICO.check}<span>${S.user.email_verified?'Email verified':'Email pending'}</span></div>
        </div>
      </div>

      <button class="card between" style="width:100%;text-align:left;margin-top:14px" data-act="settings">
        <span><b style="font-size:13.5px">Settings</b>
        <span class="muted" style="display:block;font-size:11.5px">Profile, security, notifications</span></span>
        <span style="color:var(--mute)">${ICO.chev}</span>
      </button>

      <div class="h2">Session</div>
      <div class="card kvs" style="font-size:11.5px">
        <div class="between" style="padding:5px 0"><span class="muted">Access token</span><span class="mono">${S.tokens?esc(S.tokens.access.slice(0,18))+'…':'—'}</span></div>
        <div class="between" style="padding:5px 0"><span class="muted">mfa_verified claim</span><span class="mono" style="color:${S.tokens&&S.tokens.mfa_verified?'#2F7A4F':'#9B3B1E'}">${S.tokens?S.tokens.mfa_verified:false}</span></div>
        <div class="between" style="padding:5px 0"><span class="muted">Cart session header</span><span class="mono">${esc(S.cartSession.slice(0,13))}…</span></div>
        <div class="between" style="padding:5px 0"><span class="muted">API</span><span class="mono">${esc(API_BASE)}</span></div>
      </div>

      <div class="h2">Inbox</div>
      ${(S.inbox||[]).length ? S.inbox.map(n => `<div class="card" style="margin-bottom:8px">
        <b style="font-size:13px">${esc(n.title)}</b>
        <div class="muted" style="font-size:12px;margin-top:3px">${esc(n.body||'')}</div>
      </div>`).join('') : `<p class="muted" style="font-size:12px">No messages yet</p>`}

      <div class="h2">Orders</div>
      <button class="card between" style="width:100%;text-align:left" data-act="tab" data-v="orders">
        <span><b style="font-size:13.5px">Order history</b>
        <span class="muted" style="display:block;font-size:11.5px">${S.orders.length} order${S.orders.length===1?'':'s'}</span></span>
        <span style="color:var(--mute)">${ICO.chev}</span>
      </button>

      ${S.user.is_staff_ops ? `
      <div class="h2">Operations</div>
      <button class="card between" style="width:100%;text-align:left" data-act="tab" data-v="staff">
        <span><b style="font-size:13.5px">Staff console</b>
        <span class="muted" style="display:block;font-size:11.5px">Orders · refunds · reconciliation</span></span>
        <span style="color:var(--mute)">${ICO.chev}</span>
      </button>` : ''}
    </div>
  </div>`;
}

function scStaff(){
  if (!S.user || !S.user.is_staff_ops) {
    return `<div class="screen"><div class="appbar"><div style="flex:1"><h1>Staff</h1></div></div>
      <div class="empty"><h3>Staff only</h3><p class="muted">Sign in as staff@northbound.test</p></div></div>`;
  }
  const recon = S.recon;
  const filters = [
    ['', 'All'],
    ['awaiting_payment', 'Unpaid'],
    ['payment_confirmed', 'Paid'],
    ['packed', 'Packed'],
    ['out_for_delivery', 'Ship'],
    ['delivered', 'Done'],
    ['refunded', 'Refunded'],
  ];
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1>Ops</h1>
      <div class="sub">${S.staffOrders.length} orders · staff</div></div>
      <button class="iconbtn" data-act="staffrefresh" aria-label="Refresh">${ICO.search}</button>
    </div>
    <div class="body">
      <button class="card between" style="width:100%;text-align:left;margin-bottom:14px" data-act="store">
        <span><b style="font-size:13.5px">Store settings</b>
        <span class="muted" style="display:block;font-size:11.5px">Delivery, banner, and promotion</span></span>
        <span style="color:var(--mute)">${ICO.chev}</span>
      </button>
      ${recon ? `<div class="card" style="margin-bottom:14px">
        <div class="between"><b style="font-size:13px">Today’s recon</b>
          <span class="mono" style="font-size:11px;color:var(--mute)">${esc(recon.date)}</span></div>
        <div class="totals" style="margin-top:8px">
          <div class="ln"><span>Captured</span><span>${money(recon.gross_captured)}</span></div>
          <div class="ln disc"><span>Refunded</span><span>− ${money(recon.gross_refunded)}</span></div>
          <div class="ln big"><span>Net</span><span>${money(recon.net)}</span></div>
        </div>
        <p class="muted" style="font-size:11.5px;margin-top:8px">
          ${recon.payments_succeeded} paid · ${recon.payments_pending} pending ·
          <b style="color:${recon.exception_count?'#9B3B1E':'#2F7A4F'}">${recon.exception_count} exceptions</b>
        </p>
      </div>` : ''}

      <div class="chips">
        ${filters.map(([k,l]) => `<button class="chip ${S.staffFilter===k?'on':''}" data-act="stafffilter" data-v="${k}">${l}</button>`).join('')}
      </div>

      ${S.staffOrders.length ? S.staffOrders.map(o => {
        const awaiting = o.status === 'awaiting_payment';
        return `<div class="card" style="margin-bottom:10px">
          <div class="between"><b class="mono" style="font-size:12px">${esc(o.reference)}</b>
            <span class="mono" style="font-size:12px;font-weight:600">${money(o.grand_total)}</span></div>
          <div class="muted" style="font-size:11px;margin:4px 0 10px">${esc(o.status)} · ${o.item_count||0} items · ${esc(o.payment_method||'')}</div>
          ${shipmentLine(o)}
          <div class="row" style="gap:6px;flex-wrap:wrap">
            ${!awaiting && o.status !== 'refunded' && o.status !== 'cancelled' ? `
              ${o.status === 'packed'
                ? `<button class="btn sm ghost" data-act="staffdispatch" data-v="${esc(o.reference)}">Dispatch</button>`
                : o.status === 'out_for_delivery'
                  ? `<button class="btn sm ghost" data-act="staffcourier" data-v="${esc(o.reference)}" data-status="${(o.shipment&&o.shipment.status)==='in_transit'?'delivered':'in_transit'}">${(o.shipment&&o.shipment.status)==='in_transit'?'Mark delivered':'Mark in transit'}</button>`
                  : `<button class="btn sm ghost" data-act="staffadvance" data-v="${esc(o.reference)}">Advance</button>`}
              <button class="btn sm ghost" data-act="staffrefund" data-v="${esc(o.reference)}">Refund</button>
            ` : ''}
            ${awaiting ? `<span class="muted" style="font-size:11px">Awaiting customer payment</span>` : ''}
            ${o.status === 'refunded' ? `<span class="muted" style="font-size:11px;color:#2F7A4F">Refunded</span>` : ''}
          </div>
        </div>`;
      }).join('') : `<div class="empty"><h3>No orders</h3><p class="muted">Nothing matches this filter.</p></div>`}

      <p class="muted" style="font-size:11px;margin-top:12px;text-align:center">
        Demo staff: <b class="mono">staff@northbound.test</b> / staff-ops-42
      </p>
    </div>
  </div>`;
}

function scAuth(){
  const v = S.authView;
  if (v === 'mfa') return `
  <div class="screen">
    <div class="appbar"><button class="iconbtn" data-act="authview" data-v="login">${ICO.back}</button></div>
    <div class="body" style="padding-top:12px">
      <div style="width:46px;height:46px;border-radius:13px;background:var(--forest);color:var(--lime);display:grid;place-items:center;margin-bottom:16px">${ICO.shield}</div>
      <h2 style="font-family:'Archivo';font-size:24px;font-weight:800;letter-spacing:-.02em">Enter your code</h2>
      <p class="muted" style="margin:8px 0 20px">Six digits from your authenticator. In DEBUG any six digits work except <b class="mono">000000</b>.</p>
      ${S.formErr ? `<div class="err">${esc(S.formErr)}</div>` : ''}
      <div class="field"><label>Verification code</label>
        <input id="mfacode" inputmode="numeric" maxlength="6" placeholder="••••••" value="${esc(S.form.mfacode)}" class="mono" style="letter-spacing:.5em;font-size:19px;text-align:center"></div>
      <button class="btn" data-act="mfaverify" ${S.busy?'disabled':''}>${S.busy?'<span class="spinner"></span> Verifying':'Verify and sign in'}</button>
      <button class="btn ghost" style="margin-top:8px" data-act="usebackup">Use a backup code instead</button>
    </div>
  </div>`;

  const reg = v === 'register';
  return `
  <div class="screen">
    <div class="appbar"><div style="flex:1"><h1 style="font-size:24px">${reg?'Create account':'Sign in'}</h1>
      <div class="sub">${reg?'Takes about thirty seconds':'Welcome back'}</div></div></div>
    <div class="body">
      ${S.formErr ? `<div class="err">${esc(S.formErr)}</div>` : ''}
      ${reg ? `<div class="field"><label>Username</label><input id="username" placeholder="jordan.m" value="${esc(S.form.username)}" autocomplete="off"></div>` : ''}
      <div class="field"><label>Email</label><input id="email" type="email" placeholder="you@example.com" value="${esc(S.form.email)}" autocomplete="off"></div>
      <div class="field"><label>Password</label><input id="password" type="password" placeholder="••••••••" value="${esc(S.form.password)}"></div>
      ${reg ? `<div class="field"><label>Confirm password</label><input id="password2" type="password" placeholder="••••••••" value="${esc(S.form.password2)}"></div>` : ''}
      ${reg ? `<div class="field"><label>Friend's referral code (optional)</label><input id="referral" value="${esc(S.form.referral||'')}" autocomplete="off"></div>` : ''}
      <button class="btn" data-act="${reg?'register':'login'}" ${S.busy?'disabled':''}>
        ${S.busy?'<span class="spinner"></span> Working':(reg?'Create account':'Sign in')}</button>

      <div class="row" style="margin:18px 0;gap:12px"><div style="flex:1;height:1px;background:var(--hair)"></div>
        <span class="muted" style="font-size:11px">OR</span><div style="flex:1;height:1px;background:var(--hair)"></div></div>
      <button class="btn ghost" data-act="social" data-v="google">Continue with Google</button>
      <button class="btn ghost" style="margin-top:8px" data-act="social" data-v="facebook">Continue with Facebook</button>

      <p style="text-align:center;margin-top:20px;font-size:13px;color:var(--mute)">
        ${reg?'Already have an account?':'New here?'}
        <button class="linkbtn" style="font-size:13px;color:var(--forest);font-weight:600" data-act="authview" data-v="${reg?'login':'register'}">
          ${reg?'Sign in':'Create one'}</button></p>
      ${cartCount() ? `<p class="muted" style="text-align:center;margin-top:14px;font-size:11.5px">
        ${cartCount()} guest item${cartCount()===1?'':'s'} will merge into your account on sign-in.</p>` : ''}
    </div>
  </div>`;
}

function scSettings(){
  if (!S.user) return scAuth();
  const p = S.profile || {};
  const prefs = S.prefs || {};
  const sw = (key, label) => `<div class="between" style="padding:6px 0">
      <span style="font-size:13px">${label}</span>
      <button class="btn sm ${prefs[key]?'lime':'ghost'}" data-act="pref" data-v="${key}">${prefs[key]?'On':'Off'}</button>
    </div>`;
  return `
  <div class="screen">
    <div class="appbar"><button class="iconbtn" data-act="back">${ICO.back}</button>
      <div style="flex:1"><h1>Settings</h1></div></div>
    <div class="body">
      ${(() => {
        const loy = S.loyalty || {};
        return `<div class="h2">Points and referrals</div>
        <div class="card">
          <b>${esc(loy.points ?? '—')} points</b>
          <p class="muted" style="margin:6px 0">Your code <span class="mono">${esc(loy.referral_code||'')}</span></p>
          ${loy.referrer_code ? `<p class="muted">Friend code <span class="mono">${esc(loy.referrer_code)}</span></p>` : ''}
          <p class="muted" style="font-size:12px">100 points become a personal R10 voucher.</p>
          ${S.loyaltyNote ? `<p style="margin:8px 0">Voucher <span class="mono">${esc(S.loyaltyNote)}</span></p>` : ''}
          <button class="btn sm" data-act="redeem">Redeem 100 points</button>
          <div class="field" style="margin-top:10px"><label>Friend's referral code</label><input id="set-referral" value="${esc(loy.referrer_code||'')}"></div>
          <button class="btn sm ghost" data-act="attachreferral">Save referral code</button>
        </div>`;
      })()}
      <div class="h2">Profile</div>
      <div class="card">
        <div class="field"><label>First name</label><input id="set-first" value="${esc(p.first_name||'')}"></div>
        <div class="field"><label>Last name</label><input id="set-last" value="${esc(p.last_name||'')}"></div>
        <div class="field"><label>Phone</label><input id="set-phone" value="${esc(p.phone_number||'')}"></div>
        <div class="field"><label>Date of birth</label><input id="set-dob" placeholder="YYYY-MM-DD" value="${esc(p.date_of_birth||'')}"></div>
        <div class="field"><label>Address</label><input id="set-address" value="${esc(p.address||'')}"></div>
        <button class="btn sm" data-act="saveprofile">Save profile</button>
      </div>
      <div class="h2">Security</div>
      <div class="card">
        <div class="between">
          <div class="row" style="gap:10px;color:var(--forest)">${ICO.shield}
            <div><b style="font-size:13.5px">Two-factor authentication</b>
            <div class="muted" style="font-size:11.5px">${S.user.mfa ? 'Authenticator app · active' : 'Not set up'}</div></div></div>
          <button class="btn sm ${S.user.mfa?'ghost':'lime'}" data-act="togglemfa">${S.user.mfa?'Turn off':'Turn on'}</button>
        </div>
        ${S.user.mfa ? `<div class="hr"></div>
          <div class="between"><div class="row" style="gap:10px;color:var(--forest)">${ICO.key}
            <div><b style="font-size:13.5px">Backup codes</b>
            <div class="muted" style="font-size:11.5px">${S.user.backup ? S.user.backup.length + ' unused codes' : 'None generated'}</div></div></div>
            <button class="btn sm ghost" data-act="backupcodes">Generate</button></div>
          ${S.user.backup ? `<div class="mono" style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:11px;font-size:12px;
            background:var(--paper);padding:11px;border-radius:9px">${S.user.backup.map(c => `<span>${c}</span>`).join('')}</div>` : ''}` : ''}
        <div class="hr"></div>
        <div class="field"><label>Current password</label><input id="set-current" type="password"></div>
        <div class="field"><label>New password</label><input id="set-new" type="password"></div>
        <button class="btn sm ghost" data-act="changepassword">Change password</button>
      </div>
      <div class="h2">Notifications</div>
      <div class="card">
        <div class="between" style="padding:6px 0"><span style="font-size:13px">Order emails</span><span class="muted">Required</span></div>
        ${sw('email_marketing','Marketing email')}
        ${sw('push_order_updates','Order push')}
        ${sw('push_marketing','Marketing push')}
      </div>
    </div>
  </div>`;
}

function scStore(){
  if (!S.user || !S.user.is_staff_ops) {
    return `<div class="screen"><div class="appbar"><button class="iconbtn" data-act="back">${ICO.back}</button><div style="flex:1"><h1>Store settings</h1></div></div>
      <div class="empty"><h3>Staff only</h3></div></div>`;
  }
  const rates = (S.shippingRates||[]).map(r => `<div class="card" style="margin-bottom:8px">
      <b style="font-size:13px">${esc(r.method_name)}</b>
      <div class="field"><label>Price (ZAR)</label><input id="rate-price-${r.id}" value="${esc(r.price)}"></div>
      <div class="field"><label>Days</label><input id="rate-days-${r.id}" value="${esc(r.estimated_days)}"></div>
      <button class="btn sm ghost" data-act="saverate" data-v="${r.id}">Save delivery</button>
    </div>`).join('');
  const ads = (S.staffAds||[]).map(a => `<div class="card" style="margin-bottom:8px">
      <div class="field"><label>Title</label><input id="ad-title-${a.id}" value="${esc(a.title)}"></div>
      <div class="field"><label>Body</label><input id="ad-body-${a.id}" value="${esc(a.body||'')}"></div>
      <div class="field"><label>Product slug</label><input id="ad-slug-${a.id}" value="${esc(a.product_slug||'')}"></div>
      <div class="between" style="margin-top:8px">
        <button class="btn sm ghost" data-act="savead" data-v="${a.id}">Save banner</button>
        <button class="btn sm ${a.is_active?'lime':'ghost'}" data-act="savead" data-v="${a.id}" data-flip="1">${a.is_active?'Active':'Hidden'}</button>
      </div>
    </div>`).join('');
  const promos = (S.staffPromos||[]).map(p => `<div class="card" style="margin-bottom:8px">
      <b style="font-size:13px">${esc(p.code)}</b>
      <div class="field"><label>Title</label><input id="promo-title-${esc(p.code)}" value="${esc(p.title||'')}"></div>
      <div class="field"><label>Description</label><input id="promo-body-${esc(p.code)}" value="${esc(p.description||'')}"></div>
      <div class="field"><label>${p.discount_type==='percentage'?'Percent':'Amount (ZAR)'}</label><input id="promo-amount-${esc(p.code)}" value="${esc(p.amount)}"></div>
      <div class="field"><label>Starts</label><input id="promo-start-${esc(p.code)}" placeholder="ISO date" value="${esc(p.starts_at||'')}"></div>
      <div class="field"><label>Ends</label><input id="promo-end-${esc(p.code)}" placeholder="ISO date" value="${esc(p.ends_at||'')}"></div>
      <div class="between" style="margin-top:8px">
        <button class="btn sm ghost" data-act="savepromo" data-v="${esc(p.code)}">Save promotion</button>
        <button class="btn sm ${p.is_active?'lime':'ghost'}" data-act="savepromo" data-v="${esc(p.code)}" data-flip="1">${p.is_active?'Active':'Hidden'}</button>
      </div>
    </div>`).join('');
  return `
  <div class="screen">
    <div class="appbar"><button class="iconbtn" data-act="back">${ICO.back}</button>
      <div style="flex:1"><h1>Store settings</h1></div></div>
    <div class="body">
      <div class="h2">Delivery</div>
      ${rates || '<p class="muted">No rates yet</p>'}
      <div class="h2">Shop banner</div>
      ${ads || '<p class="muted">No banner yet</p>'}
      <div class="h2">Flash sale</div>
      ${(S.staffFlashes||[]).map(f => `<div class="card" style="margin-bottom:8px">
        <b style="font-size:13px">${esc(f.product_name)}</b>
        <p class="muted" style="font-size:12px">Catalogue ${money(f.compare_at)}</p>
        <div class="field"><label>Sale price (ZAR)</label><input id="flash-price-${f.id}" value="${esc(f.sale_price)}"></div>
        <div class="field"><label>Starts</label><input id="flash-start-${f.id}" placeholder="ISO date" value="${esc(f.starts_at||'')}"></div>
        <div class="field"><label>Ends</label><input id="flash-end-${f.id}" placeholder="ISO date" value="${esc(f.ends_at||'')}"></div>
        <div class="between" style="margin-top:8px">
          <button class="btn sm ghost" data-act="saveflash" data-v="${f.id}">Save flash sale</button>
          <button class="btn sm ${f.is_active?'lime':'ghost'}" data-act="saveflash" data-v="${f.id}" data-flip="1">${f.is_active?'Active':'Hidden'}</button>
        </div>
      </div>`).join('') || '<p class="muted">No flash sale yet</p>'}
      <div class="h2">Bundle</div>
      ${(S.staffBundles||[]).map(b => `<div class="card" style="margin-bottom:8px">
        <div class="field"><label>Title</label><input id="bundle-title-${b.id}" value="${esc(b.title)}"></div>
        <div class="field"><label>Price (ZAR)</label><input id="bundle-price-${b.id}" value="${esc(b.price)}"></div>
        <div class="between" style="margin-top:8px">
          <button class="btn sm ghost" data-act="savebundle" data-v="${b.id}">Save bundle</button>
          <button class="btn sm ${b.is_active?'lime':'ghost'}" data-act="savebundle" data-v="${b.id}" data-flip="1">${b.is_active?'Active':'Hidden'}</button>
        </div>
      </div>`).join('') || '<p class="muted">No bundle yet</p>'}
      <div class="h2">Shared promotion</div>
      ${promos || '<p class="muted">No promotion yet</p>'}
    </div>
  </div>`;
}

const SCREENS = {shop:scShop, search:scSearch, product:scProduct, cart:scCart,
                 saved:scSaved, checkout:scCheckout, orders:scOrders, profile:scProfile, staff:scStaff,
                 settings:scSettings, store:scStore};
const NAV = [
  {k:'shop',   l:'Shop',    i:'shop'},
  {k:'search', l:'Search',  i:'search'},
  {k:'cart',   l:'Cart',    i:'cart'},
  {k:'saved',  l:'Saved',   i:'saved'},
  {k:'profile',l:'Account', i:'user'}
];

function navItems(){
  const items = [...NAV];
  if (S.user && S.user.is_staff_ops) {
    items.splice(4, 0, {k:'staff', l:'Ops', i:'staff'});
  }
  return items;
}

function render(){
  const vp = document.getElementById('viewport');
  if (!vp) return;
  vp.innerHTML = (SCREENS[S.screen] || scShop)() + (S.snack ? `<div class="snack"><span class="dot"></span><span>${esc(S.snack)}</span></div>` : '');

  document.getElementById('bottomnav').innerHTML = navItems().map(n => `
    <button class="navitem ${S.tab===n.k?'active':''}" data-act="tab" data-v="${n.k}">
      ${S.tab===n.k?'<i class="navpill"></i>':''}${ICO[n.i]}<span>${n.l}</span>
      ${n.k==='cart'&&cartCount()?`<i class="badge" style="top:4px;right:22px">${cartCount()}</i>`:''}
    </button>`).join('');

  const pill = document.getElementById('sessionpill');
  if (pill) {
    const role = S.user && S.user.is_staff_ops ? 'staff' : 'authenticated';
    pill.textContent = S.user ? role + ' · ' + (S.user.email||'').split('@')[0] : 'guest session';
    pill.className = 'pill' + (S.user ? ' on' : '');
  }
  const net = document.getElementById('netpill');
  if (net) net.textContent = 'v1 · ' + (S.lastMs ? S.lastMs + 'ms' : 'live');
  renderConsole();
}

const CTABS = [{k:'log',l:'Request log'},{k:'state',l:'Session'},{k:'cov',l:'Coverage'},{k:'flags',l:'Simulate'}];

function renderConsole(){
  const ctabs = document.getElementById('ctabs');
  const cbody = document.getElementById('cbody');
  if (!ctabs || !cbody) return;
  ctabs.innerHTML = CTABS.map(t => `<button class="ctab ${S.ctab===t.k?'on':''}" data-act="ctab" data-v="${t.k}">${t.l}</button>`).join('');
  cbody.innerHTML = ({log:cLog, state:cState, cov:cCov, flags:cFlags}[S.ctab])();
}

function cLog(){
  if (!S.log.length) return `<div class="ctitle">Waiting</div>
    <p class="cnote">No calls yet. Tap anything in the app — each request hits <b>${esc(API_BASE)}</b>.</p>`;
  return `<div class="between" style="margin-bottom:10px">
      <span class="ctitle" style="margin:0">${S.log.length} calls</span>
      <button class="clear" data-act="clearlog">clear</button></div>` +
    S.log.map(r => {
      const open = S.expanded.has(String(r.id));
      const cls = r.status >= 400 || r.status === 0 ? 'bad' : 'ok';
      return `<div class="req">
        <button class="hd" data-act="expand" data-v="${r.id}">
          <span class="m ${r.method}">${r.method}</span>
          <span class="pt">${esc(r.path)}</span>
          <span class="st ${cls}">${r.status} · ${r.ms}ms</span>
        </button>
        ${open ? `<pre>${esc(JSON.stringify({request:r.body || null, response:r.res}, null, 2))}</pre>` : ''}
      </div>`;
    }).join('');
}

function cState(){
  const t = cartTotals();
  const rows = [
    ['auth state', S.user ? 'authenticated' : 'guest', !!S.user],
    ['user id', S.user ? String(S.user.id) : '—', false],
    ['access token', S.tokens ? S.tokens.access.slice(0,22) + '…' : '—', false],
    ['mfa_verified', S.tokens ? String(S.tokens.mfa_verified) : '—', S.tokens && S.tokens.mfa_verified],
    ['X-Cart-Session', S.cartSession, !S.user],
    ['cart items', String(cartCount()), false],
    ['cart total', money(t.grand_total), false],
    ['orders', String(S.orders.length), false],
    ['API base', API_BASE, false],
  ];
  return `<div class="ctitle">Client state</div><div class="kvs">
    ${rows.map(([k,v,hi]) => `<div class="kv"><span class="k">${k}</span><span class="v ${hi?'hi':''}">${esc(v)}</span></div>`).join('')}
  </div>`;
}

function cCov(){
  const live = ENDPOINTS;
  const hit = live.filter(e => S.hits.has(e.m + ' ' + e.p)).length;
  const pct = Math.round(hit / live.length * 100);
  const groups = [...new Set(ENDPOINTS.map(e => e.g))];
  return `<div class="ctitle">Endpoint coverage · ${hit}/${live.length} exercised</div>
    <div class="covbar"><i style="width:${pct}%"></i></div>
    ${groups.map(g => `<div class="ctitle">${esc(g)}</div>` +
      ENDPOINTS.filter(e => e.g === g).map(e => {
        const on = S.hits.has(e.m + ' ' + e.p);
        return `<div class="ep ${on?'hit':''}">
          <span class="tick">${on?'✓':''}</span>
          <span class="m ${e.m}" style="font-size:9px">${e.m}</span>
          <span style="flex:1;word-break:break-all">${esc(e.p.replace('/api/v1',''))}</span></div>`;
      }).join('')).join('')}`;
}

function cFlags(){
  return `<div class="ctitle">Failure simulation</div>
    <button class="flag ${S.flags.slow?'on':''}" data-act="flag" data-v="slow">
      <span class="sw"></span><span class="tx">Slow network<em>Adds ~1.2s to every call.</em></span></button>
    <div class="ctitle">Guest → account merge</div>
    <p class="cnote">Add items while signed out, then sign in. The client fires
    <b>POST /cart/cart/transfer_cart/</b> with the stored session id.</p>
    <div class="ctitle">Demo credentials</div>
    <p class="cnote">jordan@northbound.test / correct-horse-42<br>MFA: any 6 digits except 000000</p>`;
}

async function withBusy(fn){
  S.busy = true; render();
  try { await fn(); } finally { S.busy = false; render(); }
}

function captureForm(){
  ['email','password','password2','username','mfacode','code','q','referral'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    if (id === 'q') S.filters.q = el.value;
    else if (id === 'code') S.form.code = el.value;
    else S.form[id] = el.value;
  });
}

async function finishLogin(tokens, profile){
  S.tokens = {
    access: tokens.access,
    refresh: tokens.refresh,
    mfa_verified: !!tokens.mfa_verified,
  };
  S.user = {
    id: profile.id,
    email: profile.email,
    username: profile.username,
    name: profile.display_name || profile.username || profile.email,
    email_verified: profile.email_verified,
    mfa: !!profile.mfa,
    is_staff: !!profile.is_staff,
    is_staff_ops: !!(profile.is_staff_ops || profile.is_staff),
    backup: null,
  };
  S.mfaPending = null;
  S.preAuthToken = null;
  S.form.mfacode = '';
  persistAuth();

  // Merge guest cart
  await api('POST', '/api/v1/cart/cart/transfer_cart/', {
    body: { session_id: S.cartSession },
  });
  await loadCart();
  await loadOrders();
  await loadSaved();
  await loadInbox();
  if (S.user.is_staff_ops) {
    await loadStaffOrders();
    await loadRecon();
    go('staff', 'staff');
  } else {
    go('shop', 'shop');
  }
}

const ACTIONS = {
  async tab(v){
    if (v === 'profile' && !S.user){ S.tab = 'profile'; S.screen = 'profile'; S.authView = 'login'; render(); return; }
    if (v === 'staff' && (!S.user || !S.user.is_staff_ops)) {
      snack('Staff sign-in required'); go('profile','profile'); return;
    }
    S.tab = v;
    if (v === 'cart') { await loadCart(); go('cart','cart'); return; }
    if (v === 'saved') { await loadSaved(); go('saved','saved'); return; }
    if (v === 'orders') { await loadOrders(); go('orders','orders'); return; }
    if (v === 'staff') { await loadStaffOrders(); await loadRecon(); go('staff','staff'); return; }
    if (v === 'search') { await loadProducts(); go('search','search'); setTimeout(() => { const q = document.getElementById('q'); if (q) q.focus(); }, 60); return; }
    if (v === 'shop') { S.filters.cat = S.filters.cat || 'all'; await loadProducts(); go('shop','shop'); return; }
    go(v, v);
  },
  async cat(v){ S.filters.cat = v; await loadProducts(); render(); },
  async sort(v){ S.filters.sort = v; await loadProducts(); render(); },
  async clearq(){ S.filters.q = ''; await loadProducts(); render(); },
  async open(v){ remember(v); await loadProduct(v); go('product'); },
  back(){ go(S.tab); },
  variant(v){ S.variant = (S.product.variants||[]).find(x => String(x.id) === String(v)); render(); },
  wish(v){
    const id = +v;
    if (S.wishlist.includes(id)) S.wishlist = S.wishlist.filter(x => x !== id);
    else S.wishlist.push(id);
    persistAuth();
    snack(S.wishlist.includes(id) ? 'Saved to wishlist' : 'Removed from wishlist');
  },

  add(){ withBusy(async () => {
    const p = S.product, v = S.variant;
    const r = await api('POST', '/api/v1/cart/cart/add_item/', {
      body: { product: p.id, variant: v.id, quantity: 1 },
    });
    if (!r.ok) { snack(errMsg(r.data, 'Could not add to cart')); return; }
    S.cart = r.data;
    snack(p.name + ' added to cart');
  }); },

  qty(v, el){ withBusy(async () => {
    const item = cartItems().find(i => String(i.id) === String(v));
    if (!item) return;
    const d = +el.dataset.d;
    const next = item.quantity + d;
    if (next < 1) { return ACTIONS.remove(v); }
    const r = await api('POST', '/api/v1/cart/cart/items/{id}/update/', {
      path: `/api/v1/cart/cart/items/${item.id}/update/`,
      body: { quantity: next },
    });
    if (r.ok) S.cart = r.data;
    else snack(errMsg(r.data));
  }); },

  remove(v){ withBusy(async () => {
    const r = await api('DELETE', '/api/v1/cart/cart/items/{id}/remove/', {
      path: `/api/v1/cart/cart/items/${v}/remove/`,
    });
    if (r.ok) { S.cart = r.data; snack('Item removed'); }
  }); },

  savelater(v){ withBusy(async () => {
    if (!S.user) { snack('Sign in to save for later'); return; }
    const r = await api('POST', '/api/v1/cart/cart/items/{id}/save-for-later/', {
      path: `/api/v1/cart/cart/items/${v}/save-for-later/`,
    });
    if (r.ok) { await loadCart(); await loadSaved(); snack('Moved to Saved'); }
    else snack(errMsg(r.data));
  }); },

  movecart(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/cart/saved-items/{id}/move_to_cart/', {
      path: `/api/v1/cart/saved-items/${v}/move_to_cart/`,
    });
    if (r.ok) { S.cart = r.data; await loadSaved(); snack('Moved to cart'); }
    else snack(errMsg(r.data));
  }); },

  clear(){ withBusy(async () => {
    const r = await api('POST', '/api/v1/cart/cart/clear/');
    if (r.ok) { S.cart = r.data; snack('Cart cleared'); }
  }); },

  discount(){ withBusy(async () => {
    captureForm();
    const code = String(S.form.code || '').trim().toUpperCase();
    if (!code) return;
    S.form.code = '';
    const r = await api('POST', '/api/v1/cart/cart/apply_discount/', { body: { code } });
    if (r.ok) { S.cart = r.data; snack('Discount applied'); }
    else snack(errMsg(r.data, 'That code is not valid'));
  }); },

  undiscount(){ withBusy(async () => {
    const r = await api('POST', '/api/v1/cart/cart/remove_discount/', { body: {} });
    if (r.ok) { S.cart = r.data; snack('Discount removed'); }
  }); },

  ship(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/cart/cart/select_shipping/', {
      body: { shipping_method_id: +v },
    });
    if (r.ok) S.cart = r.data;
  }); },

  checkout(){ go('checkout'); },
  pay(v){ S.checkout.pay = v; render(); },

  placeorder(){ withBusy(async () => {
    const r = await api('POST', '/api/v1/orders/', {
      body: {
        payment_method: S.checkout.pay,
        address: S.checkout.addr,
      },
      headers: { 'Idempotency-Key': uuid() },
    });
    if (!r.ok) { snack(errMsg(r.data, 'Could not place order')); return; }

    // Card/EFT: confirm only via signed sandbox webhook path (ADR-0011)
    const pay = r.data.payment || {};
    if (pay.redirect_url && S.checkout.pay !== 'cod') {
      snack('Opening secure checkout…');
      const done = await api('POST', '/api/v1/payments/sandbox/complete/', {
        path: '/api/v1/payments/sandbox/complete/',
        body: { order_reference: r.data.reference },
      });
      if (!done.ok) {
        snack(errMsg(done.data, 'Payment not completed — finish in hosted checkout'));
        // Still show the order; user can retry pay
      } else {
        snack('Payment confirmed · ' + r.data.reference);
      }
    } else {
      snack('Order ' + r.data.reference + ' placed');
    }

    await loadCart();
    await loadOrders();
    go('orders', 'orders');
  }); },

  advance(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/orders/{id}/advance/', {
      path: `/api/v1/orders/${v}/advance/`,
      body: {},
    });
    if (r.ok) {
      const ix = S.orders.findIndex(o => o.reference === v);
      if (ix >= 0) S.orders[ix] = r.data;
      else await loadOrders();
      snack('Status updated');
    } else snack(errMsg(r.data));
  }); },

  payorder(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/payments/sandbox/complete/', {
      path: '/api/v1/payments/sandbox/complete/',
      body: { order_reference: v },
    });
    if (r.ok) {
      await loadOrders();
      snack('Payment confirmed via signed webhook path');
    } else snack(errMsg(r.data, 'Payment failed'));
  }); },

  invoice(v){
    const url = API_BASE + `/api/v1/orders/${encodeURIComponent(v)}/invoice/`;
    // open with bearer is awkward in a new tab — fetch blob then open
    withBusy(async () => {
      const r = await fetch(url, {
        headers: {
          'Authorization': S.tokens ? 'Bearer ' + S.tokens.access : '',
          'X-App-Version': APP_VERSION,
          'X-Cart-Session': S.cartSession,
        },
      });
      const text = await r.text();
      S.log.unshift({
        id: ++reqId, method: 'GET', route: '/api/v1/orders/{id}/invoice/',
        path: `/api/v1/orders/${v}/invoice/`, status: r.status, ms: 0,
        body: null, res: r.ok ? { html: text.slice(0, 200) + '…' } : text,
      });
      renderConsole();
      if (!r.ok) { snack('Invoice unavailable'); return; }
      const w = window.open('', '_blank');
      if (w) { w.document.write(text); w.document.close(); }
      else snack('Allow pop-ups to view the invoice');
    });
  },

  coolingoff(v){ withBusy(async () => {
    if (!confirm('Exercise your 7-day cooling-off right? This issues a full refund.')) return;
    const r = await api('POST', '/api/v1/orders/{id}/cooling-off/exercise/', {
      path: `/api/v1/orders/${v}/cooling-off/exercise/`,
      body: { reason: 'Customer cooling-off (ECTA s44)' },
    });
    if (r.ok) {
      await loadOrders();
      snack('Cooling-off accepted — full refund issued');
    } else snack(errMsg(r.data, 'Cooling-off not available'));
  }); },

  staffrefresh(){ withBusy(async () => {
    await loadStaffOrders();
    await loadRecon();
    snack('Ops data refreshed');
  }); },

  stafffilter(v){ withBusy(async () => {
    S.staffFilter = v || '';
    await loadStaffOrders();
    render();
  }); },

  staffdispatch(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/orders/staff/{id}/dispatch/', {
      path: `/api/v1/orders/staff/${v}/dispatch/`,
      body: {},
    });
    if (r.ok) {
      await loadStaffOrders();
      const tracking = r.data.shipment && r.data.shipment.tracking_number;
      snack(tracking ? (v + ' · ' + tracking) : (v + ' dispatched'));
    } else snack(errMsg(r.data));
  }); },

  staffcourier(v, el){ withBusy(async () => {
    const status = (el && el.dataset && el.dataset.status) || 'in_transit';
    const r = await api('POST', '/api/v1/orders/staff/{id}/courier/', {
      path: `/api/v1/orders/staff/${v}/courier/`,
      body: { status },
    });
    if (r.ok) {
      await loadStaffOrders();
      snack(v + ' → ' + status);
    } else snack(errMsg(r.data));
  }); },

  staffadvance(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/orders/staff/{id}/advance/', {
      path: `/api/v1/orders/staff/${v}/advance/`,
      body: {},
    });
    if (r.ok) {
      await loadStaffOrders();
      snack(v + ' → ' + r.data.status);
    } else snack(errMsg(r.data));
  }); },

  staffrefund(v){ withBusy(async () => {
    const amt = prompt('Refund amount in ZAR (blank = full remaining):', '');
    if (amt === null) return;
    const body = { order_reference: v, reason: 'Staff refund from SPA' };
    if (String(amt).trim()) body.amount = String(amt).trim();
    const r = await api('POST', '/api/v1/payments/refunds/', {
      path: '/api/v1/payments/refunds/',
      body,
      headers: { 'Idempotency-Key': uuid() },
    });
    if (r.ok) {
      await loadStaffOrders();
      await loadRecon();
      snack('Refund ' + r.data.amount + ' · ' + r.data.payment_status);
    } else snack(errMsg(r.data, 'Refund failed'));
  }); },

  authview(v){ S.authView = v; S.formErr = null; render(); },

  login(){ withBusy(async () => {
    captureForm();
    const email = S.form.email, password = S.form.password;
    const r = await api('POST', '/api/v1/auth/token/', { body: { email, password } });
    if (!r.ok) { S.formErr = errMsg(r.data, 'Invalid credentials.'); return; }
    if (r.data.mfa_required || r.data.pre_auth_token) {
      S.preAuthToken = r.data.pre_auth_token;
      S.mfaPending = { email };
      S.authView = 'mfa';
      snack('Password accepted — one more step');
      return;
    }
    // Full tokens without MFA
    S.tokens = { access: r.data.access, refresh: r.data.refresh, mfa_verified: !!r.data.mfa_verified };
    const me = await api('GET', '/api/v1/auth/users/me/', { path: '/api/v1/auth/users/me/' });
    const prof = await api('GET', '/api/v1/auth/profiles/');
    const profile = (prof.data && (prof.data.results || prof.data)[0]) || me.data || {};
    await finishLogin(S.tokens, {
      id: me.data?.id || profile.id,
      email: me.data?.email || email,
      username: me.data?.username || profile.username,
      display_name: profile.display_name || profile.first_name,
      email_verified: me.data?.email_verified,
      is_staff: me.data?.is_staff,
      is_staff_ops: me.data?.is_staff_ops,
      mfa: false,
    });
    snack('Signed in');
  }); },

  register(){ withBusy(async () => {
    captureForm();
    const body = {
      email: S.form.email,
      username: S.form.username,
      password: S.form.password,
      password2: S.form.password2,
    };
    if ((S.form.referral || '').trim()) body.referral_code = S.form.referral.trim();
    const r = await api('POST', '/api/v1/auth/users/', { body });
    if (!r.ok) { S.formErr = errMsg(r.data, 'Could not register.'); return; }
    // Auto-verify in DEBUG when server returns dev_email_token
    if (r.data.dev_email_token) {
      await api('POST', '/api/v1/auth/email/verify/', {
        path: '/api/v1/auth/email/verify/',
        body: { token: r.data.dev_email_token },
      });
    }
    // Auto-login
    const login = await api('POST', '/api/v1/auth/token/', {
      body: { email: S.form.email, password: S.form.password },
    });
    if (login.ok && login.data.access) {
      S.tokens = { access: login.data.access, refresh: login.data.refresh, mfa_verified: false };
      await finishLogin(S.tokens, {
        id: r.data.id,
        email: r.data.email,
        username: r.data.username,
        display_name: r.data.username,
        email_verified: true,
        mfa: false,
      });
      snack('Account created');
    } else if (login.data && login.data.mfa_required) {
      S.preAuthToken = login.data.pre_auth_token;
      S.mfaPending = { email: S.form.email, name: S.form.username };
      S.authView = 'mfa';
      snack('Account created — verify MFA');
    } else {
      S.authView = 'login';
      snack('Account created — please sign in');
    }
  }); },

  social(v){ withBusy(async () => {
    const r = await api('POST', `/api/v1/auth/social/${v}/`, {
      path: `/api/v1/auth/social/${v}/`,
      body: { email: 'jordan@northbound.test', username: 'jordan.m' },
    });
    if (!r.ok) { snack(errMsg(r.data)); return; }
    S.tokens = { access: r.data.access, refresh: r.data.refresh, mfa_verified: false };
    await finishLogin(S.tokens, {
      id: 0, email: 'jordan@northbound.test', username: 'jordan.m',
      display_name: 'Jordan Mabaso', email_verified: true, mfa: false,
    });
    snack('Signed in with ' + v);
  }); },

  mfaverify(){ withBusy(async () => {
    captureForm();
    const code = S.form.mfacode;
    const r = await api('POST', '/api/v1/auth/mfa/verify/', {
      body: {
        code,
        device_type: 'authenticator',
        pre_auth_token: S.preAuthToken,
      },
      headers: S.preAuthToken ? { Authorization: 'Bearer ' + S.preAuthToken } : {},
    });
    if (!r.ok) { S.formErr = errMsg(r.data, 'Invalid verification code.'); return; }
    S.tokens = { access: r.data.access, refresh: r.data.refresh, mfa_verified: true };
    const me = await api('GET', '/api/v1/auth/users/me/', { path: '/api/v1/auth/users/me/' });
    const prof = await api('GET', '/api/v1/auth/profiles/');
    const profile = (prof.data && (prof.data.results || prof.data)[0]) || {};
    await finishLogin(S.tokens, {
      id: me.data?.id,
      email: me.data?.email || (S.mfaPending && S.mfaPending.email),
      username: me.data?.username,
      display_name: profile.display_name || profile.first_name || me.data?.username,
      email_verified: me.data?.email_verified,
      is_staff: me.data?.is_staff,
      is_staff_ops: me.data?.is_staff_ops,
      mfa: true,
    });
    snack('Signed in — mfa_verified is true');
  }); },

  usebackup(){ withBusy(async () => {
    captureForm();
    const code = S.form.mfacode || 'A7F2-91KD';
    const r = await api('POST', '/api/v1/auth/mfa/verify/', {
      body: { code, device_type: 'backup', pre_auth_token: S.preAuthToken },
      headers: S.preAuthToken ? { Authorization: 'Bearer ' + S.preAuthToken } : {},
    });
    if (!r.ok) { S.formErr = errMsg(r.data, 'Invalid backup code.'); return; }
    S.tokens = { access: r.data.access, refresh: r.data.refresh, mfa_verified: true };
    const me = await api('GET', '/api/v1/auth/users/me/', { path: '/api/v1/auth/users/me/' });
    await finishLogin(S.tokens, {
      id: me.data?.id, email: me.data?.email, username: me.data?.username,
      display_name: me.data?.username, email_verified: me.data?.email_verified,
      is_staff: me.data?.is_staff, is_staff_ops: me.data?.is_staff_ops, mfa: true,
    });
    snack('Backup code accepted');
  }); },

  togglemfa(){ withBusy(async () => {
    if (S.user.mfa) {
      const r = await api('DELETE', '/api/v1/auth/mfa/disable/');
      if (r.ok || r.status === 204) {
        S.user.mfa = false; S.user.backup = null; persistAuth();
        snack('Two-factor turned off');
      }
    } else {
      const r = await api('POST', '/api/v1/auth/mfa/setup/', { body: { device_type: 'authenticator' } });
      if (r.ok) {
        S.user.mfa = true; persistAuth();
        snack('Authenticator registered');
      } else snack(errMsg(r.data));
    }
  }); },

  backupcodes(){ withBusy(async () => {
    const r = await api('POST', '/api/v1/auth/mfa/generate_backup_codes/', { body: {} });
    if (r.ok) {
      S.user.backup = r.data.backup_codes;
      persistAuth();
      snack('Backup codes generated');
    }
  }); },

  logout(){ withBusy(async () => {
    if (S.tokens && S.tokens.refresh) {
      await api('POST', '/api/v1/auth/logout/', { path: '/api/v1/auth/logout/', body: { refresh: S.tokens.refresh } });
    }
    S.user = null; S.tokens = null; S.mfaPending = null;
    S.profile = null; S.prefs = null; S.inbox = [];
    S.loyalty = null; S.loyaltyNote = '';
    S.cartSession = uuid();
    S.cart = null; S.orders = []; S.saved = [];
    S.authView = 'login';
    persistAuth();
    await loadCart();
    snack('Signed out');
    go('profile', 'profile');
  }); },

  ctab(v){ S.ctab = v; renderConsole(); },
  expand(v){ const k = String(v); S.expanded.has(k) ? S.expanded.delete(k) : S.expanded.add(k); renderConsole(); },
  clearlog(){ S.log = []; S.expanded.clear(); renderConsole(); },
  flag(v){ S.flags[v] = !S.flags[v]; render(); },

  settings(){ withBusy(async () => { await loadSettings(); go('settings'); }); },
  store(){ withBusy(async () => { await loadStore(); go('store'); }); },

  saveprofile(){
    const id = S.profile && S.profile.id;
    const dob = val('set-dob').trim();
    const body = {
      first_name: val('set-first').trim(),
      last_name: val('set-last').trim(),
      phone_number: val('set-phone').trim(),
      date_of_birth: dob || null,
      address: val('set-address').trim(),
    };
    withBusy(async () => {
      if (!id) { snack('Profile is still loading'); return; }
      const r = await api('PATCH', '/api/v1/auth/profiles/' + id + '/', {
        path: '/api/v1/auth/profiles/' + id + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save profile')); return; }
      S.profile = r.data;
      snack('Profile saved');
    });
  },

  changepassword(){
    const body = { current_password: val('set-current'), new_password: val('set-new') };
    withBusy(async () => {
      const r = await api('POST', '/api/v1/auth/users/change_password/', {
        path: '/api/v1/auth/users/change_password/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not change password')); return; }
      snack('Password updated');
    });
  },

  pref(v){ withBusy(async () => {
    if (!S.prefs) await loadSettings();
    const next = !(S.prefs && S.prefs[v]);
    const r = await api('PATCH', '/api/v1/notifications/preferences/', {
      path: '/api/v1/notifications/preferences/',
      body: { [v]: next },
    });
    if (!r.ok) { snack(errMsg(r.data, 'Could not update notifications')); return; }
    S.prefs = r.data;
    snack(next ? 'Preference on' : 'Preference off');
  }); },

  saverate(v){
    const body = { price: val('rate-price-' + v).trim(), estimated_days: val('rate-days-' + v).trim() };
    withBusy(async () => {
      const r = await api('PATCH', '/api/v1/orders/staff/shipping-rates/' + v + '/', {
        path: '/api/v1/orders/staff/shipping-rates/' + v + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save delivery')); return; }
      await loadStore();
      snack('Delivery saved');
    });
  },

  savead(v, btn){
    const current = (S.staffAds || []).find(row => String(row.id) === String(v));
    const active = btn && btn.dataset.flip === '1' ? !(current && current.is_active) : !!(current && current.is_active);
    const body = {
      title: val('ad-title-' + v).trim(),
      body: val('ad-body-' + v).trim(),
      product_slug: val('ad-slug-' + v).trim(),
      is_active: active,
    };
    withBusy(async () => {
      const r = await api('PATCH', '/api/v1/ads/staff/' + v + '/', {
        path: '/api/v1/ads/staff/' + v + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save banner')); return; }
      await loadStore();
      await loadMerch();
      snack('Banner saved');
    });
  },

  addbundle(v){ withBusy(async () => {
    const r = await api('POST', '/api/v1/promotions/bundles/' + v + '/add/', {
      path: '/api/v1/promotions/bundles/' + v + '/add/',
      body: {},
    });
    if (!r.ok) { snack(errMsg(r.data, 'Could not add the bundle')); return; }
    S.cart = r.data;
    snack('Bundle added');
  }); },

  review(){
    const body = val('review-body').trim();
    const rating = parseInt(val('review-rating'), 10) || 5;
    withBusy(async () => {
      if (!S.product) return;
      const r = await api('POST', '/api/v1/products/' + S.product.id + '/reviews/', {
        path: '/api/v1/products/' + S.product.id + '/reviews/',
        body: { rating, body },
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not post the review')); return; }
      await loadProduct(S.product.id);
      snack('Review posted');
    });
  },

  redeem(){ withBusy(async () => {
    const r = await api('POST', '/api/v1/promotions/loyalty/redeem/', {
      path: '/api/v1/promotions/loyalty/redeem/',
      body: {},
    });
    if (!r.ok) { snack(errMsg(r.data, 'Could not redeem points')); return; }
    S.loyaltyNote = r.data.voucher_code || '';
    await loadLoyalty();
    snack('Voucher ' + S.loyaltyNote);
  }); },

  attachreferral(){
    const code = val('set-referral').trim();
    withBusy(async () => {
      const r = await api('POST', '/api/v1/promotions/referrals/', {
        path: '/api/v1/promotions/referrals/',
        body: { code },
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save the code')); return; }
      await loadLoyalty();
      snack('Referral saved');
    });
  },

  saveflash(v, btn){
    const current = (S.staffFlashes || []).find(row => String(row.id) === String(v));
    const active = btn && btn.dataset.flip === '1' ? !(current && current.is_active) : !!(current && current.is_active);
    const start = val('flash-start-' + v).trim();
    const end = val('flash-end-' + v).trim();
    const body = {
      sale_price: val('flash-price-' + v).trim(),
      is_active: active,
      starts_at: start || null,
      ends_at: end || null,
    };
    withBusy(async () => {
      const r = await api('PATCH', '/api/v1/promotions/staff/flashes/' + v + '/', {
        path: '/api/v1/promotions/staff/flashes/' + v + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save the flash sale')); return; }
      await loadStore();
      await loadProducts();
      snack('Flash sale saved');
    });
  },

  savebundle(v, btn){
    const current = (S.staffBundles || []).find(row => String(row.id) === String(v));
    const active = btn && btn.dataset.flip === '1' ? !(current && current.is_active) : !!(current && current.is_active);
    const body = {
      title: val('bundle-title-' + v).trim(),
      price: val('bundle-price-' + v).trim(),
      is_active: active,
    };
    withBusy(async () => {
      const r = await api('PATCH', '/api/v1/promotions/staff/bundles/' + v + '/', {
        path: '/api/v1/promotions/staff/bundles/' + v + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save the bundle')); return; }
      await loadStore();
      await loadMerch();
      snack('Bundle saved');
    });
  },

  savepromo(v, btn){
    const current = (S.staffPromos || []).find(row => row.code === v);
    const active = btn && btn.dataset.flip === '1' ? !(current && current.is_active) : !!(current && current.is_active);
    const start = val('promo-start-' + v).trim();
    const end = val('promo-end-' + v).trim();
    const body = {
      title: val('promo-title-' + v).trim(),
      description: val('promo-body-' + v).trim(),
      amount: val('promo-amount-' + v).trim(),
      is_active: active,
      starts_at: start || null,
      ends_at: end || null,
    };
    withBusy(async () => {
      const r = await api('PATCH', '/api/v1/promotions/staff/' + encodeURIComponent(v) + '/', {
        path: '/api/v1/promotions/staff/' + v + '/',
        body,
      });
      if (!r.ok) { snack(errMsg(r.data, 'Could not save promotion')); return; }
      await loadStore();
      await loadMerch();
      snack(v + ' saved');
    });
  },
};

// Event delegation
document.addEventListener('click', e => {
  const btn = e.target.closest('[data-act]');
  if (!btn) return;
  const act = btn.dataset.act;
  const fn = ACTIONS[act];
  if (!fn) return;
  captureForm();
  fn(btn.dataset.v, btn);
});

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.id === 'q') {
    captureForm();
    loadProducts().then(render);
  }
});

document.addEventListener('input', e => {
  if (e.target.id === 'q') {
    clearTimeout(document._qT);
    document._qT = setTimeout(() => {
      S.filters.q = e.target.value;
      loadProducts().then(render);
    }, 320);
  }
});

async function boot(){
  render();
  try {
    await api('GET', '/api/v1/app/version-check/', { path: '/api/v1/app/version-check/' });
    await loadProducts();
    await loadMerch();
    await loadCart();
    if (S.user && S.tokens) {
      await loadOrders();
      await loadSaved();
      await loadInbox();
    }
    S.categories = [
      {id:'all', label:'Everything'},
      {id:'packs', label:'Packs'},
      {id:'shells', label:'Shells'},
      {id:'sleep', label:'Sleep'},
      {id:'tools', label:'Tools'},
    ];
    S.ready = true;
  } catch (err) {
    snack('API unavailable at ' + API_BASE);
  }
  render();
}

boot();
})();
