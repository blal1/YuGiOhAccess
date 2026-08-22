from unittest.mock import MagicMock


class FakeControl:
    def __init__(self, parent=None, **kwargs):
        self.parent = parent
        self.kwargs = kwargs
        self.label = kwargs.get("label", "")
        self.value = ""
        self.focused = False

    def SetLabel(self, label):
        self.label = label

    def GetLabel(self):
        return self.label

    def Bind(self, *args, **kwargs):
        pass

    def Show(self):
        pass

    def Destroy(self):
        pass

    def SetFocus(self):
        self.focused = True

    def SetValue(self, value):
        self.value = value

    def GetValue(self):
        return self.value

    def SetSelection(self, *args):
        pass


class FakeNoLabelControl(FakeControl):
    def __init__(self, parent=None, **kwargs):
        if "label" in kwargs:
            raise TypeError("label unsupported")
        super().__init__(parent, **kwargs)


class FakeBlankControl(FakeControl):
    def GetLabel(self):
        return ""


def _base(mocker, rows=2, cols=2):
    from ui.base_ui import BaseUI

    frame = MagicMock()
    frame.sound_effects_audio_manager.play_audio = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.Control", FakeControl)
    mocker.patch("ui.base_ui.wx.StaticText", FakeControl)
    mocker.patch("ui.base_ui.wx.CallLater")
    mocker.patch("ui.base_ui.utils.output")
    ui = BaseUI.__new__(BaseUI)
    ui.name = "UI"
    ui.frame = frame
    ui.parent = frame
    ui.rows = rows
    ui.cols = cols
    ui.repeat_on_boundaries = True
    ui.allow_movement_to_none = True
    ui.sound_scaler_factor = 2
    ui.center_x = (cols - 1) / 2 if cols != 1 else 0
    ui.center_y = (rows - 1) / 2 if rows != 1 else 0
    ui.current_row = 0
    ui.current_col = 0
    ui.cells = [[None for _ in range(cols)] for _ in range(rows)]
    ui.cell_functions = [[None for _ in range(cols)] for _ in range(rows)]
    ui.cell_extras = [[None for _ in range(cols)] for _ in range(rows)]
    ui.sound_positions = ui.calculate_sound_positions()
    ui.cell_positions = {}
    ui.sizer = MagicMock()
    ui.Layout = MagicMock()
    ui.Destroy = MagicMock()
    ui.help_text = ""
    return ui


def test_base_set_cell_focus_movement_and_key_handling(mocker):
    from ui.base_ui import BaseUI

    ui = _base(mocker, 2, 2)
    callback = MagicMock()
    c1 = ui.set_cell(0, 0, "First", callback)
    c2 = ui.set_cell(0, 1, FakeControl, None, label="Second")
    c3 = ui.set_cell(1, 0, FakeNoLabelControl, None, label="Stored label")

    assert c1.GetLabel() == "First"
    assert c2.GetLabel() == "Second"
    assert ui.cell_extras[1][0] == "Stored label"
    assert ui.get_cell(0, 0) is c1
    assert "First" in str(ui)
    blank = ui.set_cell(1, 1, FakeBlankControl, None)
    assert ui.get_cell_label(1, 1) == "FakeBlankControl"
    assert "()" not in str(ui)
    other = BaseUI.__new__(BaseUI)
    other.name = "UI"
    assert ui == other

    ui.set_position(0, 0)
    ui.move_focus(1, 0)
    assert ui.current_col == 1
    ui.move_focus(0, 1)
    assert ui.current_row == 1
    ui.current_row = 99
    ui.current_col = 99
    ui.move_focus(0, 1)
    assert (ui.current_row, ui.current_col) == (1, 1)
    ui.set_position_by_name(c1)
    assert (ui.current_row, ui.current_col) == (0, 0)

    event = MagicMock()
    event.GetKeyCode.return_value = 13
    mocker.patch("ui.base_ui.wx.WXK_RETURN", 13)
    ui.on_key_down(event)
    callback.assert_called_once()

    ui.help_text = "Help"
    event.GetKeyCode.return_value = 112
    mocker.patch("ui.base_ui.wx.WXK_F1", 112)
    ui.on_key_down(event)
    from ui.base_ui import utils
    utils.output.assert_called_with("Help")

    ui.on_resize(event)
    event.Skip.assert_called()
    ui.on_focus(event)
    c1.SetFocus()


