import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { analyseFrame, analyseRgba, quadFrame, toLed } from '../src/colour';
import type { Layout, Rgb } from '../src/types';

interface Vector {
    name: string; width: number; height: number; quads: Rgb[]; layout: Layout; boost: number; brightness: number;
    targets: number[][]; frameLevel: number; leds: Rgb[];
}
const vectors: Vector[] = JSON.parse(readFileSync(new URL('./vectors/colour.json', import.meta.url), 'utf8'));

describe('colour maths matches the Python backend', () => {
    for (const v of vectors) {
        it(v.name, () => {
            for (const order of ['bgrx', 'rgba'] as const) {
                const frame = quadFrame(v.width, v.height, v.quads, order);
                const a = analyseFrame(frame, v.width, v.height, v.width * 4, order, v.layout, v.boost, v.brightness);
                a.targets.forEach((t, i) => t.forEach((c, j) => expect(c).toBeCloseTo(v.targets[i][j], 8)));
                expect(a.frameLevel).toBeCloseTo(v.frameLevel, 8);
                a.targets.map(toLed).forEach((led, i) => led.forEach((c, j) => expect(Math.abs(c - v.leds[i][j])).toBeLessThanOrEqual(1)));
            }
        });
    }
    it('analyseRgba gives LED zones', () => {
        const v = vectors[0];
        const zones = analyseRgba(quadFrame(v.width, v.height, v.quads, 'rgba'), v.width, v.height,
            { layout: v.layout, boost: v.boost, brightness: v.brightness, speed: 'balanced' });
        expect(zones).toHaveLength(4);
    });
});
