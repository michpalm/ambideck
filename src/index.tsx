import { definePlugin } from '@decky/api';
import { staticClasses } from '@decky/ui';
import { FaLightbulb } from 'react-icons/fa';
import { setArtworkSource, startAmbideck } from './app';
import { artworkZones } from './artwork';
import { SettingsPanel } from './components/SettingsPanel';
import { LOG_PREFIX, PLUGIN_NAME } from './constants';

export default definePlugin(() => {
    setArtworkSource((appId, s) => artworkZones(appId, s));
    const app = startAmbideck();
    console.log(`${LOG_PREFIX} loaded`);
    return {
        name: PLUGIN_NAME,
        titleView: <div className={staticClasses.Title}>{PLUGIN_NAME}</div>,
        content: <SettingsPanel />,
        icon: <FaLightbulb />,
        onDismount() {
            void app.stop();
            console.log(`${LOG_PREFIX} unloaded`);
        },
    };
});
