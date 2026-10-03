import { IDLE_SITUATION, Situation } from './decide';

export interface SituationDeps {
    runningAppId(): string | null;
    currentPath(): string | null;
    onSuspend(cb: () => void): () => void;
    onResume(cb: () => void): () => void;
    onCharger(cb: (onCharger: boolean) => void): () => void;
    onDocked(cb: (docked: boolean) => void): () => void;
    initialStatus(): Promise<{ docked: boolean; onCharger: boolean }>;
    every(fn: () => void, ms: number): () => void;
}

const POLL_MS = 250;

export function artworkFromPath(path: string | null): string | null {
    const match = /^\/library\/app\/(\d+)/.exec(path ?? '');
    return match ? match[1] : null;
}

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
    return {
        get: (): Situation => current,
        subscribe(listener: () => void): () => void {
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
        start(): void {
            const poll = () => set({ appId: deps.runningAppId(), artworkAppId: artworkFromPath(deps.currentPath()) });
            poll();
            // A source Steam doesn't support must not take the others down with it.
            const sources: (() => () => void)[] = [
                () => deps.every(poll, POLL_MS),
                () => deps.onSuspend(() => set({ suspended: true })),
                () => deps.onResume(() => set({ suspended: false })),
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
