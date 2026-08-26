const auth = require('../../utils/auth')
const api = require('../../utils/request')
const cart = require('../../utils/cart')
const media = require('../../utils/media')

Page({
  data: {
    items: [],
    total: '0.00',
    balance: '2000.00',
    checking: false
  },

  async onShow() {
    if (!auth.requireCustomer()) return
    await this.refresh()
    await cart.pullFromServer()
    await this.refresh()
    this.loadWallet()
  },

  async refresh() {
    const items = await Promise.all(
      cart.getState().items.map(async (item) => ({
        product: await media.hydrateProduct(item.product),
        quantity: item.quantity
      }))
    )
    const total = items.reduce((sum, item) => sum + Number(item.product.price || 0) * (item.quantity || 0), 0)
    this.setData({
      items,
      total: total.toFixed(2),
      balance: Number(auth.getWallet() || 0).toFixed(2)
    })
  },

  async loadWallet() {
    try {
      const me = await api.getMe()
      auth.saveProfile(me)
      this.setData({ balance: Number(me.wallet_balance || 0).toFixed(2) })
    } catch (err) {}
  },

  remove(e) {
    cart.removeProduct(e.currentTarget.dataset.id)
    this.refresh()
  },

  async checkout() {
    if (this.data.checking) return
    const items = this.data.items
    if (!items.length) return
    const total = Number(this.data.total)
    const balance = Number(this.data.balance)
    if (balance < total) {
      wx.showToast({ title: '钱包余额不足', icon: 'none' })
      return
    }
    const ok = await new Promise((resolve) => {
      wx.showModal({
        title: '确认下单',
        content: '将从钱包扣除 ¥' + this.data.total + '，生成订单但不发货',
        success: (res) => resolve(Boolean(res.confirm))
      })
    })
    if (!ok) return
    this.setData({ checking: true })
    try {
      const result = await api.checkout(
        items.map((item) => ({
          product_id: item.product.product_id,
          quantity: item.quantity
        }))
      )
      cart.clear()
      auth.saveProfile({ wallet_balance: result.remaining_balance })
      await this.refresh()
      wx.showModal({
        title: '下单成功',
        content: '订单号 ' + result.order_id + '\n余额 ¥' + Number(result.remaining_balance).toFixed(2),
        showCancel: false,
        confirmText: '查看订单',
        success: (res) => {
          if (res.confirm) wx.navigateTo({ url: '/pages/orders/orders' })
        }
      })
    } catch (err) {
      wx.showToast({ title: err.message || '下单失败', icon: 'none' })
    } finally {
      this.setData({ checking: false })
    }
  },

  goShop() {
    wx.switchTab({
      url: '/pages/showcase/showcase',
      fail() {
        wx.reLaunch({ url: '/pages/showcase/showcase' })
      }
    })
  }
})
