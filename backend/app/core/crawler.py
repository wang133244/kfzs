# 商品页爬虫：使用 OpenCLI 通过已登录 Chrome 抓取抖音商城/淘宝等商品页，
# 提取标题/价格/主图/图集/描述。OpenCLI 复用浏览器登录态，JS 渲染由 Chrome 完成。
#
# 前置条件：
#   1. npm install -g @jackwener/opencli
#   2. Chrome 安装 OpenCLI Browser Bridge 扩展（chrome://extensions/ → 开发者模式）
#   3. Chrome 保持运行并登录目标电商平台
import asyncio
import json
import re
from typing import Any

# OpenCLI 浏览器会话名：同一会话复用标签页，避免每次抓取新开标签
_SESSION = "crawl"

# 价格正则：兼容 ¥/￥ 前缀与"元"后缀
_PRICE_PATTERNS = [
    re.compile(r"[¥￥]\s*(\d+(?:\.\d+)?)"),
    re.compile(r"(\d+(?:\.\d+)?)\s*元"),
]

# 在页面上下文中提取商品字段的 JS，返回 JSON 字符串
# 优先读取 og: meta 标签（抖音商城/淘宝商品页普遍支持），兜底用 CSS 选择器
_EXTRACT_JS = r"""
(() => {
  const meta = (p) => {
    const el = document.querySelector(`meta[property="${p}"], meta[name="${p}"]`);
    return el && el.content ? el.content.trim() : "";
  };
  const title = meta("og:title") || document.title || (document.querySelector("h1")?.textContent || "").trim();
  const ogImage = meta("og:image");
  const description = meta("og:description") || meta("description") || "";

  let priceText = "";
  for (const sel of ['[class*="price"]', '[data-price]', '[class*="Price"]', '[class*="amount"]']) {
    const el = document.querySelector(sel);
    if (el && el.textContent && el.textContent.trim()) { priceText = el.textContent.trim(); break; }
  }

  // 图集：og:image + 页面商品图，过滤图标/Logo/精灵图
  const skip = /icon|logo|sprite|avatar|favicon|\.svg|placeholder|blank|loading|emoji/i;
  const imgs = [...document.querySelectorAll("img")]
    .map((i) => i.src || (i.dataset && i.dataset.src) || "")
    .filter((s) => s.startsWith("http") && !skip.test(s));
  const gallery = [...new Set([ogImage, ...imgs].filter(Boolean))].slice(0, 8);

  return JSON.stringify({ title, ogImage, description, priceText, gallery });
})()
"""


async def _run_opencli(*args: str) -> str:
    """执行 opencli 子命令，返回 stdout；失败时抛出 RuntimeError。"""
    proc = await asyncio.create_subprocess_exec(
        "opencli",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = stderr.decode(errors="replace").strip() or stdout.decode(errors="replace").strip()
        raise RuntimeError(f"opencli 命令失败: {msg}")
    return stdout.decode(errors="replace").strip()


def _parse_eval_output(raw: str) -> dict:
    """解析 eval 返回的 JSON；兼容裸 JSON 与 envelope 包裹两种格式。"""
    if not raw:
        return {}
    # 直接解析
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        pass
    # OpenCLI 可能将结果包裹在 {"result": "..."} 等 envelope 中
    try:
        envelope = json.loads(raw)
        if isinstance(envelope, dict):
            for key in ("result", "data", "value", "output"):
                inner = envelope.get(key)
                if isinstance(inner, str):
                    try:
                        return json.loads(inner)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(inner, dict):
                    return inner
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _extract_price(text: str) -> float:
    """从价格文本中提取数值，失败返回 0。"""
    for pattern in _PRICE_PATTERNS:
        m = pattern.search(text)
        if m:
            return float(m.group(1))
    return 0.0


async def crawl_product_page(url: str) -> dict[str, Any]:
    """用 OpenCLI 通过已登录 Chrome 抓取商品页并返回预填数据。

    依赖 OpenCLI + Chrome Browser Bridge 扩展；未安装或未连接时抛出异常，
    员工可退回手动填写。返回结构与旧 Scrapling 实现一致，product_admin 无需改动。
    """
    # 在已登录 Chrome 中打开商品页（后台模式，不抢占焦点）
    try:
        await _run_opencli("browser", _SESSION, "open", url, "--window", "background")
    except FileNotFoundError as exc:
        raise RuntimeError(
            "爬虫依赖 OpenCLI 未安装：npm install -g @jackwener/opencli"
        ) from exc
    except RuntimeError as exc:
        msg = str(exc).lower()
        if any(k in msg for k in ("not connected", "extension", "bridge", "no session")):
            raise RuntimeError(
                "OpenCLI 浏览器桥未连接，请在 Chrome 安装 OpenCLI 扩展并保持 Chrome 运行"
            ) from exc
        raise RuntimeError(f"打开商品页失败: {exc}") from exc

    # 等待页面渲染（抖音/淘宝为 SPA，需 JS 渲染时间）
    try:
        await _run_opencli("browser", _SESSION, "wait", "time", "3")
    except RuntimeError:
        pass  # 等待失败不阻塞后续提取

    # 用 JS 提取商品字段
    raw = await _run_opencli("browser", _SESSION, "eval", _EXTRACT_JS)
    data = _parse_eval_output(raw)

    # eval 未返回 JSON 时，用 extract 获取页面 markdown 兜底
    if not data:
        try:
            md = await _run_opencli("browser", _SESSION, "extract")
            # 从 markdown 提取标题（首个 # 标题或首行）与描述（首段）
            lines = md.strip().split("\n")
            md_title = ""
            for line in lines:
                line = line.strip()
                if line and not line.startswith("!["):
                    md_title = line.lstrip("# ").strip()
                    break
            data = {
                "title": md_title,
                "description": md[:500],
                "priceText": md,
                "gallery": [],
                "ogImage": "",
            }
        except RuntimeError:
            data = {}

    title = str(data.get("title") or "").strip()
    if not title:
        raise RuntimeError("无法从页面提取商品标题，请确认链接为商品详情页。")

    price = _extract_price(str(data.get("priceText") or ""))
    gallery = [str(g) for g in (data.get("gallery") or []) if g]
    og_image = str(data.get("ogImage") or "")
    cover = og_image or (gallery[0] if gallery else "")

    # 释放浏览器会话标签
    try:
        await _run_opencli("browser", _SESSION, "close")
    except RuntimeError:
        pass

    return {
        "title": title,
        "subtitle": "",
        "price": price,
        "original_price": price,
        "cover": cover,
        "cover_color": "#E5E7EB",
        "description": str(data.get("description") or ""),
        "gallery": gallery,
        "source_url": url,
    }
