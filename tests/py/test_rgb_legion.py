import pytest
from ambideck.rgb.legion import legion_reports, LegionLights
from ambideck.rgb.model import DeviceInfo

def test_go_uses_independent_sides_and_reloads_for_old_firmware():
    reps = legion_reports('go', 'show', ((1, 2, 3), (4, 5, 6)), True)
    assert [r.hex() for r in reps] == ['050c720103010102033f000301', '050c720104010405063f000301',
                                     '05067302030301', '05067302040301', '05067002030101', '05067002040101']
    assert len(legion_reports('go', 'show', ((1, 2, 3), (4, 5, 6)), False)) == 6
    assert [r.hex() for r in legion_reports('go', 'off', (), False)] == ['05067002030001', '05067002040001']

def test_go_s_has_its_own_shared_protocol_and_native_rainbow():
    assert [r.hex() for r in legion_reports('go_s', 'show', ((1, 2, 3),), True)] == [
        '040601', '100203', '1005000102033f3f']
    assert legion_reports('go_s', 'rainbow', (), True)[-1].hex() == '1005020000003f3f'
    assert legion_reports('go_s', 'off', (), False) == [bytes.fromhex('040600')]

def test_failed_initialization_is_not_remembered_as_success():
    class Transport:
        def __init__(self): self.sent = []; self.fail = True
        def write(self, report):
            self.sent.append(report)
            if self.fail and len(self.sent) == 2: raise OSError('lost')
        def close(self): pass
    t = Transport()
    d = LegionLights(t, DeviceInfo('Go', 'sides', 10, True), 'go')
    with pytest.raises(OSError): d.show(((1, 2, 3),) * 4)
    t.sent.clear(); t.fail = False
    d.show(((1, 2, 3),) * 4)
    assert len(t.sent) == 6
    t.sent.clear(); d.show(((2, 3, 4),) * 4)
    assert len(t.sent) == 6
