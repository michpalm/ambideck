import { describe, expect, it } from 'vitest';
import { createHueSync, HueSyncTransport } from '../src/huesync/bridge';
import { hsvToRgb } from '../src/huesync/hsv';
import { pickSetting, setColorArgs } from '../src/huesync/pick';

const base = {
    enableControl: true, ledEnabled: true, mode: 'rainbow', hue: 0, saturation: 100, brightness: 30,
    hue2: 120, saturation2: 100, brightness2: 100, secondaryZoneHue: 240, secondaryZoneSaturation: 100,
    secondaryZoneBrightness: 50, secondaryZoneEnabled: true, speed: 'medium', brightnessLevel: 'high',
};
const config = {
    perApp: {
        '0': { overwrite: false, acStateOverwrite: true, defaultSetting: base, acSetting: { ...base, mode: 'gradient' } },
        '42': { overwrite: true, acStateOverwrite: false, defaultSetting: { ...base, mode: 'solid', hue: 200 } },
        '7': { overwrite: false, defaultSetting: { ...base, mode: 'pulse' } },
    },
};

describe('hsvToRgb', () => {
    it('matches what HueSync sent for hue 0, saturation 100, brightness 30', () => {
        expect(hsvToRgb(0, 100, 30)).toEqual({ R: 77, G: 0, B: 0 });
    });
    it('covers the colour wheel and wraps', () => {
        expect(hsvToRgb(120, 100, 100)).toEqual({ R: 0, G: 255, B: 0 });
        expect(hsvToRgb(240, 50, 100)).toEqual({ R: 128, G: 128, B: 255 });
        expect(hsvToRgb(360, 100, 100)).toEqual({ R: 255, G: 0, B: 0 });
        expect(hsvToRgb(30, 0, 100)).toEqual({ R: 255, G: 255, B: 255 });
    });
});

describe('pickSetting', () => {
    it('uses the default entry, and its AC setting on the charger', () => {
        expect(pickSetting(config, null, false)?.mode).toBe('rainbow');
        expect(pickSetting(config, null, true)?.mode).toBe('gradient');
    });
    it('uses a game entry only when it overwrites', () => {
        expect(pickSetting(config, '42', true)?.mode).toBe('solid');
        expect(pickSetting(config, '7', false)?.mode).toBe('rainbow');
    });
    it('copes with missing or broken configs', () => {
        expect(pickSetting(null, null, false)).toBeNull();
        expect(pickSetting({ perApp: {} }, '1', false)).toBeNull();
        expect(pickSetting({ perApp: { '0': { overwrite: false } } }, null, false)).toBeNull();
    });
});

describe('setColorArgs', () => {
    it('passes HueSync values through with its own colours', () => {
        expect(setColorArgs(base)).toEqual([
            'rainbow', 77, 0, 0, 0, 255, 0, true, 30, 'medium', 'high',
            { secondary: { R: 0, G: 0, B: 128 } }, { secondary: true },
        ]);
    });
    it('handles HueSync not managing, LEDs off and custom mode', () => {
        expect(setColorArgs({ ...base, enableControl: false })).toBe('fallback');
        expect(setColorArgs({ ...base, ledEnabled: false })).toEqual(
            ['disabled', 0, 0, 0, null, null, null, true, 0, 'medium', 'high', null, null]);
        expect(setColorArgs({ ...base, mode: 'custom' })).toBe('fallback');
    });
});

function fakeTransport(present = true, settings: unknown = config, fail = false) {
    const calls: unknown[][] = [];
    const transport: HueSyncTransport = {
        present: () => present,
        call: async (method, ...args) => {
            calls.push([method, ...args]);
            if (fail) throw new Error('boom');
            return method === 'get_settings' ? settings : true;
        },
    };
    return { transport, calls };
}

describe('createHueSync', () => {
    it('restores the setting HueSync would use now', async () => {
        const { transport, calls } = fakeTransport();
        expect(await createHueSync(transport).restore(null, true)).toBe('restored');
        expect(calls[0]).toEqual(['get_settings']);
        expect(calls[1][0]).toBe('set_color');
        expect(calls[1][1]).toBe('gradient');
    });
    it('pauses HueSync by switching it to disabled', async () => {
        const { transport, calls } = fakeTransport();
        expect(await createHueSync(transport).pause()).toBe(true);
        expect(calls).toEqual([['set_color', 'disabled', 0, 0, 0, null, null, null, true]]);
    });
    it('reports unavailable when HueSync is missing, fails or has nothing usable', async () => {
        expect(await createHueSync(fakeTransport(false).transport).restore(null, false)).toBe('unavailable');
        expect(await createHueSync(fakeTransport(true, config, true).transport).restore(null, false)).toBe('unavailable');
        expect(await createHueSync(fakeTransport(true, { perApp: {} }).transport).restore(null, false)).toBe('unavailable');
        expect(await createHueSync(fakeTransport(false).transport).pause()).toBe(false);
    });
    it('leaves the lights to Ambideck when HueSync is not managing them', async () => {
        const off = { perApp: { '0': { defaultSetting: { ...base, enableControl: false } } } };
        const { transport, calls } = fakeTransport(true, off);
        expect(await createHueSync(transport).restore(null, false)).toBe('unavailable');
        expect(calls).toEqual([['get_settings']]);
    });
});
