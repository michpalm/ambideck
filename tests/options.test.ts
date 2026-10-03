import { describe, expect, it } from 'vitest';
import { boostLabel, LAYOUT_OPTIONS, OUTSIDE_OPTIONS, SPEED_OPTIONS } from '../src/components/options';

describe('options', () => {
    it('lists every value once with a label', () => {
        expect(LAYOUT_OPTIONS.map((o) => o.data)).toEqual(['corners', 'sides']);
        expect(SPEED_OPTIONS.map((o) => o.data)).toEqual(['smooth', 'balanced', 'fast']);
        expect(OUTSIDE_OPTIONS.map((o) => o.label)).toEqual(['Off', 'Normal colour', 'Artwork']);
    });
    it('names the colour boost', () => {
        expect(boostLabel(0)).toBe('Natural');
        expect(boostLabel(58)).toBe('Vivid');
        expect(boostLabel(100)).toBe('Very vivid');
    });
});
