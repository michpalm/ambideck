import { describe, expect, it } from 'vitest';
import { memoryKv } from '../src/backend';
import { createSettingsStore, DEFAULTS, followSettings, isOnForGame, sanitize } from '../src/settings';

describe('sanitize', () => {
    it('fills defaults and rejects bad values', () => {
        expect(sanitize(null)).toEqual(DEFAULTS);
        expect(sanitize({ layout: 'sides', brightness: 5, boost: 120, speed: 'nope', outside: 'artwork', perGame: { 1: false, 2: 'x' } }))
            .toEqual({ ...DEFAULTS, layout: 'sides', brightness: 10, boost: 100, outside: 'artwork', perGame: { 1: false } });
    });
});

describe('settings store', () => {
    it('loads, updates, remembers games and notifies', async () => {
        const kv = memoryKv();
        const store = createSettingsStore(kv);
        let calls = 0;
        store.subscribe(() => calls++);
        await store.load();
        await store.update({ brightness: 40 });
        await store.setGame('730', false);
        expect(store.get().brightness).toBe(40);
        expect(isOnForGame(store.get(), '730')).toBe(false);
        await store.setGame('730', true);
        expect(store.get().perGame).toEqual({});
        expect(calls).toBe(4);
        const again = createSettingsStore(kv);
        await again.load();
        expect(again.get().brightness).toBe(40);
    });
    it('extracts what the backend needs', () => {
        expect(followSettings(DEFAULTS)).toEqual({ layout: 'corners', brightness: 70, boost: 58, speed: 'balanced' });
    });
});
