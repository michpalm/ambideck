import { describe, expect, it } from 'vitest';
import { LOG_PREFIX, PLUGIN_NAME } from '../src/constants';

describe('constants', () => {
    it('names the plugin', () => {
        expect(PLUGIN_NAME).toBe('Ambideck');
        expect(LOG_PREFIX).toBe('[ambideck]');
    });
});
