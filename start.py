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

        tk.Button(buttons, text="Start New Game (2008 Original)", font=self.font_big, command=self.start_new_game, width=20).grid(row=0, column=0, padx=4, pady=4)
        tk.Button(buttons, text="Start New Game (Random Price Changing)", font=self.font_big, command=self.name_collecter, width=20).grid(row=1, column=0, padx=4, pady=4)

        tk.Button(buttons, text="Game Ranking", font=self.font_big, command=self.game_ranking, width=20).grid(row=2, column=0, padx=4, pady=4)
        tk.Button(buttons, text="Exit Game", font=self.font_big, command=self.exit_game, width=20).grid(row=3, column=0, padx=4, pady=4)

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
        root = tk.Tk()
        app = game.TradingGameUI(root)
        root.mainloop()
        self.root.destroy()
        return
    
    def start_new_harder_game(self):
        name=self.entry_widget.get("1.0", "end-1c")
        if len(name) < 3:
            if self.r is not None:
                self.r.destroy()
                self.r = tk.Tk()
            else:
                self.r = tk.Tk()
            msg = tk.Label(self.r, text="Invaild Name", font=self.font_title, padx=8, pady=8)
            msg.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
            # print("Invaild Name")
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

        return

    def exit_game(self):
        exit(0)







if __name__ == "__main__":
    root = tk.Tk()
    app = TradingGameUI(root)
    root.mainloop()
