// ── Tab switching ──
document.querySelectorAll('.nav-item').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.nav-item').forEach(b=>b.classList.remove('on'));
    document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('on'));
    btn.classList.add('on');
    document.getElementById('tab-'+btn.dataset.tab).classList.add('on');
  });
});

// ── Logout ──
document.getElementById('logoutBtn').addEventListener('click', async ()=>{
  const res = await fetch('/admin/logout', {method:'POST'});
  const data = await res.json();
  window.location.href = data.redirect || '/admin/login';
});

let CONTENT = null;
const pendingUploads = new Map();
const uploadSerials = new Map();

function setSubmitState(isDisabled, label, formSelector){
  const button = document.querySelector((formSelector || '#testimonialForm') + ' button[type="submit"]');
  if(!button) return;
  button.disabled = !!isDisabled;
  if(label){
    button.dataset.originalLabel = button.dataset.originalLabel || button.textContent;
    button.textContent = label;
  } else if(button.dataset.originalLabel){
    button.textContent = button.dataset.originalLabel;
  }
}

function invalidateUpload(hiddenInputId, formSelector){
  uploadSerials.set(hiddenInputId, (uploadSerials.get(hiddenInputId) || 0) + 1);
  pendingUploads.delete(hiddenInputId);
  if(pendingUploads.size === 0){
    setSubmitState(false, null, formSelector);
  }
}

async function loadContent(){
  const res = await fetch('/api/admin/content');
  if(res.status === 401){ window.location.href = '/admin/login'; return; }
  CONTENT = await res.json();
  populateHero(CONTENT.hero);
  populatePricing(CONTENT.pricing);
  populateTestimonials(CONTENT.testimonials);
}

// ── HERO TAB ──
function populateHero(hero){
  const form = document.getElementById('heroForm');
  for(const key in hero){
    if(form.elements[key]) form.elements[key].value = hero[key];
  }
  document.getElementById('ceo_image_url').value = hero.ceo_image || '';
  if(hero.ceo_image){
    showPreview('ceoImagePreview', hero.ceo_image, 'ceo_image_url', '#heroForm');
  }
}
document.getElementById('ceo_image_file').addEventListener('change', async (e)=>{
  await handleImageUpload(e.target, 'ceo_image_url', 'ceoImagePreview', '#heroForm');
});
document.getElementById('heroForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const form = e.target;
  const body = {};
  ['meta_pill','meta_text','title_line1','title_line2','title_line3'].forEach(k=>{
    body[k] = form.elements[k].value;
  });
  body.ceo_image = document.getElementById('ceo_image_url').value;
  const res = await fetch('/api/admin/hero', {
    method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  });
  const status = document.getElementById('heroStatus');
  if(res.ok){ status.textContent = 'Saved ✓'; setTimeout(()=>status.textContent='', 2500); }
  else{ status.textContent = 'Error saving'; status.style.color = '#ff4d4d'; }
});

// ── PRICING TAB ──
function populatePricing(pricing){
  const grid = document.getElementById('pricingGrid');
  grid.innerHTML = '';
  Object.entries(pricing).forEach(([key, val])=>{
    const item = document.createElement('div');
    item.className = 'pricing-item';
    item.innerHTML = `
      <div class="p-label">${val.label}</div>
      <div class="p-row">
        <div>
          <label>USD ($)</label>
          <input type="number" data-key="${key}" data-field="usd" value="${val.usd}">
        </div>
        <div>
          <label>INR (₹)</label>
          <input type="number" data-key="${key}" data-field="inr" value="${val.inr}">
        </div>
      </div>
    `;
    grid.appendChild(item);
  });
}
document.getElementById('pricingForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  const inputs = document.querySelectorAll('#pricingGrid input');
  const body = {};
  inputs.forEach(inp=>{
    const key = inp.dataset.key, field = inp.dataset.field;
    body[key] = body[key] || {};
    body[key][field] = Number(inp.value);
  });
  const res = await fetch('/api/admin/pricing', {
    method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  });
  const status = document.getElementById('pricingStatus');
  if(res.ok){ status.textContent = 'Saved ✓'; setTimeout(()=>status.textContent='', 2500); }
  else{ status.textContent = 'Error saving'; status.style.color = '#ff4d4d'; }
});

