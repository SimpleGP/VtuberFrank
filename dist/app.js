import {AvatarRenderer} from './avatar-renderer.js';
import {LocalBridge, isLocal, localBase} from './bridge.js';

const {heroes} = await (await fetch('./catalog.json')).json();
const renderer = new AvatarRenderer(document.querySelector('#avatar-stage'), heroes);
const bridge = new LocalBridge();
let state = {hero: 'base', speaking: false, hero_mode: 'manual'};
let previewMouth = null;
let changingHero = false;
const byId = id => document.getElementById(id);

function render() {
  const hero = heroes.find(hero => hero.id === state.hero) || heroes[0];
  const speaking = previewMouth === null ? Boolean(state.speaking) : previewMouth;
  renderer.setState({hero: hero.id, speaking});
  byId('selected-name').textContent = hero.name;
  byId('selected-skin').textContent = hero.skin;
  byId('voice-badge').textContent = speaking ? 'Hablando' : 'En reposo';
  document.querySelectorAll('[data-hero]').forEach(button => {
    const selected = button.dataset.hero === hero.id;
    button.classList.toggle('selected', selected);
    button.setAttribute('aria-pressed', String(selected));
  });
  byId('auto-button').classList.toggle('selected', state.hero_mode === 'auto');
  byId('auto-button').setAttribute('aria-pressed', String(state.hero_mode === 'auto'));
  byId('scan-button').disabled = !bridge.connected;
  byId('mouth-live').hidden = !bridge.connected || previewMouth === null;
  document.querySelectorAll('[data-mouth]').forEach(button => button.classList.toggle('selected',
    (button.dataset.mouth === 'talk') === speaking));
}

for (const hero of heroes) {
  const button = document.createElement('button');
  button.className = 'skin-card'; button.dataset.hero = hero.id;
  button.setAttribute('aria-label', `Elegir ${hero.name} · ${hero.skin}`);
  const image = new Image(); image.src = hero.idle; image.alt = ''; image.loading = 'lazy'; image.draggable = false;
  const text = document.createElement('span'); text.className = 'skin-text';
  const name = document.createElement('strong'); name.textContent = hero.name;
  const skin = document.createElement('small'); skin.textContent = hero.skin;
  text.append(name, skin); button.append(image, text);
  button.onclick = () => selectHero(hero.id);
  byId('catalog').append(button);
  if (hero.id !== 'base') {
    const option = document.createElement('option'); option.value = hero.id; option.textContent = hero.name;
    byId('calibration-hero').append(option);
  }
}

async function selectHero(hero) {
  changingHero = true;
  try {
    if (bridge.connected) {
      await bridge.request('hero', {hero});
      state = await bridge.request('state');
    } else {
      if (hero !== 'auto') state.hero = hero;
      state.hero_mode = hero === 'auto' ? 'auto' : 'manual';
      if (hero === 'auto') byId('local-status').textContent = 'Inicia FrankVtuber en tu PC para detectar desde el juego.';
    }
    render();
  } catch (error) { byId('local-status').textContent = error.message; }
  finally { changingHero = false; }
}

document.querySelectorAll('[data-mouth]').forEach(button => button.onclick = () => {
  previewMouth = button.dataset.mouth === 'talk'; render();
});
byId('mouth-live').onclick = () => { previewMouth = null; render(); };
byId('auto-button').onclick = () => selectHero(state.hero_mode === 'auto' ? state.hero : 'auto');
byId('scan-button').onclick = async () => {
  try { await bridge.request('scan', {}); byId('game-status').textContent = 'Vuelve a Overwatch. Revisaremos el retrato en 3 segundos.'; }
  catch (error) { byId('game-status').textContent = error.message; }
};

bridge.addEventListener('state', event => {
  if (changingHero) return;
  state = event.detail;
  document.body.classList.add('connected');
  byId('connection-label').textContent = 'Avatar conectado';
  byId('local-status').textContent = state.speaking ? 'Tu voz abre la boca de Richard.' : 'Voz conectada · Richard está en reposo.';
  byId('game-status').textContent = state.overwatch?.status || 'Tecla encima de Tab para revisar';
  byId('detection-note').textContent = state.hero_mode === 'auto' ? 'Con Overwatch al frente, pulsa la tecla para cambiar de personaje.' : 'Skin manual. Activa Automático para reconocer al héroe.';
  byId('calibration-save').disabled = false;
  byId('connect-button').textContent = 'Avatar conectado';
  render();
});
bridge.addEventListener('offline', () => {
  document.body.classList.remove('connected');
  byId('connection-label').textContent = 'Vista previa';
  byId('connect-button').textContent = 'Conectar avatar local';
  byId('local-status').textContent = 'Inicia FrankVtuber en tu PC para conectar la voz y la detección.';
  byId('calibration-save').disabled = true;
  state.speaking = false; render();
});
byId('connect-button').onclick = async () => {
  byId('local-status').textContent = 'Conectando…';
  try { previewMouth = null; await bridge.connect(); }
  catch { byId('local-status').textContent = 'Inicia FrankVtuber.vbs y vuelve a conectar. También puedes abrir el panel local.'; }
};
byId('overlay-link').href = new URL('avatar.html', localBase).href;

byId('calibration-save').onclick = async () => {
  const file = byId('calibration-file').files[0];
  if (!file) { byId('calibration-status').textContent = 'Elige una captura del juego.'; return; }
  if (file.size > 12 * 1024 * 1024) { byId('calibration-status').textContent = 'Usa una captura de menos de 12 MB.'; return; }
  const objectUrl = URL.createObjectURL(file);
  try {
    const image = new Image(); image.src = objectUrl; await image.decode();
    if (image.naturalWidth < 640 || image.naturalHeight < 400) throw new Error('Usa una captura completa del juego.');
    const canvas = document.createElement('canvas'); canvas.width = 88; canvas.height = 109;
    const context = canvas.getContext('2d');
    context.drawImage(image, 62 * image.naturalWidth / 1920, 888 * image.naturalHeight / 1080,
      88 * image.naturalWidth / 1920, 109 * image.naturalHeight / 1080, 0, 0, 88, 109);
    await bridge.request('calibrate', {hero: byId('calibration-hero').value,
      portrait: canvas.toDataURL('image/png').split(',')[1]});
    byId('calibration-status').textContent = 'Retrato guardado en tu PC. Pulsa la tecla en el juego para revisar.';
  } catch (error) { byId('calibration-status').textContent = error.message; }
  finally { URL.revokeObjectURL(objectUrl); }
};
render();
if (isLocal) {
  try { await bridge.connect(); } catch { /* Static local preview remains usable. */ }
}
