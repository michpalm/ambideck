import { pickSetting, setColorArgs } from './pick';

export interface HueSyncTransport {
    present(): boolean;
    call(method: string, ...args: unknown[]): Promise<unknown>;
}

export type RestoreResult = 'restored' | 'unavailable';

export interface HueSync {
    present(): boolean;
    pause(): Promise<boolean>;
    restore(appId: string | null, onCharger: boolean): Promise<RestoreResult>;
}

export function createHueSync(transport: HueSyncTransport): HueSync {
    const present = () => {
        try {
            return transport.present();
        } catch {
            return false;
        }
    };
    return {
        present,
        async pause() {
            if (!present()) return false;
            try {
                await transport.call('set_color', 'disabled', 0, 0, 0, null, null, null, true);
                return true;
            } catch {
                return false;
            }
        },
        async restore(appId, onCharger) {
            if (!present()) return 'unavailable';
            try {
                const setting = pickSetting(await transport.call('get_settings'), appId, onCharger);
                if (!setting) return 'unavailable';
                const args = setColorArgs(setting);
                if (args === 'fallback') return 'unavailable';
                const ok = await transport.call('set_color', ...args);
                return ok === false ? 'unavailable' : 'restored';
            } catch {
                return 'unavailable';
            }
        },
    };
}
