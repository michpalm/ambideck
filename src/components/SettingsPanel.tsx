import { DropdownItem, PanelSection, PanelSectionRow, SliderField, ToggleField } from '@decky/ui';
import { useSituation, useSupported } from '../app';
import { isOnForGame, settings, useSettings } from '../settings';
import { boostLabel, LAYOUT_OPTIONS, OUTSIDE_OPTIONS, SPEED_OPTIONS } from './options';

export function SettingsPanel() {
    const s = useSettings();
    const { appId } = useSituation();
    const supported = useSupported();

    if (supported === false) {
        return (
            <PanelSection>
                <PanelSectionRow><div>This device isn't supported</div></PanelSectionRow>
            </PanelSection>
        );
    }

    return (
        <PanelSection>
            <PanelSectionRow>
                <ToggleField label="Ambideck" checked={s.enabled} onChange={(enabled) => settings.update({ enabled })} />
            </PanelSectionRow>
            {appId !== null && (
                <PanelSectionRow>
                    <ToggleField label="In this game" checked={isOnForGame(s, appId)} disabled={!s.enabled}
                        onChange={(on) => settings.setGame(appId, on)} />
                </PanelSectionRow>
            )}
            <PanelSectionRow>
                <DropdownItem label="Layout" rgOptions={LAYOUT_OPTIONS} selectedOption={s.layout}
                    onChange={(o) => settings.update({ layout: o.data })} />
            </PanelSectionRow>
            <PanelSectionRow>
                <SliderField label="Brightness" value={s.brightness} min={10} max={100} step={5} showValue
                    onChange={(brightness) => settings.update({ brightness })} />
            </PanelSectionRow>
            <PanelSectionRow>
                <SliderField label="Colour boost" description={boostLabel(s.boost)} value={s.boost} min={0} max={100}
                    step={5} onChange={(boost) => settings.update({ boost })} />
            </PanelSectionRow>
            <PanelSectionRow>
                <DropdownItem label="Speed" rgOptions={SPEED_OPTIONS} selectedOption={s.speed}
                    onChange={(o) => settings.update({ speed: o.data })} />
            </PanelSectionRow>
            <PanelSectionRow>
                <DropdownItem label="Outside games" rgOptions={OUTSIDE_OPTIONS} selectedOption={s.outside}
                    onChange={(o) => settings.update({ outside: o.data })} />
            </PanelSectionRow>
            <PanelSectionRow>
                <ToggleField label="Run when docked" checked={s.runDocked}
                    onChange={(runDocked) => settings.update({ runDocked })} />
            </PanelSectionRow>
        </PanelSection>
    );
}
