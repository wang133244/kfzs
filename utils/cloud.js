const { CLOUD_ENV, CLOUD_SERVICE } = require('./config')

function explainCloudError(err) {
  const msg = String((err && (err.errMsg || err.message)) || '')
  if (msg.indexOf('not a function') >= 0) {
    return '当前基础库过低，请将最低基础库设为 2.23.0 以上'
  }
  if (/appid|resourceAppid|Authorization mismatch/i.test(msg)) {
    return '云托管环境与当前小程序不匹配'
  }
  if (/service|X-WX-SERVICE|not found/i.test(msg)) {
    return '找不到云托管服务 prod，请在控制台核对服务名'
  }
  if (msg.indexOf('timeout') >= 0) return '云托管响应超时'
  const cleaned = msg.replace(/^[^:]+:fail\s*/i, '').trim()
  return cleaned || '无法连接云托管'
}

function callContainer(options) {
  const opts = options || {}
  if (!wx.cloud || typeof wx.cloud.callContainer !== 'function') {
    return Promise.reject(new Error('当前基础库过低，请将最低基础库设为 2.23.0 以上'))
  }
  try {
    wx.cloud.init({
      env: CLOUD_ENV,
      traceUser: true
    })
  } catch (err) {}

  const payload = {
    config: { env: CLOUD_ENV },
    path: opts.path,
    method: opts.method || 'GET',
    header: Object.assign(
      {
        'X-WX-SERVICE': CLOUD_SERVICE,
        'content-type': 'application/json'
      },
      opts.header || {}
    )
  }
  if (opts.data !== undefined) payload.data = opts.data
  if (opts.dataType) payload.dataType = opts.dataType
  if (opts.responseType) payload.responseType = opts.responseType

  return wx.cloud.callContainer(payload).catch((err) => {
    const wrapped = new Error(explainCloudError(err))
    wrapped.raw = err
    return Promise.reject(wrapped)
  })
}

function ensureCloud() {
  try {
    if (wx.cloud) {
      wx.cloud.init({ env: CLOUD_ENV, traceUser: true })
    }
  } catch (err) {}
  return Promise.resolve(wx.cloud)
}

module.exports = {
  ensureCloud,
  callContainer,
  explainCloudError
}
