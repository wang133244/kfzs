const CLOUD_API = 'https://prod-302921-8-1474916664.sh.run.tcloudbase.com'
const LOCAL_API = 'http://127.0.0.1:8000'
// true：优先走微信云托管 callContainer；失败时回退到公网地址（开发者工具可关域名校验）
const USE_CLOUD = true

function apiBase(url) {
  return String(url || '').replace(/\/+$/, '')
}

module.exports = {
  USE_CLOUD,
  BASE_URL: apiBase(USE_CLOUD ? CLOUD_API : LOCAL_API),
  // 云开发（存储、云函数）
  CLOUD_ENV: 'cloud1-d5g3o1bt42e26dbb7',
  // 云托管 callContainer 必须填控制台里的云托管环境 ID，不是 cloud1-xxx
  CLOUD_RUN_ENV: 'prod-d8gjtu72q399a7680',
  // 服务名，不是版本号 prod-021
  CLOUD_SERVICE: 'prod',
  INTRO_MESSAGE:
    '您好，我是星途户外照明专卖店智能客服，可以帮您推荐柱头灯、户外壁灯和庭院灯，也可以查询订单、物流和售后。有什么可以帮您的吗？'
}
