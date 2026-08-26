const { BASE_URL } = require('./config')
const { getToken, expireSession } = require('./auth')

function request(path, options) {
  const opts = options || {}
  return new Promise((resolve, reject) => {
    const header = Object.assign(
      { 'Content-Type': 'application/json' },
      opts.header || {}
    )
    const token = getToken()
    if (token) {
      header.Authorization = 'Bearer ' + token
    }
    wx.request({
      url: BASE_URL + path,
      method: opts.method || 'GET',
      data: opts.data,
      header,
      timeout: 60000,
      success(res) {
        if (res.statusCode === 401) {
          expireSession()
          wx.reLaunch({ url: '/pages/login/login' })
          reject(new Error('登录已过期'))
          return
        }
        if (res.statusCode === 204) {
          resolve(null)
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const detail = res.data && res.data.detail
          reject(new Error(typeof detail === 'string' ? detail : '请求失败'))
          return
        }
        resolve(res.data)
      },
      fail() {
        reject(new Error('无法连接服务器，请确认电脑上后端已在 8000 端口运行，并在开发者工具关闭域名校验'))
      }
    })
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
          wx.reLaunch({ url: '/pages/login/login' })
          reject(new Error('登录已过期'))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          let detail = '头像上传失败'
          try {
            const body = JSON.parse(res.data || '{}')
            if (body.detail) detail = body.detail
          } catch (err) {}
          reject(new Error(detail))
          return
        }
        try {
          resolve(JSON.parse(res.data))
        } catch (err) {
          reject(new Error('头像上传失败'))
        }
      },
      fail() {
        reject(new Error('无法连接服务器，请确认电脑上后端已在 8000 端口运行'))
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