def test_base_grid_expansion_dynamic_menu_and_status(mocker):
    from ui.base_ui import DynamicVerticalMenu, StatusMessage, StatusMessageWithoutTimelimit

    ui = _base(mocker, 1, 1)
    ui.expand_grid_vertically()
    ui.expand_grid_horizontally()
    assert (ui.rows, ui.cols) == (2, 2)
    assert ui.calculate_sound_position(0, 0) == {"x": -2.0, "y": 2.0}
    assert ui.get_sound_position(0, 0) is None

    dyn = DynamicVerticalMenu.__new__(DynamicVerticalMenu)
    dyn.rows = 0
    dyn.cols = 1
    dyn.cells = []
    dyn.cell_functions = []
    dyn.cell_extras = []
    dyn.index_keys = []
    dyn.index_text_or_functions = {}
    dyn.sound_scaler_factor = 2
    dyn.calculate_sound_positions = MagicMock(return_value={})
    dyn.expand_grid_vertically()
    dyn.append_item(lambda: "computed")
    dyn.on_cell_change(0, 0, 0, 0, "key_1")
    from ui.base_ui import utils
    utils.output.assert_called_with("computed")

    status = StatusMessage.__new__(StatusMessage)
    status.Destroy = MagicMock()
    status.call_after = MagicMock()
    status.hide()
    from ui.base_ui import wx
    wx.CallLater.assert_any_call(100, status.call_after)

    msg = StatusMessageWithoutTimelimit.__new__(StatusMessageWithoutTimelimit)
    msg.rows = 0
    msg.cols = 1
    msg.cells = []
    msg.cell_functions = []
    msg.cell_extras = []
    msg.sound_scaler_factor = 2
    msg.set_cell = MagicMock()
    msg.expand_grid_vertically()
    msg.append_item("Waiting")
    msg.set_cell.assert_called()


