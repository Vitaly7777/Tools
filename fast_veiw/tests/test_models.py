from core.models import SheetInfo, SheetState

def test_sheet_info_defaults():
    info = SheetInfo("test", 100, 10, True)
    assert info.name == "test"
    assert info.max_row == 100
    assert info.state == SheetState.NOT_STARTED
    assert info.data_cache == []
    assert info.effective_rows == 0
