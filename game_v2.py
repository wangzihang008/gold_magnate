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
from datetime import datetime

# Make sure Chinese characters / symbols render correctly across platforms
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'Arial']
matplotlib.rcParams['axes.unicode_minus'] = False


# =============== Built-in historical events (display only; DO NOT alter price) ===============
BUILTIN_NEWS = {
    "2008-09-07": "The US government takes over Fannie Mae and Freddie Mac, risk aversion rises. (Bullish for gold)",
    "2008-09-15": "Lehman Brothers bankruptcy triggers global financial crisis. (Strongly bullish for gold)",
    "2008-09-16": "The Federal Reserve injects huge liquidity into the market. (Bullish for gold)",
    "2008-09-29": "The US House rejects $700 billion bailout bill. (Strongly bullish for gold)",
}

# =============== Random breaking news pool: (text, direction, impact_text, weight) ===============
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
    Adjust the price according to a qualitative impact label.

    Args:
        price (float): Current price.
        impact (str): One of {"bullish", "strong_bullish", "bearish", "strong_bearish"}.

    Returns:
        float: Price after the impact multiplier is applied.
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


# =============== Account ===============
class Account:
    """
    A simple margin account for the game.
    - Uses 10% margin for opening positions.
    - Tracks one net position at a time (positive=long, negative=short, zero=flat).
    - Records realized P&L into a global tkinter DoubleVar `gloProfit` for plotting.
    """

    def __init__(self, initial_balance: float = 100000.0, lot_size: int = 1, name: str = "Player"):
        """
        Args:
            initial_balance (float): Starting cash balance.
            lot_size (int): Multiplier applied to P&L per unit price change.
            name (str): Display name for the account owner.
        """
        self.name = str(name)
        self.initial_balance = float(initial_balance)
        self.balance = float(initial_balance)
        self.position = 0               # >0 long; <0 short; =0 no position
        self.entry_price = 0.0          # last entry price
        self.lot_size = int(lot_size)

    def buy(self, price: float, quantity: int):
        """
        Open a long position.

        Returns:
            tuple[str, bool]: (message, success_flag)
        """
        if self.position != 0:
            return "Existing a position, please close first.", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = quantity
            self.entry_price = price
            self.balance -= margin
            return (f"Successfully long {quantity} lots @ {price:.2f}, "
                    f"margin used: {margin:.2f}."), True
        return "Insufficient funds to open a position.", False

    def sell(self, price: float, quantity: int):
        """
        Open a short position.

        Returns:
            tuple[str, bool]: (message, success_flag)
        """
        if self.position != 0:
            return "Existing a position, please close first.", False
        margin = price * quantity * 0.1
        if self.balance >= margin:
            self.position = -quantity
            self.entry_price = price
            self.balance -= margin
            return (f"Successfully short {quantity} lots @ {price:.2f}, "
                    f"margin used: {margin:.2f}."), True
        return "Insufficient funds to open a position.", False

    def close_position(self, current_price: float):
        """
        Close the current position, realize P&L, and release margin.

        Args:
            current_price (float): Price at which the position is closed.

        Returns:
            tuple[str, float]: (message, realized_pnl)
        """
        if self.position == 0:
            return "No positions to close.", 0.0

        pnl = (current_price - self.entry_price) * self.position * self.lot_size
        self.balance += pnl

        # record realized P&L for the profit history chart
        gloProfit.set(gloProfit.get() + pnl)

        # release margin
        margin_released = abs(self.entry_price * self.position * 0.1)
        self.balance += margin_released

        pos = self.position
        self.position = 0
        self.entry_price = 0.0
        msg = (f"Position closed successfully ({'long' if pos > 0 else 'short'} {abs(pos)} lots)! "
               f"Profit and loss for this period: {pnl:.2f}, released margin: {margin_released:.2f}. "
               f"Account balance: {self.balance:.2f}.")
        return msg, pnl

    def floating_pnl(self, current_price: float) -> float:
        """
        Compute current unrealized P&L at `current_price`.

        Returns:
            float: Unrealized profit/loss (0 if flat).
        """
        if self.position == 0:
            return 0.0
        return (current_price - self.entry_price) * self.position * self.lot_size


