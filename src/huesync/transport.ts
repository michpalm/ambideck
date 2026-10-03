import type { HueSyncTransport } from './bridge';

const HUESYNC = 'HueSync';

interface LoaderWindow {
    DeckyPluginLoader?: { hasPlugin?(name: string): boolean };
    DeckyBackend?: { callable?(route: string): (...args: unknown[]) => Promise<unknown> };
}

/** Calls HueSync's backend through Decky's shared router. Never use the loader API's connect("HueSync"): it
 * replaces HueSync's own event listeners. */
export const loaderTransport: HueSyncTransport = {
    present: () => Boolean((window as unknown as LoaderWindow).DeckyPluginLoader?.hasPlugin?.(HUESYNC)),
    call: (method, ...args) => {
        const route = (window as unknown as LoaderWindow).DeckyBackend?.callable?.('loader/call_plugin_method');
        if (!route) return Promise.reject(new Error('Decky backend router not available'));
        return route(HUESYNC, method, ...args);
    },
};
