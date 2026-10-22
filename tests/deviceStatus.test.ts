import { expect, it } from 'vitest';
import { createDeviceStatus, deviceDescription } from '../src/deviceStatus';

it('deduplicates status events while publishing availability changes', () => {
    const store = createDeviceStatus(null);
    let changes = 0;
    const remove = store.subscribe(() => changes++);
    store.update({ supported: false, unavailableReason: 'Disconnected' });
    store.update({ unavailableReason: 'Disconnected', supported: false });
    expect(changes).toBe(1);
    store.update({ supported: true, deviceName: 'Claw', deviceLayout: 'shared', hueSync: false });
    expect(changes).toBe(2);
    expect(store.get()?.supported).toBe(true);
    expect(deviceDescription(store.get())).toBe('Claw · One shared colour');
    remove(); store.update({ supported: false });
    expect(changes).toBe(2);
});

it('explains the actual zone capability without changing the sampling layout', () => {
    expect(deviceDescription({ supported: true, deviceName: 'Ally', deviceLayout: 'corners' })).toBe('Ally · Four zones');
    expect(deviceDescription({ supported: true, deviceName: 'Go', deviceLayout: 'sides' })).toBe('Go · Left and right colours');
    expect(deviceDescription(null)).toBe('');
});