# =============== Main UI & Game Logic ===============
class TradingGameUI:
    """
    Controls the entire game:
    - Loads historical prices (2008 GC=F) from cache or Yahoo Finance.
    - Advances the timeline, potentially triggering random news and price adjustments.
    - Provides trading operations (buy, sell, close).
    - Tracks and plots profit history; shows daily news with coloring cues.
    - Persists results to `ranking.csv` and displays a leaderboard.
    """

    def __init__(self, root, name: str = "Player"):
        """
        Args:
            root: tk.Tk root window.
            name (str): Player name to be displayed in the final summary and leaderboard.
        """
        self.root = root
        self.root.title("Gold Magnate Game 2008")

        self.player_name = str(name)
        self.account = Account(initial_balance=100000.0, lot_size=1, name=self.player_name)

        # Data & state
        self.price_df = pd.DataFrame()
        self.days = []
        self.total_days = 0
        self.idx = 0
        self.price_history = []
        self.ProfitHist = np.array([])

        # Tk variables for profit tracking
        global gloProfit
        gloProfit = tk.DoubleVar(value=0.0)       # realized P&L
        self.UnrealizedProfit = tk.DoubleVar(value=0.0)

        # Game pacing (total ~10 minutes; step interval is derived from # of days)
        self.total_game_ms = 10 * 60 * 1000
        self.update_interval_ms = 1000
        self.timer_running = False

        # —— News system —— (built-in + optional user news + random events)
        self.news_map = dict(BUILTIN_NEWS)
        self.load_custom_news()
        self.news_history = []  # collected for end-of-game review

        # Build UI and load data
        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")
        self.build_ui()
        self.fetch_data()

        # Start the timeline
        self.start_game()

    # ---------- Data ----------
    def fetch_data(self):
        """
        Load daily close prices of 2008 COMEX gold futures (GC=F).
        - Prefer local cache `gold_2008.csv`.
        - Fallback: query Yahoo Finance JSON API.
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
                # Approx. 2008-01-01 ~ 2008-12-31 (epoch seconds, UTC)
                period1 = 1199120400
                period2 = 1230656400
                url = (
                    "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
                    f"?symbol=GC=F&period1={period1}&period2={period2}&interval=1d"
                )
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

        # Derive step interval from total duration
        self.update_interval_ms = max(200, int(self.total_game_ms / self.total_days))

        first_price = float(self.price_df.iloc[0]['Close'])
        self.price_history = [first_price]
        self.log(
            f"Data loading completed: {self.total_days} trading days. "
            f"Advance one day every {self.update_interval_ms} ms (total ~10 minutes)."
        )
        self.refresh_top_panel(first_price, self.days[0])

    def load_custom_news(self):
        """
        Read optional user-defined news from `my_news.json`.
        The news are for display only; they do not move prices.
        Expected format (dict): {"YYYY-MM-DD": "text", ...}
        """
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
        """Create all UI widgets: top info panel, trading panel, chart, log, news, and leaderboard button."""
        # Top: account & market info
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

        # Middle: trading panel + price chart
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
        tk.Button(btns, text="Buy (long)",  font=self.font_big, command=self.buy_action,  width=10)\
            .grid(row=0, column=0, padx=4, pady=4)
        tk.Button(btns, text="Sell (short)", font=self.font_big, command=self.sell_action, width=10)\
            .grid(row=0, column=1, padx=4, pady=4)
        tk.Button(btns, text="Close a position", font=self.font_big, command=self.close_action, width=22)\
            .grid(row=1, column=0, columnspan=2, padx=4, pady=4)

        tk.Label(
            trade,
            text="Note: 10% margin; close an existing position before opening a new one.",
            font=("Microsoft YaHei", 12),
        ).pack(anchor="w", pady=(6, 0))

        pf = tk.Frame(trade)
        pf.pack(anchor="w", pady=4)
        tk.Button(pf, text="Profit",  font=self.font_big, command=self.getProfitChart, width=10)\
            .grid(row=0, column=0, padx=4, pady=4)
        tk.Button(pf, text="Leaderboard", font=self.font_big, command=self.show_leaderboard, width=12)\
            .grid(row=0, column=1, padx=4, pady=4)

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

        # Bottom: log + news
        bottom = tk.Frame(self.root)
        bottom.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=False, padx=8, pady=(4, 8))

        log_frame = tk.LabelFrame(bottom, text="Operation Record", font=self.font_title, padx=8, pady=8)
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=10, font=self.font_big, state=tk.NORMAL)
        self.txt_log.pack(fill=tk.BOTH, expand=True)

        news_frame = tk.LabelFrame(bottom, text="Important news of the day", font=self.font_title, padx=8, pady=8)
        news_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.txt_news = scrolledtext.ScrolledText(news_frame, height=10, font=self.font_big,
                                                  state=tk.DISABLED, wrap=tk.WORD)
        self.txt_news.pack(fill=tk.BOTH, expand=True)

    # ---------- Logging ----------
    def log(self, msg: str):
        """Append a line to the operation log widget."""
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)

    # ---------- News display with coloring ----------
    def set_news(self, text: str, color: str = "black"):
        """Show the news string with a given foreground color."""
        self.txt_news.config(state=tk.NORMAL)
        self.txt_news.delete("1.0", tk.END)
        if text:
            self.txt_news.insert(tk.END, text, ("color",))
            self.txt_news.tag_config("color", foreground=color)
        self.txt_news.config(state=tk.DISABLED)

    # ---------- Top panel refresh ----------
    def refresh_top_panel(self, price, day):
        """Refresh top labels: balance, position, floating P&L, and date/price."""
        self.lbl_balance.config(text=f"Account balance: {self.account.balance:.2f}")
        if self.account.position == 0:
            pos_text = "None"
            pnl_text = "0.00"
            pnl_color = "black"
        else:
            pos_text = (f"{'Long' if self.account.position > 0 else 'Short'} "
                        f"({abs(self.account.position)} lots @ {self.account.entry_price:.2f})")
            pnl = self.account.floating_pnl(price)
            pnl_text = f"{pnl:.2f}"
            pnl_color = "green" if pnl >= 0 else "red"
        self.lbl_pos.config(text=f"Positions: {pos_text}")
        self.lbl_pnl.config(text=f"Floating profit and loss: {pnl_text}", fg=pnl_color)
        self.lbl_date_price.config(text=f"Date: {day.strftime('%Y-%m-%d')}   Current Price: {price:.2f}")

    # ---------- Main loop control ----------
    def start_game(self):
        """Start the periodic timer that advances the trading days."""
        self.timer_running = True
        self.root.after(self.update_interval_ms, self.tick)

    def tick(self):
        """
        Advance one trading day:
        1) Read the base close price of the day.
        2) If no built-in news, trigger a random event with 20% probability and adjust price.
        3) Update chart / P&L / news / log.
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

        # Default news (if any)
        news_text = self.news_map.get(dstr, "")
        news_color = "black"

        # If no built-in news: 20% chance to trigger a random event (weighted sampling)
        if not news_text and random.random() < 0.2:
            news, impact, impact_text, _weight = random.choices(
                RANDOM_NEWS_POOL,
                weights=[item[3] for item in RANDOM_NEWS_POOL],
                k=1
            )[0]
            old_price = price
            price = apply_news_impact(price, impact)

            news_text = f"{news} (Impact on gold: {impact_text})"
            self.news_map[dstr] = news_text

            # Coloring by direction
            if "bullish" in impact:
                news_color = "green"
            elif "bearish" in impact:
                news_color = "red"

            # Log and collect for review
            change_pct = ((price - old_price) / old_price) * 100
            self.log(f"{dstr} News impact: {news} → Gold price changed {change_pct:+.2f}%")
            self.news_history.append(
                f"{dstr}: {news} (Impact: {impact_text}, Price Change: {change_pct:+.2f}%)"
            )

        # ---- Update price curve ----
        self.price_history.append(price)
        self.line.set_data(range(len(self.price_history)), self.price_history)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()

        # ---- Update P&L ----
        self.UnrealizedProfit.set(self.account.floating_pnl(price))
        self.ProfitHist = np.append(self.ProfitHist, gloProfit.get() + self.UnrealizedProfit.get())

        # News & top info
        self.set_news(news_text, news_color)
        self.refresh_top_panel(price, day)

        self.idx += 1
        self.root.after(self.update_interval_ms, self.tick)

    # ---------- Trading actions ----------
    def _current_trade_price(self):
        """Return (price, day) used for trading at the latest available index."""
        use_idx = max(0, self.idx - 1)
        return float(self.price_df.iloc[use_idx]['Close']), self.days[use_idx]

    def _get_qty(self):
        """Validate and return the integer lot size from the entry widget, or None if invalid."""
        try:
            qty = int(self.entry_qty.get().strip())
            if qty <= 0:
                raise ValueError
            return qty
        except Exception:
            messagebox.showerror("Input Error", "Please enter a valid lot size (positive integer).")
            return None

    def buy_action(self):
        """Handle Buy button: open a long position if possible."""
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
        """Handle Sell button: open a short position if possible."""
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
        """Handle Close button: close the current position."""
        price, day = self._current_trade_price()
        msg, pnl = self.account.close_position(price)
        if "No positions" in msg:
            messagebox.showerror("Transaction Failure", msg)
        else:
            self.log(f"{day.strftime('%Y-%m-%d')} close a position @ {price:.2f} → {msg}")
            self.refresh_top_panel(price, day)

    # ---------- Profit history pop-up ----------
    def drawChart(self):
        """
        Continuously draw/refresh the profit history chart in the pop-up window.
        This is scheduled repeatedly via `after`.
        """
        self.ax2.clear()
        self.ax2.plot(self.ProfitHist, marker='o', label='Profit')
        self.ax2.set_title("Profit History", fontsize=14)
        self.ax2.set_xlabel("Time", fontsize=12)
        self.ax2.set_ylabel("Profit", fontsize=12)
        if len(self.ProfitHist) > 0:
            self.ax2.axhline(y=self.ProfitHist[-1], linestyle="--",
                             label=f"Profit: {self.ProfitHist[-1]:.2f}")
        self.ax2.legend(loc='upper left')
        self.ax2.relim()
        self.ax2.autoscale_view()
        self.canvas2.draw()
        self.profitRoot.after(self.update_interval_ms, self.drawChart)

    def getProfitChart(self):
        """Open a new window and start plotting the rolling profit history."""
        self.profitRoot = tk.Toplevel(self.root)
        self.profitRoot.title("Profit History")
        self.profitRoot.geometry("1200x800")
        self.fig2, self.ax2 = plt.subplots(figsize=(5, 3))
        self.canvas2 = FigureCanvasTkAgg(self.fig2, master=self.profitRoot)
        self.canvas2.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.drawChart()

    # ---------- Leaderboard (Ranking) ----------
    def show_leaderboard(self):
        """Open a popup window to show the leaderboard loaded from `ranking.csv` (if any)."""
        win = tk.Toplevel(self.root)
        win.title("Leaderboard")
        win.geometry("760x520")
        main_frame = tk.Frame(win, bg="white")
        main_frame.pack(fill=tk.BOTH, expand=True)

        df_rank = self._load_ranking_df()

        # podium / row colors (top 3 highlighted)
        bg_colors = ["#f1c40f", "#bdc3c7", "#e67e22"] + ["white"] * 100

        self.render_leaderboard(main_frame, df_rank, bg_colors)

    def _load_ranking_df(self) -> pd.DataFrame | None:
        """
        Load and sort ranking data from `ranking.csv` if the file exists.

        Expected columns:
            player_name (str), final_balance (float), return_rate (float), end_time (str)
        Returns:
            pd.DataFrame | None
        """
        file = "ranking.csv"
        if not os.path.exists(file):
            return None
        try:
            df = pd.read_csv(file)
            # Ensure required columns exist
            for col in ["player_name", "final_balance", "return_rate"]:
                if col not in df.columns:
                    raise ValueError(f"Column '{col}' missing in ranking.csv")
            # Sort by return_rate descending, then balance
            df = df.sort_values(["return_rate", "final_balance"], ascending=[False, False]).reset_index(drop=True)
            return df
        except Exception as e:
            # Show an empty DataFrame with error captured in UI layer
            print("Failed to load ranking:", e)
            return None

    def render_leaderboard(self, main_frame: tk.Frame, df_rankings: pd.DataFrame, bg_colors: list[str]):
        """
        Part 9 — comments/meaningful names
        ----------------------------------
        Render the leaderboard panel.

        Args:
            main_frame (tk.Frame): The parent container to hold the leaderboard UI.
            df_rankings (pd.DataFrame): Ranking data with columns:
                - 'player_name' (str)
                - 'return_rate' (float, percentage, e.g. 5.23 means +5.23%)
                - 'final_balance' (float, ending cash balance)
            bg_colors (list[str]): Background colors to highlight top rows
                                   (e.g., first 3 for podium).
        """
        # Clear previous content
        for child in main_frame.winfo_children():
            child.destroy()

        try:
            if df_rankings is not None and len(df_rankings) > 0:
                header = tk.Label(
                    main_frame,
                    text=f"{'#':<6} {'Player':<16} {'Return':>12} {'Final Balance':>16}",
                    font=("Courier New", 12, "bold"),
                    bg="white",
                    fg="#2c3e50",
                    anchor="w",
                )
                header.pack(fill=tk.X, padx=10, pady=(8, 4))

                rank_frame = tk.Frame(main_frame, bg="white")
                rank_frame.pack(fill=tk.BOTH, expand=True)

                for idx, row in df_rankings.reset_index(drop=True).iterrows():
                    # Format display text
                    rank_num = f"#{idx + 1}"
                    player_name = str(row['player_name'])[:16]  # truncate to fit
                    return_rate = f"{row['return_rate']:+6.2f}%"
                    balance = f"${row['final_balance']:>13,.0f}"

                    # Fixed-width aligned row
                    rank_text = f"{rank_num:<6} {player_name:<16} {return_rate:>12} {balance:>16}"

                    font_weight = "bold" if idx < 3 else "normal"
                    row_bg = bg_colors[idx] if idx < len(bg_colors) else "white"

                    rank_label = tk.Label(
                        rank_frame,
                        text=rank_text,
                        font=("Courier New", 11, font_weight),
                        bg=row_bg,
                        fg="#2c3e50",
                        anchor='w'
                    )
                    rank_label.pack(fill=tk.BOTH, expand=True, padx=10, pady=2)

            else:
                no_data_label = tk.Label(
                    main_frame,
                    text="No ranking data available yet.\nComplete a game to see rankings!",
                    font=self.font_big, bg='white', fg='#7f8c8d'
                )
                no_data_label.pack(expand=True)

        except Exception as e:
            error_label = tk.Label(
                main_frame,
                text=f"Error loading ranking data:\n{str(e)}",
                font=self.font_big, bg='white', fg='#e74c3c'
            )
            error_label.pack(expand=True)

    # ---------- End-of-game settlement ----------
    def end_game(self):
        """
        Stop the timer, force-close any open position at the last price,
        compute final performance, persist to leaderboard, show a summary, and exit.
        """
        self.timer_running = False
        last_price = float(self.price_df.iloc[-1]['Close'])
        if self.account.position != 0:
            msg, pnl = self.account.close_position(last_price)
            self.log(f"Automatically close a position (last day @ {last_price:.2f}): {msg}")

        final_balance = self.account.balance
        pl = final_balance - self.account.initial_balance
        rr = (pl / self.account.initial_balance) * 100.0

        # Persist to ranking.csv (append mode)
        try:
            row = pd.DataFrame([{
                "player_name": self.player_name,
                "final_balance": round(final_balance, 2),
                "return_rate": round(rr, 2),
                "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])
            file = "ranking.csv"
            if os.path.exists(file):
                row.to_csv(file, mode="a", index=False, header=False)
            else:
                row.to_csv(file, index=False)
        except Exception as e:
            self.log(f"Warning: failed to write ranking.csv → {e}")

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


# =============== Main (with your testing section) ===============
if __name__ == "__main__":
    # If started with "test" argument: run Account unit tests only; otherwise launch the game UI.
    if "test" in sys.argv:
        print("Tests begin.")
        acc = Account(initial_balance=10000, lot_size=1, name="Tester")

        # Test: open long
        msg, ok = acc.buy(1000, 1)
        print("Buy Test:", msg, "OK?", ok, "Balance:", acc.balance)

        # Test: floating P&L
        pnl = acc.floating_pnl(1010)
        print("Floating Profit and Loss:", pnl)

        # Test: close long
        msg, pnl = acc.close_position(1020)
        print("Close Test:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)

        # Test: open short
        msg, ok = acc.sell(950, 2)
        print("Sell Short Test:", msg, "OK?", ok, "Balance:", acc.balance)

        # Test: close short
        msg, pnl = acc.close_position(940)
        print("Close Short:", msg, "Profit and Loss:", pnl, "Balance:", acc.balance)

        print("Tests Finish.")
    else:
        root = tk.Tk()
        app = TradingGameUI(root, name="Player1")
        root.mainloop()
