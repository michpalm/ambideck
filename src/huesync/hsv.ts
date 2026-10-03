/** Standard HSV → RGB. Hue in degrees, saturation and value 0–100. */
export function hsvToRgb(hue: number, saturation: number, value: number): { R: number; G: number; B: number } {
    const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
    const h = ((((hue % 360) + 360) % 360) / 60);
    const s = clamp01(saturation / 100);
    const v = clamp01(value / 100);
    const c = v * s;
    const x = c * (1 - Math.abs((h % 2) - 1));
    const m = v - c;
    const [r, g, b] =
        h < 1 ? [c, x, 0] : h < 2 ? [x, c, 0] : h < 3 ? [0, c, x] : h < 4 ? [0, x, c] : h < 5 ? [x, 0, c] : [c, 0, x];
    const to8 = (u: number) => Math.round((u + m) * 255);
    return { R: to8(r), G: to8(g), B: to8(b) };
}
