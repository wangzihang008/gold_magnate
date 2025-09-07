import os
import sys
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
from datetime import datetime
import random

# 让中文/符号在各系统上尽可能正常显示
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False


# =============== 内置历史大事件（展示，不改价） ===============
BUILTIN_NEWS = {
    "2008-09-07": "The US government takes over Fannie Mae and Freddie Mac, risk aversion rises. (Bullish for gold)",
    "2008-09-15": "Lehman Brothers bankruptcy triggers global financial crisis. (Strongly bullish for gold)",
    "2008-09-16": "The Federal Reserve injects huge liquidity into the market. (Bullish for gold)",
    "2008-09-29": "The US House rejects $700 billion bailout bill. (Strongly bullish for gold)",
}

# =============== 随机突发新闻池（文本, 方向, 幅度文本, 权重） ===============
RANDOM_NEWS_POOL = [
    ("Central bank unexpectedly cuts interest rates.",                 "bullish",        "+1%", 10),
    ("Major bank reports massive losses, market panic rises.",         "strong_bullish", "+2%", 5),
    ("Oil prices surge sharply, inflation fears increase.",            "bullish",        "+1%", 10),
    ("Global stock markets rebound strongly.",                         "bearish",        "-1%", 10),
    ("Dollar strengthens significantly against major currencies.",     "bearish",        "-1%", 10),
    ("Geopolitical tensions escalate in the Middle East.",             "strong_bullish", "+2%", 5),
    ("International Monetary Fund warns of global recession.",         "bullish",        "+1%", 10),
    ("US unemployment rate falls unexpectedly.",                       "bearish",        "-1%", 10),
    ("Large fund forced liquidation sparks market turbulence.",        "strong_bearish", "-2%", 4),
]

def apply_news_impact(price: float, impact: str) -> float:
    """
    根据新闻影响调整价格
    bullish:        +1%
    strong_bullish: +2%
    bearish:        -1%
    strong_bearish: -2%
    """
    if impact == "bullish":
        return price * 1.01
    if impact == "strong_bullish":
        return price * 1.02
    if impact == "bearish":
        return price * 0.99
    if impact == "strong_bearish":
        return price * 0.98
    return price


# =============== 账户类 ===============
class Account:
    def __init__(self, initial_balance=100000.0, lot_size=1, name="Player"):
        self.name = str(name)
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.position = 0                 # >0 多头；<0 空头；=0 无持仓
        self.entry_price = 0.0            # 最近一次开仓价
        self.lot_size = lot_size
        self.name = name

    def buy(self, price, quantity):
        if self.position != 0:
            return "Existing a position, please close first.", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = quantity
            self.entry_price = price
            self.balance -= margin
            return f"Successfully long {quantity} lots @ {price:.2f}, margin used: {margin:.2f}.", True
        return "Insufficient funds to open a position.", False

    def sell(self, price, quantity):
        if self.position != 0:
            return "Existing a position, please close first.", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = -quantity
            self.entry_price = price
            self.balance -= margin
            return f"Successfully short {quantity} lots @ {price:.2f}, margin used: {margin:.2f}.", True
        return "Insufficient funds to open a position.", False

    def close_position(self, current_price):
        if self.position == 0:
            return "No positions to close.", 0.0
        pnl = (current_price - self.entry_price) * self.position * self.lot_size
        self.balance += pnl
        gloProfit.set(gloProfit.get() + pnl)  # 计入已实现盈亏（供历史曲线用）
        margin_released = abs(self.entry_price * self.position * 0.1)
        self.balance += margin_released
        pos = self.position
        self.position = 0
        self.entry_price = 0.0
        msg = (f"Position closed successfully ({'long' if pos>0 else 'short'} {abs(pos)} lots)! "
               f"Profit and loss for this period: {pnl:.2f}, released margin: {margin_released:.2f}. "
               f"Account balance: {self.balance:.2f}.")
        return msg, pnl

    def floating_pnl(self, current_price):
        if self.position == 0:
            return 0.0
        return (current_price - self.entry_price) * self.position * self.lot_size


