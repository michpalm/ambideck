import { afterEach, expect, it, vi } from 'vitest';

const f = vi.hoisted(() => ({ listeners: new Map<string, (...args: any[]) => void>(), log: [] as string[],
    status: { supported: false, hueSync: false } as Record<string, unknown> }));
vi.mock('@decky/api', () => ({
    callable: () => async () => null,
    addEventListener: (event: string, fn: (...args: any[]) => void) => { f.listeners.set(event, fn); return fn; },
    removeEventListener: (event: string) => f.listeners.delete(event),
}));
vi.mock('../src/backend', () => ({ backendKv: {}, backend: {
    getStatus: async () => f.status,
    follow: async () => { f.log.push('follow'); }, stop: async () => { f.log.push('stop'); },
    fallback: async () => { f.log.push('fallback'); }, off: async () => {}, show: async () => {}, rainbow: async () => {},
} }));
vi.mock('../src/steamSources', () => ({ steamSituationDeps: () => ({}) }));
vi.mock('../src/situation', () => ({ createSituation: () => ({
    get: () => ({ appId: '1', onCharger: false, docked: false, capturing: false, asleep: false }),
    subscribe: () => () => {}, start: () => {}, stop: () => {},
}) }));
vi.mock('../src/settings', () => ({ settings: {
    load: async () => {}, get: () => ({ enabled: true }), subscribe: () => () => {},
}, followSettings: () => ({ layout: 'corners' }) }));
vi.mock('../src/decide', () => ({ decide: () => ({ kind: 'follow' }) }));
vi.mock('../src/updater', () => ({ createUpdater: () => ({ checkOnStart: async () => {} }) }));

afterEach(() => { f.listeners.clear(); f.log.length = 0; vi.resetModules(); });
const settle = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); };

it('starts after late RGB discovery, ignores duplicate events and removes listeners on stop', async () => {
    const { startAmbideck } = await import('../src/app');
    const app = startAmbideck();
    await settle();
    expect(f.log).not.toContain('follow');
    const event = f.listeners.get('lights_status')!;
    expect(event).toBeTypeOf('function');
    event({ supported: true, hueSync: false, deviceName: 'Claw', deviceLayout: 'shared' });
    await settle();
    expect(f.log.filter(x => x === 'follow')).toHaveLength(1);
    event({ supported: true, hueSync: false, deviceName: 'Claw', deviceLayout: 'shared' });
    await settle();
    expect(f.log.filter(x => x === 'follow')).toHaveLength(1);
    await app.stop();
    expect(f.listeners.has('lights_status')).toBe(false);
    const n = f.log.length;
    event({ supported: true, hueSync: false }); await settle();
    expect(f.log).toHaveLength(n);
});