// ── TESTIMONIALS TAB ──
function populateTestimonials(list){
  const wrap = document.getElementById('testimonialList');
  wrap.innerHTML = '';
  if(!list.length){
    wrap.innerHTML = '<p style="color:var(--muted);font-size:13px">No testimonials yet — add your first one above.</p>';
    return;
  }
  list.forEach(t=>{
    const card = document.createElement('div');
    card.className = 't-card testimonial-card' + (t.published ? '' : ' unpublished');
    const thumb = t.avatar_url
      ? `<img class="t-thumb" src="${t.avatar_url}" alt="${escapeHtml(t.name)}">`
      : `<div class="t-avatar-fallback">${escapeHtml((t.name||'?').charAt(0).toUpperCase())}</div>`;
    card.innerHTML = `
      ${thumb}
      <div class="t-main">
        <div class="t-name-row">
          <span class="t-name">${escapeHtml(t.name)}</span>
          <span class="t-role">${escapeHtml(t.role || '')}${t.company ? ' · '+escapeHtml(t.company) : ''}</span>
          <span class="t-badge">${t.location === 'india' ? '🇮🇳 India' : '🌍 Intl'}</span>
          <span class="t-badge">${t.published ? 'Published' : 'Hidden'}</span>
        </div>
        <div class="t-stars">${'★'.repeat(t.rating)}${'☆'.repeat(5-t.rating)}</div>
        <div class="t-text">${escapeHtml(t.text)}</div>
        ${getProofImages(t).length ? `<div class="t-proof-badge">📎 ${getProofImages(t).length} attachment${getProofImages(t).length === 1 ? '' : 's'} attached</div>` : ''}
      </div>
      <div class="t-actions">
        <button class="edit-btn" data-id="${t.id}">Edit</button>
        <button class="toggle-btn" data-id="${t.id}">${t.published ? 'Unpublish' : 'Publish'}</button>
        <button class="danger delete-btn" data-id="${t.id}">Delete</button>
      </div>
    `;
    wrap.appendChild(card);
  });

  wrap.querySelectorAll('.edit-btn').forEach(b=>b.addEventListener('click', ()=>openModal(Number(b.dataset.id))));
  wrap.querySelectorAll('.delete-btn').forEach(b=>b.addEventListener('click', ()=>deleteTestimonial(Number(b.dataset.id))));
  wrap.querySelectorAll('.toggle-btn').forEach(b=>b.addEventListener('click', ()=>togglePublish(Number(b.dataset.id))));
}

