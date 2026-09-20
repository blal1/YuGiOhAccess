import logging
from concurrent.futures import ThreadPoolExecutor
import re
import platform
from core.i18n import _

import wx

from core import utils

logger = logging.getLogger(__name__)
class BaseUI(wx.Panel):
    def __init__(self, rows, cols, name="Game Area", repeat_on_boundaries=True, allow_movement_to_none=True):
        super(BaseUI, self).__init__(wx.GetTopLevelWindows()[0], style=wx.WANTS_CHARS, name=name)
        self.name = name
        self.frame = wx.GetTopLevelWindows()[0]
        self.parent = self.frame
        self.rows = rows
        self.cols = cols
        self.repeat_on_boundaries = repeat_on_boundaries
        self.allow_movement_to_none = allow_movement_to_none
        self.sound_scaler_factor = 2
        self.center_x, self.center_y = (cols-1)/2, (rows-1)/2
        if self.cols == 1:
            self.center_x = 0
        if self.rows == 1:
            self.center_y = 0
        self.sizer = wx.GridSizer(rows, cols, 2, 2)  # Adjust spacing as needed
        self.SetSizer(self.sizer)
        self.sound_positions = self.calculate_sound_positions()
        self.current_row = 0  # Track the current row
        self.current_col = 0  # Track the current column
        self.return_value = None
        self.cells = [[None for _unused in range(cols)] for _unused in range(rows)]
        self.cell_functions = [[None for _unused in range(cols)] for _unused in range(rows)]
        self.cell_extras = [[None for _unused in range(cols)] for _unused in range(rows)] # extra data for the cells in the case where labels aren't available on the native control
        self.help_text = ""
        self.Fit()
        self.Bind(wx.EVT_SIZE, self.on_resize)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.SetFocus()

    def set_cell(self, row, col, value, function=None, *args, **kwargs):
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            logger.warning(f"Invalid cell position: {row}, {col}")
            return

        if self.cells[row][col]:
            self.cells[row][col].Destroy()

        added_control = None
        if isinstance(value, str):
            # make a button with the label
            added_control = wx.Control(self, style=wx.WANTS_CHARS)
            added_control.SetLabel(value)
            added_control.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
            self.sizer.Add(added_control)
            added_control.Show()
            self.cells[row][col] = added_control
        elif issubclass(value, wx.Control):
            fallback_label = kwargs.get('label')
            if fallback_label:
                self.cell_extras[row][col] = fallback_label
            if 'style' in kwargs:
                kwargs['style'] |= wx.WANTS_CHARS
            else:
                kwargs['style'] = wx.WANTS_CHARS
            # construct the value with the parent as self
            try:
                added_control = value(self, **kwargs)
                if fallback_label:
                    if hasattr(added_control, "SetName"):
                        added_control.SetName(fallback_label)
                    if hasattr(added_control, "SetToolTip"):
                        added_control.SetToolTip(fallback_label)
            except TypeError as e:
                # if label is not a valid argument, try to construct the control without it
                if 'label' in kwargs:
                    label = kwargs['label']
                    wx.StaticText(self, label=label)
                    del kwargs['label']
                    added_control = value(self, **kwargs)
                    if hasattr(added_control, "SetName"):
                        added_control.SetName(label)
                    if hasattr(added_control, "SetToolTip"):
                        added_control.SetToolTip(label)
                else:
                    logger.error(f"Error constructing control: {e}")
                    return
            added_control.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
            self.sizer.Add(added_control)
            added_control.Show()
            self.cells[row][col] = added_control
        else:
            logger.warning(f"Invalid value type: {value}")

        self.cell_functions[row][col] = function
        self.Layout()
        self.sound_positions = self.calculate_sound_positions()
        return added_control
    
    def get_cell(self, row, col):
        return self.cells[row][col]

    def get_cell_label(self, row, col):
        element = self.cells[row][col]
        label = ""
        if element is not None and hasattr(element, "GetLabel"):
            label = element.GetLabel()
        if not label:
            label = self.cell_extras[row][col]
        if not label and element is not None and hasattr(element, "GetName"):
            label = element.GetName()
        if not label and element is not None:
            label = element.__class__.__name__
        return label or _("Empty item")
    
    def set_position(self, row, col):
        self.current_row = row
        self.current_col = col

    def set_position_by_name(self, name):
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.cells[row][col]
                if cell and cell == name:
                    self.current_row = row
                    self.current_col = col
                    return
 
    def set_return_value(self, value):
        self.return_value = value

    def set_help_text(self, help_text):
        self.help_text = help_text

    def on_focus(self, event):                                                                                         
        self.try_set_focus()                                                                                           
        event.Skip()                                                                                                   

    def try_set_focus(self):
        try:                                                                                                           
            # get the current row and col and set the focus                                                            
            cell = self.cells[self.current_row][self.current_col]
            if not cell:
                return
            cell.SetFocus()                                                                                            
            utils.output(str(self.get_cell_label(self.current_row, self.current_col)))
        except (IndexError, AttributeError):                                                                           
            wx.CallLater(100, self.try_set_focus)                                                                      
                                                                                                                       
 

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            ui = self.cell_functions[self.current_row][self.current_col]
            if ui:
                ui()
            return
        if keycode == wx.WXK_LEFT and (self.cols > 1 or self.repeat_on_boundaries):
            self.move_focus(-1, 0)
        elif keycode == wx.WXK_RIGHT and (self.cols > 1 or self.repeat_on_boundaries):
            self.move_focus(1, 0)
        elif keycode == wx.WXK_UP and (self.rows > 1 or self.repeat_on_boundaries):
            self.move_focus(0, -1)
        elif keycode == wx.WXK_DOWN and (self.rows > 1 or self.repeat_on_boundaries):
            self.move_focus(0, 1)
        elif keycode == wx.WXK_HOME:
            self.move_focus(-2, -2)
        elif keycode == wx.WXK_END:
            self.move_focus(2, 2)
        elif keycode == wx.WXK_F1:
            if not self.help_text:
                return
            utils.output(str(self.help_text))
        else:
            wx.GetTopLevelWindows()[0].on_key_down(event)
        #event.Skip()  # Important to allow other key events to be processed

    def on_resize(self, event):
        self.Layout()
        event.Skip()

    def move_focus(self, dx, dy):
        if self.rows <= 0 or self.cols <= 0:
            return
        self.current_row = min(max(self.current_row, 0), self.rows - 1)
        self.current_col = min(max(self.current_col, 0), self.cols - 1)
        old_row = self.current_row
        old_col = self.current_col
        # go to start of row, if dx and dy is -2 and there's only 1 col (vertical menu)
        if dx == -2 and dy == -2 and self.cols == 1:
            self.current_row = 0
        # go to end of row, if dx and dy is 2 and there's only 1 col (vertical menu)
        elif dx == 2 and dy == 2 and self.cols == 1:
            self.current_row = self.rows - 1
        # go to start of col, if dx and dy is -2 and there's only 1 row (horizontal menu)
        elif dx == -2 and dy == -2 and self.rows == 1:
            self.current_col = 0
        # go to end of col, if dx and dy is 2 and there's only 1 row (horizontal menu)
        elif dx == 2 and dy == 2 and self.rows == 1:
            self.current_col = self.cols - 1
        else:
            new_row = self.current_row + dy
            new_col = self.current_col + dx
            if 0 <= new_row < self.rows and 0 <= new_col < self.cols:
                self.current_row = new_row
                self.current_col = new_col
        if not self.cells[self.current_row][self.current_col] and not self.allow_movement_to_none:
            self.current_row = old_row
            self.current_col = old_col
            return

        # set the focus
        try:
            self.cells[self.current_row][self.current_col].SetFocus()
            # if we are running on MacOS, speak the cell
            if platform.system() == "Darwin":
                cell = self.cells[self.current_row][self.current_col]
                if hasattr(cell, "GetLabel"):
                    label = cell.GetLabel()
                    utils.output(str(label))
        except (IndexError, AttributeError):
            pass
        wx.GetTopLevelWindows()[0].sound_effects_audio_manager.play_audio("click.wav", **self.sound_positions[(self.current_row, self.current_col)])
        cell = self.cells[self.current_row][self.current_col]
        if hasattr(self, "on_cell_change"):
            return self.on_cell_change(old_row, old_col, self.current_row, self.current_col, cell)
        label = self.get_cell_label(self.current_row, self.current_col)
        utils.output(str(label))
 
    def calculate_sound_positions(self):
        sound_positions = {}
        for row in range(self.rows):
            for col in range(self.cols):
                sound_positions[(row, col)] = self.calculate_sound_position(row, col)
        return sound_positions
        
    def calculate_sound_position(self, row, col):
        # Calculate scale factors to fit the grid within the -25 to +25 range
        scale_x = (self.sound_scaler_factor*2) / (self.cols - 1) if self.cols > 1 else 0  # Avoid division by zero
        scale_y = (self.sound_scaler_factor*2) / (self.rows - 1) if self.rows > 1 else 0
        
        x = (col * scale_x) - self.sound_scaler_factor
        # Y coordinate: Transform and then flip (because top left is positive and bottom right is negative in y)
        y = self.sound_scaler_factor - (row * scale_y)

        if self.cols == 1:
            x = 0

        if self.rows == 1:
            y = 0

        return {'x': x, 'y': y}

    def get_sound_position(self, row, col):
        return self.cell_positions.get((row, col), None)
    
    def __str__(self):
        result = f"UI({self.name})\n"
        for row in range(self.rows):
            for col in range(self.cols):
                element = self.cells[row][col]
                label = self.get_cell_label(row, col)
                result += f"({label}) - {self.cell_functions[row][col]})\t"
            result += "\n"
        return result.strip()
    
    def __eq__(self, other):
        return self.name == other.name

    def expand_grid_vertically(self):
        # Increment the number of rows
        self.rows += 1
        # Expand the cells and cell_functions arrays
        self.cells.append([None] * self.cols)
        self.cell_functions.append([None] * self.cols)
        self.cell_extras.append([None] * self.cols)

    def expand_grid_horizontally(self):
        # Increment the number of columns
        self.cols += 1
        # Expand the cells and cell_functions arrays
        for row in range(self.rows):
            self.cells[row].append(None)
            self.cell_functions[row].append(None)
            self.cell_extras[row].append(None)



