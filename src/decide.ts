import { isOnForGame, Settings } from './settings';

export interface Situation {
    appId: string | null; // running game
    suspended: boolean;
    docked: boolean;
    onCharger: boolean;
    artworkAppId: string | null; // game page in view, for artwork mode
}

export const IDLE_SITUATION: Situation = { appId: null, suspended: false, docked: false, onCharger: false, artworkAppId: null };

export type Decision =
    | { kind: 'follow' }
    | { kind: 'artwork'; appId: string }
    | { kind: 'off' }
    | { kind: 'handBack' }
    | { kind: 'pause' };

export function decide(situation: Situation, s: Settings): Decision {
    if (situation.suspended) return { kind: 'pause' };
    if (!s.enabled) return { kind: 'handBack' };
    if (situation.docked && !s.runDocked) return { kind: 'handBack' };
    if (situation.appId !== null) return isOnForGame(s, situation.appId) ? { kind: 'follow' } : { kind: 'handBack' };
    if (s.outside === 'off') return { kind: 'off' };
    if (s.outside === 'artwork' && situation.artworkAppId !== null) return { kind: 'artwork', appId: situation.artworkAppId };
    return { kind: 'handBack' };
}
