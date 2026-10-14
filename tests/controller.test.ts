import { describe, expect, it } from 'vitest';
import { createController } from '../src/controller';
import type { HueSync, RestoreResult } from '../src/huesync/bridge';
import type { FollowSettings } from '../src/types';

const FOLLOW: FollowSettings = { layout: 'corners', brightness: 70, boost: 58, speed: 'balanced', dark: 'glow' };
const CTX = { appId: '1', onCharger: false };

function setup(opts: { present?: boolean; restore?: RestoreResult; stopFails?: boolean } = {}) {
    const log: string[] = [];
    const pending: (() => void)[] = [];
    const backend = {
        follow: async (s: FollowSettings) => void log.push(`follow:${s.layout}`),
        show: async () => void log.push('show'),
        rainbow: async (keep?: boolean) => void log.push(keep ? 'rainbow:keep' : 'rainbow'),
        off: async () => void log.push('off'),
        stop: async () => {
            log.push('stop');
            if (opts.stopFails) throw new Error('backend gone');
        },
    };
    const hueSync: HueSync = {
        present: () => opts.present ?? true,
        pause: async () => (log.push('pause'), true),
        restore: async () => (log.push('restore'), opts.restore ?? 'restored'),
    };
    const controller = createController({
        backend, hueSync,
        later: (fn) => {
            pending.push(fn);
            return () => {
                const i = pending.indexOf(fn);
                if (i >= 0) pending.splice(i, 1);
            };
        },
    });
    const flushLater = async () => {
        for (const fn of pending.splice(0)) fn();
        await controller.idle();
    };
    return { controller, log, flushLater, pending };
}

describe('controller', () => {
    it('takes over from HueSync, then follows; repeats the pause once', async () => {
        const { controller, log, flushLater } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        expect(log).toEqual(['pause', 'follow:corners']);
        await flushLater();
        expect(log).toEqual(['pause', 'follow:corners', 'pause']);
    });
    it('only updates settings while already following', async () => {
        const { controller, log } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        await controller.apply({ kind: 'follow' }, { ...FOLLOW, layout: 'sides' }, CTX);
        await controller.apply({ kind: 'follow' }, { ...FOLLOW, layout: 'sides' }, CTX);
        expect(log).toEqual(['pause', 'follow:corners', 'follow:sides']);
    });
    it('stops before handing back, and asks HueSync again a second later', async () => {
        const { controller, log, flushLater } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        log.length = 0;
        await controller.apply({ kind: 'handBack' }, FOLLOW, { appId: null, onCharger: false });
        expect(log).toEqual(['stop', 'restore']);
        await flushLater();
        expect(log).toEqual(['stop', 'restore', 'restore']);
    });
    it('falls back to rainbow without HueSync', async () => {
        const { controller, log } = setup({ present: false, restore: 'unavailable' });
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        await controller.apply({ kind: 'handBack' }, FOLLOW, CTX);
        expect(log).toEqual(['follow:corners', 'stop', 'restore', 'rainbow']);
    });
    it('does nothing for a hand-back when it already handed back (start-up included)', async () => {
        const { controller, log } = setup();
        await controller.apply({ kind: 'handBack' }, FOLLOW, CTX);
        expect(log).toEqual([]);
    });
    it('pauses without handing back while asleep', async () => {
        const { controller, log } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        log.length = 0;
        await controller.apply({ kind: 'pause' }, FOLLOW, CTX);
        expect(log).toEqual(['stop']);
    });
    it('keeps following from a game to the home screen, only asking HueSync to step aside again', async () => {
        const { controller, log, flushLater } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, { appId: '1', onCharger: false });
        await flushLater();
        log.length = 0;
        await controller.apply({ kind: 'follow' }, FOLLOW, { appId: null, onCharger: false });
        expect(log).toEqual(['pause']);
        await flushLater();
        expect(log).toEqual(['pause', 'pause']);
    });
    it('does nothing when only the charger changed while following', async () => {
        const { controller, log, flushLater } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, { appId: '1', onCharger: false });
        await flushLater();
        log.length = 0;
        await controller.apply({ kind: 'follow' }, FOLLOW, { appId: '1', onCharger: true });
        expect(log).toEqual([]);
    });
    it('turns the lights off for outside games = off', async () => {
        const { controller, log } = setup();
        await controller.apply({ kind: 'off' }, FOLLOW, { appId: null, onCharger: false });
        expect(log).toEqual(['pause', 'off']);
    });
    it('repeats the HueSync pause after turning the lights off', async () => {
        const { controller, log, flushLater } = setup();
        await controller.apply({ kind: 'off' }, FOLLOW, CTX);
        expect(log).toEqual(['pause', 'off']);
        await flushLater();
        expect(log).toEqual(['pause', 'off', 'pause']);
    });
    it('drops a repeat whose decision is no longer current', async () => {
        const { controller, log, pending } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        const stale = pending.slice();
        await controller.apply({ kind: 'pause' }, FOLLOW, CTX);
        stale.forEach((fn) => fn());
        await controller.idle();
        expect(log.filter((l) => l === 'pause')).toHaveLength(1);
    });
    it('runs overlapping applies one at a time, in order', async () => {
        const { controller, log } = setup();
        void controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        void controller.apply({ kind: 'handBack' }, FOLLOW, CTX);
        await controller.idle();
        expect(log).toEqual(['pause', 'follow:corners', 'stop', 'restore']);
    });
    it('re-pauses HueSync on charger changes and hands back while the stream is lost', async () => {
        const { controller, log } = setup();
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        log.length = 0;
        await controller.chargerChanged();
        await controller.followState('waiting');
        await controller.followState('following');
        expect(log).toEqual(['pause', 'restore', 'pause']);
    });
    it('without HueSync, a lost stream shows rainbow but keeps following', async () => {
        const { controller, log } = setup({ present: false, restore: 'unavailable' });
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        log.length = 0;
        await controller.followState('waiting');
        expect(log).toEqual(['restore', 'rainbow:keep']);
    });
    it('still restores HueSync when stopping the backend fails, and retries the decision next time', async () => {
        const { controller, log } = setup({ stopFails: true });
        await controller.apply({ kind: 'follow' }, FOLLOW, CTX);
        log.length = 0;
        await controller.apply({ kind: 'handBack' }, FOLLOW, CTX);
        expect(log).toEqual(['stop', 'restore']);
        log.length = 0;
        await controller.apply({ kind: 'handBack' }, FOLLOW, CTX);
        expect(log).toEqual(['stop', 'restore']);
    });
});
