const auth = require('../../utils/auth')
const api = require('../../utils/request')
const cart = require('../../utils/cart')
const buy = require('../../utils/buy')
const media = require('../../utils/media')

Page({
  data: {
    product: null,
    loading: true,
    error: '',
    isAdmin: false
  },

  onLoad(query) {
    this.productId = query.id || ''
    if (!this.productId) {
      this.setData({ loading: false, error: '缺少商品编号' })
      return
    }
  },

  onShow() {
    this.setData({ isAdmin: auth.isAdmin() })
    if (this.productId) this.loadDetail(this.productId)
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
  },

  onEdit() {
    if (!auth.requireAdmin()) return
    wx.navigateTo({ url: '/pages/admin-product/admin-product?id=' + this.productId })
  },

  async onToggleShelf() {
    if (!auth.requireAdmin() || !this.data.product) return
    const next = this.data.product.status === 'off_shelf' ? 'on_sale' : 'off_shelf'
    try {
      await api.setAdminProductStatus(this.productId, next)
      await this.loadDetail(this.productId)
      wx.showToast({ title: next === 'off_shelf' ? '已下架' : '已上架', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  },

  onDelete() {
    if (!auth.requireAdmin() || !this.data.product) return
    wx.showModal({
      title: '删除商品',
      content: '删除后橱窗不再展示，确定删除？',
      confirmText: '删除',
      confirmColor: '#b91c1c',
      success: async (res) => {
        if (!res.confirm) return
        try {
          await api.deleteAdminProduct(this.productId)
          wx.showToast({ title: '已删除', icon: 'success' })
          setTimeout(() => wx.navigateBack(), 400)
        } catch (err) {
          wx.showToast({ title: err.message || '删除失败', icon: 'none' })
        }
      }
    })
  }
})
