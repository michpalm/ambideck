import type { KvBackend } from './backend';

/** Updates come from the GitHub releases of the public repo; Decky's own installer does the install. */
export const RELEASES_URL = 'https://api.github.com/repos/michpalm/ambideck/releases/latest';
export const CHECK_EVERY_MS = 24 * 60 * 60 * 1000;
const KEY = 'updateCheck';
const ASSET = 'ambideck.zip';

export interface Release {
    version: string;
    url: string | null; // ambideck.zip, if the release has it
    sha256: string | null; // from GitHub's asset digest; Decky checks the download against it
}

export type UpdateState =
    | { kind: 'idle' }
    | { kind: 'checking' }
    | { kind: 'upToDate'; version: string }
    | { kind: 'available'; release: Release }
    | { kind: 'checkFailed' }
    | { kind: 'installFailed'; release: Release };

export interface UpdaterDeps {
    fetchLatest(): Promise<unknown>;
    currentVersion(): Promise<string>;
    install(release: Release): Promise<void>;
    kv: KvBackend;
    now(): number;
}

interface Cached {
    at: number;
    release: Release | null;
}

const record = (v: unknown): Record<string, unknown> | null =>
    v && typeof v === 'object' ? (v as Record<string, unknown>) : null;

export function parseRelease(json: unknown): Release | null {
    const r = record(json);
    if (!r || typeof r.tag_name !== 'string') return null;
    const assets = Array.isArray(r.assets) ? r.assets.map(record) : [];
    const zip = assets.find((a) => a?.name === ASSET);
    const url = typeof zip?.browser_download_url === 'string' ? zip.browser_download_url : null;
    const digest = typeof zip?.digest === 'string' ? /^sha256:([0-9a-f]{64})$/i.exec(zip.digest) : null;
    return { version: r.tag_name.replace(/^v/, ''), url, sha256: url && digest ? digest[1].toLowerCase() : null };
}

const parts = (v: string) => (/^\d+\.\d+\.\d+$/.test(v) ? v.split('.').map(Number) : null);

export function isNewer(latest: string, current: string): boolean {
    const a = parts(latest);
    const b = parts(current);
    if (!a || !b) return false;
    for (let i = 0; i < 3; i++) {
        if (a[i] !== b[i]) return a[i] > b[i];
    }
    return false;
}

const isCached = (v: unknown): v is Cached => {
    const c = record(v);
    return !!c && typeof c.at === 'number' && (c.release === null || typeof record(c.release)?.version === 'string');
};

export function createUpdater(deps: UpdaterDeps) {
    let state: UpdateState = { kind: 'idle' };
    const listeners = new Set<() => void>();
    const set = (next: UpdateState) => {
        state = next;
        listeners.forEach((listener) => listener());
    };

    const fetchAndStore = async (): Promise<Release | null> => {
        const release = parseRelease(await deps.fetchLatest());
        await deps.kv.set(KEY, { at: deps.now(), release } satisfies Cached);
        return release;
    };
    const offer = (release: Release | null, current: string): boolean => {
        if (release && isNewer(release.version, current)) {
            set({ kind: 'available', release });
            return true;
        }
        return false;
    };

    return {
        get: (): UpdateState => state,
        subscribe(listener: () => void): () => void {
            listeners.add(listener);
            return () => listeners.delete(listener);
        },
        /** Quiet: only ever shows an available update. */
        async checkOnStart(): Promise<void> {
            try {
                const current = await deps.currentVersion();
                const cached = await deps.kv.get(KEY);
                const release = isCached(cached) && deps.now() - cached.at < CHECK_EVERY_MS
                    ? cached.release
                    : await fetchAndStore();
                offer(release, current);
            } catch (error) {
                console.warn('[ambideck] update check failed', error);
            }
        },
        async checkNow(): Promise<void> {
            set({ kind: 'checking' });
            try {
                const current = await deps.currentVersion();
                if (!offer(await fetchAndStore(), current)) set({ kind: 'upToDate', version: current });
            } catch (error) {
                console.warn('[ambideck] update check failed', error);
                set({ kind: 'checkFailed' });
            }
        },
        async install(): Promise<void> {
            if (state.kind !== 'available' && state.kind !== 'installFailed') return;
            const { release } = state;
            if (!release.url || !release.sha256) return;
            try {
                await deps.install(release);
            } catch (error) {
                console.error('[ambideck] could not start the update', error);
                set({ kind: 'installFailed', release });
            }
        },
    };
}

/** The panel's line for each state; null shows nothing. */
export function updateLabel(state: UpdateState): string | null {
    switch (state.kind) {
        case 'available':
            return state.release.url && state.release.sha256
                ? `Update to ${state.release.version}`
                : `Version ${state.release.version} is available on GitHub`;
        case 'upToDate':
            return `Up to date (${state.version})`;
        case 'checkFailed':
            return "Couldn't check for updates";
        case 'installFailed':
            return "Couldn't start the update";
        default:
            return null;
    }
}
