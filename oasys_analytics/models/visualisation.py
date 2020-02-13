# ADDING SPINES AND HORIZONTAL LINE
import base64

from odoo import models, fields, api, _
import matplotlib.pyplot as plt
import numpy as np
import urllib
import datetime as dt
import matplotlib.dates as mdates
try:
    from StringIO import StringIO ## for Python 2
except ImportError:
    from io import StringIO ## for Python 3



def bytespdate2num(fmt, encoding='utf-8'):
    strconverter = mdates.strpdate2num(fmt)

    def bytesconverter(b):
        s = b.decode(encoding)
        return strconverter(s)

    return bytesconverter

class Visualisation(models.Model):
    _name = 'oasys.visualisation'
    _description = 'Data Visualisation'

    graph_image = fields.Binary(string='Graph', compute='graph_data')

    @api.multi
    def graph_data(self):

        datasets = ['DJIADM2019',
                    'TAIEXDG2019',
                    'JGBSLDM2019',
                    'JGBMDM2019',
                    'JGBLDM2019',
                    'MOTHEDM2019',
                    'REITDM2019',
                    'TPX30DM2019',
                    'JN400DM2019',
                    'TOPIXMDM2019',
                    'NK225MDH2019',
                    'JGBLMDM2019',
                    'NKVIDG2019',
                    'FTC50DF2019',
                    'TAIEXDF2019',
                    'NKVIDF2019',
                    'NK225MDG2019',
                    'NK225MDF2019',
                    'DJIADH2019']

        for stock in datasets:

            pic_data = StringIO()
            plt.figure()
            ax1 = plt.subplot(212)


            # Unfortunately, Yahoo's API is no longer available
            # feel free to adapt the code to another source, or use this drop-in replacement.
            stock_price_url = 'https://www.quandl.com/api/v3/datasets/OSE/%s.csv?api_key=8BfzK6Jo82TP_mF4CCvz'%(stock)
            source_code = urllib.urlopen(stock_price_url).read().decode()
            stock_data = []
            split_source = source_code.split('\n')
            for line in split_source[1:]:
                split_line = line.split(',')
                if len(split_line) == 9:
                    if 'values' not in line and 'labels' not in line:
                        stock_data.append(line)
            date, open, high, low, last, change, volume, sett_price, open_int = np.genfromtxt(stock_data,
                                                                                              delimiter=',',
                                                                                              unpack=True,
                                                                                              converters={0: bytespdate2num('%Y-%m-%d')})
            col = last
            ax1.plot_date(date, col, '-', label='Price')
            ax1.plot([], [], linewidth=5, label='loss', color='r', alpha=0.5)
            ax1.plot([], [], linewidth=5, label='gain', color='g', alpha=0.5)

            ax1.fill_between(date, col, col[0], where=(col > col[0]), facecolor='g', alpha=0.5)
            ax1.fill_between(date, col, col[0], where=(col < col[0]), facecolor='r', alpha=0.5)

            for label in ax1.xaxis.get_ticklabels():
                label.set_rotation(45)
            ax1.grid(True)  # , color='g', linestyle='-', linewidth=5)
            ax1.xaxis.label.set_color('c')
            ax1.yaxis.label.set_color('r')
            # ax1.set_yticks([26000,28000])
            ax1.margins(0)

            ax1.spines['left'].set_color('c')
            ax1.spines['right'].set_visible(False)
            ax1.spines['top'].set_visible(False)
            ax1.spines['left'].set_linewidth(5)

            ax1.tick_params(axis='x', colors='#f06215')  # attributes to ticks
            ax1.axhline(col[0], color='r', linewidth=5)  # adds horizontal line to mean

            plt.xlabel('Date')
            plt.ylabel('Price')
            plt.title(stock)
            plt.legend()
            plt.subplots_adjust(left=0, bottom=0, right=1.5, top=1.5, wspace=0, hspace=0)
            #plt.show()

            plt.savefig(pic_data, format='png', bbox_inches='tight')
            object = base64.encodestring(pic_data.getvalue())
            print(object)
            try:
                self.env['oasys.visualisation'].create({'graph_image': object})
            except Exception as e:
                raise (_(str(e)))

            if stock == datasets[0]:

                for record in self:
                    record.graph_image =  object
            print(object)

    # for dataset in datasets:
    #     graph_data(dataset)

