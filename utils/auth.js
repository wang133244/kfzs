const TOKEN_KEY = 'xingtu_token'
const ROLE_KEY = 'xingtu_role'
const USERNAME_KEY = 'xingtu_username'
const AVATAR_KEY = 'xingtu_avatar'
const WALLET_KEY = 'xingtu_wallet'
const LOGIN_TYPE_KEY = 'xingtu_login_type'
const LOCAL_KEY = 'xingtu_local_key'
const SKIP_AUTO_LOGIN_KEY = 'xingtu_skip_auto_login'
const USER_ID_KEY = 'xingtu_user_id'
const { BASE_URL } = require('./config')

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || ''
}

function getRole() {
  return wx.getStorageSync(ROLE_KEY) || ''
}

function getUsername() {
  return wx.getStorageSync(USERNAME_KEY) || ''
}

function getAvatar() {
  return wx.getStorageSync(AVATAR_KEY) || ''
}

function getWallet() {
  const value = wx.getStorageSync(WALLET_KEY)
  return typeof value === 'number' ? value : 2000
}

function getLoginType() {
  return wx.getStorageSync(LOGIN_TYPE_KEY) || ''
}

function getUserId() {
  const value = wx.getStorageSync(USER_ID_KEY)
  return value ? String(value) : ''
}

function isLoggedIn() {
  return Boolean(getToken())
}

function getLocalKey() {
  let key = wx.getStorageSync(LOCAL_KEY)
  if (!key) {
    key = 'mp_' + Date.now() + '_' + Math.random().toString(36).slice(2, 10)
    wx.setStorageSync(LOCAL_KEY, key)
  }
  return key
}

function resolveMediaUrl(url) {
  const value = (url || '').trim()
  if (!value) return '/assets/default-avatar.png'
  if (value.indexOf('cloud://') === 0) return value
  if (value.indexOf('/uploads/') === 0 || value.indexOf('/api/v1/') === 0) {
    return BASE_URL ? BASE_URL + value : value
  }
  return value
}

function resolveProductMedia(url) {
  const value = (url || '').trim()
  if (!value) return ''
  if (value.indexOf('cloud://') === 0) return value
  if (value.indexOf('/uploads/') === 0 || value.indexOf('/api/v1/') === 0) {
    return BASE_URL ? BASE_URL + value : value
  }
  return value
}

function saveAuth(data) {
  wx.setStorageSync(TOKEN_KEY, data.access_token || '')
  wx.setStorageSync(ROLE_KEY, data.role || '')
  wx.setStorageSync(USERNAME_KEY, data.username || '')
  wx.setStorageSync(AVATAR_KEY, data.avatar_url || '')
  const userId = data.user_id || data.id
  if (userId) {
    wx.setStorageSync(USER_ID_KEY, String(userId))
  }
  if (typeof data.wallet_balance === 'number') {
    wx.setStorageSync(WALLET_KEY, data.wallet_balance)
  }
  if (data.login_type) {
    wx.setStorageSync(LOGIN_TYPE_KEY, data.login_type)
  }
}

function saveProfile(data) {
  if (data.username) wx.setStorageSync(USERNAME_KEY, data.username)
  if (typeof data.avatar_url === 'string') wx.setStorageSync(AVATAR_KEY, data.avatar_url)
  if (typeof data.wallet_balance === 'number') wx.setStorageSync(WALLET_KEY, data.wallet_balance)
  if (data.role) wx.setStorageSync(ROLE_KEY, data.role)
  if (data.login_type) wx.setStorageSync(LOGIN_TYPE_KEY, data.login_type)
  const userId = data.user_id || data.id
  if (userId) wx.setStorageSync(USER_ID_KEY, String(userId))
}

function markManualLogout() {
  wx.setStorageSync(SKIP_AUTO_LOGIN_KEY, 1)
}

function consumeManualLogout() {
  const skipped = Boolean(wx.getStorageSync(SKIP_AUTO_LOGIN_KEY))
  if (skipped) {
    wx.removeStorageSync(SKIP_AUTO_LOGIN_KEY)
  }
  return skipped
}

function shouldSkipAutoLogin() {
  return Boolean(wx.getStorageSync(SKIP_AUTO_LOGIN_KEY))
}

function expireSession() {
  wx.removeStorageSync(TOKEN_KEY)
}

function clearAuth() {
  wx.removeStorageSync(TOKEN_KEY)
  wx.removeStorageSync(ROLE_KEY)
  wx.removeStorageSync(USERNAME_KEY)
  wx.removeStorageSync(AVATAR_KEY)
  wx.removeStorageSync(WALLET_KEY)
  wx.removeStorageSync(LOGIN_TYPE_KEY)
  wx.removeStorageSync(USER_ID_KEY)
}

function requireCustomer() {
  if (!isLoggedIn()) {
    wx.reLaunch({ url: '/pages/login/login' })
    return false
  }
  return true
}

function requireLoginForAction(message) {
  if (isLoggedIn()) return true
  wx.showToast({ title: message || '请先登录', icon: 'none' })
  setTimeout(() => {
    wx.reLaunch({ url: '/pages/login/login' })
  }, 400)
  return false
}

module.exports = {
  getToken,
  getRole,
  getUsername,
  getAvatar,
  getWallet,
  getLoginType,
  getUserId,
  isLoggedIn,
  getLocalKey,
  resolveMediaUrl,
  resolveProductMedia,
  saveAuth,
  saveProfile,
  expireSession,
  clearAuth,
  markManualLogout,
  consumeManualLogout,
  shouldSkipAutoLogin,
  requireCustomer,
  requireLoginForAction
}
