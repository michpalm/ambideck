import { describe, expect, it } from 'vitest';
import { decide, IDLE_SITUATION, Situation } from '../src/decide';
import { DEFAULTS, Settings } from '../src/settings';

const sit = (patch: Partial<Situation>): Situation => ({ ...IDLE_SITUATION, ...patch });
const set = (patch: Partial<Settings>): Settings => ({ ...DEFAULTS, ...patch });

describe('decide', () => {
    it('follows the screen in a game', () => {
        expect(decide(sit({ appId: '1' }), set({}))).toEqual({ kind: 'follow' });
    });
    it('hands back when off, off for this game, or docked without permission', () => {
        expect(decide(sit({ appId: '1' }), set({ enabled: false }))).toEqual({ kind: 'handBack' });
        expect(decide(sit({ appId: '1' }), set({ perGame: { 1: false } }))).toEqual({ kind: 'handBack' });
        expect(decide(sit({ appId: '1', docked: true }), set({}))).toEqual({ kind: 'handBack' });
        expect(decide(sit({ appId: '1', docked: true }), set({ runDocked: true }))).toEqual({ kind: 'follow' });
    });
    it('pauses while asleep, whatever else is true', () => {
        expect(decide(sit({ appId: '1', suspended: true }), set({}))).toEqual({ kind: 'pause' });
        expect(decide(sit({ suspended: true }), set({ enabled: false }))).toEqual({ kind: 'pause' });
    });
    it('follows the outside-games choice', () => {
        expect(decide(sit({}), set({}))).toEqual({ kind: 'handBack' });
        expect(decide(sit({}), set({ outside: 'off' }))).toEqual({ kind: 'off' });
        expect(decide(sit({}), set({ outside: 'artwork' }))).toEqual({ kind: 'handBack' });
        expect(decide(sit({ artworkAppId: '9' }), set({ outside: 'artwork' }))).toEqual({ kind: 'artwork', appId: '9' });
        expect(decide(sit({ artworkAppId: '9', docked: true }), set({ outside: 'artwork' }))).toEqual({ kind: 'handBack' });
    });
});
