#!/usr/bin/env python3

from argparse import ArgumentParser, RawTextHelpFormatter
import cbpro
from collections import deque as dq
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style


# parse command line arguments provided to the script
parser = ArgumentParser(description='Monitor prices of cryptocurrencies', formatter_class=RawTextHelpFormatter)

parser.add_argument('-f', '--plots-per-fig', type=int, help="maximum number of plots per figure (default: 2)", default=2)
parser.add_argument('-i', '--animation-interval', type=int, help="interval (in milliseconds) after which animation is updated (default: 1000)\nWarning: low interval might increase resource usage", default=1000)
parser.add_argument('-m', '--maxlen', type=int, help="maxium number of data points to show on plots (default: 1000)\nWarning: high number of data points might increase resource usage", default=1000)
parser.add_argument('-p', '--products', type=str, help="comma separated list of products to monitor (e.g., -p BTC-USD,ETH-USD,XLM-USD) (default: BTC-USD)", default="BTC-USD")
parser.add_argument('-s', '--show-supported-products', help="display products supported by coinbase (default: show all products; filter using --select-currency)", action='store_true', default=False)
parser.add_argument('-c', '--select-currency', type=str, help="display products supported by coinbase in a specific quote currency (default: show all products; similar to --show-supported-products)", default=None)
parser.add_argument('-q', '--show-supported-quote-currencies', help="display supported quote currencies", action='store_true')
args = parser.parse_args()


# error handling
if args.select_currency is not None and args.show_supported_products is False:
    print()
    print(">> ERROR : --select-currency must be used with --show-supported-products")
    print()
    exit(-1)


# helper function to show supported products in all or a specific quote currency
def DisplaySupportedProducts(currency=None):

    s = dict()
    public_client = cbpro.PublicClient()
    products = public_client.get_products()
    for p in products:
        if p['quote_currency'] not in s:
            s[p['quote_currency']] = []
        s[p['quote_currency']].append(p['id'])
    if currency is None:
        for q in s:
            print(">> {}:".format(q), sorted(s[q]))
    else:
        print(sorted(s[currency]))


# display all products supported by coinbase that can be monitored using this tool
if args.show_supported_products:
    DisplaySupportedProducts(args.select_currency)
    exit(0)

# display all quote currencies supported by coinbase
if args.show_supported_quote_currencies:
    public_client = cbpro.PublicClient()
    products = public_client.get_products()
    c = set()
    for p in products:
        c.add(p['quote_currency'])
    print(c)
    exit(0)


# websocket class used to connect with coinbase pro apis
class myWebsocketClient(cbpro.WebsocketClient):

    # initialize parameters before connecting to coinbase pro feed
    def on_open(self):
        self.url = "wss://ws-feed.pro.coinbase.com/"
        self.channels = ["ticker"]
        self.price_data = dict()
        for product in self.products:
            assert(product not in self.price_data)
            self.price_data[product] = {
                'data' : dq(maxlen=args.maxlen),
                'min'  : None,
                'max'  : None,
            }

    # update data on each product when a message is received
    def on_message(self, msg):
        if 'price' in msg and 'type' in msg and 'product_id' in msg:
            self.price_data[msg['product_id']]['data'].append(float(msg['price']))
            if self.price_data[msg['product_id']]['min'] is None:
                self.price_data[msg['product_id']]['min'] = float(msg['price'])
                self.price_data[msg['product_id']]['max'] = float(msg['price'])
            elif float(msg['price']) < self.price_data[msg['product_id']]['min']:
                self.price_data[msg['product_id']]['min'] = float(msg['price'])
            elif float(msg['price']) > self.price_data[msg['product_id']]['max']:
                self.price_data[msg['product_id']]['max'] = float(msg['price'])
    def on_close(self):
        print("-- Goodbye! --")

# connect to the websocket client and start receiving messages
products = args.products.split(',')
wsClient = myWebsocketClient(products=products)
wsClient.start()

print(">> Monitoring client started successfully")
print(">> Monitoring: " + str(products))

# configure plots
style.use('bmh')
numplots = len(products)
plotsperfig = args.plots_per_fig
if numplots > plotsperfig:
    numfigs = numplots // plotsperfig if numplots % plotsperfig == 0 else (numplots // plotsperfig) + 1
else:
    numfigs = 1

productlist = dq(products)
axesc = dict()
figs = []
for f in range(numfigs):
    numsps = plotsperfig if numplots >= plotsperfig else numplots
    fig, axes = plt.subplots(numsps, constrained_layout=True)
    fig.canvas.manager.set_window_title('coinbase monitor - figure # {}'.format(1 + f))
    figs.append(fig)
    if numsps == 1:
        axes = [axes]
    for ax in axes:
        k = productlist.popleft()
        assert(k not in axesc)
        axesc[k] = ax
    numplots -= plotsperfig


# function refreshes axes with latest data when called
def animate(i):
    for p in products:
        graph_data = wsClient.price_data[p]['data']
        axesc[p].clear()
        axesc[p].plot(graph_data, label=p)
        llim = wsClient.price_data[p]['min']
        ulim = wsClient.price_data[p]['max']
        if llim is not None and ulim is not None:
            axesc[p].set_ylim([0.9999 * llim, 1.0001 * ulim])
        else:
            axesc[p].set_ylim([0, 1])
        axesc[p].legend()
        axesc[p].set_xticks([])


# animate
anis = []
for fig in figs:
    anis.append(animation.FuncAnimation(fig, animate, interval=1000))
plt.show()

wsClient.close()
