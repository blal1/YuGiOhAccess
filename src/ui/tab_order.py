class DuelFieldTabOrder:
    def __init__(self):
        self._tab_order_list = []
        self.current_index = 0

    def set_tabable_items(self, tab_order_list=[]):
        if not isinstance(tab_order_list, list):
            raise ValueError("tab_order_list must be a list")
        self._tab_order_list = tab_order_list
        self.current_index = 0

    def resolve_next_tab_order(self):
        # if tab order list is empty, return None
        if not self._tab_order_list:
            return None
        if self.current_index >= len(self._tab_order_list):
            self.current_index = 0
        tab_order = self._tab_order_list[self.current_index]
        self.current_index += 1
        return tab_order
    
    def resolve_previous_tab_order(self):
        # if tab order list is empty, return None
        if not self._tab_order_list:
            return None
        if self.current_index < 0:
            self.current_index = len(self._tab_order_list) - 1
        tab_order = self._tab_order_list[self.current_index]
        self.current_index -= 1
        return tab_order
