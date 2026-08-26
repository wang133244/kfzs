const ROOT_KEY = 'xingtu_user_store'
const { getUserId } = require('./auth')

function _all() {
  const saved = wx.getStorageSync(ROOT_KEY)
  return saved && typeof saved === 'object' ? saved : {}
}

function _key() {
  const id = getUserId()
  return id ? String(id) : ''
}

function loadRecord() {
  const key = _key()
  if (!key) {
    return { cart: { items: [] }, chat: null }
  }
  const record = _all()[key]
  if (!record || typeof record !== 'object') {
    return { cart: { items: [] }, chat: null }
  }
  const cart = record.cart && Array.isArray(record.cart.items) ? record.cart : { items: [] }
  return {
    cart,
    chat: record.chat || null
  }
}

function saveRecord(patch) {
  const key = _key()
  if (!key) return
  const all = _all()
  const current = Object.assign({ cart: { items: [] }, chat: null }, all[key] || {})
  all[key] = Object.assign(current, patch || {})
  wx.setStorageSync(ROOT_KEY, all)
}

function getCart() {
  return loadRecord().cart
}

function setCart(cart) {
  saveRecord({ cart: { items: (cart && cart.items) || [] } })
}

function getChat() {
  return loadRecord().chat
}

function setChat(chat) {
  saveRecord({ chat: chat || null })
}

function clearChat() {
  saveRecord({ chat: null })
}

module.exports = {
  getCart,
  setCart,
  getChat,
  setChat,
  clearChat
}
