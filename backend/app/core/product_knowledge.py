# 根据橱窗在售商品生成 RAG 知识库 Markdown，供客服回答商品咨询。
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "data" / "knowledge" / "products.md"


def _money(value: object) -> str:
    number = float(value if not isinstance(value, Decimal) else value)
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}"


def _render_product(product: dict) -> str:
    title = str(product.get("title") or "未命名商品").strip()
    category = str(product.get("category") or "灯具")
    subtitle = str(product.get("subtitle") or "").strip()
    description = str(product.get("description") or "").strip()
    if description.startswith("来源:"):
        description = ""
    price = _money(product.get("price") or 0)
    original = _money(product.get("original_price") or product.get("price") or 0)
    tags = "、".join(str(t) for t in (product.get("tags") or []) if t)
    services = "、".join(str(s) for s in (product.get("services") or []) if s)
    specs = product.get("specs") or []
    spec_lines = "\n".join(
        f"- {item.get('label', '')}：{item.get('value', '')}"
        for item in specs
        if item.get("label")
    )
    sku_lines = "\n".join(
        f"- {sku.get('spec') or sku.get('sku_id')}，售价 {_money(sku.get('price') or price)} 元，库存 {int(sku.get('stock') or 0)} 件"
        for sku in (product.get("skus") or [])
    )
    pid = product.get("product_id") or ""
    lines = [
        f"# {title}",
        "",
        f"商品编号 {pid}，分类 {category}。售价 {price} 元，原价 {original} 元。",
    ]
    if subtitle:
        lines.append(f"卖点：{subtitle}。")
    if tags:
        lines.append(f"标签：{tags}。")
    if description:
        lines.extend(["", "## 商品介绍", "", description])
    if spec_lines:
        lines.extend(["", "## 规格参数", "", spec_lines])
    if sku_lines:
        lines.extend(["", "## 规格与库存", "", sku_lines])
    if services:
        lines.extend(["", "## 服务承诺", "", services + "。"])
    lines.extend(
        [
            "",
            "## 常见问题",
            "",
            f"- {title} 当前售价 {price} 元。",
            f"- 本款属于{category}，商品编号 {pid}。",
        ]
    )
    return "\n".join(lines).strip()


def build_product_knowledge_markdown(products: list[dict]) -> str:
    on_sale = [p for p in products if p.get("status", "on_sale") == "on_sale"]
    grouped: dict[str, list[dict]] = {}
    for product in on_sale:
        grouped.setdefault(str(product.get("category") or "灯具"), []).append(product)

    overview = [
        "# 店铺商品总览",
        "",
        "本店为星途户外照明专卖店，只经营户外灯具：柱头灯、户外壁灯与太阳能庭院灯。",
        f"当前在售 {len(on_sale)} 款，分类包括柱头灯、户外壁灯、太阳能庭院灯，全部支持全国包邮和 7 天无理由退换。",
        "客服介绍商品时必须使用下面清单中的真实名称、售价和规格，不要编造没有的型号。",
        "",
        "## 在售清单",
        "",
    ]
    for category, items in grouped.items():
        overview.append(f"### {category}")
        overview.append("")
        for product in items:
            overview.append(
                f"- {product.get('title')}（{product.get('product_id')}），售价 {_money(product.get('price') or 0)} 元"
            )
        overview.append("")
    overview.extend(
        [
            "## 选购建议",
            "",
            "- 别墅大门、围墙立柱：推荐太阳能柱头灯，一般不用接线。",
            "- 外墙、走廊、大门两侧：推荐户外壁灯，注意防水等级。",
            "- 花园、围栏氛围照明：推荐太阳能庭院灯。",
            "- 问有什么灯、推荐灯具时，按上述分类介绍在售清单中的具体商品和价格。",
            "",
        ]
    )
    parts = ["\n".join(overview).strip()]
    parts.extend(_render_product(product) for product in on_sale)
    parts.append(GENERIC_FAQ)
    return "\n\n".join(parts) + "\n"


