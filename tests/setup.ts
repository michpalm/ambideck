import { vi } from 'vitest';

vi.mock('@decky/api', () => ({
    callable: () => async () => null,
    addEventListener: vi.fn((_event: string, listener: unknown) => listener),
    removeEventListener: vi.fn(),
    definePlugin: (fn: () => unknown) => fn,
    toaster: { toast: vi.fn() },
}));