class WaitUI(BaseUI):
    """A ui that displays a message and runs a function with arguments, kind of like the threading module in Python. It will hide when the function is done."""
    def __init__(self, message, function, *args, **kwargs):
        super(WaitUI, self).__init__(2, 1, name=message)
        self._progress = 0
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.set_cell(0, 0, message, None)
        self.progress_Gauge = self.set_cell(1, 0, wx.Gauge, None, range=101, style=wx.GA_HORIZONTAL)

    def show(self):
        wx.GetTopLevelWindows()[0].push_ui(self)
        with ThreadPoolExecutor() as executor:
            if self.args and   self.kwargs:
                future = executor.submit(self.function, self, *self.args, **self.kwargs)
            elif self.args:
                future = executor.submit(self.function, self, *self.args)
            elif self.kwargs:
                future = executor.submit(self.function, self, **self.kwargs)
            else:
                future = executor.submit(self.function, self)
            while not future.done():
                wx.Yield()
            result = future.result()
        self.hide()
        return result

    def hide(self):
        wx.GetTopLevelWindows()[0].pop_ui()
        try:
            self.Destroy()
        except RuntimeError:
            logger.debug("InputUI was already destroyed by pop_ui")

    @property
    def progress(self):
        return self._progress

    @progress.setter
    def progress(self, value):
        self._progress = value
        self.progress_Gauge.SetValue(value)

