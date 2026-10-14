import { describe, expect, it } from 'vitest';
import { boostLabel, DARK_OPTIONS, LAYOUT_OPTIONS, OUTSIDE_OPTIONS, SPEED_OPTIONS } from '../src/components/options';

describe('options', () => {
    it('lists every value once with a label', () => {
        expect(LAYOUT_OPTIONS.map((o) => o.data)).toEqual(['corners', 'sides']);
        expect(SPEED_OPTIONS.map((o) => o.data)).toEqual(['smooth', 'balanced', 'fast']);
        expect(OUTSIDE_OPTIONS.map((o) => o.label)).toEqual(['Off', 'Normal colour', 'Follow']);
        expect(OUTSIDE_OPTIONS.map((o) => o.data)).toEqual(['off', 'normal', 'follow']);
        expect(DARK_OPTIONS.map((o) => o.label)).toEqual(['Glow', 'Off']);
        expect(DARK_OPTIONS.map((o) => o.data)).toEqual(['glow', 'off']);
    });
    it('names the colour boost', () => {
        expect(boostLabel(0)).toBe('Natural');
        expect(boostLabel(58)).toBe('Vivid');
        expect(boostLabel(100)).toBe('Very vivid');
    });
});
