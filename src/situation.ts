import { IDLE_SITUATION, Situation } from './decide';

export interface SituationDeps {
    runningAppId(): string | null;
    /** null: this Steam build has no such event. */
    onSuspend(cb: () => void): (() => void) | null;
    onResume(cb: () => void): (() => void) | null;
    onCharger(cb: (onCharger: boolean) => void): () => void;
    onDocked(cb: (docked: boolean) => void): () => void;
    initialStatus(): Promise<{ docked: boolean; onCharger: boolean }>;
    every(fn: () => void, ms: number): () => void;
}

const POLL_MS = 250;

export function createSituation(deps: SituationDeps) {
    let current: Situation = IDLE_SITUATION;
    const listeners = new Set<() => void>();
    let stops: (() => void)[] = [];
    const set = (patch: Partial<Situation>) => {
        const next = { ...current, ...patch };
        if ((Object.keys(next) as (keyof Situation)[]).every((key) => next[key] === current[key])) return;
        current = next;
        listeners.forEach((listener) => listener());
    };
    /** Sleep without wake would pin 'pause', so both register or neither does. */
    const sleepAndWake = (): (() => void) => {
        let active = false;
        const attempt = (register: () => (() => void) | null) => {
            try {
                return register();
            } catch {
                return null;
            }
        };
        const stopSuspend = attempt(() => deps.onSuspend(() => active && set({ suspended: true })));
        const stopResume = attempt(() => deps.onResume(() => active && set({ suspended: false })));
        if (stopSuspend === null || stopResume === null) {
            stopSuspend?.();
            stopResume?.();
            throw new Error('sleep or wake events unavailable');
        }
        active = true;
        return () => {
            active = false;
            stopSuspend();
            stopResume();
        };
    };
    return {
        get: (): Situation => current,
        subscribe(listener: () => void): () => void {
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
        start(): void {
            const poll = () => set({ appId: deps.runningAppId() });
            poll();
            // A source Steam doesn't support must not take the others down with it.
            const sources: (() => () => void)[] = [
                () => deps.every(poll, POLL_MS),
                () => sleepAndWake(),
                () => deps.onCharger((onCharger) => set({ onCharger })),
                () => deps.onDocked((docked) => set({ docked })),
            ];
            stops = [];
            for (const source of sources) {
                try {
                    stops.push(source());
                } catch (error) {
                    console.warn('[ambideck] a situation source is unavailable', error);
                }
            }
            deps.initialStatus().then(({ docked, onCharger }) => set({ docked, onCharger }), () => {});
        },
        stop(): void {
            stops.forEach((stop) => stop());
            stops = [];
        },
    };
}
