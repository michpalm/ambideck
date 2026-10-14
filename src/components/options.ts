import type { Dark, Layout, Outside, Speed } from '../types';

export const LAYOUT_OPTIONS: { data: Layout; label: string }[] = [
    { data: 'corners', label: 'Corners' },
    { data: 'sides', label: 'Sides' },
];
export const SPEED_OPTIONS: { data: Speed; label: string }[] = [
    { data: 'smooth', label: 'Smooth' },
    { data: 'balanced', label: 'Balanced' },
    { data: 'fast', label: 'Fast' },
];
export const OUTSIDE_OPTIONS: { data: Outside; label: string }[] = [
    { data: 'off', label: 'Off' },
    { data: 'normal', label: 'Normal colour' },
    { data: 'follow', label: 'Follow' },
];
export const DARK_OPTIONS: { data: Dark; label: string }[] = [
    { data: 'glow', label: 'Glow' },
    { data: 'off', label: 'Off' },
];

export function boostLabel(boost: number): string {
    if (boost < 20) return 'Natural';
    if (boost < 45) return 'Lively';
    if (boost < 80) return 'Vivid';
    return 'Very vivid';
}