def test_base_key_navigation_boundaries_and_fallbacks(mocker):
    ui = _base(mocker, 2, 2)
    ui.set_cell(0, 0, "First", None)
    ui.set_cell(0, 1, "Second", None)
    ui.set_cell(1, 0, "Third", None)
    ui.set_cell(1, 1, "Fourth", None)
    mocker.patch("ui.base_ui.platform.system", return_value="Darwin")

    key_values = {
        "WXK_LEFT": 1,
        "WXK_RIGHT": 2,
        "WXK_UP": 3,
        "WXK_DOWN": 4,
        "WXK_HOME": 5,
        "WXK_END": 6,
        "WXK_F1": 7,
        "WXK_RETURN": 8,
    }
    for name, value in key_values.items():
        mocker.patch(f"ui.base_ui.wx.{name}", value)

    event = MagicMock()
    event.GetKeyCode.return_value = key_values["WXK_RIGHT"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (0, 1)

    event.GetKeyCode.return_value = key_values["WXK_DOWN"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (1, 1)

    event.GetKeyCode.return_value = key_values["WXK_LEFT"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (1, 0)

    event.GetKeyCode.return_value = key_values["WXK_UP"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (0, 0)

    event.GetKeyCode.return_value = key_values["WXK_END"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (0, 0)

    event.GetKeyCode.return_value = key_values["WXK_HOME"]
    ui.on_key_down(event)
    assert (ui.current_row, ui.current_col) == (0, 0)

    event.GetKeyCode.return_value = 999
    ui.on_key_down(event)
    ui.frame.on_key_down.assert_called_with(event)

    ui.help_text = ""
    event.GetKeyCode.return_value = key_values["WXK_F1"]
    ui.on_key_down(event)

    from ui.base_ui import utils
    assert utils.output.call_count >= 1


def test_base_focus_and_invalid_cell_branches(mocker):
    ui = _base(mocker, 1, 1)
    from ui.base_ui import wx

    ui.set_cell(-1, 0, "bad")
    assert ui.cells == [[None]]

    ui.set_cell(0, 0, int, None)
    assert ui.cells == [[None]]

    class BrokenControl(FakeControl):
        def __init__(self, parent=None, **kwargs):
            raise TypeError("broken")

    ui.set_cell(0, 0, BrokenControl, None)
    assert ui.cells == [[None]]

    ui.try_set_focus()
    assert wx.CallLater.call_count == 0

    ui.current_row = 9
    ui.try_set_focus()
    wx.CallLater.assert_called_with(100, ui.try_set_focus)

    ui = _base(mocker, 1, 2)
    ui.allow_movement_to_none = False
    ui.set_cell(0, 0, "Only", None)
    ui.move_focus(1, 0)
    assert (ui.current_row, ui.current_col) == (0, 0)

    vertical = _base(mocker, 3, 1)
    vertical.set_cell(0, 0, "Top", None)
    vertical.set_cell(2, 0, "Bottom", None)
    vertical.move_focus(2, 2)
    assert vertical.current_row == 2
    vertical.move_focus(-2, -2)
    assert vertical.current_row == 0

    horizontal = _base(mocker, 1, 3)
    horizontal.set_cell(0, 0, "Left", None)
    horizontal.set_cell(0, 2, "Right", None)
    horizontal.move_focus(2, 2)
    assert horizontal.current_col == 2
    horizontal.move_focus(-2, -2)
    assert horizontal.current_col == 0


def test_wait_status_and_input_show_paths(mocker):
    from ui.base_ui import InputUI, StatusMessage, WaitUI, wx

    frame = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.CallLater")
    mocker.patch("ui.base_ui.wx.Yield", side_effect=lambda: setattr(input_ui, "running", False))

    status = StatusMessage.__new__(StatusMessage)
    status.time = 3
    status.Destroy = MagicMock()
    status.call_after = MagicMock()
    status.show()
    wx.CallLater.assert_any_call(3000, status.hide)

    input_ui = InputUI.__new__(InputUI)
    input_ui.running = True
    input_ui.return_value = "done"
    input_ui.input_box = FakeControl()
    assert InputUI.show(input_ui) == "done"
    frame.push_ui.assert_called_with(input_ui)

    wait = WaitUI.__new__(WaitUI)
    wait.function = lambda self, value=None: value or "ok"
    wait.args = ("value",)
    wait.kwargs = {}
    wait.hide = MagicMock()
    assert WaitUI.show(wait) == "value"
    wait.hide.assert_called_once()

    wait.function = lambda self, *, value=None: value
    wait.args = ()
    wait.kwargs = {"value": "kw"}
    assert WaitUI.show(wait) == "kw"

    wait.function = lambda self, value, *, suffix: value + suffix
    wait.args = ("a",)
    wait.kwargs = {"suffix": "b"}
    assert WaitUI.show(wait) == "ab"


def test_input_ui_validation_and_number_conversion(mocker):
    from ui.base_ui import InputUI, NumberInputUI

    input_ui = InputUI.__new__(InputUI)
    input_ui.current_row = 0
    input_ui.running = True
    input_ui.regex = r"\d+"
    input_ui.input_box = FakeControl()
    input_ui.input_box.SetValue("abc")
    input_ui.hide = MagicMock()

    event = MagicMock()
    event.GetKeyCode.return_value = 13
    mocker.patch("ui.base_ui.wx.WXK_RETURN", 13)
    mocker.patch("ui.base_ui.utils.output")
    InputUI.on_key_down(input_ui, event)
    assert input_ui.input_box.GetValue() == ""

    input_ui.input_box.SetValue("123")
    InputUI.on_key_down(input_ui, event)
    assert input_ui.return_value == "123"
    assert input_ui.running is False

    input_ui.current_row = 1
    input_ui.running = True
    InputUI.on_key_down(input_ui, event)
    assert input_ui.return_value is None

    number = NumberInputUI.__new__(NumberInputUI)
    mocker.patch("ui.base_ui.InputUI.show", return_value="42")
    assert NumberInputUI.show(number) == 42
    mocker.patch("ui.base_ui.InputUI.show", return_value=None)
    assert NumberInputUI.show(number) is None


def test_base_ui_real_initializers_with_wx_methods_patched(mocker):
    from ui.base_ui import BaseUI, HorizontalMenu, InputUI, StatusMessage, StatusMessageWithoutTimelimit, VerticalMenu, WaitUI

    frame = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.Panel.__init__", return_value=None)
    mocker.patch("ui.base_ui.wx.GridSizer", return_value=MagicMock())
    mocker.patch.object(BaseUI, "SetSizer", MagicMock())
    mocker.patch.object(BaseUI, "Fit", MagicMock())
    mocker.patch.object(BaseUI, "Bind", MagicMock())
    mocker.patch.object(BaseUI, "SetFocus", MagicMock())
    mocker.patch.object(BaseUI, "Layout", MagicMock())
    mocker.patch("ui.base_ui.wx.Control", FakeControl)
    mocker.patch("ui.base_ui.wx.StaticText", FakeControl)
    mocker.patch("ui.base_ui.wx.TextCtrl", FakeControl)
    mocker.patch("ui.base_ui.wx.Gauge", FakeControl)

    ui = BaseUI(1, 1, "Real")
    assert ui.name == "Real"
    assert ui.center_x == 0
    assert ui.center_y == 0

    vertical = VerticalMenu("Vertical")
    vertical.append_item("Item")
    assert vertical.rows == 1

    horizontal = HorizontalMenu("Horizontal")
    horizontal.append_item("Item", lambda: None)
    assert horizontal.cols == 1

    status = StatusMessage("Status", lambda: None, time=1)
    assert status.time == 1

    timeless = StatusMessageWithoutTimelimit("Wait")
    assert timeless.rows == 1

    wait = WaitUI("Loading", lambda self: "ok")
    assert wait.progress == 0
    wait.progress = 50
    assert wait.progress == 50

    input_ui = InputUI("Prompt", default_value="abc")
    assert input_ui.input_box.GetValue() == "abc"