class VerticalMenu(BaseUI):
    """This is a vertical menu, that dynamically adds rows as needed."""
    def __init__(self, *args, **kwargs):
        # Initialize with zero rows and one column to reflect no initial items
        super(VerticalMenu, self).__init__(0, 1, *args, **kwargs)
        self.current_col = 0
        self.current_row = 0

    def append_item(self, option, function=None, *args, **kwargs):
        # Check if the grid needs to be expanded (it will always be when self.rows == len(self.cells))
        if self.rows == len(self.cells):
            self.expand_grid_vertically()
        
        # Set the cell for the new row, this time correctly aligned to the current item index
        return self.set_cell(self.rows-1, 0, option, function, args, **kwargs)

class HorizontalMenu(BaseUI):
    """This is a horizontal menu, that dynamically adds columns as needed."""
    def __init__(self, *args, **kwargs):
        # Initialize with zero columns and one row to reflect no initial items
        super(HorizontalMenu, self).__init__(1, 0, *args, **kwargs)
        self.current_col = 0
        self.current_row = 0

    def append_item(self, option, function, **kwargs):
        # Check if the grid needs to be expanded (it will always be when self.cols == len(self.cells[0]))
        if self.cols == len(self.cells[0]):
            self.expand_grid_horizontally()
        
        # Set the cell for the new column, this time correctly aligned to the current item index
        return self.set_cell(0, self.cols - 1, option, function, **kwargs)

class DynamicVerticalMenu(VerticalMenu):
    """This is a vertical menu, that dynamically adds rows as needed, but also allows for a function to be run when a row is selected."""
    def __init__(self, *args, **kwargs):
        super(DynamicVerticalMenu, self).__init__(*args, **kwargs)
        self.index_keys = []
        self.index_text_or_functions = {}

    def set_cell(self, row, col, value, function=None, *args, **kwargs):
        self.cells[row][col] = value
        self.cell_functions[row][col] = function
        self.sound_positions = self.calculate_sound_positions()


    def append_item(self, text_or_function, function=None, *args, **kwargs):
        # Check if the grid needs to be expanded (it will always be when self.rows == len(self.cells))
        if self.rows == len(self.cells):
            self.expand_grid_vertically()
        
        # Set the cell for the new row, this time correctly aligned to the current item index
        new_key = f"key_{self.rows-1}"
        self.index_keys.append(new_key)
        self.index_text_or_functions[new_key] = text_or_function
        return self.set_cell(self.rows-1, 0, str(new_key), function, *args, **kwargs)
    
    def on_cell_change(self, old_row, old_col, new_row, new_col, cell):
        text_or_function = self.index_text_or_functions[cell]
        logger.debug(f"Cell change: {text_or_function}")
        if callable(text_or_function):
            utils.output(str(text_or_function()))
        else:
            utils.output(str(text_or_function))

