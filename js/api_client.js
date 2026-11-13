window.get = async function(path, raw = false) {
  const r = await fetch(window.API + path);
  const payload = await r.json();
  if (raw) return payload;
  if (
    payload &&
    typeof payload === 'object' &&
    Object.prototype.hasOwnProperty.call(payload, 'ok') &&
    Object.prototype.hasOwnProperty.call(payload, 'data')
  ) {
    return payload.data;
  }
  return payload;
};

window.post = async function(path, body, raw = false) {
  const r = await fetch(window.API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {})
  });
  const payload = await r.json();
  if (raw) return payload;
  if (
    payload &&
    typeof payload === 'object' &&
    Object.prototype.hasOwnProperty.call(payload, 'ok') &&
    Object.prototype.hasOwnProperty.call(payload, 'data')
  ) {
    return payload.data;
  }
  return payload;
};

window.fillSel = function(id, items, key = 'asset') {
  const s = document.getElementById(id);
  const old = s.value;
  s.innerHTML = '';
  items.forEach(i => {
    const o = document.createElement('option');
    o.value = i[key];
    o.textContent = i[key];
    s.appendChild(o);
  });
  if (items.find(i => i[key] === old)) s.value = old;
  return s.value;
};

window.fillSelKV = function(id, items, valueKey = 'id', textKey = 'name') {
  const s = document.getElementById(id);
  const old = s.value;
  s.innerHTML = '';
  items.forEach(i => {
    const o = document.createElement('option');
    o.value = i[valueKey];
    o.textContent = i[textKey];
    s.appendChild(o);
  });
  if (items.find(i => String(i[valueKey]) === old)) s.value = old;
  return s.value;
};
