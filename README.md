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
- 测试账号：`customer` / `Customer@123`（与普通用户同一套顾客界面）
- 管理员：`admin` / `Admin@123456`（独立四栏：用户会话 / 橱窗 / 订单查询 / 我的）

## 功能

- 客服对话（含清空对话、商品卡片）
- 灯具橱窗与商品详情
- 购物车钱包下单：初始余额 2000 元，下单扣款并生成订单（不发货）
- 个人中心：头像 / 用户名可改、钱包、订单查询
- 管理员：微信式用户列表，仅用户转人工后可接入聊天；订单页按「名字 + 订单号」查询
- 订单号格式为下单时间，例如 `2024.12.3.8.23.12`

接口走微信云托管 `callContainer`，**不要**把 `*.sh.run.tcloudbase.com` 配进小程序合法域名（那是测试域名，正式环境会被拒绝）。

小程序默认连接云托管服务 `prod`，环境 ID 在 `utils/config.js` 的 `CLOUD_ENV`。本地调试后端时把 `USE_CLOUD` 改为 `false`。

正式使用前：
1. 云托管控制台确认服务名是 `prod`，并已发布最新版本。
2. 微信公众平台 → 设置 → 基本设置 → **基础库最低版本 2.23.0** 以上。
3. 重新编译 / 上传小程序。无需再配置 request / downloadFile 合法域名。

云上用户、聊天、购物车要持久保存时，给服务 `prod` 增加环境变量（密码只填控制台，不要写进 Git）：

```
MYSQL_ADDRESS=10.31.107.132:3306
MYSQL_USERNAME=root
MYSQL_PASSWORD=开通 MySQL 时设置的密码
MYSQL_DATABASE=doudian
```

本机不配这几项，继续用 SQLite。改完环境变量后必须重新发布 `prod`。
