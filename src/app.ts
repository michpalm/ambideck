import { addEventListener, removeEventListener } from '@decky/api';
import { useSyncExternalStore } from 'react';
import { backend, backendKv } from './backend';
import { LOG_PREFIX } from './constants';
import { createController } from './controller';
import { decide } from './decide';
import { createHueSync } from './huesync/bridge';
import { loaderTransport } from './huesync/transport';
import { retry } from './retry';
import { createUpdater, Release, RELEASES_URL } from './updater';
import { followSettings, settings } from './settings';
import { createSituation } from './situation';
import { steamSituationDeps } from './steamSources';

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

interface DeckyWindow {
    DeckyBackend: { call(route: string, ...args: unknown[]): Promise<unknown> };
}

const DECKY_INSTALL_TYPE_UPDATE = 2;

export const updater = createUpdater({
    fetchLatest: async () => {
        const response = await fetch(RELEASES_URL, { headers: { Accept: 'application/vnd.github+json' } });
        if (!response.ok) throw new Error(`GitHub answered ${response.status}`);
        return response.json();
    },
    currentVersion: () => backend.getVersion(),
    // Decky downloads the zip, checks the hash and asks the user to confirm.
    install: async (r: Release) => {
        await (window as unknown as DeckyWindow).DeckyBackend.call('utilities/install_plugin', r.url, 'Ambideck',
            r.version, r.sha256, DECKY_INSTALL_TYPE_UPDATE);
    },
    kv: backendKv,
    now: () => Date.now(),
});

export const useUpdate = () => useSyncExternalStore(updater.subscribe, updater.get);
export const useSituation = () => useSyncExternalStore(situation.subscribe, situation.get);
export const useSupported = () => useSyncExternalStore(supportStore.subscribe, supportStore.get);

export function startAmbideck() {
    const controller = createController({
        backend,
        hueSync: createHueSync(loaderTransport),
        later: (fn, ms) => {
            const id = setTimeout(fn, ms);
            return () => clearTimeout(id);
        },
    });
    let lastCharger = situation.get().onCharger;
    let running = false;
    let stopped = false;
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
        const status = await retry(() => backend.getStatus(), 3, 1000);
        if (stopped) return;
        supported = status.supported;
        supportListeners.forEach((listener) => listener());
        if (!status.supported) return;
        await settings.load();
        if (stopped) return;
        situation.start();
        running = true;
        run();
        void updater.checkOnStart();
        console.log(`${LOG_PREFIX} started`);
    })().catch((error) => console.error(`${LOG_PREFIX} failed to start`, error));

    return {
        async stop() {
            stopped = true;
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
