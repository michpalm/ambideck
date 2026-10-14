import { definePlugin } from '@decky/api';
import { staticClasses } from '@decky/ui';
import { FaLightbulb } from 'react-icons/fa';
import { startAmbideck } from './app';
import { SettingsPanel } from './components/SettingsPanel';
import { UpdateSection } from './components/UpdateSection';
import { LOG_PREFIX, PLUGIN_NAME } from './constants';

export default definePlugin(() => {
    const app = startAmbideck();
    console.log(`${LOG_PREFIX} loaded`);
    return {
        name: PLUGIN_NAME,
        titleView: <div className={staticClasses.Title}>{PLUGIN_NAME}</div>,
        content: (
            <>
                <SettingsPanel />
                <UpdateSection />
            </>
        ),
        icon: <FaLightbulb />,
        onDismount() {
            void app.stop();
            console.log(`${LOG_PREFIX} unloaded`);
        },
    };
});