class StatusMessage(BaseUI):
    """A status message that will hide after a certain amount of time (in seconds)."""
    def __init__(self, message, call_after, time=2):
        super(StatusMessage, self).__init__(1, 1, message)
        self.time = time
        self.set_cell(0, 0, message, self.hide)
        self.call_after = call_after

    def show(self):
        wx.GetTopLevelWindows()[0].push_ui(self)
        wx.CallLater(self.time * 1000, self.hide)

    def hide(self, *args, **kwargs):
        wx.GetTopLevelWindows()[0].pop_ui()
        wx.CallLater(100, self.call_after)
        try:
            self.Destroy()
        except RuntimeError:
            pass

class StatusMessageWithoutTimelimit(VerticalMenu):
    """A status message that will shown, until it's pupped from the ui stack"""
    def __init__(self, message):
        super(StatusMessageWithoutTimelimit, self).__init__(message)
        self.append_item(str(message))


class InputUI(BaseUI):
    """Make an input ui that takes input and returns it, if it matches a regex, default is everything."""
    def __init__(self, message, regex=".*", default_value=""):
        super(InputUI, self).__init__(2, 1, message, False)
        self.running = True
        self.input_box = self.set_cell(0, 0, wx.TextCtrl, None, label=message, style=wx.TE_PROCESS_ENTER)
        self.input_box = self.set_cell(0, 0, wx.TextCtrl, None, label=message, style=wx.TE_PROCESS_ENTER)
        self.input_box.SetValue(default_value)
        # if default value is not empty, select all the text
        if default_value:
            self.input_box.SetSelection(-1, -1)
        self.set_cell(1, 0, "back", self.hide)
        self.regex = regex
        self.return_value = None

    def show(self):
        wx.GetTopLevelWindows()[0].push_ui(self)
        # set focus to the input box
        self.input_box.SetFocus()
        # run a loop and wait until the return value is set, similar to the wait ui
        while self.running:
            wx.Yield()
        return self.return_value

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            # if the thing pressed is back, hide the ui
            if self.current_row == 1: # back
                self.return_value = None
                self.running = False
                self.hide()
                return
            value = self.input_box.GetValue()
            if re.match(self.regex, value):
                self.return_value = value
                self.running = False
                self.hide()
            else:
                utils.output(_("Invalid input"))
                self.input_box.SetValue("")
        else:
            super(InputUI, self).on_key_down(event)

    def hide(self):
        wx.GetTopLevelWindows()[0].pop_ui()
        self.Destroy()


class CallbackInputUI(BaseUI):
    """A text prompt that hands its answer to a callback instead of blocking.

    InputUI.show() spins wx.Yield() until the user answers. That is fine in a
    menu, but during a duel the server keeps sending messages, their handlers
    push their own screens onto the same UI stack while that loop runs, and the
    prompt ends up hidden behind one of them with a loop that never finishes.
    The duel screen then answers nothing but the menu bar.

    This version owns no loop: it lives on the stack like any other screen and
    removes itself by identity when it is done.
    """

    def __init__(self, message, on_done, regex=".*", default_value=""):
        super(CallbackInputUI, self).__init__(2, 1, message, False)
        self.on_done = on_done
        self.regex = regex
        self.input_box = self.set_cell(0, 0, wx.TextCtrl, None, label=message, style=wx.TE_PROCESS_ENTER)
        self.input_box.SetValue(default_value)
        if default_value:
            self.input_box.SetSelection(-1, -1)
        self.set_cell(1, 0, _("Cancel"), self.cancel)

    def show(self):
        wx.GetTopLevelWindows()[0].push_ui(self)
        self.input_box.SetFocus()
        return self

    def _finish(self, value):
        callback = self.on_done
        self.on_done = None
        wx.GetTopLevelWindows()[0].remove_ui(self)
        if callback:
            callback(value)

    def cancel(self):
        self._finish(None)

    def submit(self):
        value = self.input_box.GetValue()
        if not re.match(self.regex, value):
            utils.output(_("Invalid input"))
            self.input_box.SetValue("")
            return
        self._finish(value)

    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_RETURN:
            if self.current_row == 1:
                self.cancel()
            else:
                self.submit()
            return
        if keycode == wx.WXK_ESCAPE:
            self.cancel()
            return
        super(CallbackInputUI, self).on_key_down(event)


class NumberInputUI(InputUI):
    def __init__(self, message):
        super(NumberInputUI, self).__init__(message, r"\d+")

    def show(self):
        result = super(NumberInputUI, self).show()
        if not result:
            return None
        return int(result)
