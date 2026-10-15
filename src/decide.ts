import { isOnForGame, Settings } from './settings';

export interface Situation {
    appId: string | null; // running game
    suspended: boolean;
    docked: boolean;
    onCharger: boolean;
    capturing: boolean; // a screen recorder holds the capture lock
}

export const IDLE_SITUATION: Situation = { appId: null, suspended: false, docked: false, onCharger: false, capturing: false };

export type Decision =
    | { kind: 'follow' }
    | { kind: 'off' }
    | { kind: 'handBack' }
    | { kind: 'pause' };

export function decide(situation: Situation, s: Settings): Decision {
    if (situation.suspended) return { kind: 'pause' };
    if (situation.capturing) return { kind: 'handBack' };
    if (!s.enabled) return { kind: 'handBack' };
    if (situation.docked && !s.runDocked) return { kind: 'handBack' };
    if (situation.appId !== null) return isOnForGame(s, situation.appId) ? { kind: 'follow' } : { kind: 'handBack' };
    if (s.outside === 'off') return { kind: 'off' };
    if (s.outside === 'follow') return { kind: 'follow' };
    return { kind: 'handBack' };
}
