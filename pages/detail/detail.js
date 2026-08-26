const auth = require('../../utils/auth')
const api = require('../../utils/request')
const cart = require('../../utils/cart')
const buy = require('../../utils/buy')
const media = require('../../utils/media')

Page({
  data: {
    product: null,
    loading: true,
    error: ''
  },

  onLoad(query) {
    const id = query.id || ''
    if (!id) {
      this.setData({ loading: false, error: '缺少商品编号' })
      return
    }
    this.loadDetail(id)
  },

  async loadDetail(id) {
    this.setData({ loading: true, error: '' })
    try {
      const product = await api.getShopProduct(id)
      if (product.sku_list && (!product.skus || !product.skus.length)) {
        product.skus = product.sku_list
      }
      const hydrated = await media.hydrateProduct(product)
      this.setData({ product: hydrated, loading: false })
      wx.setNavigationBarTitle({ title: product.title ? product.title.slice(0, 12) : '商品详情' })
    } catch (err) {
      this.setData({ loading: false, error: err.message || '详情加载失败' })
    }
  },

  addCart() {
    if (!auth.requireLoginForAction('请先登录再加购')) return
    if (!this.data.product) return
    cart.addProduct(this.data.product)
    wx.showToast({ title: '已加入购物车', icon: 'success' })
  },

  openSource() {
    if (!this.data.product) return
    buy.openProductWeb(this.data.product.source_url)
  },

  askCs() {
    if (!auth.requireLoginForAction('请先登录再咨询客服')) return
    if (!this.data.product) return
    getApp().globalData.pendingAsk = '我想了解 ' + this.data.product.title
    wx.switchTab({ url: '/pages/chat/chat' })
  }
})
