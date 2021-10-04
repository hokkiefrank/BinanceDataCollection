from time import sleep
from binance.client import Client
from datetime import datetime
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import subprocess

# Get environment variables from OS/Docker image
import os

TEST = True

if TEST:
    import credentials as cred

    API_KEY = cred.API_KEY
    API_SECRET = cred.API_SECRET
    BUCKET_NAME =cred.BUCKET_NAME
    ORG_NAME = cred.ORG_NAME
    INFLUX_TOKEN = cred.INFLUX_TOKEN
    INFLUX_URL = cred.INFLUX_URL
else:
    API_KEY = os.environ['API_KEY']
    API_SECRET = os.environ['API_SECRET']
    BUCKET_NAME = os.environ['BUCKET_NAME']
    ORG_NAME = os.environ['ORG_NAME']
    INFLUX_TOKEN = os.environ['INFLUX_TOKEN']
    INFLUX_URL = os.environ['INFLUX_URL']

# project to get the balance from the wallet per coin per minute, and write that to a spreadsheet for easy tracking
# of the wallet.


def getbalances(client):
    info = client.get_account()
    #savingsInfo = client.get_lending_position()
    allBalances = info['balances']
    #print(allBalances)
    actualBalances = {}
    BTCtoEuro = float(client.get_avg_price(symbol='BTCEUR')['price'])
    USDTtoEuro = float(client.get_avg_price(symbol='EURUSDT')['price'])
    print("The BTC to Euro conversion at the moment of fetching is:{}".format(BTCtoEuro))
    print("These are the coins in your wallet:")
    for bal in allBalances:
        continue
        if not bal['free'] == bal['locked']:
            asset = bal['asset']
            print(asset)
            quantity = float(bal['free']) + float(bal['locked'])

            if asset == 'EUR':
                btcvalue = quantity / BTCtoEuro
                eurovalue = quantity
            if asset == 'USDT' or asset == 'BUSD':
                continue

            if asset == 'BTC':
                btcvalue = quantity
                eurovalue = btcvalue * BTCtoEuro
            else:
                try:
                    btcvalue = float(client.get_avg_price(symbol=asset + 'BTC')['price']) * quantity
                    eurovalue = btcvalue * BTCtoEuro
                except:
                    pass
                try:
                    btcvalue = float(client.get_avg_price(symbol=asset + 'BNB')['price']) * quantity
                    btcvalue = float(client.get_avg_price(symbol='BNBBTC')['price']) * btcvalue
                    eurovalue = btcvalue * BTCtoEuro
                except:
                    pass

                try:
                    eurovalue = float(client.get_avg_price(symbol=asset + 'EUR')['price']) * quantity
                    btcvalue = eurovalue / BTCtoEuro
                except:
                    pass

                try:
                    usdtvalue = float(client.get_avg_price(symbol=asset + 'USDT')['price']) * quantity
                    eurovalue = usdtvalue / USDTtoEuro
                    btcvalue = eurovalue / BTCtoEuro
                except:
                    pass

            actualBalances[asset] = {'amount': quantity,
                                     'BTC_value': btcvalue,
                                     'Euro_value': eurovalue}

    try:
        f = open("radix.txt", "r")
        print(f.read())
        bashCommand = "curl -s --request GET --url https://api.bitfinex.com/v1/pubticker/xrdusd | jq -r '.last_price'"
        process = subprocess.Popen(bashCommand.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()
        print(output)
        usdtvalue = output * f.read()
        eurovalue = usdtvalue / USDTtoEuro
        btcvalue = eurovalue / BTCtoEuro

        actualBalances[asset] = {'amount': quantity,
                                 'BTC_value': btcvalue,
                                 'Euro_value': eurovalue}
    except:
        print("No file found")


    return actualBalances


def pushDB(wD, wO):
    # You can generate a Token from the "Tokens Tab" in the UI
    token = INFLUX_TOKEN
    org = ORG_NAME
    bucket = BUCKET_NAME
    url = INFLUX_URL

    client = InfluxDBClient(url=url, token=token)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    sequence = []
    for detail in wD:
        coin = detail[1]
        amount = str(detail[2])
        euro_value = str(detail[3])
        btc_value = str(detail[4])
        sequence.append("wallet,coin="+coin+" euro_value="+euro_value)
        sequence.append("wallet,coin="+coin+" btc_value="+btc_value)
        sequence.append("wallet,coin="+coin+" amount="+amount)

    sequence.append("walletOverview,coin=EUR euro_value_total="+str(wO[0][1]))
    sequence.append("walletOverview,coin=BTC btc_value_total=" + str(wO[0][2]))
    print(sequence)



    #point = Point("mem").tag("host", "host1").field("used_percent", 23.43234543).time(datetime.utcnow(), WritePrecision.NS)
    #sequence = ["mem,coin=BTC amount=22.43234543",
    #            "mem,coin=BNB amount=16.856523"]
    write_api.write(bucket, org, sequence)
    print("Sequence is written to the DB!")
    #write_api.write(bucket, org, point)

def getOverview(balance):

    # parse the balance to fit into the correct form for pushing it into the sheets
    # every asset should have the following data: Timestamp	Coin_Name	Amount	Euro_Value	BTC_Value
    # as columns.

    time = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    walletDetail = []
    walletOverview = [[str(time), 0, 0]]

    for bal in balance:
        asset = bal
        bal = balance[asset]
        row = [str(time), asset, bal['amount'], bal['Euro_value'], bal['BTC_value'], 0, 0]
        walletDetail.append(row)

        walletOverview[0][1] = walletOverview[0][1] + bal['Euro_value']
        walletOverview[0][2] = walletOverview[0][2] + bal['BTC_value']

    return walletDetail, walletOverview


if __name__ == '__main__':

    client = Client(API_KEY,API_SECRET)
    while True:
        try:
            b = getbalances(client)
            wallet_detail, wallet_overview = getOverview(b)
            pushDB(wallet_detail, wallet_overview)
            sleep(55)
        except Exception as e:
            print("{}\n Exiting".format(e))
            exit(1)

