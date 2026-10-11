import {AvatarRenderer} from './avatar-renderer.js';
import {LocalBridge} from './bridge.js';
const {heroes} = await (await fetch('./catalog.json')).json();
const renderer = new AvatarRenderer(document.querySelector('#avatar-stage'), heroes);
const query = new URLSearchParams(location.search);
if (query.has('demo')) {
  await renderer.setState({hero: query.get('hero') || 'base', speaking: query.get('talk') === '1'});
} else {
  const bridge = new LocalBridge();
  bridge.addEventListener('state', event => renderer.setState(event.detail));
  bridge.addEventListener('offline', () => renderer.setState({hero: renderer.selected.id, speaking: false}));
  try { await bridge.connect(); } catch { /* Keep Richard idle while the local service starts. */ }
}
