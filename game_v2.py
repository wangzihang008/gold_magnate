import os
import json
import ssl
import tkinter as tk
from tkinter import messagebox, scrolledtext
import urllib.request
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import random
from datetime import datetime

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False

#virtual news
NEWS = {
    "Fed Raises Interest Rates by 0.25%\n": 0.95,
    "Fed Raises Interest Rates by 0.5%\n": 0.92,
    "Fed Raises Interest Rates by 0.75%\n": 0.88,
    "Fed Cut Interest Rates by 0.25%\n": 1.05,
    "Fed Cut Interest Rates by 0.5%\n": 1.1,
    "Fed Cut Interest Rates by 0.75%\n": 1.15,
    "War Breaks Out\n": 1.1,
    "Exacerbate Geopolitical Tensions\n": 1.1,
    "New Rescue Act Onboard\n": 0.9
}



# Account
class Account:
    def __init__(self, initial_balance=100000.0, lot_size=1, name="unknown"):
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.position = 0  
        self.entry_price = 0.0
        self.lot_size = lot_size 
        self.name = name

    def buy(self, price, quantity):
        if self.position != 0:
            return "Long Position Hold, Pls Sell All First", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = quantity
            self.entry_price = price
            self.balance -= margin
            return f"Buy Successful {quantity} Qutity @ {price:.2f}, Used Insurence {margin:.2f}。", True
        return "Short of Money, Cannot Action", False

    def sell(self, price, quantity):
        if self.position != 0:
            return "Long Position Hold, Pls Sell All First", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = -quantity
            self.entry_price = price
            self.balance -= margin
            return f"Short Sell Successful {quantity} Qutity @ {price:.2f}, Used Insurence {margin:.2f}.", True
        return "Short of Money, Cannot Action", False

    def close_position(self, current_price):
        if self.position == 0:
            return "No Position Can be Sell", 0.0
        pnl = (current_price - self.entry_price) * self.position * self.lot_size
        self.balance += pnl
        gloProfit.set(gloProfit.get() + pnl)
        margin_released = abs(self.entry_price * self.position * 0.1)
        self.balance += margin_released
        pos = self.position
        self.position = 0
        self.entry_price = 0.0
        msg = f"Sell All Successful（{'Long Buy' if pos>0 else 'Short Sell'} {abs(pos)} )! Qutity: {pnl:.2f}, Insurence Release{margin_released:.2f}. Account: {self.balance:.2f}。"
        return msg, pnl

    def floating_pnl(self, current_price):
        if self.position == 0:
            return 0.0
        return (current_price - self.entry_price) * self.position * self.lot_size

