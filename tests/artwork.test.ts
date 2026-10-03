import { describe, expect, it } from 'vitest';
import { artworkUrls, artworkZones } from '../src/artwork';
import { quadFrame } from '../src/colour';

const S = { layout: 'corners' as const, brightness: 100, boost: 0, speed: 'balanced' as const };

describe('artworkZones', () => {
    it('uses the first image that loads', async () => {
        const tried: string[] = [];
        const zones = await artworkZones('9', S, {
            urls: (id) => [`a/${id}`, `b/${id}`],
            load: async (url) => {
                tried.push(url);
                return url.startsWith('b/')
                    ? { data: quadFrame(16, 8, [[255, 0, 0], [255, 0, 0], [255, 0, 0], [255, 0, 0]], 'rgba'), width: 16, height: 8 }
                    : null;
            },
        });
        expect(tried).toEqual(['a/9', 'b/9']);
        expect(zones?.[0][0]).toBeGreaterThan(200);
        expect(zones?.[0][1]).toBe(0);
    });
    it('gives null when nothing loads', async () => {
        expect(await artworkZones('9', S, { urls: () => ['x'], load: async () => null })).toBeNull();
    });
});

describe('artworkUrls', () => {
    it('prefers the hero image, then header and capsule, from Steam stores', () => {
        const stores = {
            details: (id: number) => (id === 292030 ? { libraryAssets: { strHeroImage: 'h/library_hero.jpg' } } : undefined),
            overview: (id: number) => (id === 292030 ? { header_filename: 'x/library_header.jpg', library_capsule_filename: 'y/library_capsule.jpg' } : undefined),
        };
        expect(artworkUrls('292030', stores)).toEqual([
            'https://steamloopback.host/assets/292030/h/library_hero.jpg',
            'https://steamloopback.host/assets/292030/x/library_header.jpg',
            'https://steamloopback.host/assets/292030/y/library_capsule.jpg',
        ]);
        expect(artworkUrls('5', stores)).toEqual([]);
    });
    it('survives stores that throw', () => {
        expect(artworkUrls('1', { details: () => { throw new Error('x'); }, overview: () => undefined })).toEqual([]);
    });
});
