const { CLOUD_ENV, CLOUD_RUN_ENV, CLOUD_SERVICE } = require('./config')

function runEnvs() {
  const envs = []
  ;[CLOUD_RUN_ENV, CLOUD_ENV].forEach((env) => {
    if (env && envs.indexOf(env) < 0) envs.push(env)
  })
  return envs
}

function explainCloudError(err) {
  const msg = String((err && (err.errMsg || err.message)) || '')
  if (msg.indexOf('not a function') >= 0) {
    return '当前基础库过低，请将最低基础库设为 2.23.0 以上'
  }
  if (/appid|resourceAppid|Authorization mismatch/i.test(msg)) {
    return '云托管环境与当前小程序不匹配'
  }
  if (/service|X-WX-SERVICE|not found/i.test(msg)) {
    return '找不到云托管服务 ' + CLOUD_SERVICE + '，请在控制台核对服务名和环境 ID'
  }
  if (msg.indexOf('timeout') >= 0) return '云托管响应超时'
  const cleaned = msg.replace(/^[^:]+:fail\s*/i, '').trim()
  return cleaned || '无法连接云托管'
}

function isUninitError(err) {
  const msg = String((err && (err.errMsg || err.message)) || '')
  return /isn't enabled|not init|未初始化/i.test(msg)
}

function isMissingService(err) {
  const msg = String((err && (err.errMsg || err.message)) || '')
  return /service|X-WX-SERVICE|not found/i.test(msg)
}

function ensureCloud() {
  try {
    if (wx.cloud) {
      wx.cloud.init({
        env: CLOUD_ENV || wx.cloud.DYNAMIC_CURRENT_ENV,
        traceUser: true
      })
    }
  } catch (err) {}
  return Promise.resolve(wx.cloud)
}

function invoke(payload, env) {
  return wx.cloud.callContainer(
    Object.assign({}, payload, {
      config: { env: env }
    })
  )
}

function tryEnvs(payload, index) {
  const envs = runEnvs()
  const env = envs[index]
  return invoke(payload, env).catch((err) => {
    if (index + 1 < envs.length && isMissingService(err)) {
      return tryEnvs(payload, index + 1)
    }
    return Promise.reject(err)
  })
}

function callContainer(options, retry) {
  const opts = options || {}
  const attempt = retry || 0
  if (!wx.cloud || typeof wx.cloud.callContainer !== 'function') {
    return Promise.reject(new Error('当前基础库过低，请将最低基础库设为 2.23.0 以上'))
  }
  ensureCloud()

  const payload = {
    path: opts.path,
    method: opts.method || 'GET',
    header: Object.assign(
      {
        'X-WX-SERVICE': CLOUD_SERVICE
      },
      opts.header || {}
    )
  }
  if (opts.data !== undefined) payload.data = opts.data
  if (opts.dataType) payload.dataType = opts.dataType
  if (opts.responseType) payload.responseType = opts.responseType

  return tryEnvs(payload, 0).catch((err) => {
    if (attempt < 3 && isUninitError(err)) {
      return new Promise((resolve, reject) => {
        setTimeout(() => {
          callContainer(options, attempt + 1).then(resolve, reject)
        }, 300)
      })
    }
    const wrapped = new Error(explainCloudError(err))
    wrapped.raw = err
    return Promise.reject(wrapped)
  })
}

function connectContainerSocket(path) {
  ensureCloud()
  if (!wx.cloud || typeof wx.cloud.connectContainer !== 'function') {
    return Promise.reject(new Error('当前基础库过低，无法使用云托管 WebSocket'))
  }
  const envs = runEnvs()
  function tryAt(index) {
    if (index >= envs.length) {
      return Promise.reject(new Error('找不到云托管服务 ' + CLOUD_SERVICE))
    }
    return new Promise((resolve, reject) => {
      let settled = false
      const done = (fn) => (value) => {
        if (settled) return
        settled = true
        fn(value)
      }
      const req = {
        config: { env: envs[index] },
        service: CLOUD_SERVICE,
        path: path,
        success: done(resolve),
        fail: done(reject)
      }
      try {
        const ret = wx.cloud.connectContainer(req)
        if (ret && typeof ret.then === 'function') {
          ret.then(done(resolve), done(reject))
        }
      } catch (err) {
        done(reject)(err)
      }
    }).then((res) => {
      const task = res && res.socketTask
      if (task) return task
      return tryAt(index + 1)
    }).catch((err) => {
      if (index + 1 < envs.length && isMissingService(err)) return tryAt(index + 1)
      return Promise.reject(err)
    })
  }
  return tryAt(0)
}

module.exports = {
  ensureCloud,
  callContainer,
  connectContainerSocket,
  explainCloudError
}
