export type Rgb = [number, number, number];
export type Zones = [Rgb, Rgb, Rgb, Rgb]; // left-bottom, left-top, right-top, right-bottom
export type Layout = 'corners' | 'sides';
export type Speed = 'smooth' | 'balanced' | 'fast';
export type Outside = 'off' | 'normal' | 'follow';
export type Dark = 'glow' | 'off';

export interface FollowSettings {
    layout: Layout;
    brightness: number; // 10–100
    boost: number; // 0–100
    speed: Speed;
    dark: Dark;
}
