import logging

import wx

logger = logging.getLogger(__name__)

class YuGiOhAccessAPP(wx.App):
    def OnInit(self):
        logger.info("Initializing app")
        wx.App.OnInit(self)
        logger.info("App initialized")
        return True