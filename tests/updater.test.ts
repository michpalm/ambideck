import { describe, expect, it } from 'vitest';
import { memoryKv } from '../src/backend';
import { CHECK_EVERY_MS, createUpdater, isNewer, parseRelease, Release, updateLabel } from '../src/updater';

const SHA = 'a'.repeat(64);
const ZIP = { name: 'ambideck.zip', browser_download_url: 'https://x/ambideck.zip', digest: `sha256:${SHA}` };
const GH = (tag: string, assets: object[] = [ZIP]) => ({ tag_name: tag, assets });
const HOUR = 60 * 60 * 1000;

function setup(opts: { current?: string; latest?: unknown; fails?: boolean; installFails?: boolean } = {}) {
    const clock = { now: 1_000_000 };
    const calls = { fetch: 0, installed: [] as Release[] };
    const kv = memoryKv();
    const updater = createUpdater({
        fetchLatest: async () => {
            calls.fetch++;
            if (opts.fails) throw new Error('offline');
            return opts.latest ?? GH('v1.2.0');
        },
        currentVersion: async () => opts.current ?? '1.1.0',
        install: async (r) => {
            if (opts.installFails) throw new Error('no route');
            calls.installed.push(r);
        },
        kv,
        now: () => clock.now,
    });
    return { updater, clock, calls, kv };
}

describe('parseRelease', () => {
    it('reads version, zip url and sha256', () => {
        expect(parseRelease(GH('v1.2.0'))).toEqual({ version: '1.2.0', url: 'https://x/ambideck.zip', sha256: SHA });
        expect(parseRelease(GH('1.2.0'))?.version).toBe('1.2.0');
    });
    it('copes with a missing digest, zip or tag', () => {
        expect(parseRelease(GH('v1.2.0', [{ ...ZIP, digest: undefined }]))).toMatchObject({ url: 'https://x/ambideck.zip', sha256: null });
        expect(parseRelease(GH('v1.2.0', [{ ...ZIP, digest: 'sha1:abc' }]))).toMatchObject({ sha256: null });
        expect(parseRelease(GH('v1.2.0', [{ ...ZIP, name: 'other.zip' }]))).toMatchObject({ url: null, sha256: null });
        expect(parseRelease({})).toBeNull();
        expect(parseRelease(null)).toBeNull();
    });
});

describe('isNewer', () => {
    it('compares major.minor.patch numerically', () => {
        expect(isNewer('1.10.0', '1.9.9')).toBe(true);
        expect(isNewer('2.0.0', '1.99.99')).toBe(true);
        expect(isNewer('1.1.0', '1.1.0')).toBe(false);
        expect(isNewer('1.0.9', '1.1.0')).toBe(false);
    });
    it('never treats something unparseable as newer', () => {
        expect(isNewer('1.2.0-beta', '1.1.0')).toBe(false);
        expect(isNewer('2.0', '1.1.0')).toBe(false);
        expect(isNewer('1.2.0', 'dev')).toBe(false);
    });
});

describe('updater', () => {
    it('offers a newer release found at start-up', async () => {
        const { updater } = setup();
        await updater.checkOnStart();
        expect(updater.get()).toEqual({ kind: 'available', release: { version: '1.2.0', url: 'https://x/ambideck.zip', sha256: SHA } });
    });
    it('checks GitHub at most once a day on start', async () => {
        const { updater, clock, calls } = setup();
        await updater.checkOnStart();
        clock.now += 23 * HOUR;
        await updater.checkOnStart();
        expect(calls.fetch).toBe(1);
        expect(updater.get().kind).toBe('available');
        clock.now += 2 * HOUR;
        await updater.checkOnStart();
        expect(calls.fetch).toBe(2);
        expect(CHECK_EVERY_MS).toBe(24 * HOUR);
    });
    it('stays quiet on start when up to date or offline', async () => {
        const upToDate = setup({ latest: GH('v1.1.0') });
        await upToDate.updater.checkOnStart();
        expect(upToDate.updater.get()).toEqual({ kind: 'idle' });
        const offline = setup({ fails: true });
        await offline.updater.checkOnStart();
        expect(offline.updater.get()).toEqual({ kind: 'idle' });
    });
    it('does not offer the version that is now installed', async () => {
        const { updater, calls, kv, clock } = setup({ current: '1.2.0' });
        await kv.set('updateCheck', { at: clock.now, release: { version: '1.2.0', url: 'u', sha256: SHA } });
        await updater.checkOnStart();
        expect(calls.fetch).toBe(0);
        expect(updater.get()).toEqual({ kind: 'idle' });
    });
    it('a manual check says up to date, or that it failed', async () => {
        const ok = setup({ latest: GH('v1.1.0') });
        await ok.updater.checkNow();
        expect(ok.updater.get()).toEqual({ kind: 'upToDate', version: '1.1.0' });
        const failed = setup({ fails: true });
        await failed.updater.checkNow();
        expect(failed.updater.get()).toEqual({ kind: 'checkFailed' });
    });
    it('a manual check always asks GitHub and notifies while checking', async () => {
        const { updater, calls } = setup();
        await updater.checkOnStart();
        const seen: string[] = [];
        updater.subscribe(() => seen.push(updater.get().kind));
        await updater.checkNow();
        expect(calls.fetch).toBe(2);
        expect(seen).toEqual(['checking', 'available']);
    });
    it('install hands the release to the installer; a failure is shown', async () => {
        const ok = setup();
        await ok.updater.checkOnStart();
        await ok.updater.install();
        expect(ok.calls.installed.map((r) => r.version)).toEqual(['1.2.0']);
        const bad = setup({ installFails: true });
        await bad.updater.checkOnStart();
        await bad.updater.install();
        expect(bad.updater.get()).toMatchObject({ kind: 'installFailed', release: { version: '1.2.0' } });
    });
    it('install does nothing without a verifiable zip', async () => {
        const { updater, calls } = setup({ latest: GH('v1.2.0', [{ ...ZIP, digest: undefined }]) });
        await updater.checkOnStart();
        await updater.install();
        expect(calls.installed).toEqual([]);
    });
});

describe('updateLabel', () => {
    it('labels each state with the panel copy', () => {
        const r = { version: '1.2.0', url: 'u', sha256: 's' };
        expect(updateLabel({ kind: 'available', release: r })).toBe('Update to 1.2.0');
        expect(updateLabel({ kind: 'available', release: { ...r, sha256: null } })).toBe('Version 1.2.0 is available on GitHub');
        expect(updateLabel({ kind: 'available', release: { ...r, url: null } })).toBe('Version 1.2.0 is available on GitHub');
        expect(updateLabel({ kind: 'upToDate', version: '1.1.0' })).toBe('Up to date (1.1.0)');
        expect(updateLabel({ kind: 'checkFailed' })).toBe("Couldn't check for updates");
        expect(updateLabel({ kind: 'installFailed', release: r })).toBe("Couldn't start the update");
        expect(updateLabel({ kind: 'checking' })).toBeNull();
        expect(updateLabel({ kind: 'idle' })).toBeNull();
    });
});