GENERIC_FAQ = """
# 太阳能柱头灯

## 商品介绍

太阳能柱头灯适合别墅大门、庭院围墙立柱安装。日间太阳能板蓄电，夜间光控自动亮灯，铝材灯体户外防水。
星途户外照明提供现代简约、新中式、福字装饰等多种造型，电压通常为安全低压（≤36V）。

## 规格参数

- 供电方式：太阳能
- 光源：LED
- 防护：户外防水
- 安装位置：柱头 / 围墙立柱
- 常见风格：新中式、现代简约、后现代

## 保修与售后

- 保修期：12 个月
- 支持 7 天无理由退换
- 支持全国包邮

## 常见问题

- 问：耐用吗？答：户外灯做了防水，不锈钢或铝材灯体，日常风吹雨淋能用，不要长时间泡在水里。
- 问：阴天能亮吗？答：连续阴雨天续航会缩短，一般仍可维持数小时照明，晴天会自动补电。
- 问：需要接线吗？答：太阳能款通常无需市电布线，按说明书固定在柱头即可。
- 问：柱头灯怎么安装？答：先确认柱头尺寸与灯座匹配，将灯座固定在立柱顶部，再装上灯体；太阳能款对准阳光方向即可。
- 问：怎么开关？答：多数为光控自动开关，天黑亮、天亮灭；部分款式支持手动开关。

# 户外壁灯

## 商品介绍

户外壁灯采用 LED 光源与防水灯体，适合别墅外墙、庭院走廊、大门两侧壁挂安装。
常见防护等级 IP65，玻璃灯罩，色温约 2700K-4000K，夜间照明柔和。

## 规格参数

- 光源：LED
- 防护：IP65 防水
- 安装：壁挂
- 色温：约 2700K-4000K
- 材质：铝材 / 玻璃灯罩

## 保修与售后

- 保修期：12 个月
- 支持 7 天无理由退换
- 支持全国包邮

## 常见问题

- 问：室内能装吗？答：本店壁灯按户外防护设计，室内也可使用，但外观更偏庭院风格。
- 问：防水吗？答：户外壁灯一般为 IP65，可淋雨，不建议长时间浸泡。

# 太阳能庭院灯

## 商品介绍

太阳能庭院灯用于花园、围栏、庭院氛围照明，日间充电、天黑自动点亮，无需布线。
星途户外照明新中式与现代简约款均可用于别墅庭院装饰。

## 规格参数

- 供电方式：太阳能
- 控制：光控自动开关
- 安装：庭院 / 围栏 / 地面
- 风格：新中式或现代简约

## 保修与售后

- 保修期：12 个月
- 支持 7 天无理由退换
- 支持全国包邮

## 常见问题

- 问：灯具怎么充电？答：太阳能款将灯具置于阳光直射处即可充电，无需插电。
- 问：有柱头灯推荐吗？答：庭院围墙立柱建议选太阳能柱头灯；外墙建议选户外壁灯。请按在售清单中的具体型号和售价介绍。

# 购物与客服

购买方式：在小程序橱窗选择灯具加入购物车，使用钱包余额结算下单即可。
客服营业时间：在线客服每天 9:00-22:00 在线。
运费与包邮：本店在售灯具支持全国包邮。
发票：商品默认开具电子发票，确认收货后可在订单详情中申请开票。
钱包支付：下单时使用小程序钱包余额结算；余额不足请先充值后再下单。
""".strip()


def live_catalog_chunks(products: list[dict]) -> list[dict]:
    # 把当前在售商品做成整块文本，混合检索时即使向量库未重建也能命中真实售价
    on_sale = [p for p in products if p.get("status", "on_sale") == "on_sale"]
    if not on_sale:
        return []
    overview_lines = ["本店在售灯具清单，以下名称与售价以当前橱窗为准。"]
    for product in on_sale:
        overview_lines.append(
            f"{product.get('title')}（{product.get('product_id')}）售价 {_money(product.get('price') or 0)} 元，分类 {product.get('category')}。"
        )
    chunks = [{"text": "\n".join(overview_lines), "source": "products.md"}]
    chunks.extend({"text": _render_product(product), "source": "products.md"} for product in on_sale)
    return chunks


def write_product_knowledge(products: list[dict]) -> Path:
    KNOWLEDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_PATH.write_text(build_product_knowledge_markdown(products), encoding="utf-8")
    from ..rag.store import invalidate_knowledge_cache

    invalidate_knowledge_cache()
    return KNOWLEDGE_PATH


def sync_from_memory(*, rebuild_index: bool = False) -> None:
    # 测试环境不改仓库内 Markdown，避免覆盖线上淘宝灯具知识
    from ..config import settings
    from ..data import showcase
    from ..rag.store import invalidate_knowledge_cache

    if settings.env == "test":
        invalidate_knowledge_cache()
        return
    write_product_knowledge(list(showcase.PRODUCTS))
    if rebuild_index:
        from ..rag.store import get_collection

        get_collection(rebuild=True)

