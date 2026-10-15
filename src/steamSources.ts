import { addEventListener, removeEventListener } from '@decky/api';
import { Router } from '@decky/ui';
import { backend } from './backend';
import { Register, safeRegister } from './safeRegister';
import type { SituationDeps } from './situation';

interface SteamWindow {
    SteamClient?: {
        System?: Record<string, Register | undefined>;
        User?: Record<string, Register | undefined>;
    };
}

const steam = () => (window as unknown as SteamWindow).SteamClient;

/** The first of these Steam events that exists and works; null if none does (some Steam builds). */
const firstWorking = (names: [scope: 'System' | 'User', name: string][], cb: () => void): (() => void) | null => {
    for (const [scope, name] of names) {
        const target = steam()?.[scope];
        const fn = target?.[name];
        if (typeof fn !== 'function') continue;
        let works = true;
        const stop = safeRegister((inner) => {
            try {
                return fn.call(target, inner);
            } catch (error) {
                works = false;
                throw error;
            }
        }, cb);
        if (works) return stop;
    }
    return null;
};

const backendEvent = (event: string, cb: (value: boolean) => void) => {
    const listener = addEventListener<[boolean]>(event, cb);
    return () => removeEventListener(event, listener);
};

export function steamSituationDeps(): SituationDeps {
    return {
        runningAppId: () => (Router.MainRunningApp?.appid ? String(Router.MainRunningApp.appid) : null),
        onSuspend: (cb) => firstWorking([['System', 'RegisterForOnSuspendRequest'], ['User', 'RegisterForPrepareForSystemSuspendProgress']], cb),
        onResume: (cb) => firstWorking([['System', 'RegisterForOnResumeFromSuspend'], ['User', 'RegisterForResumeSuspendedGamesProgress']], cb),
        // Steam's battery event throws on some builds; the backend reads the charger from the system instead.
        onCharger: (cb) => backendEvent('charger_changed', cb),
        onDocked: (cb) => backendEvent('docked_changed', cb),
        onCapture: (cb) => backendEvent('capture_lock', cb),
        initialStatus: async () => {
            const { docked, onCharger, capturing } = await backend.getStatus();
            return { docked, onCharger, capturing };
        },
        every: (fn, ms) => {
            const id = setInterval(fn, ms);
            return () => clearInterval(id);
        },
    };
}
