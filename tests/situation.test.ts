import { describe, expect, it } from 'vitest';
import { createSituation, SituationDeps } from '../src/situation';

function fakeDeps() {
    const cbs: Record<string, (v?: unknown) => void> = {};
    let tick: () => void = () => {};
    const state = { app: null as string | null };
    const deps: SituationDeps = {
        runningAppId: () => state.app,
        onSuspend: (cb) => ((cbs.suspend = cb), () => {}),
        onResume: (cb) => ((cbs.resume = cb), () => {}),
        onCharger: (cb) => ((cbs.charger = cb as (v?: unknown) => void), () => {}),
        onDocked: (cb) => ((cbs.docked = cb as (v?: unknown) => void), () => {}),
        onCapture: (cb) => ((cbs.capture = cb as (v?: unknown) => void), () => {}),
        initialStatus: async () => ({ docked: true, onCharger: false, capturing: false }),
        every: (fn) => ((tick = fn), () => {}),
    };
    return { deps, cbs, state, tick: () => tick() };
}

describe('createSituation', () => {
    it('tracks game, sleep, charger and dock, notifying only on change', async () => {
        const { deps, cbs, state, tick } = fakeDeps();
        const s = createSituation(deps);
        let calls = 0;
        s.subscribe(() => calls++);
        s.start();
        await Promise.resolve();
        expect(s.get().docked).toBe(true);
        state.app = '730';
        tick();
        tick();
        cbs.suspend();
        cbs.resume();
        cbs.charger(true);
        expect(s.get()).toEqual({ appId: '730', suspended: false, docked: true, onCharger: true, capturing: false });
        expect(calls).toBe(5);
    });
});

describe('the capture lock', () => {
    it('starts from the backend status and follows the capture_lock event', async () => {
        const { deps, cbs } = fakeDeps();
        const s = createSituation({ ...deps, initialStatus: async () => ({ docked: false, onCharger: false, capturing: true }) });
        let calls = 0;
        s.subscribe(() => calls++);
        s.start();
        await Promise.resolve();
        expect(s.get().capturing).toBe(true);
        calls = 0;
        cbs.capture(false);
        expect(s.get().capturing).toBe(false);
        expect(calls).toBe(1);
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

describe('sleep and wake events', () => {
    it('ignores sleep events when wake events are unavailable', () => {
        const { deps, cbs } = fakeDeps();
        let stopped = false;
        const s = createSituation({ ...deps,
            onSuspend: (cb) => ((cbs.suspend = cb), () => { stopped = true; }),
            onResume: () => null });
        s.start();
        cbs.suspend();
        expect(s.get().suspended).toBe(false);
        expect(stopped).toBe(true);
    });
    it('ignores wake events when sleep events throw', () => {
        const { deps } = fakeDeps();
        let stopped = false;
        const s = createSituation({ ...deps,
            onSuspend: () => { throw new Error('Unknown method'); },
            onResume: () => () => { stopped = true; } });
        expect(() => s.start()).not.toThrow();
        expect(stopped).toBe(true);
    });
});
