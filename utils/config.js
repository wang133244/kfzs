const CLOUD_API = 'https://prod-302921-8-1474916664.sh.run.tcloudbase.com'
const LOCAL_API = 'http://127.0.0.1:8000'
// 小程序请求云托管；本地调试后端时改为 false
const USE_CLOUD = true

function apiBase(url) {
  return String(url || '').replace(/\/+$/, '')
}

module.exports = {
  BASE_URL: apiBase(USE_CLOUD ? CLOUD_API : LOCAL_API),
  // 腾讯云开发环境 ID。留空则使用微信开发者工具里当前选中的环境
  CLOUD_ENV: 'cloud1-d5g3o1bt42e26dbb7',
  INTRO_MESSAGE: '您好，我是星途户外照明专卖店智能客服，可以帮您推荐柱头灯、户外壁灯和庭院灯，也可以查询订单、物流和售后。有什么可以帮您的吗？'
}
