import type { FollowSettings, Layout, Rgb, Zones } from './types';

// Mirrors py_modules/ambideck/colour.py exactly; tests/vectors/colour.json keeps them in step.
export const BASE_WEIGHT = 0.05;
export const MIN_LEVEL = 0.15;
export const GAMMA = 2.2;
export const SAMPLE_STEP = 4;
type Order = 'bgrx' | 'rgba';
const OFFSETS: Record<Order, [number, number, number]> = { bgrx: [2, 1, 0], rgba: [0, 1, 2] };
type Rect = [number, number, number, number];

export const roundHalfUp = (x: number) => Math.floor(x + 0.5);
export const boostFactor = (boost: number) => 1 + (1.2 * Math.max(0, Math.min(100, boost))) / 100;

export function regions(width: number, height: number, layout: Layout): Rect[] {
    const hw = Math.floor(width / 2);
    const hh = Math.floor(height / 2);
    if (layout === 'sides') {
        const left: Rect = [0, 0, hw, height];
        const right: Rect = [hw, 0, width, height];
        return [left, left, right, right];
    }
    return [[0, hh, hw, height], [0, 0, hw, hh], [hw, 0, width, hh], [hw, hh, width, height]];
}

export function regionColour(frame: ArrayLike<number>, stride: number, rect: Rect, step = SAMPLE_STEP, order: Order = 'bgrx'): [number[], number] {
    const [ro, go, bo] = OFFSETS[order];
    const [x0, y0, x1, y1] = rect;
    let sr = 0, sg = 0, sb = 0, sw = 0, level = 0, n = 0;
    for (let y = y0; y < y1; y += step) {
        const row = y * stride;
        for (let x = x0; x < x1; x += step) {
            const i = row + x * 4;
            const r = frame[i + ro], g = frame[i + go], b = frame[i + bo];
            const mx = Math.max(r, g, b);
            const mn = Math.min(r, g, b);
            const w = BASE_WEIGHT + (mx - mn) / 255.0;
            sr += r * w;
            sg += g * w;
            sb += b * w;
            sw += w;
            level += mx;
            n += 1;
        }
    }
    if (n === 0) return [[0, 0, 0], 0];
    return [[sr / sw, sg / sw, sb / sw], level / (255.0 * n)];
}

export function boost(rgb: number[], factor: number): number[] {
    const mx = Math.max(...rgb);
    const mn = Math.min(...rgb);
    if (mx <= 0 || mx === mn) return [...rgb];
    const s = (mx - mn) / mx;
    const k = Math.min(1.0, s * factor) / s;
    return rgb.map((c) => mx - (mx - c) * k);
}

export function zoneTarget(rgb: number[], value: number, brightness: number): number[] {
    const mx = Math.max(...rgb);
    const norm = mx <= 0 ? [1.0, 1.0, 1.0] : rgb.map((c) => c / mx);
    const level = (MIN_LEVEL + (1.0 - MIN_LEVEL) * Math.max(0.0, Math.min(1.0, value))) * brightness;
    return norm.map((c) => c * level);
}

export function analyseFrame(frame: ArrayLike<number>, width: number, height: number, stride: number, order: Order,
    layout: Layout, boostValue: number, brightness: number): { targets: number[][]; frameLevel: number } {
    const cache = new Map<string, [number[], number]>();
    const factor = boostFactor(boostValue);
    const targets: number[][] = [];
    for (const rect of regions(width, height, layout)) {
        const key = rect.join(',');
        if (!cache.has(key)) cache.set(key, regionColour(frame, stride, rect, SAMPLE_STEP, order));
        const [rgb, value] = cache.get(key)!;
        targets.push(zoneTarget(boost(rgb, factor), value, brightness / 100.0));
    }
    const values = [...cache.values()].map(([, value]) => value);
    return { targets, frameLevel: values.reduce((a, b) => a + b, 0) / values.length };
}

export function toLed(target: number[]): Rgb {
    const [r, g, b] = target.map((c) => roundHalfUp(255.0 * Math.pow(Math.max(0.0, Math.min(1.0, c)), GAMMA)));
    return [r, g, b];
}

export function analyseRgba(data: ArrayLike<number>, width: number, height: number, s: FollowSettings): Zones {
    const { targets } = analyseFrame(data, width, height, width * 4, 'rgba', s.layout, s.boost, s.brightness);
    const [a, b, c, d] = targets.map(toLed);
    return [a, b, c, d];
}

export function quadFrame(width: number, height: number, quads: Rgb[], order: Order): Uint8ClampedArray {
    const [ro, go, bo] = OFFSETS[order];
    const [lb, lt, rt, rb] = quads;
    const out = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const top = y < Math.floor(height / 2);
            const left = x < Math.floor(width / 2);
            const [r, g, b] = top ? (left ? lt : rt) : left ? lb : rb;
            const i = (y * width + x) * 4;
            out[i + ro] = r;
            out[i + go] = g;
            out[i + bo] = b;
            out[i + 3] = 255;
        }
    }
    return out;
}
