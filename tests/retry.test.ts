import { describe, expect, it } from 'vitest';
import { retry } from '../src/retry';

describe('retry', () => {
    it('retries until it works, then gives up with the last error', async () => {
        const waits: number[] = [];
        const sleep = async (ms: number) => void waits.push(ms);
        let n = 0;
        await expect(retry(async () => {
            if (++n < 3) throw new Error(`no ${n}`);
            return n;
        }, 3, 1000, sleep)).resolves.toBe(3);
        expect(waits).toEqual([1000, 1000]);
        await expect(retry(async () => {
            throw new Error('down');
        }, 3, 1000, sleep)).rejects.toThrow('down');
    });
});
