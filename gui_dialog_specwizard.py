import wx
import re
import operator
from decimal import Decimal


# def split_into_triplets(s):
#     if s:
#         l = s[:3]
#         yield l
#         yield from split_into_triplets(s[3:])
#
#
# def to_eng_string(s):
#     print(float(s))
#     new_string = ''
#     if 'e' in s:
#         new_string = s
#     elif int(float(s)) == 0:
#         s_split = s.split('.')
#         s_list = list(split_into_triplets(s_split[1]))
#         for idx, group in enumerate(s_list):
#             if int(group) > 0:
#                 lop = str(int(group)) + '.' + s_split[1][3 * (idx + 1):]
#                 new_string = lop + f'e-{3 * (idx + 1)}'
#                 break
#     else:
#         new_string = Decimal(s).to_eng_string()
#     return new_string


def find_order(val, order=0):
    if int(val) == 0:
        order += 1
        return find_order(1000 * val, order)
    else:
        return f'{val}e-{order*3}'

def to_eng_string(s):
    if int(float(s)) == 0:
        new_string = find_order(float(s))
    else:
        new_string = Decimal(s).to_eng_string()
    return new_string


class SpecParser(object):
    def __init__(self):
        self.text_reading = ''
        self.text_range = ''
        self.text_spec = ''
        self.prefix = {'c': 1e-2,
                       '%': 1e-2,
                       'm': 1e-3,
                       'u': 1e-6,
                       'μ': 1e-6,
                       'n': 1e-9,
                       'p': 1e-12,
                       'f': 1e-15,
                       'a': 1e-18,
                       'z': 1e-21,
                       'y': 1e-24}
        self.uncertainty = {'ppm': 1e-6,
                            'PPM': 1e-6,
                            '%': 1e-2}
        self.units = ['s', 'm', 'kg', 'A', 'K', 'mol', 'cd', 'V', 'Ω', 'ohm', 'J']
        self.opn = {"+": operator.add,
                    "-": operator.sub,
                    "*": operator.mul,
                    "/": operator.truediv,
                    "^": operator.pow}

    def find_multiplier(self, val):
        # val could equal '12mA', '1.2mA' '12', '12PPM', '12 ppm'
        string_val, unit = tuple(filter(None, re.split(r'(-?\d*\.?\d+)', val)))
        val = 0.0
        if unit in self.units:
            val = 1.0
        elif unit in self.uncertainty.keys():
            val = self.uncertainty[unit]
        elif unit[0] in self.prefix.keys():
            val = self.prefix[unit[0]]
        else:
            print('ERROR: invalid string: units are not recognized.')
        return val * float(string_val)

    def eval_units(self, op):
        # op could equal ['range', 12PPM], ['reading': 12%], [12mA], or [12m]...
        # https://stackoverflow.com/a/3340115/3382269
        spec_type, spec_val = op[0], op[1]
        spec = list(filter(None, re.split(r'(-?\d*\.?\d+)', spec_val)))
        s = 0

        if spec[1] == '%' or spec[1] in ['PPM', 'ppm']:
            # (X of value + Y of range + Z)
            if spec_type == 'X':
                s = self.find_multiplier(spec_val) * self.find_multiplier(self.text_reading)
            elif spec_type == 'Y':
                s = self.find_multiplier(spec_val) * self.find_multiplier(self.text_range)
            else:
                print('ERROR: something went wrong. Review how spec items are identified (X of value + Y of range + Z)')
        else:
            s = self.find_multiplier(spec_val)
        return s

    def buildStack(self, spec):
        """
        https://stackoverflow.com/a/4998688/3382269
        https://stackoverflow.com/a/2136580/3382269

        stack = [['X', '20ppm'], ['Y', '10ppm'], ['Z', '10uV']]
        """
        ops = ['\+']
        s = [item.strip() for item in re.split(f'({"|".join(ops)})', spec)]
        opStack = []
        stack = []
        spec_item = {0: 'X', 2: 'Y', 4: 'Z'}
        for idx, item in enumerate(s):
            if item in '+-*/':
                opStack.append(item)
            else:
                stack.append([spec_item[idx], item])

        print(stack)
        return stack + opStack[::-1]  # merges opStack in reverse order with stack

    def evaluateStack(self, s):
        # note: operands are pushed onto the stack in reverse order. See .pop()
        op, num_args = s.pop(), 0
        if isinstance(op, list):
            return self.eval_units(op)

        elif op in "+-*/^":
            # note: operands are pushed onto the stack in reverse order
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return self.opn[op](op1, op2)


