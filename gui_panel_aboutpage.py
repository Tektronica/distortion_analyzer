import wx
import wx.adv
import wx.html2
import webbrowser


class wxHTML(wx.html2.WebView):
    def OnLinkClicked(self, link):
        webbrowser.open(link.GetHref())


class AboutTab(wx.Panel):
    def __init__(self, frame):
        wx.Panel.__init__(self, frame, wx.ID_ANY)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.html = wx.html2.WebView.New(self)
        # self.html = wx.html2.WebView(self, -1, size=(1013, 533), style=wx.html2.HW_SCROLLBAR_AUTO | wx.TE_READONLY)

        self.html.LoadURL("C:\\Users\\rholle\\Documents\\Python Projects\\distortion_analyzer\\about.html")

        self.sizer.Add(self.html, 1, wx.EXPAND)

        self.SetSizer(self.sizer)
        self.Fit()
