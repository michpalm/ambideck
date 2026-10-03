import { hsvToRgb } from './hsv';

/** The fields of a HueSync light setting that Ambideck reads (from HueSync's get_settings). */
export interface HueSyncSetting {
    enableControl: boolean;
    ledEnabled: boolean;
    mode: string;
    hue: number;
    saturation: number;
    brightness: number;
    hue2: number;
    saturation2: number;
    brightness2: number;
    secondaryZoneHue: number;
    secondaryZoneSaturation: number;
    secondaryZoneBrightness: number;
    secondaryZoneEnabled: boolean;
    speed: string;
    brightnessLevel: string;
}

interface AppEntry {
    overwrite?: boolean;
    acStateOverwrite?: boolean;
    defaultSetting?: Partial<HueSyncSetting>;
    acSetting?: Partial<HueSyncSetting>;
}

export interface HueSyncConfig {
    perApp?: Record<string, AppEntry>;
}

const DEFAULT_APP = '0';

/** The setting HueSync applies now: a game's own entry if it overrides, else the default; AC variant on the charger. */
export function pickSetting(config: unknown, appId: string | null, onCharger: boolean): Partial<HueSyncSetting> | null {
    const perApp = (config as HueSyncConfig | null)?.perApp;
    if (!perApp || typeof perApp !== 'object') return null;
    const own = appId !== null ? perApp[appId] : undefined;
    const entry = own?.overwrite ? own : perApp[DEFAULT_APP];
    if (!entry) return null;
    if (onCharger && entry.acStateOverwrite && entry.acSetting) return entry.acSetting;
    return entry.defaultSetting ?? null;
}

/** Arguments for HueSync's backend set_color, or what to do instead. */
export function setColorArgs(setting: Partial<HueSyncSetting>): unknown[] | 'fallback' {
    if (setting.enableControl === false) return 'fallback'; // HueSync isn't managing the lights: Ambideck's rainbow
    const speed = setting.speed ?? 'low';
    const level = setting.brightnessLevel ?? 'high';
    if (setting.ledEnabled === false) return ['disabled', 0, 0, 0, null, null, null, true, 0, speed, level, null, null];
    const mode = setting.mode ?? 'solid';
    if (mode === 'custom') return 'fallback';
    const brightness = setting.brightness ?? 100;
    const main = hsvToRgb(setting.hue ?? 0, setting.saturation ?? 100, brightness);
    const second = hsvToRgb(setting.hue2 ?? 0, setting.saturation2 ?? 100, setting.brightness2 ?? 100);
    const zone = hsvToRgb(setting.secondaryZoneHue ?? 0, setting.secondaryZoneSaturation ?? 100,
        setting.secondaryZoneBrightness ?? 100);
    return [mode, main.R, main.G, main.B, second.R, second.G, second.B, true, brightness, speed, level,
        { secondary: zone }, { secondary: setting.secondaryZoneEnabled ?? true }];
}
