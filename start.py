import game
import game_v2

import tkinter as tk


class TradingGameUI:
    def __init__(self, root):
        self.root = root
        self.root.title("gold magnate 2008")
        self.r = None

        self.font_big = ("Microsoft YaHei", 18)
        self.font_title = ("Microsoft YaHei", 20, "bold")

        self.build_ui()

    def build_ui(self):
        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=80, pady=40)

        mainfarme = tk.LabelFrame(frame, text="Game Dashboard", font=self.font_title, padx=8, pady=8)
        mainfarme.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        
        buttons = tk.Frame(mainfarme)
        buttons.pack(anchor="w", pady=4)

        tk.Button(buttons, text="Start New Game (2008 Original)", font=self.font_big, command=self.name_collecter_original, width=20).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(buttons, text="Start New Game (Random Price Changing)", font=self.font_big, command=self.name_collecter, width=20).grid(row=1, column=0, padx=4, pady=4)

        tk.Button(buttons, text="Game Ranking", font=self.font_big, command=self.game_ranking, width=20).grid(row=2, column=0, padx=4, pady=4)
        tk.Button(buttons, text="Exit Game", font=self.font_big, command=self.exit_game, width=20).grid(row=3, column=0, padx=4, pady=4)

    def name_collecter_original(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=80, pady=40)

        mainfarme = tk.LabelFrame(frame, text="Player Name (2008 Original)", font=self.font_title, padx=8, pady=8)
        mainfarme.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.entry_widget_original=tk.Text(mainfarme, width=50, height=1)
        self.entry_widget_original.pack(padx=10, pady=10)
        self.entry_widget_original.insert("1.0", "Unknown") 

        
        buttons = tk.Frame(mainfarme)
        buttons.pack(anchor="w", pady=4)

        btn=tk.Button(buttons, text="Submit", font=self.font_big, command=self.start_new_game, width=20)
        btn.grid(row=0, column=0, padx=4, pady=4)

    def name_collecter(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        
        frame = tk.Frame(self.root)
        frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=80, pady=40)

        mainfarme = tk.LabelFrame(frame, text="Player Name", font=self.font_title, padx=8, pady=8)
        mainfarme.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.entry_widget=tk.Text(mainfarme, width=50, height=1)
        self.entry_widget.pack(padx=10, pady=10)
        self.entry_widget.insert("1.0", "Unknown") 

        
        buttons = tk.Frame(mainfarme)
        buttons.pack(anchor="w", pady=4)

        btn=tk.Button(buttons, text="Submit", font=self.font_big, command=self.start_new_harder_game, width=20)
        btn.grid(row=0, column=0, padx=4, pady=4)


    def start_new_game(self):
        name=self.entry_widget_original.get("1.0", "end-1c")
        if len(name) < 3:
            if self.r is not None:
                self.r.destroy()
                self.r = tk.Tk()
            else:
                self.r = tk.Tk()
            msg = tk.Label(self.r, text="Invalid Name", font=self.font_title, padx=8, pady=8)
            msg.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
            return
        else:
            if self.r is not None:
                self.r.destroy()
            for widget in self.root.winfo_children():
                widget.destroy()
            app = game.TradingGameUI(self.root, name)
            self.root.mainloop()
        return
    
    def start_new_harder_game(self):
        name=self.entry_widget.get("1.0", "end-1c")
        if len(name) < 3:
            if self.r is not None:
                self.r.destroy()
                self.r = tk.Tk()
            else:
                self.r = tk.Tk()
            msg = tk.Label(self.r, text="Invalid Name", font=self.font_title, padx=8, pady=8)
            msg.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
            # print("Invalid Name")
            return
        else:
            if self.r is not None:
                self.r.destroy()
            for widget in self.root.winfo_children():
                widget.destroy()
            app = game_v2.TradingGameUI(self.root, name)
            self.root.mainloop()
        return

    def game_ranking(self):
        """显示2008原版游戏排行榜"""
        csv_file = "game_rankings_2008.csv"
        
        # 创建排行榜窗口
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
        
        # 检查是否有数据
        if os.path.exists(csv_file):
            try:
                df = pd.read_csv(csv_file)
                if not df.empty:
                    # 按回报率排序并去重（每个玩家只显示最佳成绩）
                    df_best = df.loc[df.groupby('player_name')['return_rate'].idxmax()]
                    df_sorted = df_best.sort_values('return_rate', ascending=False).head(10)
                    
                    # 创建排行榜框架
                    ranking_frame = tk.Frame(main_frame, bg='white')
                    ranking_frame.pack(fill=tk.BOTH, expand=True)
                    
                    # 添加滚动条
                    canvas = tk.Canvas(ranking_frame, bg='white')
                    scrollbar = tk.Scrollbar(ranking_frame, orient="vertical", command=canvas.yview)
                    scrollable_frame = tk.Frame(canvas, bg='white')
                    
                    scrollable_frame.bind(
                        "<Configure>",
                        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                    )
                    
                    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                    canvas.configure(yscrollcommand=scrollbar.set)
                    
                    medals = ['🥇', '🥈', '🥉', '🏅', '🏅', '🎖️', '🎖️', '🎖️', '🎖️', '🎖️']
                    colors = ['#ffd700', '#c0c0c0', '#cd7f32', '#4a90e2', '#4a90e2', '#7f8c8d', '#7f8c8d', '#7f8c8d', '#7f8c8d', '#7f8c8d']
                    
                    for idx, (_, row) in enumerate(df_sorted.iterrows()):
                        medal = medals[idx] if idx < len(medals) else f"#{idx+1}"
                        color = colors[idx] if idx < len(colors) else '#7f8c8d'
                        
                        # 每个排名的框架
                        rank_frame = tk.Frame(scrollable_frame, bg='white')
                        rank_frame.pack(fill=tk.X, pady=5)
                        
                        # 排名文本
                        rank_text = f"{medal} {row['player_name']:>15} | Return: {row['return_rate']:>8.2f}% | Balance: ${row['final_balance']:>10,.2f}"
                        
                        rank_label = tk.Label(rank_frame, text=rank_text, 
                                             font=("Courier New", 14, "bold" if idx < 3 else "normal"),
                                             bg='white', fg=color, anchor='w')
                        rank_label.pack(fill=tk.X)
                    
                    canvas.pack(side="left", fill="both", expand=True)
                    scrollbar.pack(side="right", fill="y")
                    
                else:
                    no_data_label = tk.Label(main_frame, text="No game records found.\nPlay the 2008 Original game to see rankings!", 
                                           font=self.font_big, bg='white', fg='#7f8c8d')
                    no_data_label.pack()
            except Exception as e:
                error_label = tk.Label(main_frame, text=f"Error reading ranking data:\n{str(e)}", 
                                     font=self.font_big, bg='white', fg='#e74c3c')
                error_label.pack()
        else:
            no_file_label = tk.Label(main_frame, text="No ranking file found.\nPlay the 2008 Original game to create rankings!", 
                                   font=self.font_big, bg='white', fg='#7f8c8d')
            no_file_label.pack()
        
        # 关闭按钮
        close_btn = tk.Button(main_frame, text="Close", font=self.font_big, 
                             command=ranking_window.destroy, width=15,
                             bg='#3498db', fg='white', relief=tk.FLAT)
        close_btn.pack(pady=(20, 0))

    def exit_game(self):
        exit(0)




if __name__ == "__main__":
    root = tk.Tk()
    app = TradingGameUI(root)
    root.mainloop()
