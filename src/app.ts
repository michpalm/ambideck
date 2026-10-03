import { addEventListener, removeEventListener } from '@decky/api';
import { useSyncExternalStore } from 'react';
import { backend } from './backend';
import { LOG_PREFIX } from './constants';
import { createController } from './controller';
import { decide } from './decide';
import { createHueSync } from './huesync/bridge';
import { loaderTransport } from './huesync/transport';
import { followSettings, settings } from './settings';
import { createSituation } from './situation';
import { steamSituationDeps } from './steamSources';
import type { FollowSettings, Zones } from './types';

export const situation = createSituation(steamSituationDeps());

let supported: boolean | null = null;
const supportListeners = new Set<() => void>();
export const supportStore = {
    get: () => supported,
    subscribe(listener: () => void) {
        supportListeners.add(listener);
        return () => supportListeners.delete(listener);
    },
};

export const useSituation = () => useSyncExternalStore(situation.subscribe, situation.get);
export const useSupported = () => useSyncExternalStore(supportStore.subscribe, supportStore.get);

/** Artwork mode lands in Task 13; until then there is no artwork and the controller hands back. */
let artworkSource: (appId: string, s: FollowSettings) => Promise<Zones | null> = async () => null;
export const setArtworkSource = (fn: typeof artworkSource) => (artworkSource = fn);

export function startAmbideck() {
    const controller = createController({
        backend,
        hueSync: createHueSync(loaderTransport),
        artwork: (appId, s) => artworkSource(appId, s),
        later: (fn, ms) => {
            const id = setTimeout(fn, ms);
            return () => clearTimeout(id);
        },
    });
    let lastCharger = situation.get().onCharger;
    let running = false;
    const run = () => {
        if (!running) return;
        const s = settings.get();
        const sit = situation.get();
        void controller.apply(decide(sit, s), followSettings(s), { appId: sit.appId, onCharger: sit.onCharger });
    };
    const unsubscribe = [
        situation.subscribe(() => {
            const charger = situation.get().onCharger;
            if (charger !== lastCharger) {
                lastCharger = charger;
                void controller.chargerChanged();
            }
            run();
        }),
        settings.subscribe(run),
    ];
    const onFollowState = addEventListener<[string]>('follow_state', (state) => {
        if (state === 'following' || state === 'waiting') void controller.followState(state);
    });

    (async () => {
        const status = await backend.getStatus();
        supported = status.supported;
        supportListeners.forEach((listener) => listener());
        if (!status.supported) return;
        await settings.load();
        situation.start();
        running = true;
        run();
        console.log(`${LOG_PREFIX} started`);
    })().catch((error) => console.error(`${LOG_PREFIX} failed to start`, error));

    return {
        async stop() {
            running = false;
            unsubscribe.forEach((u) => u());
            removeEventListener('follow_state', onFollowState);
            situation.stop();
            const s = settings.get();
            const sit = situation.get();
            await controller.apply({ kind: 'handBack' }, followSettings(s), { appId: sit.appId, onCharger: sit.onCharger });
        },
    };
}
