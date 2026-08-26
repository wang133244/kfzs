# 星途户外照明专卖店橱窗数据
from decimal import Decimal

SHOP_NAME = "星途户外照明专卖店"

# 商品分类：code 供前端与 API 筛选使用，name 为展示名
PRODUCT_CATEGORIES = [
    {"code": "post", "name": "柱头灯"},
    {"code": "wall", "name": "户外壁灯"},
    {"code": "solar", "name": "太阳能庭院灯"},
]

# 空库时的种子商品（测试与首次启动）。线上已导入的淘宝灯具以数据库为准。
PRODUCTS = [
    {
        "product_id": "P10001",
        "title": "太阳能柱头灯 户外防水 LED 庭院围墙灯",
        "subtitle": "星途户外照明 · 光控开关 · 太阳能供电",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("350.00"),
        "original_price": Decimal("420.00"),
        "sales_count": 128,
        "cover": "https://images.unsplash.com/photo-1565814329452-a99b4d08b1d5?auto=format&fit=crop&w=800&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1565814329452-a99b4d08b1d5?auto=format&fit=crop&w=800&q=80",
            "https://images.unsplash.com/photo-1513506003901-1e6a229e2d15?auto=format&fit=crop&w=800&q=80",
        ],
        "cover_color": "#FDE68A",
        "description": "星途户外照明柱头灯，太阳能板日间蓄电、夜间自动亮灯。铝材灯体户外防水，适合别墅大门、庭院围墙立柱安装。",
        "specs": [
            {"label": "供电方式", "value": "太阳能"},
            {"label": "光源", "value": "LED"},
            {"label": "防护", "value": "户外防水"},
            {"label": "安装", "value": "柱头/围墙"},
        ],
        "skus": [
            {
                "sku_id": "SKU001",
                "spec": "方形福字 · 标准款",
                "price": Decimal("350.00"),
                "stock": 40,
                "threshold": 8,
            },
        ],
        "status": "on_sale",
        "tags": ["太阳能", "柱头灯"],
        "services": ["7 天无理由退换", "全国包邮", "12 个月保修"],
        "source_url": "",
    },
    {
        "product_id": "P10002",
        "title": "现代简约 LED 户外壁灯 IP65 防水",
        "subtitle": "星途户外照明 · 玻璃灯罩 · 壁挂安装",
        "category": "户外壁灯",
        "category_code": "wall",
        "price": Decimal("100.00"),
        "original_price": Decimal("139.00"),
        "sales_count": 86,
        "cover": "https://images.unsplash.com/photo-1507473883500-6e3d4d484e46?auto=format&fit=crop&w=800&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1507473883500-6e3d4d484e46?auto=format&fit=crop&w=800&q=80",
        ],
        "cover_color": "#E0E7FF",
        "description": "户外壁灯采用 IP65 防护与玻璃灯罩，适合别墅外墙、庭院走廊。色温约 3000K-4000K，夜间照明柔和。",
        "specs": [
            {"label": "光源", "value": "LED"},
            {"label": "防护", "value": "IP65 防水"},
            {"label": "安装", "value": "壁挂"},
            {"label": "色温", "value": "3000K-4000K"},
        ],
        "skus": [
            {
                "sku_id": "SKU002",
                "spec": "现代简约 · 黑色",
                "price": Decimal("100.00"),
                "stock": 36,
                "threshold": 8,
            },
        ],
        "status": "on_sale",
        "tags": ["壁灯", "IP65"],
        "services": ["7 天无理由退换", "全国包邮", "12 个月保修"],
        "source_url": "",
    },
    {
        "product_id": "P10003",
        "title": "新中式太阳能庭院灯 光控自动开关",
        "subtitle": "星途户外照明 · 智能光控 · 庭院氛围",
        "category": "太阳能庭院灯",
        "category_code": "solar",
        "price": Decimal("180.00"),
        "original_price": Decimal("238.00"),
        "sales_count": 64,
        "cover": "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=800&q=80",
        "gallery": [
            "https://images.unsplash.com/photo-1494438639946-1ebd1d20bf85?auto=format&fit=crop&w=800&q=80",
        ],
        "cover_color": "#FEF3C7",
        "description": "太阳能庭院灯日间充电、天黑自动点亮，适合庭院、花园、围栏装饰照明，无需布线。",
        "specs": [
            {"label": "供电方式", "value": "太阳能"},
            {"label": "控制", "value": "光控自动开关"},
            {"label": "风格", "value": "新中式"},
            {"label": "安装", "value": "庭院/围栏"},
        ],
        "skus": [
            {
                "sku_id": "SKU003",
                "spec": "新中式 · 标准款",
                "price": Decimal("180.00"),
                "stock": 28,
                "threshold": 6,
            },
        ],
        "status": "on_sale",
        "tags": ["太阳能", "庭院灯"],
        "services": ["7 天无理由退换", "全国包邮", "12 个月保修"],
        "source_url": "",
    },
]

AFTER_SALES = [
    {
        "after_sale_id": "AS20260817001",
        "order_id": "1002",
        "product": "中式户外壁灯",
        "amount": Decimal("105.00"),
        "status": "refunding",
        "status_cn": "退款中",
        "reason": "尺寸不合适",
        "applied_at": "2026-08-17 10:24:00",
    },
    {
        "after_sale_id": "AS20260815002",
        "order_id": "1001",
        "product": "太阳能柱头灯",
        "amount": Decimal("350.00"),
        "status": "closed",
        "status_cn": "已关闭",
        "reason": "撤销申请",
        "applied_at": "2026-08-15 16:02:00",
    },
    {
        "after_sale_id": "AS20260810003",
        "order_id": "1005",
        "product": "太阳能庭院灯",
        "amount": Decimal("180.00"),
        "status": "refunded",
        "status_cn": "已退款",
        "reason": "外观色差",
        "applied_at": "2026-08-10 09:41:00",
    },
]
