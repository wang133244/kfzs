const { USE_CLOUD, BASE_URL } = require('./config')
const { getToken, expireSession } = require('./auth')
const cloud = require('./cloud')

function isPublicShopPath(path) {
  return (
    path.indexOf('/api/v1/shop/categories') === 0 ||
    path.indexOf('/api/v1/shop/products') === 0 ||
    path.indexOf('/api/v1/shop/cover-proxy') === 0
  )
}

function parseDetail(data) {
  let body = data
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body)
    } catch (err) {
      return '请求失败'
    }
  }
  const detail = body && body.detail
  return typeof detail === 'string' ? detail : '请求失败'
}

function authHeader(skipAuth) {
  const header = { 'content-type': 'application/json', 'Content-Type': 'application/json' }
  const token = skipAuth ? '' : getToken()
  if (token) header.Authorization = 'Bearer ' + token
  return header
}

function finish(res, resolve, reject, path) {
  if (!res) {
    reject(new Error('无法连接云端客服'))
    return
  }
  if (res.statusCode === 401) {
    if (!isPublicShopPath(path)) expireSession()
    reject(new Error(isPublicShopPath(path) ? 'SHOP_AUTH' : '登录已过期'))
    return
  }
  if (res.statusCode === 204) {
    resolve(null)
    return
  }
  if (res.statusCode < 200 || res.statusCode >= 300) {
    reject(new Error(parseDetail(res.data)))
    return
  }
  let body = res.data
  if (typeof body === 'string') {
    try {
      body = JSON.parse(body)
    } catch (err) {}
  }
  resolve(body)
}

function httpRequest(path, options, skipAuth) {
  const opts = options || {}
  const method = opts.method || 'GET'
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE_URL + path,
      method,
      data: opts.data,
      header: authHeader(skipAuth),
      timeout: 60000,
      success(res) {
        finish(res, resolve, reject, path)
      },
      fail() {
        reject(new Error(USE_CLOUD ? '无法连接云托管公网地址' : '无法连接本机后端，请先启动 backend'))
      }
    })
  })
}

function containerRequest(path, options, skipAuth) {
  const opts = options || {}
  const method = opts.method || 'GET'
  const payload = {
    path,
    method,
    header: authHeader(skipAuth),
    dataType: 'json'
  }
  if (method !== 'GET' && method !== 'HEAD' && method !== 'DELETE') {
    payload.data = opts.data || {}
  }
  return cloud.callContainer(payload).then(
    (res) =>
      new Promise((resolve, reject) => {
        finish(res, resolve, reject, path)
      })
  )
}

function requestOnce(path, options, skipAuth) {
  if (!USE_CLOUD) return httpRequest(path, options, skipAuth)
  return containerRequest(path, options, skipAuth).catch((err) => {
    return httpRequest(path, options, skipAuth).catch(() => Promise.reject(err))
  })
}

function request(path, options) {
  return requestOnce(path, options, false)
    .catch((err) => {
      if (err && err.message === 'SHOP_AUTH' && getToken()) {
        return requestOnce(path, options, true)
      }
      return Promise.reject(err)
    })
    .catch((err) => {
      if (err && err.message === 'SHOP_AUTH') {
        expireSession()
        return Promise.reject(new Error('请先登录后查看橱窗'))
      }
      return Promise.reject(err)
    })
}

function login(username, password) {
  return request('/api/v1/auth/login', {
    method: 'POST',
    data: { username, password }
  })
}

function chat(sessionId, message) {
  return request('/api/v1/chat', {
    method: 'POST',
    data: { session_id: sessionId, message }
  })
}

function listSessions() {
  return request('/api/v1/sessions')
}

function getMessages(sessionId) {
  return request('/api/v1/sessions/' + sessionId + '/messages')
}

function deleteSession(sessionId) {
  return request('/api/v1/sessions/' + sessionId, { method: 'DELETE' })
}

function listShopCategories() {
  return request('/api/v1/shop/categories')
}

function listShopProducts(params) {
  const query = []
  const data = params || {}
  if (data.q) query.push('q=' + encodeURIComponent(data.q))
  if (data.category) query.push('category=' + encodeURIComponent(data.category))
  if (data.page) query.push('page=' + data.page)
  if (data.size) query.push('size=' + data.size)
  const suffix = query.length ? '?' + query.join('&') : ''
  return request('/api/v1/shop/products' + suffix)
}

function getShopProduct(productId) {
  return request('/api/v1/shop/products/' + encodeURIComponent(productId))
}

function wechatLogin(payload) {
  return request('/api/v1/auth/wechat', {
    method: 'POST',
    data: payload
  })
}

function getMe() {
  return request('/api/v1/auth/me')
}

function updateMe(data) {
  return request('/api/v1/auth/me', {
    method: 'PATCH',
    data: data
  })
}

function listMyOrders() {
  return request('/api/v1/auth/me/orders')
}

function checkout(items) {
  return request('/api/v1/shop/checkout', {
    method: 'POST',
    data: { items }
  })
}

function getCart() {
  return request('/api/v1/auth/me/cart')
}

function saveCart(items) {
  return request('/api/v1/auth/me/cart', {
    method: 'PUT',
    data: { items: items || [] }
  })
}

function uploadAvatar(filePath) {
  if (USE_CLOUD) {
    const { CLOUD_ENV } = require('./config')
    const cloudPath = 'avatars/' + Date.now() + '_' + Math.random().toString(36).slice(2, 8) + '.jpg'
    return cloud.ensureCloud().then(
      () =>
        new Promise((resolve, reject) => {
          wx.cloud.uploadFile({
            cloudPath,
            filePath,
            config: { env: CLOUD_ENV },
            success(res) {
              if (!res.fileID) {
                reject(new Error('头像上传失败'))
                return
              }
              updateMe({ avatar_url: res.fileID }).then(resolve).catch(reject)
            },
            fail() {
              reject(new Error('头像上传失败，请在云开发开通云存储'))
            }
          })
        })
    )
  }

  return new Promise((resolve, reject) => {
    const token = getToken()
    wx.uploadFile({
      url: BASE_URL + '/api/v1/auth/me/avatar',
      filePath,
      name: 'file',
      header: token ? { Authorization: 'Bearer ' + token } : {},
      timeout: 60000,
      success(res) {
        if (res.statusCode === 401) {
          expireSession()
          reject(new Error('登录已过期'))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          reject(new Error(parseDetail(res.data)))
          return
        }
        try {
          resolve(typeof res.data === 'string' ? JSON.parse(res.data) : res.data)
        } catch (err) {
          reject(new Error('头像上传失败'))
        }
      },
      fail() {
        reject(new Error('无法连接本机后端，请检查网络'))
      }
    })
  })
}

module.exports = {
  request,
  login,
  wechatLogin,
  getMe,
  updateMe,
  listMyOrders,
  checkout,
  getCart,
  saveCart,
  uploadAvatar,
  chat,
  listSessions,
  getMessages,
  deleteSession,
  listShopCategories,
  listShopProducts,
  getShopProduct
}
