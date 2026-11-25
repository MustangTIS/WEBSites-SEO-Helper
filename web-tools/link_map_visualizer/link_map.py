from collections import defaultdict
import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
import webbrowser

from bs4 import BeautifulSoup
from pyvis.network import Network
import requests


DEFAULT_DOC_BASES = (
    "index",
    "default",
    "home",
    "top",
    "main",
    "start",
)

DEFAULT_DOC_EXTENSIONS = (
    ".html",
    ".htm",
    ".php",
    ".asp",
    ".aspx",
    ".jsp",
    ".cgi",
    ".shtml",
)


SEARCH_BAR_SNIPPET = """
<div id="node-search-bar" style="
  position: fixed;
  top: 12px;
  right: 12px;
  z-index: 9999;
  background: rgba(24, 24, 24, 0.94);
  color: #f5f5f5;
  border: 1px solid #555;
  border-radius: 6px;
  padding: 8px 10px;
  font-family: sans-serif;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
">
  <label for="nodeSearchInput" style="white-space: nowrap;">🔍 ファイル/パス検索:</label>
  <input
    id="nodeSearchInput"
    type="text"
    placeholder="例: index.html, setting-sub"
    style="
      width: 190px;
      padding: 4px 8px;
      border-radius: 4px;
      border: 1px solid #777;
      background: #141414;
      color: #fff;
      outline: none;
    "
  />
  <button id="nodeSearchNextBtn" type="button" style="
    padding: 4px 9px;
    border-radius: 4px;
    border: 1px solid #2b7ce9;
    background: #2b7ce9;
    color: #fff;
    cursor: pointer;
    font-weight: bold;
  ">次へ</button>
  <button id="nodeSearchClearBtn" type="button" style="
    padding: 4px 8px;
    border-radius: 4px;
    border: 1px solid #666;
    background: #333;
    color: #eee;
    cursor: pointer;
  ">クリア</button>
  <span id="nodeSearchCount" style="min-width: 72px; text-align: right; color: #bbb; font-size: 12px;"></span>
</div>
<script>
(function() {
  const inputEl = document.getElementById("nodeSearchInput");
  const nextBtn = document.getElementById("nodeSearchNextBtn");
  const clearBtn = document.getElementById("nodeSearchClearBtn");
  const countEl = document.getElementById("nodeSearchCount");

  let matches = [];
  let matchIndex = -1;
  let lastQuery = "";
  let originalStyles = new Map();

  function getNetworkInstance() {
    return (typeof network !== "undefined" && network) ? network : null;
  }

  function snapshotOriginalStyles(net) {
    if (originalStyles.size > 0 || !net || !net.body || !net.body.data || !net.body.data.nodes) {
      return;
    }
    const allNodes = net.body.data.nodes.get();
    for (const n of allNodes) {
      originalStyles.set(n.id, {
        opacity: n.opacity !== undefined ? n.opacity : 1.0
      });
    }
  }

  function restoreAllStyles(net) {
    if (!net || !net.body || !net.body.data || !net.body.data.nodes || originalStyles.size === 0) {
      return;
    }
    const updates = [];
    for (const [id, st] of originalStyles.entries()) {
      updates.push({ id: id, opacity: st.opacity });
    }
    net.body.data.nodes.update(updates);
  }

  function applyDimming(net, matchedSet) {
    if (!net || !net.body || !net.body.data || !net.body.data.nodes) {
      return;
    }
    snapshotOriginalStyles(net);
    const allNodes = net.body.data.nodes.get();
    const updates = [];
    for (const n of allNodes) {
      const isHit = matchedSet.has(n.id);
      const baseOp = originalStyles.has(n.id) ? originalStyles.get(n.id).opacity : 1.0;
      updates.push({
        id: n.id,
        opacity: isHit ? baseOp : 0.18
      });
    }
    net.body.data.nodes.update(updates);
  }

  function rebuildMatches(query) {
    const net = getNetworkInstance();
    matches = [];
    matchIndex = -1;
    lastQuery = query;

    const q = query.trim().toLowerCase();
    if (!q || !net || !net.body || !net.body.data || !net.body.data.nodes) {
      restoreAllStyles(net);
      countEl.textContent = "";
      return;
    }

    const allNodes = net.body.data.nodes.get();
    for (const n of allNodes) {
      const labelStr = String(n.label || "").toLowerCase();
      const idStr = String(n.id || "").toLowerCase();
      const titleStr = String(n.title || "").toLowerCase();
      if (labelStr.includes(q) || idStr.includes(q) || titleStr.includes(q)) {
        matches.push(n.id);
      }
    }

    if (matches.length > 0) {
      applyDimming(net, new Set(matches));
      countEl.textContent = "0 / " + matches.length + " 件";
    } else {
      restoreAllStyles(net);
      countEl.textContent = "該当なし";
    }
  }

  function focusNextMatch() {
    const net = getNetworkInstance();
    const query = inputEl.value;
    if (!query.trim()) {
      clearSearch();
      return;
    }

    if (query !== lastQuery || matches.length === 0) {
      rebuildMatches(query);
    }

    if (matches.length === 0 || !net) {
      return;
    }

    matchIndex = (matchIndex + 1) % matches.length;
    const targetId = matches[matchIndex];
    net.selectNodes([targetId]);
    net.focus(targetId, {
      scale: 1.25,
      animation: {
        duration: 350,
        easingFunction: "easeInOutQuad"
      }
    });
    countEl.textContent = (matchIndex + 1) + " / " + matches.length + " 件";
  }

  function clearSearch() {
    const net = getNetworkInstance();
    inputEl.value = "";
    matches = [];
    matchIndex = -1;
    lastQuery = "";
    countEl.textContent = "";
    restoreAllStyles(net);
    if (net) {
      net.unselectAll();
    }
  }

  nextBtn.addEventListener("click", focusNextMatch);
  clearBtn.addEventListener("click", clearSearch);
  inputEl.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      focusNextMatch();
    } else if (e.key === "Escape") {
      clearSearch();
    }
  });
})();
</script>
"""


