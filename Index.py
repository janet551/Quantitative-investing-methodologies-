import os
import json
import datetime
import time
import logging
import asyncio
from dotenv import load_dotenv
from metaapi.cloud_metaapi import MetaApi

# Load environment variables
load_dotenv()
METAAPI_TOKEN = os.getenv("METAAPI_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")

# Logging setup
logging.basicConfig(
    filename="trading_log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Trading settings
ASSETS = ["EURUSD", "GBPUSD", "USDCHF", "EURCAD"]
TP = 25  # Take Profit (points)
BREAKOUT_TIMEFRAME = 900  # 15-minute in seconds
LOT_SIZE = 5  # Increased lot size

class TradingBot:
    def __init__(self):
        self.api = MetaApi(METAAPI_TOKEN)
        self.account = None

    async def connect_account(self):
        """Connect to the MetaApi account."""
        try:
            self.account = await self.api.metatrader_account_api.get_account(ACCOUNT_ID)
            await self.account.deploy()
            await self.account.wait_connected()
            logging.info("✅ Connected to MetaApi successfully.")
        except Exception as e:
            logging.error(f"❌ Error connecting to MetaApi: {e}")

    async def fetch_market_data(self, asset):
        """Fetch latest candlestick data using MetaApi."""
        try:
            connection = self.account.get_rpc_connection()
            await connection.connect()
            candles = await connection.get_historical_candles(asset, '15m', 2)
            return candles
        except Exception as e:
            logging.error(f"❌ Error fetching market data for {asset}: {e}")
            return None

    async def process_candlestick(self, asset):
        """Identify breakouts and execute trades."""
        candles = await self.fetch_market_data(asset)
        if not candles or len(candles) < 2:
            return

        prev_candle = candles[-2]
        breakout_candle = candles[-1]

        if breakout_candle['close'] > prev_candle['high']:
            await self.trade("BUY", asset, breakout_candle)
        elif breakout_candle['close'] < prev_candle['low']:
            await self.trade("SELL", asset, breakout_candle)

    async def trade(self, direction, asset, breakout_candle):
        """Place a trade if a breakout occurs."""
        entry_price = breakout_candle['close']
        stop_loss = breakout_candle['low'] if direction == "BUY" else breakout_candle['high']
        take_profit = entry_price + TP if direction == "BUY" else entry_price - TP

        order_payload = {
            "action": "ORDER_FILL",
            "symbol": asset,
            "volume": LOT_SIZE,
            "type": "MARKET",
            "side": direction,
            "stopLoss": stop_loss,
            "takeProfit": take_profit
        }

        await self.send_trade(order_payload)

    async def send_trade(self, order_payload):
        """Send trade order using MetaApi and verify execution."""
        try:
            connection = self.account.get_rpc_connection()
            await connection.connect()

            result = await connection.create_market_order(
                order_payload['symbol'],
                order_payload['side'],
                order_payload['volume'],
                stop_loss=order_payload['stopLoss'],
                take_profit=order_payload['takeProfit']
            )

            if result:
                logging.info(f"✅ Trade executed: {order_payload}")
                print(f"✅ Trade executed: {order_payload}")
            else:
                logging.error(f"❌ Trade execution failed: {result}")
                print(f"❌ Trade execution failed: {result}")

        except Exception as e:
            logging.error(f"❌ Trade execution error: {e}")
            print(f"❌ Trade execution error: {e}")

    async def check_trade_history(self):
        """Fetch and log recent trades from MetaApi account history."""
        try:
            connection = self.account.get_rpc_connection()
            await connection.connect()

            history = await connection.get_history_orders_by_time(
                start_time=datetime.datetime.utcnow() - datetime.timedelta(hours=1),
                end_time=datetime.datetime.utcnow()
            )

            if history:
                logging.info("📌 Recent Trades:")
                for trade in history[-5:]:
                    logging.info(trade)
                    print(trade)  # Print trade details to console
            else:
                logging.info("❌ No recent trades found.")

        except Exception as e:
            logging.error(f"❌ Error fetching trade history: {e}")
            print(f"❌ Error fetching trade history: {e}")

# Run the Trading Bot
async def main():
    bot = TradingBot()
    await bot.connect_account()

    while True:
        for asset in ASSETS:
            await bot.process_candlestick(asset)

        await bot.check_trade_history()  # Check history every cycle
        time.sleep(BREAKOUT_TIMEFRAME)  # Wait for next 15-minute candle

asyncio.run(main())