function escapeHtml(str){
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

function getStoredImages(hiddenInputId){
  const input = document.getElementById(hiddenInputId);
  if(!input || !input.value.trim()) return [];
  try{
    const parsed = JSON.parse(input.value);
    if(Array.isArray(parsed)) return parsed.filter(Boolean);
    return parsed ? [String(parsed)] : [];
  }catch(_err){
    return [input.value].filter(Boolean);
  }
}

function setStoredImages(hiddenInputId, urls){
  const input = document.getElementById(hiddenInputId);
  if(!input) return;
  input.value = JSON.stringify(urls);
}

function renderImagePreviewList(containerId, urls, hiddenInputId, fileInputId){
  const box = document.getElementById(containerId);
  if(!box) return;
  if(!urls.length){
    box.innerHTML = '';
    return;
  }
  box.innerHTML = urls.map((url, index)=>`
    <div class="up-remove" data-index="${index}">
      <img src="${url}" alt="Attachment preview">
      <button type="button" title="Remove">×</button>
    </div>
  `).join('');
  box.querySelectorAll('button').forEach(button=>button.addEventListener('click', ()=>{
    const wrapper = button.closest('.up-remove');
    if(!wrapper) return;
    const index = Number(wrapper.dataset.index);
    const next = getStoredImages(hiddenInputId);
    next.splice(index, 1);
    setStoredImages(hiddenInputId, next);
    if(fileInputId){
      const input = document.getElementById(fileInputId);
      if(input) input.value = '';
    }
    invalidateUpload(hiddenInputId);
    renderImagePreviewList(containerId, next, hiddenInputId, fileInputId);
  }));
}

function getProofImages(testimonial){
  if(Array.isArray(testimonial.proof_images)) return testimonial.proof_images.filter(Boolean);
  if(testimonial.proof_image) return [testimonial.proof_image].filter(Boolean);
  return [];
}

// ── Image uploads (client photo + proof screenshot) ──
async function uploadFile(file){
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/api/admin/upload', {method:'POST', body: fd, credentials:'same-origin'});
  const raw = await res.text();
  let data = {};
  try{
    data = raw ? JSON.parse(raw) : {};
  }catch(_err){
    data = {error: raw || 'Upload failed'};
  }
  if(!res.ok) throw new Error(data.error || 'Upload failed');
  return data.url;
}
async function handleImageUpload(inputEl, hiddenInputId, previewId, formSelector){
  const file = inputEl.files && inputEl.files[0];
  if(!file) return;

  const uploadSerial = (uploadSerials.get(hiddenInputId) || 0) + 1;
  uploadSerials.set(hiddenInputId, uploadSerial);
  const uploadPromise = uploadFile(file);
  pendingUploads.set(hiddenInputId, uploadPromise);
  setSubmitState(true, 'Uploading...', formSelector);

  try{
    const url = await uploadPromise;
    if(uploadSerials.get(hiddenInputId) !== uploadSerial) return;
    document.getElementById(hiddenInputId).value = url;
    showPreview(previewId, url, hiddenInputId);
  }catch(err){
    if(uploadSerials.get(hiddenInputId) === uploadSerial){
      document.getElementById(hiddenInputId).value = '';
      document.getElementById(previewId).innerHTML = '';
      alert(err.message);
    }
  }finally{
    if(uploadSerials.get(hiddenInputId) === uploadSerial){
      pendingUploads.delete(hiddenInputId);
    }
    if(pendingUploads.size === 0){
      setSubmitState(false, null, formSelector);
    }
  }
}
async function handleImageBatchUpload(inputEl, hiddenInputId, previewId){
  const files = Array.from(inputEl.files || []);
  if(!files.length) return;

  const uploadSerial = (uploadSerials.get(hiddenInputId) || 0) + 1;
  uploadSerials.set(hiddenInputId, uploadSerial);
  const uploadPromise = Promise.all(files.map(uploadFile));
  pendingUploads.set(hiddenInputId, uploadPromise);
  setSubmitState(true, 'Uploading...');

  try{
    const urls = await uploadPromise;
    if(uploadSerials.get(hiddenInputId) !== uploadSerial) return;
    const combined = [...getStoredImages(hiddenInputId), ...urls];
    setStoredImages(hiddenInputId, combined);
    renderImagePreviewList(previewId, combined, hiddenInputId, inputEl.id);
  }catch(err){
    if(uploadSerials.get(hiddenInputId) === uploadSerial){
      alert(err.message);
    }
  }finally{
    if(uploadSerials.get(hiddenInputId) === uploadSerial){
      pendingUploads.delete(hiddenInputId);
    }
    if(pendingUploads.size === 0){
      setSubmitState(false);
    }
  }
}
function showPreview(containerId, url, hiddenInputId, formSelector){
  const box = document.getElementById(containerId);
  if(!url){ box.innerHTML = ''; return; }
  box.innerHTML = `<div class="up-remove"><img src="${url}"><button type="button" title="Remove">×</button></div>`;
  box.querySelector('button').addEventListener('click', ()=>{
    document.getElementById(hiddenInputId).value = '';
    const fileInput = document.getElementById(hiddenInputId.replace('_url', '_file'));
    if(fileInput) fileInput.value = '';
    invalidateUpload(hiddenInputId, formSelector);
    box.innerHTML = '';
  });
}
document.getElementById('t_avatar_file').addEventListener('change', async (e)=>{
  await handleImageUpload(e.target, 't_avatar_url', 'avatarPreview');
});
document.getElementById('t_proof_files').addEventListener('change', async (e)=>{
  await handleImageBatchUpload(e.target, 't_proof_urls', 'proofPreview');
});

// ── Modal (add/edit) ──
const modal = document.getElementById('testimonialModal');
document.getElementById('newTestimonialBtn').addEventListener('click', ()=>openModal(null));
document.getElementById('cancelModalBtn').addEventListener('click', closeModal);
modal.addEventListener('click', (e)=>{ if(e.target === modal) closeModal(); });

function openModal(id){
  const form = document.getElementById('testimonialForm');
  form.reset();
  document.getElementById('tid').value = '';
  document.getElementById('t_published').checked = true;
  document.getElementById('t_rating').value = 5;
  document.getElementById('t_avatar_url').value = '';
  setStoredImages('t_proof_urls', []);
  document.getElementById('avatarPreview').innerHTML = '';
  document.getElementById('proofPreview').innerHTML = '';

  if(id){
    const t = CONTENT.testimonials.find(x=>x.id===id);
    document.getElementById('modalTitle').textContent = 'Edit Testimonial';
    document.getElementById('tid').value = t.id;
    document.getElementById('t_name').value = t.name;
    document.getElementById('t_role').value = t.role || '';
    document.getElementById('t_company').value = t.company || '';
    document.getElementById('t_location').value = t.location || 'intl';
    document.getElementById('t_text').value = t.text;
    document.getElementById('t_rating').value = t.rating;
    document.getElementById('t_published').checked = !!t.published;
    const proofImages = getProofImages(t);
    if(t.avatar_url){
      document.getElementById('t_avatar_url').value = t.avatar_url;
      showPreview('avatarPreview', t.avatar_url, 't_avatar_url');
    }
    setStoredImages('t_proof_urls', proofImages);
    renderImagePreviewList('proofPreview', proofImages, 't_proof_urls', 't_proof_files');
  } else {
    document.getElementById('modalTitle').textContent = 'Add Testimonial';
  }
  modal.classList.add('show');
}

function closeModal(){
  invalidateUpload('t_avatar_url');
  invalidateUpload('t_proof_urls');
  modal.classList.remove('show');
}

document.getElementById('testimonialForm').addEventListener('submit', async (e)=>{
  e.preventDefault();
  if(pendingUploads.size){
    setSubmitState(true, 'Uploading...');
    try{
      await Promise.all([...pendingUploads.values()]);
    }catch(_err){
      alert('Please wait for image uploads to finish before saving.');
      return;
    } finally {
      if(pendingUploads.size === 0){
        setSubmitState(false);
      }
    }
  }

  const id = document.getElementById('tid').value;
  const body = {
    name: document.getElementById('t_name').value,
    role: document.getElementById('t_role').value,
    company: document.getElementById('t_company').value,
    location: document.getElementById('t_location').value,
    text: document.getElementById('t_text').value,
    rating: Number(document.getElementById('t_rating').value),
    published: document.getElementById('t_published').checked,
    avatar_url: document.getElementById('t_avatar_url').value,
    proof_images: getStoredImages('t_proof_urls'),
  };

  const url = id ? `/api/admin/testimonials/${id}` : '/api/admin/testimonials';
  const method = id ? 'PUT' : 'POST';
  const res = await fetch(url, {
    method, headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  });

  if(res.ok){
    closeModal();
    await loadContent();
  } else {
    const err = await res.json();
    alert(err.error || 'Something went wrong.');
  }
});

async function deleteTestimonial(id){
  if(!confirm('Delete this testimonial? This cannot be undone.')) return;
  const res = await fetch(`/api/admin/testimonials/${id}`, {method:'DELETE'});
  if(res.ok) await loadContent();
}

async function togglePublish(id){
  const t = CONTENT.testimonials.find(x=>x.id===id);
  const res = await fetch(`/api/admin/testimonials/${id}`, {
    method:'PUT', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({published: !t.published})
  });
  if(res.ok) await loadContent();
}

loadContent();
