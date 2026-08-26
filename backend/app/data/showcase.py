# 星途户外照明专卖店橱窗数据
from decimal import Decimal

SHOP_NAME = "星途户外照明专卖店"

# 商品分类：code 供前端与 API 筛选使用，name 为展示名
PRODUCT_CATEGORIES = [
    {"code": "post", "name": "柱头灯"},
    {"code": "wall", "name": "户外壁灯"},
    {"code": "solar", "name": "太阳能庭院灯"},
]

# 线上云托管 SQLite 默认是空库，必须把真实灯具打进种子，否则商城只有 3 条 Unsplash 占位图。
PRODUCTS = [
    {
        "product_id": "P10009",
        "title": "太阳能柱头灯户外防水现代简约LED庭院灯福字方形围墙灯后现代",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("350.00"),
        "original_price": Decimal("350.00"),
        "sales_count": 5,
        "cover": "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01qArpbV2EEc42JxzHt_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01qArpbV2EEc42JxzHt_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯户外防水现代简约LED庭院灯福字方形围墙灯后现代",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "光源",
                "value": "LED",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "现代简约",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10009",
                "spec": "默认规格",
                "price": Decimal("350.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1052884103493",
    },
    {
        "product_id": "P10010",
        "title": "太阳能柱头灯中式庭院灯户外防水别墅大门围墙灯不锈钢景观灯我买过的宝贝新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("150.00"),
        "original_price": Decimal("150.00"),
        "sales_count": 2,
        "cover": "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN01j0VUuq2EEc3zUqSaR_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN01j0VUuq2EEc3zUqSaR_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN01FKDsvq2EEc3zIYRKR_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01DwFSO72EEc3yySAfB_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN01AAs5Gn2EEc3uLMArx_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN01GkOMHR2EEc3uLIQ1s_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN01MuzvlZ2EEc3ypfQxH_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01xVI1Xe2EEc3z2kp66_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN01kuShny2EEc3yySm7o_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN01yN6iwH2EEc3ylycuM_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01Jj8EHf2EEc3z82Q6c_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01ai5t8P2EEc3z2j8yH_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN01jSywAK2EEc40UEdhl_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN013DdomO2EEc3zV8isx_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯中式庭院灯户外防水别墅大门围墙灯不锈钢景观灯我买过的宝贝新中式",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10010",
                "spec": "默认规格",
                "price": Decimal("150.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1054553644078",
    },
    {
        "product_id": "P10011",
        "title": "太阳能柱头灯户外庭院中式别墅围墙立柱灯自动开关智能光控新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("110.00"),
        "original_price": Decimal("110.00"),
        "sales_count": 1,
        "cover": "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01PxLJ0B2EEc3XigPZC_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01PxLJ0B2EEc3XigPZC_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯户外庭院中式别墅围墙立柱灯自动开关智能光控新中式",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10011",
                "spec": "默认规格",
                "price": Decimal("110.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1043402419320",
    },
    {
        "product_id": "P10012",
        "title": "中式复古柱头灯户外防水LED庭院灯菱形格栅装饰灯新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("125.00"),
        "original_price": Decimal("125.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01s2taYg2EEc3XbTRUu_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01s2taYg2EEc3XbTRUu_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "中式复古柱头灯户外防水LED庭院灯菱形格栅装饰灯新中式",
        "specs": [
            {
                "label": "光源",
                "value": "LED",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10012",
                "spec": "默认规格",
                "price": Decimal("125.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1045018565517",
    },
    {
        "product_id": "P10013",
        "title": "太阳能柱头灯户外庭院别墅围墙立柱灯中式复古门柱灯新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("88.00"),
        "original_price": Decimal("88.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i1/2219633788713/O1CN01jJPf7o2EEc3Xkl3JS_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i1/2219633788713/O1CN01jJPf7o2EEc3Xkl3JS_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯户外庭院别墅围墙立柱灯中式复古门柱灯新中式",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10013",
                "spec": "默认规格",
                "price": Decimal("88.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1045033393366",
    },
    {
        "product_id": "P10014",
        "title": "中式太阳能柱头灯LED户外庭院灯山水装饰照明灯具新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("135.00"),
        "original_price": Decimal("135.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i2/2219633788713/O1CN017ejPSr2EEc3X7Qn1V_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i2/2219633788713/O1CN017ejPSr2EEc3X7Qn1V_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "中式太阳能柱头灯LED户外庭院灯山水装饰照明灯具新中式",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "光源",
                "value": "LED",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10014",
                "spec": "默认规格",
                "price": Decimal("135.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1045897820430",
    },
    {
        "product_id": "P10015",
        "title": "中式复古柱头灯别墅庭院围墙灯户外防水太阳能柱子灯新中式",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("120.00"),
        "original_price": Decimal("120.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN01ifykji2EEc3XiDL9X_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN01ifykji2EEc3XiDL9X_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "中式复古柱头灯别墅庭院围墙灯户外防水太阳能柱子灯新中式",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10015",
                "spec": "默认规格",
                "price": Decimal("120.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1045972444679",
    },
    {
        "product_id": "P10016",
        "title": "太阳能柱头灯户外防水别墅庭院灯中式围墙门柱氛围景观灯后现代",
        "subtitle": "星途户外照明",
        "category": "太阳能庭院灯",
        "category_code": "solar",
        "price": Decimal("180.00"),
        "original_price": Decimal("180.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i1/2219633788713/O1CN01zUwLOn2EEc3uIBClB_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i1/2219633788713/O1CN01zUwLOn2EEc3uIBClB_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯户外防水别墅庭院灯中式围墙门柱氛围景观灯后现代",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10016",
                "spec": "默认规格",
                "price": Decimal("180.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1053631145805",
    },
    {
        "product_id": "P10017",
        "title": "现代简约LED壁灯户外防水IP65玻璃灯罩壁挂灯具led灯现代3000K - 4000K",
        "subtitle": "星途户外照明",
        "category": "户外壁灯",
        "category_code": "wall",
        "price": Decimal("100.00"),
        "original_price": Decimal("100.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01pM73j72EEc4wWDPkg_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01pM73j72EEc4wWDPkg_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "现代简约LED壁灯户外防水IP65玻璃灯罩壁挂灯具led灯现代3000K - 4000K",
        "specs": [
            {
                "label": "光源",
                "value": "LED",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "现代简约",
            },
            {
                "label": "安装",
                "value": "壁挂",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10017",
                "spec": "默认规格",
                "price": Decimal("100.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1070633391901",
    },
    {
        "product_id": "P10018",
        "title": "中式古典柱头灯方形福字装饰庭院围墙灯太阳能户外灯具",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("160.00"),
        "original_price": Decimal("160.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN018dvU092EEc4wThSf0_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN018dvU092EEc4wThSf0_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01n0bUW52EEc4wSLF9w_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN01cDFI3b2EEc4wWwOfV_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN01mEfsRk2EEc4wPp8v1_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN01c1EZaR2EEc4wgWhwW_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN013i7b7D2EEc4wSPKtY_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01RspbOo2EEc4wQSxUD_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN01GxYeAP2EEc4wWzxBH_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i2/2219633788713/O1CN01C3te7M2EEc4wij1Ru_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "中式古典柱头灯方形福字装饰庭院围墙灯太阳能户外灯具",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "风格",
                "value": "中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10018",
                "spec": "默认规格",
                "price": Decimal("160.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1071451222717",
    },
    {
        "product_id": "P10019",
        "title": "中式LED壁挂式户外壁灯玻璃灯罩铝材防水庭院灯具led灯中式2700K - 3000K",
        "subtitle": "星途户外照明",
        "category": "户外壁灯",
        "category_code": "wall",
        "price": Decimal("105.00"),
        "original_price": Decimal("105.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN017mFF262EEc4wkSydp_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i4/2219633788713/O1CN017mFF262EEc4wkSydp_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i4/2219633788713/O1CN012iu4ip2EEc4wUiH60_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01OUhigG2EEc4wit3r2_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN01bMJ2gh2EEc4wTLeoX_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN01zzI3QD2EEc4wgm662_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i1/2219633788713/O1CN01KJeGKD2EEc4wiqmEN_!!2219633788713.jpg",
            "https://gw.alicdn.com/bao/uploaded/i3/2219633788713/O1CN01Ylnm3I2EEc4wUjg03_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "中式LED壁挂式户外壁灯玻璃灯罩铝材防水庭院灯具led灯中式2700K - 3000K",
        "specs": [
            {
                "label": "光源",
                "value": "LED",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "中式",
            },
            {
                "label": "安装",
                "value": "壁挂",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10019",
                "spec": "默认规格",
                "price": Decimal("105.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1071482054869",
    },
    {
        "product_id": "P10020",
        "title": "太阳能柱头灯户外别墅庭院灯中式复古围栏灯防水装饰灯",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("138.00"),
        "original_price": Decimal("138.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01C4M1Cy2EEc4wFU0KA_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i3/2219633788713/O1CN01C4M1Cy2EEc4wFU0KA_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "太阳能柱头灯户外别墅庭院灯中式复古围栏灯防水装饰灯",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10020",
                "spec": "默认规格",
                "price": Decimal("138.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1072505209069",
    },
    {
        "product_id": "P10021",
        "title": "新中式太阳能柱头灯防水防锈复古方形柱子灯庭院装饰灯具新中式5W及以下",
        "subtitle": "星途户外照明",
        "category": "柱头灯",
        "category_code": "post",
        "price": Decimal("120.00"),
        "original_price": Decimal("120.00"),
        "sales_count": 0,
        "cover": "https://img.alicdn.com/imgextra/i2/2219633788713/O1CN010ktEVf2EEc3Wiavtk_!!2219633788713.jpg",
        "gallery": [
            "https://img.alicdn.com/imgextra/i2/2219633788713/O1CN010ktEVf2EEc3Wiavtk_!!2219633788713.jpg",
        ],
        "cover_color": "#FDE68A",
        "description": "新中式太阳能柱头灯防水防锈复古方形柱子灯庭院装饰灯具新中式5W及以下",
        "specs": [
            {
                "label": "供电方式",
                "value": "太阳能",
            },
            {
                "label": "防护",
                "value": "户外防水",
            },
            {
                "label": "风格",
                "value": "新中式",
            },
            {
                "label": "安装",
                "value": "柱头/围墙",
            },
        ],
        "skus": [
            {
                "sku_id": "SKU-P10021",
                "spec": "默认规格",
                "price": Decimal("120.00"),
                "stock": 50,
                "threshold": 5,
            },
        ],
        "status": "on_sale",
        "tags": [
            "太阳能",
            "户外照明",
        ],
        "services": [
            "7天无理由退换",
            "全国包邮",
        ],
        "source_url": "https://item.taobao.com/item.htm?id=1045850344964",
    }
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
