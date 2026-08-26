const userStore = require('./userStore')

function getState() {
  const saved = userStore.getCart()
  if (saved && Array.isArray(saved.items)) {
    return { items: saved.items }
  }
  return { items: [] }
}

function saveState(state, options) {
  const opts = options || {}
  userStore.setCart({ items: state.items || [] })
  const count = (state.items || []).reduce((sum, item) => sum + (item.quantity || 0), 0)
  const app = getApp()
  if (app && app.updateCartBadge) {
    app.updateCartBadge(count)
  }
  if (!opts.skipSync) {
    syncToServer(state.items || [])
  }
  return count
}

function syncToServer(items) {
  try {
    const api = require('./request')
    api.saveCart(items).catch(() => {})
  } catch (err) {}
}

function addProduct(product) {
  const state = getState()
  const found = state.items.find((item) => item.product.product_id === product.product_id)
  if (found) {
    found.quantity += 1
  } else {
    state.items.push({ product, quantity: 1 })
  }
  saveState(state)
  return state
}

function removeProduct(productId) {
  const state = getState()
  state.items = state.items.filter((item) => item.product.product_id !== productId)
  saveState(state)
  return state
}

function clear() {
  saveState({ items: [] })
}

async function pullFromServer() {
  const api = require('./request')
  try {
    const data = await api.getCart()
    if (data && Array.isArray(data.items)) {
      saveState({ items: data.items }, { skipSync: true })
    }
  } catch (err) {
    const local = getState()
    const app = getApp()
    if (app && app.updateCartBadge) {
      const count = local.items.reduce((sum, item) => sum + (item.quantity || 0), 0)
      app.updateCartBadge(count)
    }
  }
  return getState()
}

module.exports = {
  getState,
  addProduct,
  removeProduct,
  clear,
  pullFromServer
}
