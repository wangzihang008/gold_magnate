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

matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False

#2008年重要新闻
BUILTIN_NEWS = {
    "2008-09-07": "美国政府接管房利美和房地美，避险升温。（利好黄金）",
    "2008-09-15": "雷曼兄弟破产，全球金融危机爆发。（极大利好黄金）",
    "2008-09-16": "美联储向市场注入巨额流动性。（利好黄金）",
    "2008-09-29": "美国众议院否决7000亿美元救助法案。（极大利好黄金）",
}

#账户
class Account:
    def __init__(self, initial_balance=100000.0, lot_size=1):
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.position = 0  
        self.entry_price = 0.0
        self.lot_size = lot_size 

    def buy(self, price, quantity):
        if self.position != 0:
            return "已有持仓，请先平仓。", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = quantity
            self.entry_price = price
            self.balance -= margin
            return f"成功买入 {quantity} 手 @ {price:.2f}，占用保证金 {margin:.2f}。", True
        return "资金不足，无法开仓。", False

    def sell(self, price, quantity):
        if self.position != 0:
            return "已有持仓，请先平仓。", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = -quantity
            self.entry_price = price
            self.balance -= margin
            return f"成功做空 {quantity} 手 @ {price:.2f}，占用保证金 {margin:.2f}。", True
        return "资金不足，无法开仓。", False

    def close_position(self, current_price):
        if self.position == 0:
            return "没有持仓可平。", 0.0
        pnl = (current_price - self.entry_price) * self.position * self.lot_size
        self.balance += pnl
        margin_released = abs(self.entry_price * self.position * 0.1)
        self.balance += margin_released
        pos = self.position
        self.position = 0
        self.entry_price = 0.0
        msg = f"平仓成功（{'多' if pos>0 else '空'} {abs(pos)} 手）！本次盈亏：{pnl:.2f}，释放保证金：{margin_released:.2f}。账户余额：{self.balance:.2f}。"
        return msg, pnl

    def floating_pnl(self, current_price):
        if self.position == 0:
            return 0.0
        return (current_price - self.entry_price) * self.position * self.lot_size

