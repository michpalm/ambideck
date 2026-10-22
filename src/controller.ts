import type { Backend } from './backend';
import type { Decision } from './decide';
import type { HueSync } from './huesync/bridge';
import type { FollowSettings } from './types';

export interface ControllerDeps {
    backend: Backend;
    hueSync: HueSync;
    canUseHueSync?(): boolean;
    canUseDevice?(): boolean;
    later(fn: () => void, ms: number): () => void; // returns cancel
}

interface Ctx {
    appId: string | null;
    onCharger: boolean;
}

const REPEAT_MS = 1000;
const HAS_LIGHTS = new Set(['follow', 'off']);

export function createController(deps: ControllerDeps) {
    // At start-up HueSync (or nothing) has the lights. 'unknown' after a failed step, so the next decision runs again.
    let current: Decision | { kind: 'unknown' } = { kind: 'handBack' };
    let follow: FollowSettings | null = null;
    let ctx: Ctx = { appId: null, onCharger: false };
    let cancelRepeat: (() => void) | null = null;
    let queue: Promise<void> = Promise.resolve();
    let requested: { decision: Decision; settings: FollowSettings; ctx: Ctx } | null = null;
    const useHueSync = () => deps.canUseHueSync?.() ?? true;
    const hueSyncPresent = () => useHueSync() && deps.hueSync.present();

    const enqueue = (job: () => Promise<void>): Promise<void> => {
        queue = queue.then(job).catch((error) => console.error('[ambideck] controller step failed', error));
        return queue;
    };
    const cancel = () => {
        cancelRepeat?.();
        cancelRepeat = null;
    };
    /** Runs job once more after REPEAT_MS, unless the decision has changed by then. */
    const repeat = (job: () => Promise<unknown>) => {
        cancel();
        const owner = current;
        cancelRepeat = deps.later(() => void enqueue(async () => {
            if (current === owner) await job();
        }), REPEAT_MS);
    };
    const takeOver = async () => {
        if (hueSyncPresent()) await deps.hueSync.pause();
    };
    /** keepFollowing: the stream is only lost for now, so the backend keeps retrying behind the rainbow. */
    const restore = async (keepFollowing = false) => {
        const result = useHueSync() ? await deps.hueSync.restore(ctx.appId, ctx.onCharger) : 'unavailable';
        if (result === 'unavailable') await deps.backend.fallback(keepFollowing);
    };
    const handBack = async () => {
        try {
            await deps.backend.stop();
        } finally {
            await restore();
            if (hueSyncPresent()) repeat(restore);
        }
    };

    async function run(decision: Decision, nextFollow: FollowSettings, nextCtx: Ctx): Promise<void> {
        if (deps.canUseDevice?.() === false) {
            cancel();
            current = { kind: 'unknown' };
            await deps.backend.stop();
            return;
        }
        const previous = current;
        const sameSettings = JSON.stringify(follow) === JSON.stringify(nextFollow);
        if (JSON.stringify(previous) === JSON.stringify(decision) && sameSettings) {
            const appChanged = ctx.appId !== nextCtx.appId;
            ctx = nextCtx;
            // HueSync re-applies its setting when the running app changes, also while Ambideck keeps following.
            if (decision.kind === 'follow' && appChanged) {
                cancel();
                await takeOver();
                if (hueSyncPresent()) repeat(takeOver);
            }
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
                    if (hueSyncPresent()) repeat(takeOver);
                }
                await deps.backend.follow(nextFollow);
                return;
            case 'off':
                cancel();
                await takeOver();
                await deps.backend.off();
                if (hueSyncPresent()) repeat(takeOver);
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
        apply: (decision: Decision, nextFollow: FollowSettings, nextCtx: Ctx) => {
            requested = { decision, settings: nextFollow, ctx: nextCtx };
            return enqueue(() => run(decision, nextFollow, nextCtx));
        },
        refresh: () => enqueue(async () => {
            if (!requested) return;
            cancel();
            current = { kind: 'unknown' };
            await run(requested.decision, requested.settings, requested.ctx);
        }),
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
