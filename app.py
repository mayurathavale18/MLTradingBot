import streamlit as st
import os
import logging
import time
from threading import Thread
from dotenv import load_dotenv
from datetime import datetime
from lumibot.brokers import Alpaca
from lumibot.strategies.strategy import Strategy
from lumibot.traders import Trader
from alpaca_trade_api import REST
from timedelta import Timedelta
from finbert_utils import estimate_sentiment

# Set up logging
logging.basicConfig(filename="MLTradingBot/logs/itrader_log.txt", level=logging.INFO)
def log_trade_details(order):
    logging.info(f"Trade executed: {order.symbol}, {order.qty} shares at {order.filled_avg_price}, status: {order.status}")

# Load the .env file
load_dotenv()

# Access the API keys from the .env file
API_KEY = os.getenv("API_KEY") 
API_SECRET = os.getenv("API_SECRET") 
BASE_URL = "https://paper-api.alpaca.markets"

ALPACA_CREDS = {
    "API_KEY":API_KEY, 
    "API_SECRET": API_SECRET, 
    "PAPER": True
}

class MLTrader(Strategy): 
    def initialize(self, symbol:str="SPY", cash_at_risk:float=.5): 
        self.symbol = symbol
        self.sleeptime = "5m" 
        self.last_trade = None 
        self.cash_at_risk = cash_at_risk
        self.api = REST(base_url=BASE_URL, key_id=API_KEY, secret_key=API_SECRET)

    def position_sizing(self): 
        cash = self.get_cash() 
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price,0)
        return cash, last_price, quantity

    def get_dates(self): 
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        return today.strftime('%Y-%m-%d'), three_days_prior.strftime('%Y-%m-%d')

    def get_sentiment(self): 
        today, three_days_prior = self.get_dates()
        news = self.api.get_news(symbol=self.symbol, 
                                 start=three_days_prior, 
                                 end=today) 
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment 

    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing() 
        probability, sentiment = self.get_sentiment()

        if cash > last_price: 
            if sentiment == "positive" and probability > .999: 
                if self.last_trade == "sell": 
                    self.sell_all() 
                order = self.create_order(
                    self.symbol, 
                    quantity, 
                    "buy", 
                    type="bracket", 
                    take_profit_price=last_price*1.20, 
                    stop_loss_price=last_price*.95
                )
                self.submit_order(order) 
                log_trade_details(order)  #log the buying order
                self.last_trade = "buy"
            elif sentiment == "negative" and probability > .999: 
                if self.last_trade == "buy": 
                    self.sell_all() 
                order = self.create_order(
                    self.symbol, 
                    quantity, 
                    "sell", 
                    type="bracket", 
                    take_profit_price=last_price*.8, 
                    stop_loss_price=last_price*1.05
                )
                self.submit_order(order) 
                log_trade_details(order) #log the selling order
                self.last_trade = "sell"

# Define Streamlit app layout
def main():
    st.title("iTrader Trading Bot Interface")

    # Create start button to run the bot
    if st.button('Start Trading Bot'):
        st.write("Bot started...")
        trader_thread = Thread(target=start_trading_bot)
        trader_thread.start()

    # Create stop button to stop the bot
    if st.button('Stop Trading Bot'):
        st.write("Stopping the bot is not implemented here.")
        # Implement your logic to stop the bot
    
    # Show trading log file content
    log_file_path = "MLTradingBot/logs/itrader_log.txt"
    if os.path.exists(log_file_path):
        with open(log_file_path, 'r') as f:
            log_content = f.read()
            st.text_area("Trade Log", log_content, height=300)

    # Auto-refresh every 5 seconds to show latest trades
    st_autorefresh(interval=5000)

# Function to start the trading bot
def start_trading_bot():
    start_date = datetime(2024,9,1)
    end_date = datetime(2024,10,7)
    broker = Alpaca(ALPACA_CREDS)
    strategy = MLTrader(name='mlstrat', broker=broker, parameters={"symbol":"SPY", "cash_at_risk":.5})
    trader = Trader()
    trader.add_strategy(strategy)
    trader.run_all()  # paper trading starts

# Function to auto-refresh the Streamlit app
def st_autorefresh(interval=5000):
    st.experimental_rerun()

if __name__ == "__main__":
    main()
