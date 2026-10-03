import { useSyncExternalStore } from 'react';
import { backendKv, KvBackend } from './backend';
import type { FollowSettings, Layout, Outside, Speed } from './types';

export interface Settings {
    enabled: boolean;
    layout: Layout;
    brightness: number; // 10–100
    boost: number; // 0–100
    speed: Speed;
    outside: Outside;
    runDocked: boolean;
    perGame: Record<string, boolean>; // only games switched off are stored
}

export const DEFAULTS: Settings = {
    enabled: true, layout: 'corners', brightness: 70, boost: 58, speed: 'balanced', outside: 'normal',
    runDocked: false, perGame: {},
};

const KEY = 'settings';
const clamp = (v: unknown, low: number, high: number, fallback: number) =>
    typeof v === 'number' && Number.isFinite(v) ? Math.round(Math.max(low, Math.min(high, v))) : fallback;
const oneOf = <T extends string>(v: unknown, options: readonly T[], fallback: T): T =>
    options.includes(v as T) ? (v as T) : fallback;

export function sanitize(raw: unknown): Settings {
    const r = (raw && typeof raw === 'object' ? raw : {}) as Record<string, unknown>;
    const perGame: Record<string, boolean> = {};
    if (r.perGame && typeof r.perGame === 'object') {
        for (const [id, on] of Object.entries(r.perGame as Record<string, unknown>)) {
            if (on === false) perGame[id] = false;
        }
    }
    return {
        enabled: typeof r.enabled === 'boolean' ? r.enabled : DEFAULTS.enabled,
        layout: oneOf(r.layout, ['corners', 'sides'] as const, DEFAULTS.layout),
        brightness: clamp(r.brightness, 10, 100, DEFAULTS.brightness),
        boost: clamp(r.boost, 0, 100, DEFAULTS.boost),
        speed: oneOf(r.speed, ['smooth', 'balanced', 'fast'] as const, DEFAULTS.speed),
        outside: oneOf(r.outside, ['off', 'normal', 'artwork'] as const, DEFAULTS.outside),
        runDocked: typeof r.runDocked === 'boolean' ? r.runDocked : DEFAULTS.runDocked,
        perGame,
    };
}

export function createSettingsStore(kv: KvBackend) {
    let current: Settings = DEFAULTS;
    const listeners = new Set<() => void>();
    const commit = async (next: Settings) => {
        current = next;
        listeners.forEach((listener) => listener());
        await kv.set(KEY, current);
    };
    return {
        async load(): Promise<void> {
            current = sanitize(await kv.get(KEY));
            listeners.forEach((listener) => listener());
        },
        get: (): Settings => current,
        update: (patch: Partial<Omit<Settings, 'perGame'>>) => commit(sanitize({ ...current, ...patch })),
        setGame(appId: string, on: boolean): Promise<void> {
            const perGame = { ...current.perGame };
            if (on) delete perGame[appId];
            else perGame[appId] = false;
            return commit({ ...current, perGame });
        },
        subscribe(listener: () => void): () => void {
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
    };
}

export const settings = createSettingsStore(backendKv);

export function useSettings(): Settings {
    return useSyncExternalStore(settings.subscribe, settings.get);
}

export function followSettings(s: Settings): FollowSettings {
    return { layout: s.layout, brightness: s.brightness, boost: s.boost, speed: s.speed };
}

export function isOnForGame(s: Settings, appId: string): boolean {
    return s.perGame[appId] !== false;
}
