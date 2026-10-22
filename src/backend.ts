import { callable } from '@decky/api';
import type { FollowSettings, Zones } from './types';

export interface LightStatus {
    supported: boolean;
    deviceName?: string | null;
    deviceLayout?: 'corners' | 'sides' | 'shared' | null;
    hueSync?: boolean;
    unavailableReason?: string | null;
}

export interface Status extends LightStatus {
    docked: boolean;
    onCharger: boolean;
    capturing: boolean;
}

export const backend = {
    getStatus: callable<[], Status>('get_status'),
    getVersion: callable<[], string>('get_version'),
    follow: callable<[settings: FollowSettings], void>('follow'),
    show: callable<[zones: Zones], void>('show'),
    rainbow: callable<[keepFollowing?: boolean], void>('rainbow'),
    fallback: callable<[keepFollowing?: boolean], void>('fallback'),
    off: callable<[], void>('off'),
    stop: callable<[], void>('stop'),
};

export type Backend = Pick<typeof backend, 'follow' | 'show' | 'rainbow' | 'fallback' | 'off' | 'stop'>;

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
