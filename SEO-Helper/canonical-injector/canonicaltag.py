import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext


def normalize_canonical_path(url_path: str, omit_index: bool) -> str:
    """URLパスを整形する。omit_index=True の場合は末尾の index.html を省略して / に寄せる。"""
    if not omit_index:
        return url_path

    # "index.html" -> "" (ベースURL末尾の / と合わせて https://example.com/ になる)
    if url_path.lower() == "index.html":
        return ""

    # "foo/index.html" -> "foo/" (ベースURL末尾の / と合わせて https://example.com/foo/ になる)
    if url_path.lower().endswith("/index.html"):
        prefix = url_path[: -len("index.html")]
        return prefix

    return url_path


def process_html_files(directory, base_url, omit_index, log_callback):
    target_dir = os.path.abspath(directory)
    updated_count = 0

    if not os.path.exists(target_dir):
        log_callback(f"エラー: 指定されたディレクトリが存在しません -> {target_dir}\n")
        return

    clean_base = base_url.rstrip("/")

    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.lower().endswith(".html"):
                file_path = os.path.join(root, file)

                # フォルダ内での相対パスを計算してURLパスを生成
                rel_path = os.path.relpath(file_path, target_dir)
                url_path = rel_path.replace("\\", "/")

                # 先頭の不要な記号を整理
                if url_path.startswith("./"):
                    url_path = url_path[2:]

                target_path = normalize_canonical_path(url_path, omit_index)
                canonical_url = f"{clean_base}/{target_path}" if target_path else f"{clean_base}/"
                canonical_tag = f'<link rel="canonical" href="{canonical_url}">'

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except Exception as e:
                    log_callback(f"読み込みエラー: {file_path} -> {e}\n")
                    continue

                # 既にcanonicalタグが存在するかチェックして置換、なければ</head>の直前に追加
                if re.search(r'<link\s+rel=["\']canonical["\'][^>]*>', content, re.IGNORECASE):
                    new_content = re.sub(
                        r'<link\s+rel=["\']canonical["\'][^>]*>',
                        canonical_tag,
                        content,
                        flags=re.IGNORECASE,
                    )
                elif "</head>" in content:
                    new_content = content.replace("</head>", f"    {canonical_tag}\n</head>", 1)
                elif "</HEAD>" in content:
                    new_content = content.replace("</HEAD>", f"    {canonical_tag}\n</HEAD>", 1)
                else:
                    log_callback(f"スキップ（</head>が見つかりません）: {file_path}\n")
                    continue

                # 変更があった場合のみファイルを上書き保存
                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    log_callback(f"更新完了: {url_path} -> {canonical_url}\n")
                    updated_count += 1

    log_callback(f"\n処理が完了しました。合計 {updated_count} 個のファイルを更新しました。\n")


class CanonicalApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Canonicalタグ自動挿入ツール")
        self.root.geometry("600x550")

        # ターゲットフォルダ選択フレーム
        dir_frame = tk.LabelFrame(root, text=" ターゲットフォルダ ", padx=10, pady=10)
        dir_frame.pack(fill="x", padx=10, pady=(10, 6))

        self.dir_entry = tk.Entry(dir_frame)
        self.dir_entry.pack(side="left", padx=(0, 10), expand=True, fill="x")

        dir_btn = tk.Button(dir_frame, text="参照...", command=self.select_directory)
        dir_btn.pack(side="right")

        # ベースURL入力フレーム
        url_frame = tk.LabelFrame(root, text=" ベースURL ", padx=10, pady=10)
        url_frame.pack(fill="x", padx=10, pady=6)

        self.url_entry = tk.Entry(url_frame)
        self.url_entry.pack(fill="x", expand=True)
        self.url_entry.insert(0, "https://example.com")

        # オプションフレーム
        opt_frame = tk.LabelFrame(root, text=" URL整形オプション ", padx=10, pady=8)
        opt_frame.pack(fill="x", padx=10, pady=6)

        self.omit_index_var = tk.BooleanVar(value=True)
        omit_index_chk = tk.Checkbutton(
            opt_frame,
            text="index.html を省略してディレクトリURL (/) にする",
            variable=self.omit_index_var,
        )
        omit_index_chk.pack(anchor="w")

        # 実行ボタン
        self.exec_btn = tk.Button(
            root,
            text="実行する",
            bg="#4CAF50",
            fg="white",
            font=("", 11, "bold"),
            command=self.start_process,
        )
        self.exec_btn.pack(fill="x", padx=10, pady=6)

        # 実行ログ表示エリア
        log_frame = tk.LabelFrame(root, text=" 実行ログ ", padx=10, pady=8)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_area.pack(fill="both", expand=True)

    def select_directory(self):
        dir_path = filedialog.askdirectory()
        if dir_path:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, dir_path)

    def log_message(self, message):
        def _append():
            self.log_area.insert(tk.END, message)
            self.log_area.see(tk.END)

        self.root.after(0, _append)

    def start_process(self):
        target_dir = self.dir_entry.get().strip()
        base_url = self.url_entry.get().strip()
        omit_index = self.omit_index_var.get()

        if not target_dir:
            messagebox.showerror("エラー", "ターゲットフォルダを選択してください。")
            return
        if not base_url:
            messagebox.showerror("エラー", "ベースURLを入力してください。")
            return

        self.log_area.delete("1.0", tk.END)
        self.exec_btn.config(state="disabled")

        # 別スレッドで処理を実行し、画面のフリーズを防止
        def run():
            try:
                process_html_files(target_dir, base_url, omit_index, self.log_message)
            finally:
                self.root.after(0, lambda: self.exec_btn.config(state="normal"))
                self.root.after(0, lambda: messagebox.showinfo("完了", "処理が完了しました！"))

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = CanonicalApp(root)
    root.mainloop()