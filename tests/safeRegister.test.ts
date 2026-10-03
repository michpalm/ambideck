import { describe, expect, it } from 'vitest';
import { safeRegister } from '../src/safeRegister';

describe('safeRegister', () => {
    it('registers and unregisters', () => {
        let unregistered = false;
        const off = safeRegister(() => ({ unregister: () => (unregistered = true) }), () => {});
        off();
        expect(unregistered).toBe(true);
    });
    it('turns missing or throwing Steam methods into no-ops', () => {
        expect(() => safeRegister(undefined, () => {})()).not.toThrow();
        expect(() => safeRegister(() => { throw new Error('Unknown method'); }, () => {})()).not.toThrow();
    });
});
