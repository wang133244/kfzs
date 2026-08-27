const auth = require('../../utils/auth')
const api = require('../../utils/request')
const media = require('../../utils/media')

const CATEGORIES = [
  { code: 'post', name: '柱头灯' },
  { code: 'wall', name: '户外壁灯' },
  { code: 'solar', name: '太阳能庭院灯' }
]

Page({
  data: {
    productId: '',
    title: '',
    price: '',
    description: '',
    cover: '',
    coverSrc: '',
    categoryIndex: 0,
    categories: CATEGORIES,
    saving: false,
    coverChanged: false
  },

  onLoad(query) {
    if (!auth.requireAdmin()) return
    const productId = (query && query.id) || ''
    this.setData({ productId })
    wx.setNavigationBarTitle({ title: productId ? '编辑商品' : '添加商品' })
    if (productId) this.loadProduct(productId)
  },

  async loadProduct(productId) {
    wx.showLoading({ title: '加载中', mask: true })
    try {
      const product = await api.getShopProduct(productId)
      const hydrated = await media.hydrateProduct(product)
      const index = CATEGORIES.findIndex((item) => item.code === product.category_code)
      this.setData({
        title: product.title || '',
        price: String(product.price == null ? '' : product.price),
        description: product.description || '',
        cover: product.cover || '',
        coverSrc: hydrated.coverSrc || '',
        categoryIndex: index >= 0 ? index : 0
      })
    } catch (err) {
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },

  onTitle(e) {
    this.setData({ title: e.detail.value })
  },

  onPrice(e) {
    this.setData({ price: e.detail.value })
  },

  onDescription(e) {
    this.setData({ description: e.detail.value })
  },

  onCategory(e) {
    this.setData({ categoryIndex: Number(e.detail.value) || 0 })
  },

  onChooseCover() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const file = (res.tempFiles || [])[0]
        const filePath = file && file.tempFilePath
        if (!filePath) return
        wx.showLoading({ title: '上传中', mask: true })
        api.uploadProductCover(filePath)
          .then((result) => {
            this.setData({
              cover: result.cover || '',
              coverSrc: filePath,
              coverChanged: true
            })
          })
          .catch((err) => {
            wx.showToast({ title: err.message || '上传失败', icon: 'none' })
          })
          .finally(() => wx.hideLoading())
      }
    })
  },

  async onSave() {
    if (this.data.saving) return
    const title = (this.data.title || '').trim()
    const price = Number(this.data.price)
    if (!title) {
      wx.showToast({ title: '请填写标题', icon: 'none' })
      return
    }
    if (!(price > 0)) {
      wx.showToast({ title: '请填写正确价格', icon: 'none' })
      return
    }
    const category = CATEGORIES[this.data.categoryIndex] || CATEGORIES[0]
    const payload = {
      title,
      price,
      original_price: price,
      category: category.name,
      category_code: category.code,
      description: (this.data.description || '').trim()
    }
    if (!this.data.productId || this.data.coverChanged) {
      payload.cover = this.data.cover || ''
    }
    this.setData({ saving: true })
    try {
      if (this.data.productId) {
        await api.updateAdminProduct(this.data.productId, payload)
      } else {
        await api.createAdminProduct(payload)
      }
      wx.showToast({ title: '已保存', icon: 'success' })
      setTimeout(() => wx.navigateBack(), 400)
    } catch (err) {
      wx.showToast({ title: err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  }
})
