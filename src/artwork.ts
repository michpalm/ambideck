import { analyseRgba } from './colour';
import type { FollowSettings, Zones } from './types';

export interface ArtworkImage {
    data: Uint8ClampedArray;
    width: number;
    height: number;
}

export interface ArtworkDeps {
    urls(appId: string): string[];
    load(url: string): Promise<ArtworkImage | null>;
}

export interface SteamStores {
    details(appId: number): { libraryAssets?: { strHeroImage?: string } } | undefined;
    overview(appId: number): { header_filename?: string; library_capsule_filename?: string } | undefined;
}

const W = 128;
const H = 72;
const ASSETS = 'https://steamloopback.host/assets';

/** Artwork files live in hashed folders; Steam's stores know the paths (hero first: it is the widest). */
export function artworkUrls(appId: string, stores: SteamStores): string[] {
    const id = Number(appId);
    const paths: (string | undefined)[] = [];
    try {
        paths.push(stores.details(id)?.libraryAssets?.strHeroImage);
    } catch {
        // details not loaded
    }
    try {
        const overview = stores.overview(id);
        paths.push(overview?.header_filename, overview?.library_capsule_filename);
    } catch {
        // no overview
    }
    return paths.filter((p): p is string => typeof p === 'string' && p.length > 0).map((p) => `${ASSETS}/${appId}/${p}`);
}

interface StoreWindow {
    appDetailsStore?: { GetAppDetails?(appId: number): ReturnType<SteamStores['details']> };
    appStore?: { GetAppOverviewByAppID?(appId: number): ReturnType<SteamStores['overview']> };
}

const steamStores: SteamStores = {
    details: (id) => (window as unknown as StoreWindow).appDetailsStore?.GetAppDetails?.(id),
    overview: (id) => (window as unknown as StoreWindow).appStore?.GetAppOverviewByAppID?.(id),
};

export const browserArtwork: ArtworkDeps = {
    urls: (appId) => artworkUrls(appId, steamStores),
    load: (url) => new Promise((resolve) => {
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => {
            try {
                const canvas = document.createElement('canvas');
                canvas.width = W;
                canvas.height = H;
                const ctx = canvas.getContext('2d');
                if (!ctx) return resolve(null);
                ctx.drawImage(img, 0, 0, W, H);
                resolve({ data: ctx.getImageData(0, 0, W, H).data, width: W, height: H });
            } catch {
                resolve(null); // tainted canvas
            }
        };
        img.onerror = () => resolve(null);
        img.src = url;
    }),
};

export async function artworkZones(appId: string, s: FollowSettings, deps: ArtworkDeps = browserArtwork): Promise<Zones | null> {
    for (const url of deps.urls(appId)) {
        const image = await deps.load(url);
        if (image) return analyseRgba(image.data, image.width, image.height, s);
    }
    return null;
}