def normalize_url(raw_or_href: str, base_url: str | None, root_scheme: str, target_domain: str) -> str | None:
    """URLを正規化し、同一ドメインかつルートスキームに統一する。"""
    if not raw_or_href:
        return None

    candidate = raw_or_href.strip()
    lower = candidate.lower()
    if lower.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
        return None

    joined = urljoin(base_url, candidate) if base_url else candidate
    parsed = urlparse(joined)

    if parsed.scheme and parsed.scheme.lower() not in ("http", "https"):
        return None

    netloc = (parsed.netloc or "").lower()
    if netloc != target_domain:
        return None

    path = parsed.path if parsed.path else "/"
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    normalized_query = urlencode(query_pairs)

    return urlunparse((
        root_scheme,
        target_domain,
        path,
        "",
        normalized_query,
        "",
    ))


def classify_path_entry(path: str) -> tuple[str, str | None]:
    """
    パスを解析し、(ディレクトリパス, 既定ドキュメント名) を返す。
    既定ドキュメント候補に該当しないファイルの場合は second 要素が None。
    """
    clean_path = path if path else "/"
    if clean_path.endswith("/"):
        return clean_path, "/"

    parent_dir, filename = clean_path.rsplit("/", 1)
    dir_path = f"{parent_dir}/" if parent_dir else "/"
    lower_name = filename.lower()

    for base in DEFAULT_DOC_BASES:
        for ext in DEFAULT_DOC_EXTENSIONS:
            if lower_name == f"{base}{ext}":
                return dir_path, filename

    return dir_path, None


