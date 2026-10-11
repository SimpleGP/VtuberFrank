export const isLocal = ['localhost', '127.0.0.1'].includes(location.hostname);
export const localBase = isLocal ? new URL('/', location.href) : new URL('http://127.0.0.1:18766/');

export class LocalBridge extends EventTarget {
  constructor() { super(); this.connected = false; this.running = false; this.failures = 0; }
  async request(path, body) {
    const response = await fetch(new URL(path, localBase), {
      method: body === undefined ? 'GET' : 'POST', cache: 'no-store',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(2200),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo conectar');
    return data;
  }
  async connect() {
    const health = await this.request('health');
    if (health.service !== 'FrankVtuber' || health.version !== 1) throw new Error('Inicia FrankVtuber en tu PC');
    this.connected = true;
    if (!this.running) { this.running = true; this.poll(); }
  }
  async poll() {
    if (!this.running) return;
    try {
      const state = await this.request('state');
      this.connected = true; this.failures = 0;
      this.dispatchEvent(new CustomEvent('state', {detail: state}));
    } catch (error) {
      if (++this.failures >= 3) {
        this.connected = false; this.running = false;
        this.dispatchEvent(new CustomEvent('offline', {detail: error.message}));
        return;
      }
    }
    setTimeout(() => this.poll(), 50);
  }
}
