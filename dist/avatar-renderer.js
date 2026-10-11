export function frameFor(hero, speaking) {
  return speaking ? hero.talk : hero.idle;
}

export class AvatarRenderer {
  constructor(container, heroes, makeImage = () => new Image()) {
    this.heroes = heroes;
    this.makeImage = makeImage;
    this.cache = new Map();
    this.request = 0;
    this.selected = heroes[0];
    this.speaking = false;
    this.image = makeImage();
    this.image.className = 'avatar-image';
    this.image.alt = 'Richard con audífonos';
    this.image.draggable = false;
    container.append(this.image);
    this.setState({hero: 'base', speaking: false});
  }

  async preload(hero) {
    if (!this.cache.has(hero.id)) {
      const promise = Promise.all([hero.idle, hero.talk].map(async source => {
        const image = this.makeImage();
        image.src = new URL(source, document.baseURI).href;
        await image.decode();
        return image;
      }));
      this.cache.set(hero.id, promise);
      promise.catch(() => this.cache.delete(hero.id));
    }
    return this.cache.get(hero.id);
  }

  async setState(state) {
    const hero = this.heroes.find(hero => hero.id === state.hero) || this.heroes[0];
    this.speaking = Boolean(state.speaking);
    this.selected = hero;
    const request = ++this.request;
    try {
      const frames = await this.preload(hero);
      if (request !== this.request) return;
      this.image.src = frames[this.speaking ? 1 : 0].src;
      this.image.alt = `Richard · ${hero.name} · ${this.speaking ? 'boca abierta' : 'boca cerrada'}`;
      this.image.dataset.hero = hero.id;
      this.image.dataset.speaking = String(this.speaking);
    } catch (error) {
      if (request === this.request && hero.id !== 'base') {
        await this.setState({hero: 'base', speaking: state.speaking});
      }
    }
  }
}