# =============== 主界面与游戏逻辑 ===============
class TradingGameUI:
    def __init__(self, root, name="Player"):
        self.root = root
        self.player_name = name
        self.root.title(f"{self.player_name} - Gold Magnate Game 2008")

        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")
        self.font_menu = ("Microsoft YaHei", 14) # 新增菜单字体

        self.player_name = str(name)
        self.account = Account(initial_balance=100000.0, lot_size=1, name=self.player_name)

        # 数据与状态
        self.price_df = pd.DataFrame()
        self.days = []
        self.total_days = 0
        self.idx = 0
        self.price_history = []
        self.ProfitHist = np.array([])

        # 绑定变量
        global gloProfit
        gloProfit = tk.DoubleVar(value=0.0)
        self.UnrealizedProfit = tk.DoubleVar(value=0.0)

        # 游戏时长设置
        self.total_game_ms = 10 * 60 * 1000
        self.update_interval_ms = 1000
        self.timer_running = False

        # —— 新闻系统 ——（内置 + 可选自定义 + 随机突发）
        self.news_map = dict(BUILTIN_NEWS)
        self.load_custom_news()
        self.news_history = []  # 用于结算时回顾

        # UI
        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")
        self.build_ui()

        # 数据
        self.fetch_data()

        # 开始
        self.start_game()

    # ---------- 数据 ----------
    def fetch_data(self):
        """
        读取或下载 2008 年黄金期货（GC=F）日线收盘价。
        优先读取本地缓存 gold_2008.csv，否则从 Yahoo Finance 抓取。
        """
        cache_file = "gold_2008.csv"
        if os.path.exists(cache_file):
            try:
                self.price_df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                self.price_df = self.price_df[['Close']].dropna()
            except Exception:
                self.price_df = pd.DataFrame()

        if self.price_df.empty:
            try:
                # 近似 2008-01-01 ~ 2008-12-31
                period1 = 1199120400  # 2008-01-01 00:00 UTC
                period2 = 1230656400  # 2008-12-31 23:59 UTC
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
                self.price_df.to_csv(cache_file)
            except Exception as e:
                messagebox.showerror("Data loading failed", f"Unable to load data from the network: {e}")
                self.root.quit()
                return

        self.days = list(self.price_df.index)
        self.total_days = len(self.days)
        if self.total_days == 0:
            messagebox.showerror("Data Error", "No trading day data available.")
            self.root.quit()
            return

        # 按总时长均匀推进
        self.update_interval_ms = max(200, int(self.total_game_ms / self.total_days))

        first_price = float(self.price_df.iloc[0]['Close'])
        self.price_history = [first_price]
        self.log(f"Data loading completed: {self.total_days} trading days. "
                 f"Advance one day every {self.update_interval_ms} ms (total ~10 minutes).")
        self.refresh_top_panel(first_price, self.days[0])

    def load_custom_news(self):
        """从 my_news.json 读取用户自定义新闻（若存在），只用于展示不改价。"""
        file = "my_news.json"
        if not os.path.exists(file):
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                user_news = json.load(f)
            for k, v in user_news.items():
                self.news_map[k] = v if isinstance(v, str) else "；".join(map(str, v))
        except Exception as e:
            messagebox.showwarning("News loading warning", f"Failed to read my_news.json: {e}")

    def show_help_window(self):
        """Creates a new window to display the game tutorial."""
        help_win = tk.Toplevel(self.root)
        help_win.title("Game Tutorial")
        help_win.geometry("700x650")

        help_text = """
Gold Magnate 2008 - Game Tutorial

Welcome to Gold Magnate 2008! 
You can access this tutorial at any time by navigating to Menu > Help in the top menu bar.
---------------------------------------------------------------------

This is a trading simulation game where you trade gold futures based on the historical price data from the year 2008. Your goal is to maximize your profit by the end of the year.

**1. Game Interface Overview**

The main screen is divided into four key areas:

* **Top Panel (Account and Market):**
    * `Account Balance`: Shows your current available cash. A 10% margin will be deducted from this when you open a position.
    * `Position`: Displays your current trade. "None" means you have no open trades. "Long" means you've bought, expecting the price to go up. "Short" means you've sold, expecting the price to go down. It also shows the quantity and your entry price.
    * `Floating Profit and Loss`: Shows the unrealized profit or loss on your current open position. It's green for profit and red for loss.
    * `Date and Current Price`: Shows the current in-game date and the corresponding gold price.

* **Middle-Left Panel (Trading Operation):**
    * `Transaction quantity (lots)`: Enter the number of lots you wish to trade here.
    * `Buy (long)`: Click this to open a long position. You profit if the price goes up.
    * `Sell (short)`: Click this to open a short position. You profit if the price goes down.
    * `Close a position`: Click this to close your current open position and realize any profit or loss.
    * `Profit / History`: Click to view a chart of your total profit over time.
    * *Note*: You must close any existing position before you can open a new one.

* **Middle-Right Panel (Gold Price Chart):**
    * This chart visually represents the gold price over time. Use it to identify trends and make trading decisions.

* **Bottom Panels (Logs and News):**
    * `Operation Record`: A log of all your trading actions (buy, sell, close).
    * `Important news of the day`: Displays major financial news for the current day. This news can significantly impact the gold price. Pay close attention to it!

**2. How to Play**

1.  **Start:** The game starts automatically with an initial balance of $100,000. The timeline will begin to advance automatically.

2.  **Analyze:** Watch the price movement on the chart and read the daily news. Decide if you think the price will go up or down.

3.  **Enter Quantity:** Type the number of lots you want to trade into the `Transaction quantity` box.

4.  **Open a Position:**
    * If you believe the price will rise, click `Buy (long)`.
    * If you believe the price will fall, click `Sell (short)`.

5.  **Manage Your Position:** As the game progresses, your `Floating Profit and Loss` will update.

6.  **Close Your Position:** When you are ready to exit your trade, click `Close a position`. Your profit or loss will be added to your account balance, and the margin used for the trade will be returned.

7.  **Repeat:** Continue to analyze the market and make trades throughout the year.

**3. End of the Game**

The game automatically ends when the timeline reaches the end of the year 2008. Any open positions will be automatically closed at the final market price. A summary of your performance will be displayed, and your score will be saved to the leaderboard.

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
        # --- End Menu Bar ---

    # ---------- UI ----------
        # 顶部：账户与市场信息
        top = tk.LabelFrame(self.root, text="Account and Market", font=self.font_title, padx=8, pady=8)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        self.lbl_balance = tk.Label(top, text="Account Balance: 0.00", font=self.font_big)
        self.lbl_balance.pack(side=tk.LEFT, padx=(4, 16))

        self.lbl_pos = tk.Label(top, text="Position: None", font=self.font_big)
        self.lbl_pos.pack(side=tk.LEFT, padx=16)

        self.lbl_pnl = tk.Label(top, text="Floating profit and loss: 0.00", font=self.font_big)
        self.lbl_pnl.pack(side=tk.LEFT, padx=16)

        self.lbl_date_price = tk.Label(top, text="Date:  -    Price: -", font=self.font_big)
        self.lbl_date_price.pack(side=tk.RIGHT, padx=8)

        # 中部：交易面板 + 价格图
        mid = tk.Frame(self.root)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        trade = tk.LabelFrame(mid, text="Trading Operation", font=self.font_title, padx=8, pady=8)
        trade.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        tk.Label(trade, text="Transaction quantity (lots):", font=self.font_big).pack(anchor="w")
        self.entry_qty = tk.Entry(trade, width=8, font=self.font_big)
        self.entry_qty.insert(0, "1")
        self.entry_qty.pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(trade)
        btns.pack(anchor="w", pady=4)
        tk.Button(btns, text="Buy (long)",  font=self.font_big, command=self.buy_action,  width=10).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(btns, text="Sell (short)", font=self.font_big, command=self.sell_action, width=10).grid(row=0, column=1, padx=4, pady=4)
        tk.Button(btns, text="Close a position", font=self.font_big, command=self.close_action, width=22).grid(row=1, column=0, columnspan=2, padx=4, pady=4)

        tk.Label(trade, text="Note: 10% margin; close an existing position before opening a new one.",
                 font=("Microsoft YaHei", 12)).pack(anchor="w", pady=(6, 0))

        pf = tk.Frame(trade)
        pf.pack(anchor="center", pady=4)

        tk.Button(pf, text="Profit", font=self.font_big, command=self.getProfitChart, width=20).grid(row=0, column=0, padx=4, pady=4)
        
        
        chart_frame = tk.LabelFrame(mid, text="Gold Price Chart", font=self.font_title, padx=8, pady=8)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig, self.ax = plt.subplots(figsize=(7, 4))
        self.ax.set_title("Gold Price Chart (2008, GC=F)", fontsize=16, fontweight='bold')
        self.ax.set_ylabel("Price (USD)", fontsize=12)
        self.ax.grid(True)
        (self.line,) = self.ax.plot([], [], linewidth=1.8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 底部：日志 + 新闻
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=8, pady=(4, 8))

        log_frame = tk.LabelFrame(bottom, text="Operation Record", font=self.font_title, padx=8, pady=8)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=10, font=self.font_big, state=tk.NORMAL)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        news_frame = tk.LabelFrame(bottom, text="Important news of the day", font=self.font_title, padx=8, pady=8)
        news_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.txt_news = scrolledtext.ScrolledText(news_frame, height=10, font=self.font_big, state=tk.DISABLED, wrap=tk.WORD)
        self.txt_news.pack(fill=tk.BOTH, expand=True)

    # ---------- 日志 ----------
    def log(self, msg: str):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    # ---------- 新闻显示（带颜色） ----------
    def set_news(self, text: str, color: str = "black"):
        self.txt_news.config(state=tk.NORMAL)
        self.txt_news.delete("1.0", tk.END)
        if text:
            self.txt_news.insert(tk.END, text, ("color",))
            self.txt_news.tag_config("color", foreground=color)
        self.txt_news.config(state=tk.DISABLED)

    # ---------- 顶部信息刷新 ----------
    def refresh_top_panel(self, price, day):
        self.lbl_balance.config(text=f"Account balance: {self.account.balance:.2f}")
        if self.account.position == 0:
            pos_text = "None"
            pnl_text = "0.00"
            pnl_color = "black"
        else:
            pos_text = f"{'Long' if self.account.position>0 else 'Short'} ({abs(self.account.position)} lots @ {self.account.entry_price:.2f})"
            pnl = self.account.floating_pnl(price)
            pnl_text = f"{pnl:.2f}"
            pnl_color = ("green" if pnl >= 0 else "red")
        self.lbl_pos.config(text=f"Positions: {pos_text}")
        self.lbl_pnl.config(text=f"Floating profit and loss: {pnl_text}", fg=pnl_color)
        self.lbl_date_price.config(text=f"Date: {day.strftime('%Y-%m-%d')}   Current Price: {price:.2f}")

    # ---------- 主循环 ----------
    def start_game(self):
        self.timer_running = True
        self.root.after(self.update_interval_ms, self.tick)

    def tick(self):
        """
        推进一天：
        1) 读取当天基准收盘价
        2) 若当日无内置新闻，则以概率触发突发新闻并调整价格
        3) 更新图表/盈亏/新闻/日志
        """
        if not self.timer_running:
            return

        if self.idx >= self.total_days:
            self.end_game()
            return

        day = self.days[self.idx]
        dstr = day.strftime("%Y-%m-%d")
        base_price = float(self.price_df.iloc[self.idx]['Close'])
        price = base_price

        # 默认新闻展示
        news_text = self.news_map.get(dstr, "")
        news_color = "black"

        # 无内置新闻 -> 20% 概率触发突发新闻（按权重抽样）
        if not news_text and random.random() < 0.2:
            news, impact, impact_text, _weight = random.choices(
                RANDOM_NEWS_POOL,
                weights=[item[3] for item in RANDOM_NEWS_POOL],
                k=1
            )[0]
            old_price = price
            price = apply_news_impact(price, impact)  # 根据新闻影响调整价格

            news_text = f"{news} (Impact on gold: {impact_text})"
            self.news_map[dstr] = news_text

            # 着色
            if "bullish" in impact:
                news_color = "green"
            elif "bearish" in impact:
                news_color = "red"

            # 记录日志与历史
            change_pct = ((price - old_price) / old_price) * 100
            self.log(f"{dstr} News impact: {news} → Gold price changed {change_pct:+.2f}%")
            self.news_history.append(f"{dstr}: {news} (Impact: {impact_text}, Price Change: {change_pct:+.2f}%)")

        # ——— 更新价格曲线 ———
        self.price_history.append(price)
        self.line.set_data(range(len(self.price_history)), self.price_history)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

        # ——— 更新盈亏 ———
        self.UnrealizedProfit.set(self.account.floating_pnl(price))
        self.ProfitHist = np.append(self.ProfitHist, gloProfit.get() + self.UnrealizedProfit.get())

        # 新闻&顶部信息
        self.set_news(news_text, news_color)
        self.refresh_top_panel(price, day)

        self.idx += 1
        self.root.after(self.update_interval_ms, self.tick)

    # ---------- 交易 ----------
    def _current_trade_price(self):
        use_idx = max(0, self.idx - 1)
        return float(self.price_df.iloc[use_idx]['Close']), self.days[use_idx]

    def _get_qty(self):
        try:
            qty = int(self.entry_qty.get().strip())
            if qty <= 0:
                raise ValueError
            return qty
        except Exception:
            messagebox.showerror("Input Error", "Please enter a valid lot size (positive integer).")
            return None

    def buy_action(self):
        qty = self._get_qty()
        if qty is None:
           return
    # Check if qty is a positive integer 
        if not isinstance(qty, int) or qty <= 0:
           messagebox.showwarning("Invalid enter, please enter a positive integer.")
           return

        price, day = self._current_trade_price()
        msg, ok = self.account.buy(price, qty)
        if ok:
          self.log(f"{day.strftime('%Y-%m-%d')} long {qty} lots @ {price:.2f} → {msg}")
          self.refresh_top_panel(price, day)
        else:
           messagebox.showerror("Transaction Failure", msg)


    def sell_action(self):
        qty = self._get_qty()
        if qty is None:
            return
      # Check if qty is a positive integer 
        if not isinstance(qty, int) or qty <= 0:
            messagebox.showwarning("Invalid enter, please enter a positive integer.")
            return
        price, day = self._current_trade_price()
        msg, ok = self.account.sell(price, qty)
        if ok:
            self.log(f"{day.strftime('%Y-%m-%d')} short {qty} lots @ {price:.2f} → {msg}")
            self.refresh_top_panel(price, day)
        else:
            messagebox.showerror("Transaction Failure", msg)

    def close_action(self):
        price, day = self._current_trade_price()
        msg, pnl = self.account.close_position(price)

        if "No positions" in msg:
           messagebox.showerror(
            "Transaction Failure",
            f"{msg}\n You must open a long or short position first."
        )
        else:
             self.log(f"{day.strftime('%Y-%m-%d')} close a position @ {price:.2f} → {msg}")
             self.refresh_top_panel(price, day)


    # ---------- 盈亏历史小窗 ----------
    def drawChart(self):
        self.ax2.clear()
        self.ax2.plot(self.ProfitHist, marker='o', label='Profit')
        self.ax2.set_title("Profit History", fontsize=14)
        self.ax2.set_xlabel("Time", fontsize=12)
        self.ax2.set_ylabel("Profit", fontsize=12)
        if len(self.ProfitHist) > 0:
            self.ax2.axhline(y=self.ProfitHist[-1], linestyle="--", label=f"Profit: {self.ProfitHist[-1]:.2f}")
        self.ax2.legend(loc='upper left')
        self.ax2.relim()
        self.ax2.autoscale_view()
        self.canvas2.draw()
        self.profitRoot.after(self.update_interval_ms, self.drawChart)

    def getProfitChart(self):
        self.profitRoot = tk.Toplevel(self.root)
        self.profitRoot.title("Profit History")
        self.profitRoot.geometry("1200x800")
        self.fig2, self.ax2 = plt.subplots(figsize=(5, 3))
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.profitRoot)
        self.canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.drawChart()

    # ---------- 结束结算 ----------
    def end_game(self):
        self.timer_running = False
        last_price = float(self.price_df.iloc[-1]['Close'])
        if self.account.position != 0:
           msg, pnl = self.account.close_position(last_price)
           self.log(f"Automatically close a position (last day @ {last_price:.2f}): {msg}")

        final_balance = self.account.balance
        pl = final_balance - self.account.initial_balance
        rr = (pl / self.account.initial_balance) * 100.0

    # 保存游戏结果
        df = self.save_game_result(final_balance, pl, rr)

    # 获取排名信息
        current_ranking, total_players = self.get_player_ranking(df)

    # 构造提示信息
        result_msg = (
                   f"Final account balance: {final_balance:.2f}\n"
                   f"Total profit and loss: {pl:.2f}\n"
                   f"Return on investment: {rr:.2f}%"
        )
        if current_ranking:
           result_msg += f"\n\nYour Ranking: #{current_ranking} out of {total_players} players!"

    # 弹窗提示
        messagebox.showinfo("Game over", result_msg)

    # 展示排行榜
        self.show_rankings(df, current_ranking, total_players, rr)

    # 关闭窗口
        self.root.quit()

    def save_game_result(self, final_balance, pl, rr):
        """保存游戏结果到CSV文件"""
        csv_file = "game_rankings_2008.csv"
        
        # 创建新记录
        new_record = {
            'player_name': self.player_name,
            'final_balance': final_balance,
            'profit_loss': pl,
            'return_rate': rr,
            'play_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 读取现有数据或创建新DataFrame
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
            except:
                df = pd.DataFrame()
        else:
            df = pd.DataFrame()
        
        # 添加新记录
        new_df = pd.DataFrame([new_record])
        df = pd.concat([df, new_df], ignore_index=True)
        
        # 保存到CSV
        df.to_csv(csv_file, index=False)
        
        return df
    
    def get_player_ranking(self, df):
        """获取当前玩家在所有记录中的排名"""
        if df.empty:
            return None, 0
        
        # 按回报率排序
        df_sorted = df.sort_values('return_rate', ascending=False).reset_index(drop=True)
        
        # 找到当前玩家最新记录的排名
        current_record = df_sorted[df_sorted['player_name'] == self.player_name].iloc[-1:]
        if not current_record.empty:
            ranking = df_sorted.index[df_sorted['return_rate'] == current_record['return_rate'].iloc[0]][0] + 1
            total_players = len(df_sorted)
            return ranking, total_players
        
        return None, len(df_sorted)
    
    def show_rankings(self, df, current_ranking, total_players, current_rr):
        """显示排行榜窗口"""
        ranking_window = tk.Toplevel(self.root)
        ranking_window.title("Game Rankings - 2008 Original")
        ranking_window.geometry("600x500")
        ranking_window.configure(bg='white')
        
        # 主框架
        main_frame = tk.Frame(ranking_window, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 标题
        title_label = tk.Label(main_frame, text="🏆 Game Rankings - 2008 Original", 
                              font=self.font_title, bg='white', fg='#2c3e50')
        title_label.pack(pady=(0, 20))
        
        # 当前玩家排名
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
        
        # 分隔线
        separator = tk.Frame(main_frame, height=2, bg='#bdc3c7')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        # 排行榜标题
        top5_label = tk.Label(main_frame, text="🥇 Top 5 Players", 
                             font=("Microsoft YaHei", 18, "bold"), 
                             bg='white', fg='#2c3e50')
        top5_label.pack(pady=(0, 15))
        
        # 排行榜内容
        if not df.empty:
            # 按回报率排序并去重（每个玩家只显示最佳成绩）
            df_best = df.loc[df.groupby('player_name')['return_rate'].idxmax()]
            df_sorted = df_best.sort_values('return_rate', ascending=False).head(5)
            
            # 创建排行榜框架
            ranking_frame = tk.Frame(main_frame, bg='white')
            ranking_frame.pack(fill=tk.BOTH, expand=True)
            
            medals = ['🥇', '🥈', '🥉', '🏅', '🏅']
            colors = ['#ffd700', '#c0c0c0', '#cd7f32', '#4a90e2', '#4a90e2']
            
            for idx, (_, row) in enumerate(df_sorted.iterrows()):
                medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
                color = colors[idx] if idx < len(colors) else '#7f8c8d'
                
                # 每个排名的框架
                rank_frame = tk.Frame(ranking_frame, bg='white')
                rank_frame.pack(fill=tk.X, pady=5)
                
                # 排名文本
                rank_text = f"{medal} {row['player_name']:>15} | Return: {row['return_rate']:>8.2f}% | Balance: ${row['final_balance']:>10,.2f}"
                
                rank_label = tk.Label(rank_frame, text=rank_text, 
                                     font=("Courier New", 14, "bold" if idx < 3 else "normal"),
                                     bg='white', fg=color, anchor='w')
                rank_label.pack(fill=tk.X)
        else:
            no_data_label = tk.Label(main_frame, text="No ranking data available yet.", 
                                   font=self.font_big, bg='white', fg='#7f8c8d')
            no_data_label.pack()
        
        # 关闭按钮
        close_btn = tk.Button(main_frame, text="Close", font=self.font_big, 
                             command=ranking_window.destroy, width=15,
                             bg='#3498db', fg='white', relief=tk.FLAT)
        close_btn.pack(pady=(20, 0))

#主程序入口
if __name__ == "__main__":
    import sys
    # 可在终端中输入‘python game.py test’来测试以下功能是否能成功实现
    
    if "test" in sys.argv:
        print("Tests begin.")
        acc = Account(initial_balance=10000, lot_size=1)
        
        # 测试买入
        msg, ok = acc.buy(1000, 1)
        print("Buy Test:", msg, "OK?" , ok, "Balance:", acc.balance)

        # 测试浮盈亏
        pnl = acc.floating_pnl(1010)
        print("Floating Profit and Loss:", pnl)

        # 测试平仓
        msg, pnl = acc.close_position(1020)
        print("Close Test:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)
        
        # 测试卖出
        msg, ok = acc.sell(950, 2)
        print("Sell Test:", msg, "OK?", ok, "Balance:", acc.balance)

        msg, pnl = acc.close_position(940)
        print("Close Short:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)

        print("Tests finish.")
    else:
        root = tk.Tk()
        app = TradingGameUI(root)
        root.mainloop()

        news_review = ("\n\nNews Review:\n" + "\n".join(self.news_history)) if self.news_history \
                      else "\n\n(No major random news was triggered during the game.)"

        messagebox.showinfo(
            "Game over",
            f"Player: {self.player_name}\n"
            f"Final account balance: {final_balance:.2f}\n"
            f"Total profit and loss: {pl:.2f}\n"
            f"Return on investment: {rr:.2f}%"
            f"{news_review}"
        )
        self.root.quit()