def analyze_root_conflicts(edges: list[tuple[str, str]], visited: set[str]):
    """
    同一ディレクトリ内での「ルート(/)と既定ファイル名の混在」および
    「トップ相当ファイル名同士の重複」を検出する。
    """
    # dir_path -> {entry_name: {"urls": set(), "sources": set()}}
    dir_entries: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"urls": set(), "sources": set()})
    )

    candidate_urls: set[str] = set()
    for url in visited:
        p = urlparse(url).path or "/"
        d_path, entry = classify_path_entry(p)
        if entry is not None:
            candidate_urls.add(url)
            dir_entries[d_path][entry]["urls"].add(url)

    for src, dst in edges:
        if src not in visited or dst not in visited:
            continue
        p = urlparse(dst).path or "/"
        d_path, entry = classify_path_entry(p)
        if entry is not None:
            candidate_urls.add(dst)
            dir_entries[d_path][entry]["urls"].add(dst)
            dir_entries[d_path][entry]["sources"].add(src)

    warnings = []
    flagged_urls: set[str] = set()

    for d_path in sorted(dir_entries.keys()):
        entries = dir_entries[d_path]
        has_slash = "/" in entries
        doc_names = sorted([k for k in entries.keys() if k != "/"])

        dir_involved_urls: set[str] = set()
        for info in entries.values():
            dir_involved_urls.update(info["urls"])

        # 1. ルート(/) と 既定ドキュメント候補の混在
        if has_slash and doc_names:
            flagged_urls.update(dir_involved_urls)
            all_sources = sorted({
                s for info in entries.values() for s in info["sources"]
            })
            warnings.append({
                "dir": d_path,
                "kind": "ルート(/)と既定ファイル名の混在",
                "detail": f"'/' と [{', '.join(doc_names)}] が同一ディレクトリで併用されています。",
                "urls": sorted(dir_involved_urls),
                "sources": all_sources,
            })

        # 2. トップ相当ファイル名同士の重複（例: index.html と top.html、index.html と index.php など）
        if len(doc_names) >= 2:
            doc_urls = sorted({
                u for name in doc_names for u in entries[name]["urls"]
            })
            doc_sources = sorted({
                s for name in doc_names for s in entries[name]["sources"]
            })
            flagged_urls.update(doc_urls)
            warnings.append({
                "dir": d_path,
                "kind": "トップ相当ファイル名の重複",
                "detail": f"複数のトップ相当ファイル [{', '.join(doc_names)}] が同一ディレクトリで参照されています。",
                "urls": doc_urls,
                "sources": doc_sources,
            })

    return warnings, flagged_urls


def format_warnings_text(warnings: list[dict]) -> str:
    """警告一覧を人間が読みやすいテキスト形式に整形する。"""
    if not warnings:
        return "ルート指定・トップ相当ファイルの混在/重複警告はありません。"

    lines = [
        f"SEO/内部リンク構造 警告 ({len(warnings)}件):",
        "同一ディレクトリ内でルート(/)やトップ相当ファイル(index/top/home/default等)が混在・重複しています。",
        "リンク表記の統一や canonical 設定の見直しが望まれます。",
        "-" * 60,
    ]
    for idx, w in enumerate(warnings, 1):
        lines.append(f"[{idx}] ディレクトリ: {w['dir']}  |  種別: {w['kind']}")
        lines.append(f"    内容: {w['detail']}")
        if w["urls"]:
            lines.append(f"    対象URL: {', '.join(w['urls'])}")
        if w["sources"]:
            lines.append(f"    参照元: {', '.join(w['sources'])}")
        lines.append("")

    return "\n".join(lines).strip()


class LinkCrawlerGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("Webサイト内部リンク可視化ツール (404検知・重複警告・検索付)")
        self.root.geometry("540x370")
        self.root.resizable(False, False)

        # 全体フレーム
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        # 1. URL入力欄
        ttk.Label(
            frame, text="対象WebサイトのURL:", font=("", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        self.url_entry = ttk.Entry(frame, width=60)
        self.url_entry.insert(0, "https://example.com/")
        self.url_entry.pack(fill=tk.X, pady=(0, 15))

        # 2. 最大ページ数設定
        ttk.Label(frame, text="最大巡回ページ数:").pack(anchor=tk.W, pady=(0, 5))
        self.max_pages_spin = ttk.Spinbox(frame, from_=5, to=500, width=10)
        self.max_pages_spin.set(200)
        self.max_pages_spin.pack(anchor=tk.W, pady=(0, 15))

        # 3. 実行ボタン
        self.run_btn = ttk.Button(
            frame, text="解析スタート", command=self.start_crawling_thread
        )
        self.run_btn.pack(fill=tk.X, ipady=5, pady=(0, 15))

        # 4. ログ・プログレス表示
        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(
            frame, text="待機中...", foreground="gray"
        )
        self.status_label.pack(anchor=tk.W)

    def _set_status(self, text, color=None):
        def _apply():
            if color:
                self.status_label.config(text=text, foreground=color)
            else:
                self.status_label.config(text=text)

        self.root.after(0, _apply)

    def start_crawling_thread(self):
        """UIがフリーズしないように別スレッドで処理を開始"""
        url = self.url_entry.get().strip()
        if not url.startswith(("http://", "https://")):
            messagebox.showerror(
                "エラー", "URLは http:// または https:// から始めてください。"
            )
            return

        try:
            max_pages = int(self.max_pages_spin.get())
            if max_pages < 1:
                raise ValueError()
        except ValueError:
            messagebox.showerror(
                "エラー", "最大巡回ページ数は 1 以上の整数で指定してください。"
            )
            return

        # UIの操作不可処理
        self.run_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self._set_status("解析中... しばらくお待ちください", "blue")

        # スレッド起動
        thread = threading.Thread(
            target=self.run_crawler, args=(url, max_pages)
        )
        thread.daemon = True
        thread.start()

    def _inject_search_ui(self, html_path):
        """生成されたHTMLにノード検索バーとスクリプトを組み込む"""
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        if "</body>" in html_content:
            updated = html_content.replace("</body>", f"{SEARCH_BAR_SNIPPET}\n</body>", 1)
        else:
            updated = html_content + "\n" + SEARCH_BAR_SNIPPET

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(updated)

    def _show_warnings_window(self, warnings_text: str):
        """SEO・リンク構造の警告一覧ウィンドウを表示"""
        win = tk.Toplevel(self.root)
        win.title("SEO・リンク構造 警告レポート")
        win.geometry("760x440")

        container = ttk.Frame(win, padding=12)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text="ルート指定 / トップ相当ファイルの混在・重複警告",
            font=("", 10, "bold"),
        ).pack(anchor=tk.W, pady=(0, 8))

        text_frame = ttk.Frame(container)
        text_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        text_area = tk.Text(
            text_frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 9),
        )
        text_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_area.yview)

        text_area.insert(tk.END, warnings_text)
        text_area.config(state=tk.DISABLED)

        ttk.Button(container, text="閉じる", command=win.destroy).pack(
            anchor=tk.E, pady=(10, 0)
        )

    def run_crawler(self, start_url, max_pages):
        """クローリング＆可視化のバックグラウンド処理"""
        root_parsed = urlparse(start_url)
        root_scheme = root_parsed.scheme.lower()
        target_domain = root_parsed.netloc.lower()
        normalized_start = normalize_url(start_url, None, root_scheme, target_domain) or start_url

        visited = set()
        to_visit = [normalized_start]
        queued = {normalized_start}
        edges = []
        seen_edges = set()
        error_nodes = {}  # エラーページのURLとメッセージを記録 {url: status_msg}

        try:
            while to_visit and len(visited) < max_pages:
                current_url = to_visit.pop(0)
                if current_url in visited:
                    continue

                visited.add(current_url)
                parsed_curr = urlparse(current_url)
                display_path = parsed_curr.path or "/"
                if parsed_curr.query:
                    display_path = f"{display_path}?{parsed_curr.query}"

                # UIに進捗表示
                self._set_status(
                    f"取得中 [{len(visited)}/{max_pages}]: {display_path}"
                )

                try:
                    res = requests.get(
                        current_url,
                        timeout=5,
                        headers={"User-Agent": "MyGUIContainer/1.0"},
                    )

                    # リダイレクト後に到達したURLも同一ドメイン・スキームに正規化して記録
                    final_url = normalize_url(res.url, None, root_scheme, target_domain) or current_url
                    if final_url != current_url:
                        visited.add(final_url)

                    # 404などのHTTPエラー検知
                    if res.status_code != 200:
                        error_nodes[final_url] = f"HTTP {res.status_code}"
                        continue

                    if "text/html" not in res.headers.get("Content-Type", ""):
                        continue

                except Exception:
                    # 接続エラーやタイムアウト
                    error_nodes[current_url] = "Connection Error"
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    full_url = normalize_url(
                        a_tag["href"], final_url, root_scheme, target_domain
                    )
                    if full_url:
                        edge_key = (final_url, full_url)
                        if edge_key not in seen_edges:
                            seen_edges.add(edge_key)
                            edges.append(edge_key)
                        if full_url not in visited and full_url not in queued:
                            queued.add(full_url)
                            to_visit.append(full_url)

            # --- ルート/トップ相当ファイルの混在・重複解析 ---
            self._set_status("リンク構造・重複警告を解析中...")
            warnings, flagged_urls = analyze_root_conflicts(edges, visited)
            warnings_text = format_warnings_text(warnings)
            if warnings:
                print("\n" + warnings_text + "\n")

            # --- pyvis 描画処理 ---
            self._set_status("マップを作成中...")

            net = Network(
                height="100vh",
                width="100%",
                directed=True,
                bgcolor="#222222",
                font_color="white",
            )

            # 反発を抑えつつ減衰を強めて揺れの収束を早める設定
            net.set_options("""
            var options = {
              "configure": {
                "enabled": false
              },
              "nodes": {
                "font": {
                  "size": 12
                }
              },
              "physics": {
                "barnesHut": {
                  "gravitationalConstant": -2000,
                  "centralGravity": 0.45,
                  "springLength": 110,
                  "springConstant": 0.03,
                  "damping": 0.25,
                  "avoidOverlap": 0.2
                },
                "maxVelocity": 35,
                "minVelocity": 0.4,
                "stabilization": {
                  "enabled": true,
                  "iterations": 200
                }
              }
            }
            """)

            # ノードの追加（正常 / 混在・重複警告 / エラー で色・形状を分岐）
            for url in visited:
                parsed_u = urlparse(url)
                path = parsed_u.path or "/"
                label_text = f"{path}?{parsed_u.query}" if parsed_u.query else path

                if url in error_nodes:
                    err_msg = error_nodes[url]
                    warn_suffix = "\n[警告: ルート/トップ重複候補]" if url in flagged_urls else ""
                    net.add_node(
                        url,
                        label=f"⚠️ {label_text}",
                        title=f"{url}\n({err_msg}){warn_suffix}",
                        color="#FF5722",
                        shape="diamond",
                    )
                elif url in flagged_urls:
                    net.add_node(
                        url,
                        label=f"⚡ {label_text}",
                        title=f"{url}\n[警告: ルート(/)またはトップ相当ファイルの混在・重複候補]",
                        color="#FFC107",
                        shape="triangle",
                    )
                else:
                    net.add_node(
                        url, label=label_text, title=url, color="#2B7CE9"
                    )

            for src, dst in edges:
                if src in visited and dst in visited:
                    net.add_edge(src, dst)

            # ファイル保存処理
            output_file = "site_link_map.html"
            net.write_html(output_file)
            self._inject_search_ui(output_file)

            # 完了処理呼び出し
            self.root.after(
                0,
                self.on_complete,
                True,
                len(visited),
                len(error_nodes),
                len(warnings),
                output_file,
                warnings_text,
            )

        except Exception as e:
            self.root.after(0, self.on_complete, False, 0, 0, 0, str(e), "")

    def on_complete(
        self,
        success,
        total_pages,
        error_count,
        warning_count,
        output_file,
        warnings_text,
    ):
        """完了後のUI復帰とブラウザ起動"""
        self.progress.stop()
        self.run_btn.config(state=tk.NORMAL)

        if success:
            status_text = (
                f"完了！ (全{total_pages}件 / エラー{error_count}件 / "
                f"重複警告{warning_count}件)"
            )
            status_color = (
                "red" if error_count > 0 else ("#D97706" if warning_count > 0 else "green")
            )
            self.status_label.config(text=status_text, foreground=status_color)

            full_path = os.path.abspath(output_file)
            webbrowser.open(f"file://{full_path}")

            msg = (
                f"解析が完了しました！\nブラウザでマップを開きます。\n\n"
                f"解析数: {total_pages} ページ\n"
                f"エラー(404等): {error_count} 箇所\n"
                f"重複・混在警告: {warning_count} 件"
            )
            messagebox.showinfo("完了", msg)

            if warning_count > 0:
                self._show_warnings_window(warnings_text)
        else:
            self.status_label.config(
                text="エラーが発生しました", foreground="red"
            )
            messagebox.showerror(
                "エラー", f"処理中にエラーが発生しました:\n{output_file}"
            )


if __name__ == "__main__":
    root = tk.Tk()
    app = LinkCrawlerGUI(root)
    root.mainloop()