#主界面
class TradingGameUI:
    def __init__(self, root):
        self.root = root
        self.root.title("黄金交易员手札 2008")

        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")

        self.account = Account(initial_balance=100000.0, lot_size=1)
        self.price_df = pd.DataFrame()
        self.days = []
        self.total_days = 0
        self.idx = 0
        self.price_history = []

        self.total_game_ms = 10 * 60 * 1000  
        self.update_interval_ms = 1000 
        self.timer_running = False

        self.news_map = dict(BUILTIN_NEWS)
        self.load_my_news()

        self.build_ui()
        self.fetch_data()
        self.start_game()

    def fetch_data(self):
        cache_file = "gold_2008.csv"
        if os.path.exists(cache_file):
            try:
                self.price_df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                self.price_df = self.price_df[['Close']].dropna()
            except Exception:
                self.price_df = pd.DataFrame()

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
                self.price_df.to_csv(cache_file)
            except Exception as e:
                messagebox.showerror("数据加载失败", f"无法从网络加载数据：{e}")
                self.root.quit()
                return

        self.days = list(self.price_df.index)
        self.total_days = len(self.days)
        if self.total_days == 0:
            messagebox.showerror("数据错误", "没有可用的交易日数据。")
            self.root.quit()
            return

        self.update_interval_ms = max(200, int(self.total_game_ms / self.total_days))

        first_price = float(self.price_df.iloc[0]['Close'])
        self.price_history = [first_price]
        self.log(f"数据加载完成：{self.total_days} 个交易日。将以每 {self.update_interval_ms} ms 推进一天（总时长约10分钟）。")
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
                    self.news_map[k] = "；".join(str(x) for x in v)
                else:
                    self.news_map[k] = str(v)
        except Exception as e:
            messagebox.showwarning("新闻加载警告", f"读取 my_news.json 失败：{e}")

    def build_ui(self):
        top = tk.LabelFrame(self.root, text="账户与市场", font=self.font_title, padx=8, pady=8)
        top.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        self.lbl_balance = tk.Label(top, text="账户余额: 0.00", font=self.font_big)
        self.lbl_balance.pack(side=tk.LEFT, padx=(4, 16))

        self.lbl_pos = tk.Label(top, text="持仓: 无", font=self.font_big)
        self.lbl_pos.pack(side=tk.LEFT, padx=16)

        self.lbl_pnl = tk.Label(top, text="浮动盈亏: 0.00", font=self.font_big)
        self.lbl_pnl.pack(side=tk.LEFT, padx=16)

        self.lbl_date_price = tk.Label(top, text="日期:  -    价格: -", font=self.font_big)
        self.lbl_date_price.pack(side=tk.RIGHT, padx=8)

        mid = tk.Frame(self.root)
        mid.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=4)

        trade = tk.LabelFrame(mid, text="交易操作", font=self.font_title, padx=8, pady=8)
        trade.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        tk.Label(trade, text="交易数量（手）:", font=self.font_big).pack(anchor="w")
        self.entry_qty = tk.Entry(trade, width=8, font=self.font_big)
        self.entry_qty.insert(0, "1")
        self.entry_qty.pack(anchor="w", pady=(0, 8))

        btns = tk.Frame(trade)
        btns.pack(anchor="w", pady=4)
        tk.Button(btns, text="买入（多）", font=self.font_big, command=self.buy_action, width=10).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(btns, text="卖出（空）", font=self.font_big, command=self.sell_action, width=10).grid(row=0, column=1, padx=4, pady=4)
        tk.Button(btns, text="平仓", font=self.font_big, command=self.close_action, width=10).grid(row=1, column=0, columnspan=2, padx=4, pady=4)

        tk.Label(trade, text="说明：10% 保证金；先平仓再反向开仓。", font=("Microsoft YaHei", 12)).pack(anchor="w", pady=(6, 0))

        chart_frame = tk.LabelFrame(mid, text="黄金价格走势图", font=self.font_title, padx=8, pady=8)
        chart_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig, self.ax = plt.subplots(figsize=(7, 4))
        self.ax.set_title("黄金价格走势图（2008，GC=F）", fontsize=16, fontweight='bold')
        self.ax.set_ylabel("价格（美元）", fontsize=12)
        self.ax.grid(True)
        (self.line,) = self.ax.plot([], [], linewidth=1.8)

        self.canvas = FigureCanvasTkAgg(self.fig, master=chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=8, pady=(4, 8))

        log_frame = tk.LabelFrame(bottom, text="操作记录", font=self.font_title, padx=8, pady=8)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=10, font=self.font_big, state=tk.NORMAL)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        news_frame = tk.LabelFrame(bottom, text="当天重要新闻", font=self.font_title, padx=8, pady=8)
        news_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.txt_news = scrolledtext.ScrolledText(news_frame, height=10, font=self.font_big, state=tk.DISABLED, wrap=tk.WORD)
        self.txt_news.pack(fill=tk.BOTH, expand=True)

    #日志与新闻显示
    def log(self, msg):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    def set_news(self, text):
        self.txt_news.config(state=tk.NORMAL)
        self.txt_news.delete("1.0", tk.END)
        if text:
            self.txt_news.insert(tk.END, text)
        self.txt_news.config(state=tk.DISABLED)

    #刷新顶部显示
    def refresh_top_panel(self, price, day):
        self.lbl_balance.config(text=f"账户余额: {self.account.balance:.2f}")
        if self.account.position == 0:
            pos_text = "无"
            pnl_text = "0.00"
            pnl_color = "black"
        else:
            pos_text = f"{'多头' if self.account.position>0 else '空头'}（{abs(self.account.position)} 手 @ {self.account.entry_price:.2f}）"
            pnl = self.account.floating_pnl(price)
            pnl_text = f"{pnl:.2f}"
            pnl_color = ("green" if pnl >= 0 else "red")
        self.lbl_pos.config(text=f"持仓: {pos_text}")
        self.lbl_pnl.config(text=f"浮动盈亏: {pnl_text}", fg=pnl_color)
        self.lbl_date_price.config(text=f"日期: {day.strftime('%Y-%m-%d')}    当前价格: {price:.2f}")

    #开始/推进
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

        dstr = day.strftime("%Y-%m-%d")
        news_text = self.news_map.get(dstr, "")
        self.set_news(news_text)

        self.refresh_top_panel(price, day)

        self.idx += 1

        self.root.after(self.update_interval_ms, self.tick)

    #交易动作
    def _current_trade_price(self):
        use_idx = max(0, self.idx - 1)
        return float(self.price_df.iloc[use_idx]['Close']), self.days[use_idx]

    def buy_action(self):
        qty = self._get_qty()
        if qty is None:
            return
        price, day = self._current_trade_price()
        msg, ok = self.account.buy(price, qty)
        self.log(f"{day.strftime('%Y-%m-%d')}  买入 {qty} 手 @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def sell_action(self):
        qty = self._get_qty()
        if qty is None:
            return
        price, day = self._current_trade_price()
        msg, ok = self.account.sell(price, qty)
        self.log(f"{day.strftime('%Y-%m-%d')}  做空 {qty} 手 @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def close_action(self):
        price, day = self._current_trade_price()
        msg, pnl = self.account.close_position(price)
        self.log(f"{day.strftime('%Y-%m-%d')}  平仓 @ {price:.2f} → {msg}")
        self.refresh_top_panel(price, day)

    def _get_qty(self):
        try:
            qty = int(self.entry_qty.get().strip())
            if qty <= 0:
                raise ValueError
            return qty
        except Exception:
            messagebox.showerror("输入错误", "请输入有效的手数（正整数）")
            return None

    #结束结算
    def end_game(self):
        self.timer_running = False
        last_price = float(self.price_df.iloc[-1]['Close'])
        if self.account.position != 0:
            msg, pnl = self.account.close_position(last_price)
            self.log(f"自动平仓（最后一日 @ {last_price:.2f}）：{msg}")

        final_balance = self.account.balance
        pl = final_balance - self.account.initial_balance
        rr = (pl / self.account.initial_balance) * 100.0
        messagebox.showinfo("游戏结束",
                            f"最终账户余额: {final_balance:.2f}\n总盈亏: {pl:.2f}\n投资回报率: {rr:.2f}%")
        self.root.quit()

#入口
if __name__ == "__main__":
    root = tk.Tk()
    app = TradingGameUI(root)
    root.mainloop()
