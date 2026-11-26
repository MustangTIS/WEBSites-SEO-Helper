from collections import defaultdict
import json
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


OVERLAY_UI_TEMPLATE = """
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

<div id="link-inspector-panel" style="
  position: fixed;
  top: 64px;
  right: 12px;
  bottom: 12px;
  width: 350px;
  max-width: calc(100vw - 24px);
  z-index: 9998;
  background: rgba(22, 22, 24, 0.96);
  color: #f2f2f2;
  border: 1px solid #4c4c4c;
  border-radius: 8px;
  padding: 12px;
  font-family: sans-serif;
  font-size: 12.5px;
  display: none;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.65);
  overflow: hidden;
">
  <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #3c3c3c; padding-bottom: 8px;">
    <strong style="font-size: 13.5px; color: #8ec5ff;">🔗 リンク先・リンク元ビューア</strong>
    <div style="display: flex; align-items: center; gap: 6px;">
      <button id="inspectorToggleAllBtn" type="button" style="
        border: 1px solid #555;
        background: #2a2d34;
        color: #d8e2ef;
        border-radius: 4px;
        padding: 2px 7px;
        cursor: pointer;
        font-size: 11px;
      ">すべて開閉</button>
      <button id="inspectorCloseBtn" type="button" title="閉じる" style="
        border: 1px solid #555;
        background: #2e2e2e;
        color: #ddd;
        border-radius: 4px;
        padding: 2px 8px;
        cursor: pointer;
        font-size: 12px;
      ">✕</button>
    </div>
  </div>

  <div id="inspectorNodeInfo" style="
    background: #18181b;
    border: 1px solid #333;
    border-radius: 6px;
    padding: 8px;
    word-break: break-all;
    line-height: 1.45;
  "></div>

  <div id="inspectorSections" style="flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; padding-right: 2px;">
    <details class="inspector-section" open style="background: #17171b; border: 1px solid #2e333d; border-radius: 6px; padding: 6px 8px;">
      <summary id="outgoingHeader" style="font-weight: bold; color: #7cc4fa; cursor: pointer; user-select: none; list-style: none;">
        ➡ リンク先 [内部] (0)
      </summary>
      <ul id="outgoingList" style="list-style: none; margin: 8px 0 2px 0; padding: 0; display: flex; flex-direction: column; gap: 4px;"></ul>
    </details>

    <details class="inspector-section" open style="background: #17171b; border: 1px solid #2e333d; border-radius: 6px; padding: 6px 8px;">
      <summary id="incomingHeader" style="font-weight: bold; color: #8ce99a; cursor: pointer; user-select: none; list-style: none;">
        ⬅ リンク元 [内部] (0)
      </summary>
      <ul id="incomingList" style="list-style: none; margin: 8px 0 2px 0; padding: 0; display: flex; flex-direction: column; gap: 4px;"></ul>
    </details>

    <details class="inspector-section" style="background: #17171b; border: 1px solid #2e333d; border-radius: 6px; padding: 6px 8px;">
      <summary id="externalHeader" style="font-weight: bold; color: #f6bd60; cursor: pointer; user-select: none; list-style: none;">
        🌐 外部リンク (0)
      </summary>
      <ul id="externalList" style="list-style: none; margin: 8px 0 2px 0; padding: 0; display: flex; flex-direction: column; gap: 4px;"></ul>
    </details>
  </div>
</div>

<script>
(function() {
  const LINK_GRAPH_META = __LINK_GRAPH_META_JSON__;

  const inputEl = document.getElementById("nodeSearchInput");
  const nextBtn = document.getElementById("nodeSearchNextBtn");
  const clearBtn = document.getElementById("nodeSearchClearBtn");
  const countEl = document.getElementById("nodeSearchCount");

  const panelEl = document.getElementById("link-inspector-panel");
  const toggleAllBtn = document.getElementById("inspectorToggleAllBtn");
  const closeBtn = document.getElementById("inspectorCloseBtn");
  const infoEl = document.getElementById("inspectorNodeInfo");
  const outgoingHeaderEl = document.getElementById("outgoingHeader");
  const outgoingListEl = document.getElementById("outgoingList");
  const incomingHeaderEl = document.getElementById("incomingHeader");
  const incomingListEl = document.getElementById("incomingList");
  const externalHeaderEl = document.getElementById("externalHeader");
  const externalListEl = document.getElementById("externalList");

  let matches = [];
  let matchIndex = -1;
  let lastQuery = "";
  let originalStyles = new Map();
  let boundNetwork = null;

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

  function focusNodeById(targetId) {
    const net = getNetworkInstance();
    if (!net || !targetId) return;
    net.selectNodes([targetId]);
    net.focus(targetId, {
      scale: 1.2,
      animation: {
        duration: 300,
        easingFunction: "easeInOutQuad"
      }
    });
    renderInspector(targetId);
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
    renderInspector(targetId);
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

  function createInternalLinkItemElement(url, badgeText, badgeColor) {
    const li = document.createElement("li");
    li.style.cssText = [
      "background: #1f2027",
      "border: 1px solid #323440",
      "border-radius: 5px",
      "padding: 6px 8px",
      "cursor: pointer",
      "word-break: break-all",
      "transition: background 0.15s ease, border-color 0.15s ease"
    ].join(";");

    li.addEventListener("mouseenter", function() {
      li.style.background = "#292e3a";
      li.style.borderColor = "#5b8def";
    });
    li.addEventListener("mouseleave", function() {
      li.style.background = "#1f2027";
      li.style.borderColor = "#323440";
    });
    li.addEventListener("click", function() {
      focusNodeById(url);
    });

    const meta = LINK_GRAPH_META.nodes[url] || {};
    const pathText = meta.path || url;

    const topRow = document.createElement("div");
    topRow.style.cssText = "display: flex; align-items: center; gap: 6px; font-weight: bold; color: #e8eef5;";
    if (badgeText) {
      const badge = document.createElement("span");
      badge.textContent = badgeText;
      badge.style.cssText = `font-size: 10.5px; padding: 1px 5px; border-radius: 3px; background: ${badgeColor}; color: #111; font-weight: bold;`;
      topRow.appendChild(badge);
    }
    const pathSpan = document.createElement("span");
    pathSpan.textContent = pathText;
    topRow.appendChild(pathSpan);

    const urlDiv = document.createElement("div");
    urlDiv.textContent = url;
    urlDiv.style.cssText = "font-size: 11px; color: #9aa4b2; margin-top: 2px;";

    li.appendChild(topRow);
    li.appendChild(urlDiv);
    return li;
  }

  function createExternalLinkItemElement(extItem) {
    const li = document.createElement("li");
    li.style.cssText = [
      "background: #1f2027",
      "border: 1px solid #36332a",
      "border-radius: 5px",
      "padding: 6px 8px",
      "word-break: break-all"
    ].join(";");

    const topRow = document.createElement("div");
    topRow.style.cssText = "display: flex; align-items: center; justify-content: space-between; gap: 6px;";

    const linkEl = document.createElement("a");
    linkEl.href = extItem.url;
    linkEl.target = "_blank";
    linkEl.rel = "noopener noreferrer";
    linkEl.textContent = extItem.url;
    linkEl.style.cssText = "color: #ffd166; text-decoration: none; font-weight: bold; font-size: 11.5px; flex: 1;";
    linkEl.addEventListener("mouseenter", function() {
      linkEl.style.textDecoration = "underline";
    });
    linkEl.addEventListener("mouseleave", function() {
      linkEl.style.textDecoration = "none";
    });
    topRow.appendChild(linkEl);

    if (extItem.count > 1) {
      const countBadge = document.createElement("span");
      countBadge.textContent = `×${extItem.count}`;
      countBadge.style.cssText = "font-size: 10.5px; padding: 1px 5px; border-radius: 3px; background: #3b3524; color: #ffd166; white-space: nowrap;";
      topRow.appendChild(countBadge);
    }

    li.appendChild(topRow);
    return li;
  }

  function renderInspector(nodeId) {
    if (!nodeId || !LINK_GRAPH_META.nodes[nodeId]) {
      panelEl.style.display = "none";
      return;
    }

    const info = LINK_GRAPH_META.nodes[nodeId];
    const outgoing = LINK_GRAPH_META.outgoing[nodeId] || [];
    const incoming = LINK_GRAPH_META.incoming[nodeId] || [];
    const external = LINK_GRAPH_META.external[nodeId] || [];

    const badges = [];
    if (info.status) badges.push(`<span style="color:#ff8a65;font-weight:bold;">[${info.status}]</span>`);
    if (info.has_conflict) badges.push(`<span style="color:#ffd54f;font-weight:bold;">[重複・混在警告]</span>`);
    if (info.has_self_loop) badges.push(`<span style="color:#81c784;font-weight:bold;">[自己ループあり]</span>`);

    const reasons = Array.isArray(info.conflict_reasons) ? info.conflict_reasons : [];
    const reasonHtml = reasons.length
      ? `<div style="margin-top:7px;padding-top:6px;border-top:1px dashed #3a3a42;display:flex;flex-direction:column;gap:4px;color:#ffe082;font-size:11.5px;">` +
        reasons.map((r) => `<div>・${r}</div>`).join("") +
        `</div>`
      : "";

    infoEl.innerHTML = `
      <div style="font-weight:bold;font-size:13px;color:#fff;margin-bottom:4px;">${info.path || nodeId}</div>
      <div style="color:#b0b8c4;font-size:11px;">${nodeId}</div>
      ${badges.length ? `<div style="margin-top:6px;display:flex;flex-wrap:wrap;gap:6px;">${badges.join("")}</div>` : ""}
      ${reasonHtml}
    `;

    outgoingHeaderEl.textContent = `➡ リンク先 [内部] (${outgoing.length})`;
    outgoingListEl.innerHTML = "";
    if (outgoing.length === 0) {
      outgoingListEl.innerHTML = `<li style="color:#888;padding:2px;">内部リンク先はありません</li>`;
    } else {
      for (const dst of outgoing) {
        const dstMeta = LINK_GRAPH_META.nodes[dst] || {};
        let bText = "";
        let bColor = "#4CAF50";
        if (dstMeta.status) {
          bText = dstMeta.status;
          bColor = "#FF7043";
        } else if (dstMeta.has_conflict) {
          bText = "重複警告";
          bColor = "#FFD54F";
        }
        outgoingListEl.appendChild(createInternalLinkItemElement(dst, bText, bColor));
      }
    }

    incomingHeaderEl.textContent = `⬅ リンク元 [内部] (${incoming.length})`;
    incomingListEl.innerHTML = "";
    if (incoming.length === 0) {
      incomingListEl.innerHTML = `<li style="color:#888;padding:2px;">内部リンク元はありません</li>`;
    } else {
      for (const src of incoming) {
        incomingListEl.appendChild(createInternalLinkItemElement(src, "", "#4CAF50"));
      }
    }

    const totalExtRefs = external.reduce((acc, item) => acc + (item.count || 1), 0);
    const extLabel = external.length === totalExtRefs
      ? `🌐 外部リンク (${external.length})`
      : `🌐 外部リンク (${external.length}種 / 計${totalExtRefs}件)`;
    externalHeaderEl.textContent = extLabel;
    externalListEl.innerHTML = "";
    if (external.length === 0) {
      externalListEl.innerHTML = `<li style="color:#888;padding:2px;">外部リンクはありません</li>`;
    } else {
      for (const extItem of external) {
        externalListEl.appendChild(createExternalLinkItemElement(extItem));
      }
    }

    panelEl.style.display = "flex";
  }

  function toggleAllSections() {
    const sections = Array.from(panelEl.querySelectorAll("details.inspector-section"));
    if (sections.length === 0) return;
    const allOpen = sections.every((d) => d.open);
    sections.forEach((d) => {
      d.open = !allOpen;
    });
  }

  function attachNetworkEvents() {
    const net = getNetworkInstance();
    if (!net || boundNetwork === net) return;
    boundNetwork = net;

    net.on("click", function(params) {
      if (params && params.nodes && params.nodes.length > 0) {
        renderInspector(params.nodes[0]);
      } else {
        panelEl.style.display = "none";
      }
    });
  }

  nextBtn.addEventListener("click", focusNextMatch);
  clearBtn.addEventListener("click", clearSearch);
  toggleAllBtn.addEventListener("click", toggleAllSections);
  closeBtn.addEventListener("click", function() {
    panelEl.style.display = "none";
  });
  inputEl.addEventListener("keydown", function(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      focusNextMatch();
    } else if (e.key === "Escape") {
      clearSearch();
      panelEl.style.display = "none";
    }
  });

  attachNetworkEvents();
  setTimeout(attachNetworkEvents, 200);
})();
</script>
"""


