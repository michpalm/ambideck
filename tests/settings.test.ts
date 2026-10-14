import { describe, expect, it } from 'vitest';
import { memoryKv } from '../src/backend';
import { createSettingsStore, DEFAULTS, followSettings, isOnForGame, sanitize } from '../src/settings';

describe('sanitize', () => {
    it('fills defaults and rejects bad values', () => {
        expect(sanitize(null)).toEqual(DEFAULTS);
        expect(sanitize({ layout: 'sides', brightness: 5, boost: 120, speed: 'nope', outside: 'off', perGame: { 1: false, 2: 'x' } }))
            .toEqual({ ...DEFAULTS, layout: 'sides', brightness: 10, boost: 100, outside: 'off', perGame: { 1: false } });
    });
    it('defaults Dark scenes to Glow, also for 1.0 settings', () => {
        expect(sanitize({ outside: 'artwork' })).toMatchObject({ outside: 'follow', dark: 'glow' });
        expect(sanitize({ dark: 'off' }).dark).toBe('off');
        expect(sanitize({ dark: 'dim' }).dark).toBe('glow');
        expect(followSettings({ ...DEFAULTS, dark: 'off' }).dark).toBe('off');
    });
    it('turns a saved Artwork choice into Follow', () => {
        expect(sanitize({ outside: 'artwork' }).outside).toBe('follow');
        expect(sanitize({ outside: 'follow' }).outside).toBe('follow');
        expect(sanitize({ outside: 'nonsense' }).outside).toBe('normal');
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
        expect(followSettings(DEFAULTS)).toEqual({ layout: 'corners', brightness: 70, boost: 58, speed: 'balanced', dark: 'glow' });
    });
});