class SpecWizardDialog(wx.Dialog):
    def __init__(self, parent, *args, **kwds):
        kwds["style"] = kwds.get("style", 0) | wx.DEFAULT_DIALOG_STYLE
        super(SpecWizardDialog, self).__init__(parent, title='Instrument Accuracy Conversion')
        wx.Dialog.__init__(self, *args, **kwds)

        # self.panel = wx.Panel(self, wx.ID_ANY)
        self.SetSize((375, 258))

        self.parser = SpecParser()

        self.panel_4 = wx.Panel(self, wx.ID_ANY)
        self.panel_5 = wx.Panel(self.panel_4, wx.ID_ANY)
        self.text_range = wx.TextCtrl(self.panel_5, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)
        self.text_input = wx.TextCtrl(self.panel_5, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)
        self.panel_6 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.text_spec = wx.TextCtrl(self.panel_6, wx.ID_ANY, "", style=wx.TE_PROCESS_ENTER)
        self.radio_box_1 = wx.RadioBox(self.panel_5, wx.ID_ANY, "",
                                       choices=["PPM", "%", "Value"],
                                       majorDimension=3,
                                       style=wx.RA_SPECIFY_ROWS)
        self.panel_7 = wx.Panel(self.panel_5, wx.ID_ANY)
        self.output_text = wx.TextCtrl(self.panel_7, wx.ID_ANY, "")

        calc_Event = lambda event: self.calc(event)
        self.Bind(wx.EVT_TEXT_ENTER, calc_Event, self.text_range)
        self.Bind(wx.EVT_TEXT_ENTER, calc_Event, self.text_input)
        self.Bind(wx.EVT_TEXT_ENTER, calc_Event, self.text_spec)
        self.Bind(wx.EVT_RADIOBOX, calc_Event, self.radio_box_1)

        self.__set_properties()
        self.__do_layout()

    def __set_properties(self):
        self.SetTitle("Uncertainty Calculator")
        self.SetFocus()
        self.text_range.SetMinSize((70, 23))
        self.text_input.SetMinSize((70, 23))
        self.text_spec.SetMinSize((150, 23))
        self.text_range.SetFont(wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, 0, ""))
        self.text_input.SetFont(wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, 0, ""))
        self.text_spec.SetFont(wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, 0, ""))
        self.radio_box_1.SetSelection(0)

        self.text_range.SetValue('0.1V')
        self.text_input.SetValue('25mV')
        self.text_spec.SetValue('20ppm + 10ppm + 10uV')
        self.calc(0)

    def __do_layout(self):
        sizer_1 = wx.BoxSizer(wx.VERTICAL)
        sizer_2 = wx.BoxSizer(wx.VERTICAL)
        grid_sizer_1 = wx.GridBagSizer(0, 0)
        grid_sizer_3 = wx.GridBagSizer(0, 0)
        grid_sizer_2 = wx.GridBagSizer(0, 0)
        label_1 = wx.StaticText(self.panel_5, wx.ID_ANY, "Absolute Accuracy")
        label_1.SetFont(wx.Font(20, wx.FONTFAMILY_DECORATIVE, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_1.Add(label_1, (0, 0), (1, 3), 0, 0)
        static_line_1 = wx.StaticLine(self.panel_5, wx.ID_ANY)
        static_line_1.SetMinSize((350, 2))
        grid_sizer_1.Add(static_line_1, (1, 0), (1, 3), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 10)
        label_2 = wx.StaticText(self.panel_5, wx.ID_ANY, "Range:")
        grid_sizer_1.Add(label_2, (2, 0), (1, 1), 0, 0)
        label_3 = wx.StaticText(self.panel_5, wx.ID_ANY, "Value")
        grid_sizer_1.Add(label_3, (2, 1), (1, 1), 0, 0)
        label_4 = wx.StaticText(self.panel_5, wx.ID_ANY, "Absolute Accuracy:")
        grid_sizer_1.Add(label_4, (2, 2), (1, 1), 0, 0)
        grid_sizer_1.Add(self.text_range, (3, 0), (1, 1), wx.RIGHT, 10)
        grid_sizer_1.Add(self.text_input, (3, 1), (1, 1), wx.RIGHT, 10)
        label_5 = wx.StaticText(self.panel_6, wx.ID_ANY, u"± (")
        label_5.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_2.Add(label_5, (0, 0), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        grid_sizer_2.Add(self.text_spec, (0, 1), (1, 1), 0, 0)
        label_6 = wx.StaticText(self.panel_6, wx.ID_ANY, u")")
        label_6.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_2.Add(label_6, (0, 2), (1, 1), wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        self.panel_6.SetSizer(grid_sizer_2)
        grid_sizer_1.Add(self.panel_6, (3, 2), (1, 1), wx.EXPAND, 0)
        static_line_2 = wx.StaticLine(self.panel_5, wx.ID_ANY)
        static_line_2.SetMinSize((350, 2))
        grid_sizer_1.Add(static_line_2, (4, 0), (1, 3), wx.ALIGN_CENTER_VERTICAL | wx.BOTTOM | wx.TOP, 10)
        grid_sizer_1.Add(self.radio_box_1, (5, 0), (2, 1), wx.TOP, 5)
        label_7 = wx.StaticText(self.panel_5, wx.ID_ANY, "Uncertainty")
        grid_sizer_1.Add(label_7, (5, 1), (1, 2), wx.TOP, 10)
        label_8 = wx.StaticText(self.panel_7, wx.ID_ANY, u"±")
        label_8.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD, 0, ""))
        grid_sizer_3.Add(label_8, (0, 0), (1, 1), wx.RIGHT, 5)
        grid_sizer_3.Add(self.output_text, (0, 1), (1, 1), 0, 0)
        self.panel_7.SetSizer(grid_sizer_3)
        grid_sizer_1.Add(self.panel_7, (6, 1), (1, 2), wx.EXPAND, 0)
        self.panel_5.SetSizer(grid_sizer_1)
        sizer_2.Add(self.panel_5, 1, wx.ALL | wx.EXPAND, 5)
        self.panel_4.SetSizer(sizer_2)
        sizer_1.Add(self.panel_4, 1, wx.EXPAND, 0)
        self.SetSizer(sizer_1)
        self.Layout()

    def calc(self, e):
        text_spec = self.text_spec.GetValue()
        text_input = self.text_input.GetValue()
        text_range = self.text_range.GetValue()
        output_format = self.radio_box_1.GetStringSelection()
        # print(f'applying spec: {text_spec} to nominal value: {text_input} with output expressed in {output_format}')

        self.parser.text_reading = text_input
        self.parser.text_range = text_range
        stack = self.parser.buildStack(text_spec)
        parsed = self.parser.evaluateStack(stack)

        if output_format == 'PPM':
            output = str(round(parsed / self.parser.find_multiplier(text_input) * 1e6, 2)) + ' PPM'
        elif output_format == '%':
            output = str(round(parsed / self.parser.find_multiplier(text_input) * 100, 5)) + '%'
        else:
            output = self.find_prefix(str(parsed))

        self.output_text.SetValue(output)

    def find_prefix(self, val_string):
        val_string = to_eng_string(val_string)
        print(val_string)
        try:
            val, exponent = val_string.split('e')
        except ValueError:
            val_string = '%.2e' % Decimal(val_string)
            print(val_string)
            val, exponent = val_string.split('e')

        exp = {0: '',
               -3: 'm',
               -6: 'u',
               -9: 'n',
               -12: 'p',
               -15: 'f'}

        r = int(exponent) % 3
        if r < 0:
            s = str(round(float(val), 5)) + f'e-0{r}' + exp[int(exponent) - r]
        else:
            s = str(round(float(val), 5)) + exp[int(exponent) - r]
        return s


########################################################################################################################
class MyApp(wx.App):
    """"""

    # ------------------------------------------------------------------------------------------------------------------
    def OnInit(self):
        dlg = SpecWizardDialog(None, None, wx.ID_ANY, "")
        dlg.ShowModal()
        dlg.Destroy()
        return True


# Run
if __name__ == "__main__":
    app = MyApp(0)