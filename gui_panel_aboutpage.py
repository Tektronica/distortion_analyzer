import wx
import wx.adv
import wx.html
import webbrowser


class wxHTML(wx.html.HtmlWindow):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())


class AboutTab(wx.Panel):
    def __init__(self, frame):
        wx.Panel.__init__(self, frame, wx.ID_ANY)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.html = wx.html.HtmlWindow(self, -1, size=(1013, 533), style=wx.html.HW_SCROLLBAR_AUTO | wx.TE_READONLY)

        self.html.LoadPage("about.html")

        self.sizer.Add(self.html, 1, wx.EXPAND)

        self.SetSizer(self.sizer)
        self.Fit()
