import { callable } from '@decky/api';
import type { FollowSettings, Zones } from './types';

export interface Status {
    supported: boolean;
    docked: boolean;
    onCharger: boolean;
}

export const backend = {
    getStatus: callable<[], Status>('get_status'),
    follow: callable<[settings: FollowSettings], void>('follow'),
    show: callable<[zones: Zones], void>('show'),
    rainbow: callable<[keepFollowing?: boolean], void>('rainbow'),
    off: callable<[], void>('off'),
    stop: callable<[], void>('stop'),
};

export type Backend = Pick<typeof backend, 'follow' | 'show' | 'rainbow' | 'off' | 'stop'>;

export interface KvBackend {
    get(key: string): Promise<unknown>;
    set(key: string, value: unknown): Promise<void>;
}

const kvGet = callable<[key: string], unknown>('kv_get');
const kvSet = callable<[key: string, value: unknown], void>('kv_set');

export const backendKv: KvBackend = { get: (key) => kvGet(key), set: (key, value) => kvSet(key, value) };

export function memoryKv(): KvBackend {
    const map = new Map<string, unknown>();
    return {
        async get(key) {
            return map.has(key) ? map.get(key) : null;
        },
        async set(key, value) {
            map.set(key, value);
        },
    };
}
