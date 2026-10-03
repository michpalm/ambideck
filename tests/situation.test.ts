import { describe, expect, it } from 'vitest';
import { artworkFromPath, createSituation, SituationDeps } from '../src/situation';

function fakeDeps() {
    const cbs: Record<string, (v?: unknown) => void> = {};
    let tick: () => void = () => {};
    const state = { app: null as string | null, path: '/library/home' };
    const deps: SituationDeps = {
        runningAppId: () => state.app,
        currentPath: () => state.path,
        onSuspend: (cb) => ((cbs.suspend = cb), () => {}),
        onResume: (cb) => ((cbs.resume = cb), () => {}),
        onCharger: (cb) => ((cbs.charger = cb as (v?: unknown) => void), () => {}),
        onDocked: (cb) => ((cbs.docked = cb as (v?: unknown) => void), () => {}),
        initialStatus: async () => ({ docked: true, onCharger: false }),
        every: (fn) => ((tick = fn), () => {}),
    };
    return { deps, cbs, state, tick: () => tick() };
}

describe('artworkFromPath', () => {
    it('finds the game page', () => {
        expect(artworkFromPath('/library/app/1245620')).toBe('1245620');
        expect(artworkFromPath('/library/app/1245620/achievements')).toBe('1245620');
        expect(artworkFromPath('/library/home')).toBeNull();
        expect(artworkFromPath(null)).toBeNull();
    });
});

describe('createSituation', () => {
    it('tracks game, page, sleep, charger and dock, notifying only on change', async () => {
        const { deps, cbs, state, tick } = fakeDeps();
        const s = createSituation(deps);
        let calls = 0;
        s.subscribe(() => calls++);
        s.start();
        await Promise.resolve();
        expect(s.get().docked).toBe(true);
        state.app = '730';
        state.path = '/library/app/730';
        tick();
        tick();
        cbs.suspend();
        cbs.resume();
        cbs.charger(true);
        expect(s.get()).toEqual({ appId: '730', suspended: false, docked: true, onCharger: true, artworkAppId: '730' });
        expect(calls).toBe(5);
    });
});

describe('a Steam source that throws', () => {
    it('does not stop the other sources', async () => {
        const { deps, cbs, state, tick } = fakeDeps();
        const s = createSituation({ ...deps, onSuspend: () => { throw new Error('Unknown method'); } });
        expect(() => s.start()).not.toThrow();
        state.app = '1';
        tick();
        cbs.charger(true);
        expect(s.get().appId).toBe('1');
        expect(s.get().onCharger).toBe(true);
    });
});
