import test from 'node:test';
import assert from 'node:assert/strict';
import {AvatarRenderer} from '../dist/avatar-renderer.js';

globalThis.document = {baseURI: 'http://localhost/'};
const heroes = [
  {id: 'base', name: 'Richard', idle: 'base-idle.png', talk: 'base-talk.png'},
  {id: 'sigma', name: 'Sigma', idle: 'sigma-idle.png', talk: 'sigma-talk.png'},
  {id: 'ashe', name: 'Ashe', idle: 'ashe-idle.png', talk: 'ashe-talk.png'},
];
const container = {append() {}};

test('the latest selected hero wins even when an older image finishes later', async () => {
  let finishSigma;
  const sigmaReady = new Promise(resolve => { finishSigma = resolve; });
  const factory = () => ({dataset: {}, decode() {
    return this.src.includes('sigma') ? sigmaReady : Promise.resolve();
  }});
  const avatar = new AvatarRenderer(container, heroes, factory);
  const old = avatar.setState({hero: 'sigma', speaking: true});
  await avatar.setState({hero: 'ashe', speaking: false});
  finishSigma(); await old;
  assert.equal(avatar.image.dataset.hero, 'ashe');
  assert.match(avatar.image.src, /ashe-idle.png$/);
});

test('voice changes only the paired frame and unknown heroes use Richard', async () => {
  const factory = () => ({dataset: {}, decode: () => Promise.resolve()});
  const avatar = new AvatarRenderer(container, heroes, factory);
  await avatar.setState({hero: 'ashe', speaking: true});
  assert.match(avatar.image.src, /ashe-talk.png$/);
  await avatar.setState({hero: 'ashe', speaking: false});
  assert.match(avatar.image.src, /ashe-idle.png$/);
  await avatar.setState({hero: '../../private', speaking: false});
  assert.equal(avatar.image.dataset.hero, 'base');
});