# Main Frame
class TradingGameUI:
    def __init__(self, root, name):
        self.root = root
        self.root.title(name+" - Gold Magnate 2008")

        self.player_name = name
        # print(self.player_name)

        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")
        self.font_menu = ("Microsoft YaHei", 14) # 新增菜单字体

        self.account = Account(initial_balance=100000.0, lot_size=1)
        self.price_df = pd.DataFrame()
        self.days = []
        self.total_days = 0
        self.idx = 0
        self.price_history = []

        self.ProfitHist = np.array([])

        global gloProfit
        gloProfit = tk.DoubleVar(value=0.0)
        self.UnrealizedProfit = tk.DoubleVar(value = 0.0)

        self.total_game_ms = 10 * 60 * 1000  
        self.update_interval_ms = 1000 
        self.origin_interval_ms = 1000
        self.timer_running = False

        self.news_map = {}
        self.load_my_news()

        self.build_ui()
        self.fetch_data()
        self.start_game()

    def fetch_data(self):
        cache_file = "gold_magnate_harder.csv"
        # if os.path.exists(cache_file):
        #     try:
        #         self.price_df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        #         self.price_df = self.price_df[['Close']].dropna()
        #     except Exception:
        #         self.price_df = pd.DataFrame()

        if self.price_df.empty:
            try:
                period1 = 1199120400 
                period2 = 1230656400 
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/GC=F?symbol=GC=F&period1={period1}&period2={period2}&interval=1d"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, context=ctx) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
                ts = data['chart']['result'][0]['timestamp']
                dates = pd.to_datetime(ts, unit='s')
                self.price_df = pd.DataFrame({'Close': closes}, index=dates).dropna()

                rand_array = np.random.randn(253)
                indexs = self.price_df.index.tolist()
                values = self.price_df.values


                index = 2
                while index < len(rand_array):
                    values[index] = str(float(values[index-1][0])*abs(1-float(rand_array[index]/100)))
                    r = random.randint(1, 98)
                    if r>=90:
                        values[index] = values[index] * list(NEWS.items())[r%10][1]
                        self.news_map[indexs[index]]=list(NEWS.items())[r%10][0]
                    index+=1
                index = 2
                while index < len(indexs):
                    self.price_df.loc[indexs[index],'Close'] = values[index]
                    index+=1

                self.price_df.to_csv(cache_file)
                # print(self.news_map)
                # exit(0)
            except Exception as e:
                messagebox.showerror("Data Load Failed", f"Cannot Load Data: {e}")
                self.root.quit()
                return

        self.days = list(self.price_df.index)
        self.total_days = len(self.days)
        if self.total_days == 0:
            messagebox.showerror("Data Error", "There is no availiable trading day data")
            self.root.quit()
            return

        self.update_interval_ms = max(200, int(self.total_game_ms / self.total_days))

        first_price = float(self.price_df.iloc[0]['Close'])
        self.price_history = [first_price]
        self.log(f"Data Loaded :{self.total_days} Trading Days. Will rocess {self.update_interval_ms} ms As 1 Day(tTotal Time is 10 Mins)")
        self.refresh_top_panel(first_price, self.days[0])

    def load_my_news(self):
        file = "my_news.json"
        if not os.path.exists(file):
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                user_news = json.load(f)
            for k, v in user_news.items():
                if isinstance(v, list):
                    self.news_map[k] = ";".join(str(x) for x in v)
                else:
                    self.news_map[k] = str(v)
        except Exception as e:
            messagebox.showwarning("New Load Warning", f"read my_news.json failed: {e}")

    def show_help_window(self):
        """Creates a new window to display the game tutorial."""
        help_win = tk.Toplevel(self.root)
        help_win.title("Game Tutorial")
        help_win.geometry("700x700")

        help_text = """
Gold Magnate (Random Price) - Game Tutorial

Welcome to the random price version of Gold Magnate!
You can access this tutorial at any time by navigating to Menu > Help in the top menu bar.
---------------------------------------------------------------------

This is a trading simulation game where gold prices are randomly generated with influences from virtual news events. Your goal is to maximize your profit.

**1. Game Interface Overview**

The main screen is divided into four key areas:

* **Top Panel (Account And Market):**
    * `Account`: Shows your current available cash. A 10% margin will be deducted from this when you open a position.
    * `Position`: Displays your current trade. "None" means you have no open trades. "Long" means you've bought, expecting the price to go up. "Short" means you've sold, expecting the price to go down. It also shows the quantity and your entry price.
    * `Floating Profit And Loss`: Shows the unrealized profit or loss on your current open position. It's green for profit and red for loss.
    * `Date and Price`: Shows the current in-game date and the corresponding gold price.

* **Middle-Left Panel (Trading):**
    * `Qutity`: Enter the number of lots you wish to trade here.
    * `Buy`: Click this to open a long position. You profit if the price goes up.
    * `Sell`: Click this to open a short position. You profit if the price goes down.
    * `Sell All`: Click this to close your current open position and realize any profit or loss.
    * `Speed Up(x2) / Normal Speed`: Toggles the game speed between normal and 2x.
    * `Pause / Resume`: Pauses or resumes the automatic progression of the game timeline.
    * `End Game`: Allows you to end the game session prematurely.
    * `Profit / History`: Click to view a chart of your total profit over time.
    * *Note*: You must close any existing position before you can open a new one.

* **Middle-Right Panel (Gold Price Trend Chart):**
    * This chart visually represents the gold price over time. Use it to identify trends and make trading decisions.

* **Bottom Panels (Logs and News):**
    * `Action History`: A log of all your trading actions (buy, sell, close).
    * `Break News`: Displays major virtual news events for the current day. This news can significantly impact the gold price.

**2. How to Play**

1.  **Start:** The game starts automatically with an initial balance of $100,000. The timeline will begin to advance automatically.

2.  **Analyze:** Watch the price movement on the chart and read the daily news. Decide if you think the price will go up or down.

3.  **Enter Quantity:** Type the number of lots you want to trade into the `Qutity` box.

4.  **Open a Position:**
    * If you believe the price will rise, click `Buy`.
    * If you believe the price will fall, click `Sell`.

5.  **Manage Your Position:** As the game progresses, your `Floating Profit And Loss` will update. You can use the `Pause` and `Speed Up` buttons to control the pace of the game.

6.  **Close Your Position:** When you are ready to exit your trade, click `Sell All`. Your profit or loss will be added to your account balance, and the margin used for the trade will be returned.

7.  **Repeat:** Continue to analyze the market and make trades.

**3. End of the Game**

The game automatically ends when the timeline is complete, or you can click `End Game`. Any open positions will be automatically closed at the final market price. A summary of your performance, including your final balance and total profit/loss, will be displayed.

Good luck, and may you become a Gold Magnate!
        """
        
        txt_help = scrolledtext.ScrolledText(help_win, font=("Microsoft YaHei", 12), wrap=tk.WORD)
        txt_help.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        txt_help.insert(tk.END, help_text)
        txt_help.config(state=tk.DISABLED)

    def build_ui(self):
        # --- Add Menu Bar ---
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        menu_dropdown = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Menu", menu=menu_dropdown, font=self.font_menu)
        menu_dropdown.add_command(label="Help", command=self.show_help_window, font=self.font_menu)
        menu_dropdown.add_command(label="Rankings", command=self.show_in_game_rankings, font=self.font_menu)

        # --- End Menu Bar ---

        top = tk.LabelFrame(self.root, text="Account And Market", font=self.font_title, padx=8, pady=8)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        self.lbl_balance = tk.Label(top, text="Account: 0.00", font=self.font_big)
        self.lbl_balance.pack(side=tk.LEFT, padx=(4, 16))

        self.lbl_pos = tk.Label(top, text="Position: 0", font=self.font_big)
        self.lbl_pos.pack(side=tk.LEFT, padx=16)

        self.lbl_pnl = tk.Label(top, text="Floating Profit And Loss: 0.00", font=self.font_big)
        self.lbl_pnl.pack(side=tk.LEFT, padx=16)

        self.lbl_date_price = tk.Label(top, text="Date:  -    Price: -", font=self.font_big)
        self.lbl_date_price.pack(side=tk.RIGHT, padx=8)

        mid = tk.Frame(self.root)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        trade = tk.LabelFrame(mid, text="Trading", font=self.font_title, padx=8, pady=8)
        trade.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        tk.Label(trade, text="Qutity:", font=self.font_big).pack(anchor="w")
        self.entry_qty = tk.Entry(trade, width=8, font=self.font_big)
        self.entry_qty.insert(0, "1")
        self.entry_qty.pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(trade)
        btns.pack(anchor="w", pady=4)
        tk.Button(btns, text="Buy", font=self.font_big, command=self.buy_action, width=10).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(btns, text="Sell", font=self.font_big, command=self.sell_action, width=10).grid(row=0, column=1, padx=4, pady=4)
        tk.Button(btns, text="Sell All", font=self.font_big, command=self.close_action, width=10).grid(row=1, column=0, padx=4, pady=4)
        self.speed_btn=tk.Button(btns, text="Speed Up(x2)", font=self.font_big, command=self.speed_up, width=10)
        self.speed_btn.grid(row=1, column=1, padx=4, pady=4)

        
        self.pause_btn=tk.Button(btns, text="Pause", font=self.font_big, command=self.game_control, width=10)
        self.pause_btn.grid(row=2, column=0, padx=4, pady=4)
        tk.Button(btns, text="End Game", font=self.font_big, command=self.end_game, width=10).grid(row=2, column=1, padx=4, pady=4)

        tk.Label(trade, text="Note: 10% insurence, close out first, then reverse Liquidation", font=("Microsoft YaHei", 12)).pack(anchor="w", pady=(6, 0))

        pf = tk.Frame(trade)
        pf.pack(anchor="w", pady=4)

        tk.Button(pf, text="Profit", font=self.font_big, command=self.getProfitChart, width=10).grid(row=0, column=0, padx=4, pady=4)
        
        chart_frame = tk.LabelFrame(mid, text="Gold Price Trend Chart", font=self.font_title, padx=8, pady=8)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig, self.ax = plt.subplots(figsize=(7, 4))
        self.ax.set_title("Gold Price Trend Chart", fontsize=16, fontweight='bold')
        self.ax.set_ylabel("Price (USD)", fontsize=12)
        self.ax.grid(True)
        (self.line,) = self.ax.plot([], [], linewidth=1.8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=8, pady=(4, 8))

        log_frame = tk.LabelFrame(bottom, text="Acion History", font=self.font_title, padx=8, pady=8)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=10, font=self.font_big, state=tk.NORMAL)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        news_frame = tk.LabelFrame(bottom, text="Break News", font=self.font_title, padx=8, pady=8)
        news_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.txt_news = scrolledtext.ScrolledText(news_frame, height=10, font=self.font_big, state=tk.DISABLED, wrap=tk.WORD)
        self.txt_news.pack(fill=tk.BOTH, expand=True)

    # New Panel
    def log(self, msg):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    def set_news(self, text):
        self.txt_news.config(state=tk.NORMAL)
        # self.txt_news.delete("1.0", tk.END)
        if text:
            self.txt_news.insert(tk.END, text)
        self.txt_news.config(state=tk.DISABLED)

    # Refresh Top Panel
    def refresh_top_panel(self, price, day):
        self.lbl_balance.config(text=f"Account: {self.account.balance:.2f}")
        if self.account.position == 0:
            pos_text = "None"
            pnl_text = "0.00"
            pnl_color = "black"
        else:
            pos_text = f"{'Long Position' if self.account.position>0 else 'Short Position'}（{abs(self.account.position)} Qutity @ {self.account.entry_price:.2f}）"
            pnl = self.account.floating_pnl(price)
            pnl_text = f"{pnl:.2f}"
            pnl_color = ("green" if pnl >= 0 else "red")
        self.lbl_pos.config(text=f"Position: {pos_text}")
        self.lbl_pnl.config(text=f"Floating Profit And Loss: {pnl_text}", fg=pnl_color)
        self.lbl_date_price.config(text=f"Date: {day.strftime('%Y-%m-%d')}    Current Price: {price:.2f}")

    # Start Game
    def start_game(self):
        self.timer_running = True
        self.root.after(self.update_interval_ms, self.tick)

    def tick(self):
        if not self.timer_running:
            return

        if self.idx >= self.total_days:
            self.end_game()
            return

        day = self.days[self.idx]
        price = float(self.price_df.iloc[self.idx]['Close'])
        self.price_history.append(price)

        self.line.set_data(range(len(self.price_history)), self.price_history)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

        self.UnrealizedProfit.set(self.account.floating_pnl(price))
        
        self.ProfitHist = np.append(self.ProfitHist, gloProfit.get()+self.UnrealizedProfit.get())

        
        # dstr = day.strftime("%Y-%m-%d")
        if self.news_map.get(day, "") != "":
            news_text = day.strftime("%Y-%m-%d") + " : " + self.news_map.get(day, "")
            self.set_news(news_text)

        self.refresh_top_panel(price, day)

        self.idx += 1

        self.root.after(self.update_interval_ms, self.tick)

    def game_control(self):
        if self.timer_running:
            self.timer_running = False
            self.pause_btn['text']="Resume"
        else:
            self.timer_running = True
            self.pause_btn['text']="Pause"
        self.root.after(self.update_interval_ms, self.tick)

    def speed_up(self):
        if self.speed_btn['text']=="Speed Up(x2)":
            self.origin_interval_ms = self.update_interval_ms
            self.update_interval_ms = self.origin_interval_ms//2
            self.speed_btn['text']="Normal Speed"
        elif self.speed_btn['text']=="Normal Speed":
            self.update_interval_ms = self.origin_interval_ms
            self.speed_btn['text']="Speed Up(x2)"
        self.root.after(self.update_interval_ms, self.tick)

    # Trading Actions
    def _current_trade_price(self):
        use_idx = max(0, self.idx - 1)
        return float(self.price_df.iloc[use_idx]['Close']), self.days[use_idx]

    def buy_action(self):
        qty = self._get_qty()
        if qty is None:
            return
        price, day = self._current_trade_price()
        msg, ok = self.account.buy(price, qty)
        self.log(f"{day.strftime('%Y-%m-%d')}  Buy {qty} Qutity @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def sell_action(self):
        qty = self._get_qty()
        if qty is None:
            return
        price, day = self._current_trade_price()
        msg, ok = self.account.sell(price, qty)
        self.log(f"{day.strftime('%Y-%m-%d')}  Short Sell {qty} Qutity @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def close_action(self):
        price, day = self._current_trade_price()
        msg, pnl = self.account.close_position(price)
        self.log(f"{day.strftime('%Y-%m-%d')}  Sell All @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def _get_qty(self):
        try:
            qty = int(self.entry_qty.get().strip())
            if qty <= 0:
                raise ValueError
            return qty
        except Exception:
            messagebox.showerror("Input Error", "Please Input Vaild Number(postive integer)")
            return None

    def drawChart(self):
            
        self.ax2.clear()
        self.ax2.plot(self.ProfitHist, marker='o', color='blue', label='Profit')
    
        self.ax2.set_title("Profit History", fontsize=14)
        self.ax2.set_xlabel("Time", fontsize=12)
        self.ax2.set_ylabel("Profit", fontsize=12)
        self.ax2.axhline(y=self.ProfitHist[-1], color="red", linestyle="--", label=f"Profit: {self.ProfitHist[-1]}")
        
        self.ax2.legend(loc='upper left')
        self.ax2.relim()
        self.ax2.autoscale_view()
        
        
        self.canvas2.draw()
        self.profitRoot.after(self.update_interval_ms, self.drawChart)
            

            
    def getProfitChart(self):
        """Open a popup window and start drawing the rolling profit history."""
        self.profitRoot = tk.Toplevel(self.root)
        self.profitRoot.title("Profit History")
        self.profitRoot.geometry("1200x800")
        self.fig2, self.ax2 = plt.subplots(figsize=(5, 3))
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.profitRoot)
        self.canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.drawChart()



    # ---------- End-of-game settlement ----------
    def end_game(self):
        """Stop timer, auto-close any position at last price, save results, show summary, and exit."""
        self.timer_running = False
        last_price = float(self.price_df.iloc[-1]['Close'])
        if self.account.position != 0:
           msg, pnl = self.account.close_position(last_price)
           self.log(f"Automatically close a position (last day @ {last_price:.2f}): {msg}")

        final_balance = self.account.balance
        pl = final_balance - self.account.initial_balance
        rr = (pl / self.account.initial_balance) * 100.0

        # Save game result
        df = self.save_game_result(final_balance, pl, rr)

        # Get ranking info
        current_ranking, total_players = self.get_player_ranking(df)

        # Build message
        result_msg = (
                   f"Final account balance: {final_balance:.2f}\n"
                   f"Total profit and loss: {pl:.2f}\n"
                   f"Return on investment: {rr:.2f}%"
        )
        if current_ranking:
           result_msg += f"\n\nYour Ranking: #{current_ranking} out of {total_players} players!"

        # Popup
        messagebox.showinfo("Game over", result_msg)

        # Show leaderboard
        self.show_rankings(df, current_ranking, total_players, rr)

# =============== Main (with your testing section) ===============
        # Close window
        self.root.quit()

    def save_game_result(self, final_balance, pl, rr):
        """Save game result to CSV file (game_rankings_hard_mode.csv)."""
        csv_file = "game_rankings_hard_mode.csv"
        
        # Create new record
        new_record = {
            'player_name': self.player_name,
            'final_balance': final_balance,
            'profit_loss': pl,
            'return_rate': rr,
            'play_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Read existing or create new DataFrame
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
            except:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        
        # Append new record
        new_df = pd.DataFrame([new_record])
        df = pd.concat([df, new_df], ignore_index=True)
        
        # Save
        df.to_csv(csv_file, index=False)
        
        return df
    
    def get_player_ranking(self, df):
        """Get current player's ranking among all records (by return_rate)."""
        if df.empty:
            return None, 0
        
        # Sort by return rate
        df_sorted = df.sort_values('return_rate', ascending=False).reset_index(drop=True)
        
        # Find current player's latest record's ranking
        current_record = df_sorted[df_sorted['player_name'] == self.player_name].iloc[-1:]
        if not current_record.empty:
            ranking = df_sorted.index[df_sorted['return_rate'] == current_record['return_rate'].iloc[0]][0] + 1
            total_players = len(df_sorted)
            return ranking, total_players
        
        return None, len(df_sorted)
    
    def show_rankings(self, df, current_ranking, total_players, current_rr):
        """Show leaderboard window (Top 5 and current player's position)."""
        ranking_window = tk.Toplevel(self.root)
        ranking_window.title("Game Rankings - 2008 Original")
        ranking_window.geometry("600x500")
        ranking_window.configure(bg='white')
        
        # Main frame
        main_frame = tk.Frame(ranking_window, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title_label = tk.Label(main_frame, text="🏆 Game Rankings - 2008 Original", 
                              font=self.font_title, bg='white', fg='#2c3e50')
        title_label.pack(pady=(0, 20))
        
        # Current player's ranking
        if current_ranking:
            rank_text = f"👤 {self.player_name}'s Ranking: #{current_ranking} / {total_players} players\nReturn Rate: {current_rr:.2f}%"
            rank_color = '#27ae60' if current_rr > 0 else '#e74c3c'
        else:
            rank_text = f"👤 {self.player_name}: No ranking data available"
            rank_color = '#7f8c8d'
        
        current_rank_label = tk.Label(main_frame, text=rank_text, 
                                     font=("Microsoft YaHei", 16), 
                                     bg='white', fg=rank_color)
        current_rank_label.pack(pady=(0, 20))
        
        # Separator
        separator = tk.Frame(main_frame, height=2, bg='#bdc3c7')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        # Top 5 title
        top5_label = tk.Label(main_frame, text="🥇 Top 5 Players", 
                             font=("Microsoft YaHei", 18, "bold"), 
                             bg='white', fg='#2c3e50')
        top5_label.pack(pady=(0, 15))
        
        # Content
        if not df.empty:
            # Sort by return and keep each player's best
            df_best = df.loc[df.groupby('player_name')['return_rate'].idxmax()]
            df_sorted = df_best.sort_values('return_rate', ascending=False).head(5)
            
            # Container
            ranking_frame = tk.Frame(main_frame, bg='white')
            ranking_frame.pack(fill=tk.BOTH, expand=True)
            
            medals = ['🥇', '🥈', '🥉', '🏅', '🏅']
            colors = ['#ffd700', '#c0c0c0', '#cd7f32', '#4a90e2', '#4a90e2']
            
            for idx, (_, row) in enumerate(df_sorted.iterrows()):
                medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
                color = colors[idx] if idx < len(colors) else '#7f8c8d'
                
                row_frame = tk.Frame(ranking_frame, bg='white')
                row_frame.pack(fill=tk.X, pady=5)
                
                # Fixed-width aligned line for consistent layout
                rank_text = f"{medal} {row['player_name']:>15} | Return: {row['return_rate']:>8.2f}% | Balance: ${row['final_balance']:>10,.2f}"
                
                rank_label = tk.Label(row_frame, text=rank_text, 
                                     font=("Courier New", 14, "bold" if idx < 3 else "normal"),
                                     bg='white', fg=color, anchor='w')
                rank_label.pack(fill=tk.X)
        else:
            no_data_label = tk.Label(main_frame, text="No ranking data available yet.", 
                                   font=self.font_big, bg='white', fg='#7f8c8d')
            no_data_label.pack()
        
        # Close button
        close_btn = tk.Button(main_frame, text="Close", font=self.font_big, 
                             command=ranking_window.destroy, width=15,
                             bg='#3498db', fg='white', relief=tk.FLAT)
        close_btn.pack(pady=(20, 0))

    def show_in_game_rankings(self):
        """Display rankings window during the game."""
        csv_file = "game_rankings_hard_mode.csv"
        
        # Create ranking window
        ranking_window = tk.Toplevel(self.root)
        ranking_window.title("Live Rankings - 2008 Original")
        ranking_window.geometry("650x450")
        ranking_window.configure(bg='white')
        
        # Window attributes
        ranking_window.transient(self.root)  # set as child of root
        ranking_window.grab_set()  # modal
        
        # Main frame
        main_frame = tk.Frame(ranking_window, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Title
        title_label = tk.Label(main_frame, text="Top 5 Players - 2008 Gold Trading", 
                              font=("Microsoft YaHei", 18, "bold"), bg='white', fg='#2c3e50')
        title_label.pack(pady=(0, 15))
        
        # If there is data
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    # Sort by return and keep only best attempt per player
                    df_best = df.loc[df.groupby('player_name')['return_rate'].idxmax()]
                    df_sorted = df_best.sort_values('return_rate', ascending=False).head(5)
                    
                    # Content frame
                    content_frame = tk.Frame(main_frame, bg='white')
                    content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
                    
                    # Header
                    header_frame = tk.Frame(content_frame, bg='#34495e', height=40)
                    header_frame.pack(fill=tk.X, pady=(0, 2))
                    header_frame.pack_propagate(False)
                    
                    header_text = "Rank   Player Name          Return Rate      Final Balance"
                    header_label = tk.Label(header_frame, text=header_text, 
                                          font=("Courier New", 12, "bold"),
                                          bg='#34495e', fg='white', anchor='w')
                    header_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
                    
                    # Ranking items
                    bg_colors = ['#fff9c4', '#f0f0f0', '#ffeaa7', '#ddd', '#ddd']
                    
                    for idx, (_, row) in enumerate(df_sorted.iterrows()):
                        rank_frame = tk.Frame(content_frame, bg=bg_colors[idx], height=35)
                        rank_frame.pack(fill=tk.X, pady=1)
                        rank_frame.pack_propagate(False)
                        
                        # Formatted display text
                        rank_num = f"#{idx + 1}"
                        player_name = str(row['player_name'])[:16]  # length limit
                        player_name = str(row['player_name'])[:16]
                        return_rate = f"{row['return_rate']:+6.2f}%"
                        balance = f"${row['final_balance']:>13,.0f}"
                        
                        rank_text = f"{rank_num:<6} {player_name:<16} {return_rate:>12} {balance:>16}"
                        
                        rank_label = tk.Label(rank_frame, text=rank_text, 
                                            font=("Courier New", 11, "bold" if idx < 3 else "normal"),
                                            bg=bg_colors[idx], fg='#2c3e50', anchor='w')
                        rank_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)
                    
                else:
                    no_data_label = tk.Label(main_frame, text="No ranking data available yet.\nComplete a game to see rankings!", 
                                           font=self.font_big, bg='white', fg='#7f8c8d')
                    no_data_label.pack(expand=True)
                    
            except Exception as e:
                error_label = tk.Label(main_frame, text=f"Error loading ranking data:\n{str(e)}", 
                                     font=self.font_big, bg='white', fg='#e74c3c')
                error_label.pack(expand=True)
        else:
            no_file_label = tk.Label(main_frame, text="No ranking file found.\nComplete a game to create the leaderboard!", 
                                   font=self.font_big, bg='white', fg='#7f8c8d')
            no_file_label.pack(expand=True)
        
        # Buttons frame
        btn_frame = tk.Frame(main_frame, bg='white')
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Refresh button
        refresh_btn = tk.Button(btn_frame, text="Refresh", font=("Microsoft YaHei", 12), 
                               command=lambda: [ranking_window.destroy(), self.show_in_game_rankings()], 
                               width=10, bg='#27ae60', fg='white', relief=tk.FLAT)
        refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Close button
        close_btn = tk.Button(btn_frame, text="Close", font=("Microsoft YaHei", 12), 
                             command=ranking_window.destroy, width=10,
                             bg='#3498db', fg='white', relief=tk.FLAT)
        close_btn.pack(side=tk.RIGHT)
        
        

# Main function
if __name__ == "__main__":
    import sys
    #Testing
    if "test" in sys.argv:
        print("Tests begin.")
        acc = Account(initial_balance=10000, lot_size=1, name="Tester")
        
        # Test Purchase
        msg, ok = acc.buy(1000, 1)
        print("Buy Test:", msg, "OK?", ok, "Balance:", acc.balance)
        
        # Testing Floating Profit and Loss
        pnl = acc.floating_pnl(1010)
        print("Floating Profit and Loss:", pnl)
        
        # Test Position Closing
        msg, pnl = acc.close_position(1020)
        print("Close Test:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)
        
        # Test Sale
        msg, ok = acc.sell(950, 2)
        print("Sell Short Test:", msg, "OK?", ok, "Balance:", acc.balance)
        
        # Test closing short positions
        msg, pnl = acc.close_position(940)
        print("Close Short:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)
        
        print("Tests Finish.")
    else:
        root = tk.Tk()
        app = TradingGameUI(root, name="Player1")
        root.mainloop()