def normalize_internal_url(raw_or_href: str, base_url: str | None, root_scheme: str, target_domain: str) -> str | None:
    """同一ドメイン・ルートスキームの内部URLを正規化する。外部URLならNoneを返す。"""
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


def normalize_external_url(raw_or_href: str, base_url: str | None, target_domain: str) -> str | None:
    """他ドメインの外部HTTP/HTTPS URLを正規化する。内部URLや非WebスキームならNoneを返す。"""
    if not raw_or_href:
        return None

    candidate = raw_or_href.strip()
    lower = candidate.lower()
    if lower.startswith(("javascript:", "mailto:", "tel:", "data:", "#")):
        return None

    joined = urljoin(base_url, candidate) if base_url else candidate
    parsed = urlparse(joined)

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return None

    netloc = (parsed.netloc or "").lower()
    if not netloc or netloc == target_domain:
        return None

    path = parsed.path if parsed.path else "/"
    query_pairs = sorted(parse_qsl(parsed.query, keep_blank_values=True))
    normalized_query = urlencode(query_pairs)

    return urlunparse((
        scheme,
        netloc,
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
    「トップ相当ファイル名同士の重複」を検出し、対象URLごとの理由も返す。
    """
    dir_entries: dict[str, dict[str, dict[str, set[str]]]] = defaultdict(
        lambda: defaultdict(lambda: {"urls": set(), "sources": set()})
    )

    for url in visited:
        p = urlparse(url).path or "/"
        d_path, entry = classify_path_entry(p)
        if entry is not None:
            dir_entries[d_path][entry]["urls"].add(url)

    for src, dst in edges:
        if src not in visited or dst not in visited:
            continue
        p = urlparse(dst).path or "/"
        d_path, entry = classify_path_entry(p)
        if entry is not None:
            dir_entries[d_path][entry]["urls"].add(dst)
            dir_entries[d_path][entry]["sources"].add(src)

    warnings = []
    flagged_urls: set[str] = set()
    url_reasons: dict[str, list[str]] = defaultdict(list)

    for d_path in sorted(dir_entries.keys()):
        entries = dir_entries[d_path]
        has_slash = "/" in entries
        doc_names = sorted([k for k in entries.keys() if k != "/"])

        dir_involved_urls: set[str] = set()
        for info in entries.values():
            dir_involved_urls.update(info["urls"])

        if has_slash and doc_names:
            flagged_urls.update(dir_involved_urls)
            all_sources = sorted({
                s for info in entries.values() for s in info["sources"]
            })
            docs_str = "、".join(doc_names)
            reason_slash = f"ルート指定（/）で終わっているリンクと {docs_str} でリンクされているものがあります"
            for u in dir_involved_urls:
                if reason_slash not in url_reasons[u]:
                    url_reasons[u].append(reason_slash)

            warnings.append({
                "dir": d_path,
                "kind": "ルート(/)と既定ファイル名の混在",
                "detail": f"'/' と [{', '.join(doc_names)}] が同一ディレクトリで併用されています。",
                "urls": sorted(dir_involved_urls),
                "sources": all_sources,
            })

        if len(doc_names) >= 2:
            doc_urls = sorted({
                u for name in doc_names for u in entries[name]["urls"]
            })
            doc_sources = sorted({
                s for name in doc_names for s in entries[name]["sources"]
            })
            flagged_urls.update(doc_urls)
            dup_str = "、".join(doc_names)
            reason_dup = f"{dup_str} はWEBサーバーでどちらがルートか迷う可能性があります"
            for u in doc_urls:
                if reason_dup not in url_reasons[u]:
                    url_reasons[u].append(reason_dup)

            warnings.append({
                "dir": d_path,
                "kind": "トップ相当ファイル名の重複",
                "detail": f"複数のトップ相当ファイル [{', '.join(doc_names)}] が同一ディレクトリで参照されています。",
                "urls": doc_urls,
                "sources": doc_sources,
            })

    return warnings, flagged_urls, dict(url_reasons)


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

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame, text="対象WebサイトのURL:", font=("", 10, "bold")
        ).pack(anchor=tk.W, pady=(0, 5))
        self.url_entry = ttk.Entry(frame, width=60)
        self.url_entry.insert(0, "https://example.com/")
        self.url_entry.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(frame, text="最大巡回ページ数:").pack(anchor=tk.W, pady=(0, 5))
        self.max_pages_spin = ttk.Spinbox(frame, from_=5, to=500, width=10)
        self.max_pages_spin.set(200)
        self.max_pages_spin.pack(anchor=tk.W, pady=(0, 15))

        self.run_btn = ttk.Button(
            frame, text="解析スタート", command=self.start_crawling_thread
        )
        self.run_btn.pack(fill=tk.X, ipady=5, pady=(0, 15))

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

        self.run_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self._set_status("解析中... しばらくお待ちください", "blue")

        thread = threading.Thread(
            target=self.run_crawler, args=(url, max_pages)
        )
        thread.daemon = True
        thread.start()

    def _inject_overlay_ui(self, html_path, graph_meta: dict):
        """生成されたHTMLに検索バー・リンク詳細パネル・スクリプトを組み込む"""
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        meta_json = json.dumps(graph_meta, ensure_ascii=False).replace("</", "<\\/")
        snippet = OVERLAY_UI_TEMPLATE.replace("__LINK_GRAPH_META_JSON__", meta_json)

        if "</body>" in html_content:
            updated = html_content.replace("</body>", f"{snippet}\n</body>", 1)
        else:
            updated = html_content + "\n" + snippet

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
        normalized_start = (
            normalize_internal_url(start_url, None, root_scheme, target_domain)
            or start_url
        )

        visited = set()
        to_visit = [normalized_start]
        queued = {normalized_start}
        edges = []
        seen_edges = set()
        error_nodes = {}  # エラーページのURLとメッセージを記録 {url: status_msg}
        self_loop_nodes = set()  # 自己ループ(src == dst)を持つURLを記録
        external_links_map: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

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

                self._set_status(
                    f"取得中 [{len(visited)}/{max_pages}]: {display_path}"
                )

                try:
                    res = requests.get(
                        current_url,
                        timeout=5,
                        headers={"User-Agent": "MyGUIContainer/1.0"},
                    )

                    final_url = (
                        normalize_internal_url(res.url, None, root_scheme, target_domain)
                        or current_url
                    )
                    if final_url != current_url:
                        visited.add(final_url)

                    if res.status_code != 200:
                        error_nodes[final_url] = f"HTTP {res.status_code}"
                        continue

                    if "text/html" not in res.headers.get("Content-Type", ""):
                        continue

                except Exception:
                    error_nodes[current_url] = "Connection Error"
                    continue

                soup = BeautifulSoup(res.text, "html.parser")
                for a_tag in soup.find_all("a", href=True):
                    href_val = a_tag["href"]
                    full_url = normalize_internal_url(
                        href_val, final_url, root_scheme, target_domain
                    )
                    if full_url:
                        if full_url == final_url:
                            # 自己ループは矢印を出さず、対象ノードの緑色表示で表現する
                            self_loop_nodes.add(final_url)
                        else:
                            edge_key = (final_url, full_url)
                            if edge_key not in seen_edges:
                                seen_edges.add(edge_key)
                                edges.append(edge_key)

                        if full_url not in visited and full_url not in queued:
                            queued.add(full_url)
                            to_visit.append(full_url)
                    else:
                        ext_url = normalize_external_url(
                            href_val, final_url, target_domain
                        )
                        if ext_url:
                            external_links_map[final_url][ext_url] += 1

            # --- ルート/トップ相当ファイルの混在・重複解析 ---
            self._set_status("リンク構造・重複警告を解析中...")
            warnings, flagged_urls, url_reasons = analyze_root_conflicts(edges, visited)
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
              "edges": {
                "color": {
                  "color": "#4A90E2",
                  "highlight": "#82B1FF",
                  "hover": "#82B1FF"
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

            outgoing_map: dict[str, list[str]] = defaultdict(list)
            incoming_map: dict[str, list[str]] = defaultdict(list)
            nodes_meta: dict[str, dict] = {}

            for url in visited:
                parsed_u = urlparse(url)
                path = parsed_u.path or "/"
                label_text = f"{path}?{parsed_u.query}" if parsed_u.query else path
                has_self_loop = url in self_loop_nodes
                is_flagged = url in flagged_urls
                reasons_list = url_reasons.get(url, [])

                loop_note = "\n[自己ループあり（自ページ/自トップ参照）]" if has_self_loop else ""
                warn_note = "\n[警告: ルート(/)またはトップ相当ファイルの混在・重複候補]" if is_flagged else ""

                status_str = error_nodes.get(url)
                nodes_meta[url] = {
                    "path": label_text,
                    "status": status_str,
                    "has_conflict": is_flagged,
                    "has_self_loop": has_self_loop,
                    "conflict_reasons": reasons_list,
                }

                if url in error_nodes:
                    err_msg = error_nodes[url]
                    net.add_node(
                        url,
                        label=f"⚠️ {label_text}",
                        title=f"{url}\n({err_msg}){warn_note}{loop_note}",
                        color="#FF5722",
                        shape="diamond",
                    )
                elif is_flagged:
                    net.add_node(
                        url,
                        label=f"⚡ {label_text}",
                        title=f"{url}{warn_note}{loop_note}",
                        color="#FFC107",
                        shape="triangle",
                    )
                elif has_self_loop:
                    net.add_node(
                        url,
                        label=f"🔁 {label_text}",
                        title=f"{url}{loop_note}",
                        color="#4CAF50",
                        shape="dot",
                    )
                else:
                    net.add_node(
                        url, label=label_text, title=url, color="#2B7CE9"
                    )

            for src, dst in edges:
                if src in visited and dst in visited:
                    net.add_edge(src, dst, color="#4A90E2")
                    outgoing_map[src].append(dst)
                    incoming_map[dst].append(src)

            external_meta: dict[str, list[dict]] = {}
            for src_url, ext_counts in external_links_map.items():
                external_meta[src_url] = [
                    {"url": ext_u, "count": cnt}
                    for ext_u, cnt in sorted(ext_counts.items())
                ]

            graph_meta = {
                "nodes": nodes_meta,
                "outgoing": {k: sorted(v) for k, v in outgoing_map.items()},
                "incoming": {k: sorted(v) for k, v in incoming_map.items()},
                "external": external_meta,
            }

            output_file = "site_link_map.html"
            net.write_html(output_file)
            self._inject_overlay_ui(output_file, graph_meta)

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