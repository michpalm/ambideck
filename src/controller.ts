import type { Backend } from './backend';
import type { Decision } from './decide';
import type { HueSync } from './huesync/bridge';
import type { FollowSettings, Zones } from './types';

export interface ControllerDeps {
    backend: Backend;
    hueSync: HueSync;
    artwork(appId: string, s: FollowSettings): Promise<Zones | null>;
    later(fn: () => void, ms: number): () => void; // returns cancel
}

interface Ctx {
    appId: string | null;
    onCharger: boolean;
}

const REPEAT_MS = 1000;
const HAS_LIGHTS = new Set(['follow', 'artwork', 'off']);

export function createController(deps: ControllerDeps) {
    // At start-up HueSync (or nothing) has the lights. 'unknown' after a failed step, so the next decision runs again.
    let current: Decision | { kind: 'unknown' } = { kind: 'handBack' };
    let follow: FollowSettings | null = null;
    let ctx: Ctx = { appId: null, onCharger: false };
    let cancelRepeat: (() => void) | null = null;
    let queue: Promise<void> = Promise.resolve();

    const enqueue = (job: () => Promise<void>): Promise<void> => {
        queue = queue.then(job).catch((error) => console.error('[ambideck] controller step failed', error));
        return queue;
    };
    const cancel = () => {
        cancelRepeat?.();
        cancelRepeat = null;
    };
    const repeat = (job: () => Promise<unknown>) => {
        cancel();
        cancelRepeat = deps.later(() => void enqueue(async () => void (await job())), REPEAT_MS);
    };
    const takeOver = async () => {
        if (deps.hueSync.present()) await deps.hueSync.pause();
    };
    /** keepFollowing: the stream is only lost for now, so the backend keeps retrying behind the rainbow. */
    const restore = async (keepFollowing = false) => {
        const result = await deps.hueSync.restore(ctx.appId, ctx.onCharger);
        if (result === 'unavailable') await deps.backend.rainbow(keepFollowing);
    };
    const handBack = async () => {
        try {
            await deps.backend.stop();
        } finally {
            await restore();
            if (deps.hueSync.present()) repeat(restore);
        }
    };

    async function run(decision: Decision, nextFollow: FollowSettings, nextCtx: Ctx): Promise<void> {
        const previous = current;
        const sameSettings = JSON.stringify(follow) === JSON.stringify(nextFollow);
        if (JSON.stringify(previous) === JSON.stringify(decision) && sameSettings) {
            ctx = nextCtx;
            return;
        }
        current = decision;
        follow = nextFollow;
        ctx = nextCtx;
        try {
            await perform(decision, previous, nextFollow);
        } catch (error) {
            current = { kind: 'unknown' };
            throw error;
        }
    }

    async function perform(decision: Decision, previous: Decision | { kind: 'unknown' }, nextFollow: FollowSettings) {
        switch (decision.kind) {
            case 'follow':
                if (previous.kind !== 'follow') {
                    cancel();
                    await takeOver();
                    if (deps.hueSync.present()) repeat(takeOver);
                }
                await deps.backend.follow(nextFollow);
                return;
            case 'artwork': {
                cancel();
                await takeOver();
                const zones = await deps.artwork(decision.appId, nextFollow);
                if (zones) await deps.backend.show(zones);
                else await handBack();
                return;
            }
            case 'off':
                cancel();
                await takeOver();
                await deps.backend.off();
                return;
            case 'pause':
                cancel();
                await deps.backend.stop();
                return;
            case 'handBack':
                if (previous.kind === 'handBack') return;
                cancel();
                await handBack();
                return;
        }
    }

    return {
        apply: (decision: Decision, nextFollow: FollowSettings, nextCtx: Ctx) =>
            enqueue(() => run(decision, nextFollow, nextCtx)),
        chargerChanged: () => enqueue(async () => {
            if (HAS_LIGHTS.has(current.kind)) await takeOver();
        }),
        followState: (state: 'following' | 'waiting') => enqueue(async () => {
            if (current.kind !== 'follow') return;
            if (state === 'waiting') await restore(true);
            else await takeOver();
        }),
        idle: () => queue,
    };
}
