# 星途客服小程序（顾客端 + 后端）

小程序和 FastAPI 后端都在本目录。以后只启动这里的后端，不再使用桌面上的「自动化电商客服助手」。

## 启动后端

在本文件夹双击 `启动后端.bat`，或在终端执行：

```bash
cd backend
conda run -n langchain python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

服务地址：`http://127.0.0.1:8000`  
健康检查：`http://127.0.0.1:8000/api/v1/healthz`

需要本机已安装 conda 环境 `langchain`（已装过原项目依赖即可）。

## 打开小程序

1. 先启动上面的后端。
2. 打开 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)。
3. 导入本文件夹：`C:\Users\wang2\Desktop\星途客服小程序`
4. 右上角详情 → 本地设置：勾选 **不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书**。

## 登录

- 普通用户：微信一键登录（开发者工具里也会记住同一模拟用户）
- 测试账号：`customer` / `Customer@123`
- 管理员：`admin` / `Admin@123456`

## 功能

- 客服对话（含清空对话、商品卡片）
- 灯具橱窗与商品详情
- 购物车钱包下单：初始余额 2000 元，下单扣款并生成订单（不发货）
- 个人中心：头像 / 用户名可改、钱包、订单查询
- 订单号格式为下单时间，例如 `2024.12.3.8.23.12`

接口地址在 `utils/config.js` 的 `BASE_URL`，默认 `http://127.0.0.1:8000`。
