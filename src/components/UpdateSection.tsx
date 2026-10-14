import { ButtonItem, PanelSection, PanelSectionRow } from '@decky/ui';
import { updater, useUpdate } from '../app';
import { updateLabel } from '../updater';

export function UpdateSection() {
    const state = useUpdate();
    const label = updateLabel(state);
    const installable = state.kind === 'available' && !!state.release.url && !!state.release.sha256;
    return (
        <PanelSection title="Updates">
            {label !== null && <PanelSectionRow><div>{label}</div></PanelSectionRow>}
            {installable && (
                <PanelSectionRow>
                    <ButtonItem layout="below" onClick={() => void updater.install()}>Update</ButtonItem>
                </PanelSectionRow>
            )}
            <PanelSectionRow>
                <ButtonItem layout="below" disabled={state.kind === 'checking'} onClick={() => void updater.checkNow()}>
                    Check for updates
                </ButtonItem>
            </PanelSectionRow>
        </PanelSection>
    );
}
