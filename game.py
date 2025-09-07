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
        self.root.title("Gold Magnate Game 2008")

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

    # ---------- UI ----------
    def build_ui(self):
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
        pf.pack(anchor="w", pady=4)
        tk.Button(pf, text="Profit",  font=self.font_big, command=self.getProfitChart, width=10).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(pf, text="History", font=self.font_big, command=self.getProfitChart, width=10).grid(row=0, column=1, padx=4, pady=4)

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
            messagebox.showerror("Transaction Failure", msg)
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


# =============== Main（含你的测试段落） ===============
if __name__ == "__main__":
    # 如果带 test 参数：只跑账户单元测试；否则启动游戏
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
