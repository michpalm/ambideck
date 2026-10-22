import type { LightStatus } from './backend';

export function createDeviceStatus(initial: LightStatus | null) {
    let status = initial;
    const listeners = new Set<() => void>();
    return {
        get: () => status,
        subscribe(listener: () => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
        update(next: LightStatus): boolean {
            const value: LightStatus = {
                supported: next.supported, deviceName: next.deviceName, deviceLayout: next.deviceLayout,
                hueSync: next.hueSync, unavailableReason: next.unavailableReason,
            };
            if (JSON.stringify(value) === JSON.stringify(status)) return false;
            status = value;
            listeners.forEach(fn => fn());
            return true;
        },
    };
}

export function deviceDescription(status: LightStatus | null): string {
    if (!status?.deviceName) return '';
    const layout = status.deviceLayout && {
        corners: 'Four zones', sides: 'Left and right colours', shared: 'One shared colour',
    }[status.deviceLayout];
    return layout ? `${status.deviceName} · ${layout}` : status.deviceName;
}
