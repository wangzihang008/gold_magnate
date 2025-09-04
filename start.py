import game
import game_v2

import tkinter as tk


class TradingGameUI:
    def __init__(self, root):
        self.root = root
        self.root.title("gold magnate 2008")

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
        tk.Button(buttons, text="Start New Game (Random Price Changing)", font=self.font_big, command=self.start_new_harder_game, width=20).grid(row=1, column=0, padx=4, pady=4)

        tk.Button(buttons, text="Game Ranking", font=self.font_big, command=self.game_ranking, width=20).grid(row=2, column=0, padx=4, pady=4)
        tk.Button(buttons, text="Exit Game", font=self.font_big, command=self.exit_game, width=20).grid(row=3, column=0, padx=4, pady=4)

    def start_new_game(self):
        root = tk.Tk()
        app = game.TradingGameUI(root)
        root.mainloop()
        self.root.quit()
        return
    
    def start_new_harder_game(self):
        self.root.quit()
        r = tk.Tk()
        app = game_v2.TradingGameUI(r)
        r.mainloop()
        return

    def game_ranking(self):

        return

    def exit_game(self):
        exit(0)






if __name__ == "__main__":
    root = tk.Tk()
    app = TradingGameUI(root)
    root.mainloop()
