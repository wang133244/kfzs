const auth = require('../../utils/auth')
const api = require('../../utils/request')
const cart = require('../../utils/cart')
const media = require('../../utils/media')

Page({
  data: {
    categories: [{ code: 'all', name: '全部' }],
    activeCategory: 'all',
    keyword: '',
    products: [],
    loading: false,
    error: '',
    isAdmin: false
  },

  onShow() {
    const isAdmin = auth.isAdmin()
    this.setData({ isAdmin })
    auth.syncTabBar()
    this.loadAll()
  },

  onKeyword(e) {
    this.setData({ keyword: e.detail.value })
  },

  async loadAll() {
    this.setData({ loading: true, error: '' })
    try {
      try {
        const cats = await api.listShopCategories()
        const base = [{ code: 'all', name: '全部' }].concat(cats || [])
        this.setData({
          categories: this.data.isAdmin
            ? [
                { code: 'all', name: '全部' },
                { code: 'post', name: '柱头灯' },
                { code: 'wall', name: '户外壁灯' },
                { code: 'solar', name: '太阳能庭院灯' }
              ]
            : base
        })
      } catch (err) {}
      await this.loadProducts()
    } catch (err) {
      const message = err.message || '商品加载失败'
      this.setData({ error: message, products: [] })
      if (message.indexOf('登录') >= 0) {
        auth.requireLoginForAction('请先登录后查看橱窗')
      }
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadProducts() {
    if (this.data.isAdmin) {
      let rows = await api.listAdminProducts()
      const keyword = (this.data.keyword || '').trim().toLowerCase()
      const category = this.data.activeCategory
      if (category && category !== 'all') {
        rows = (rows || []).filter((item) => item.category_code === category)
      }
      if (keyword) {
        rows = (rows || []).filter((item) => String(item.title || '').toLowerCase().indexOf(keyword) >= 0)
      }
      const products = await Promise.all((rows || []).map((item) => media.hydrateProduct(item)))
      this.setData({ products })
      return
    }
    const data = await api.listShopProducts({
      q: (this.data.keyword || '').trim() || undefined,
      category: this.data.activeCategory === 'all' ? undefined : this.data.activeCategory,
      page: 1,
      size: 50
    })
    const products = await Promise.all((data.items || []).map((item) => media.hydrateProduct(item)))
    this.setData({ products })
  },

  async onCategory(e) {
    const code = e.currentTarget.dataset.code
    if (code === this.data.activeCategory) return
    this.setData({ activeCategory: code, loading: true, error: '' })
    try {
      await this.loadProducts()
    } catch (err) {
      this.setData({ error: err.message || '商品加载失败', products: [] })
    } finally {
      this.setData({ loading: false })
    }
  },

  async onSearch() {
    this.setData({ loading: true, error: '' })
    try {
      await this.loadProducts()
    } catch (err) {
      this.setData({ error: err.message || '搜索失败', products: [] })
    } finally {
      this.setData({ loading: false })
    }
  },

  onAddProduct() {
    if (!auth.requireAdmin()) return
    wx.navigateTo({ url: '/pages/admin-product/admin-product' })
  },

  openDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id })
  },

  addCart(e) {
    if (this.data.isAdmin) {
      wx.showToast({ title: '管理员请在订单页查看购买记录', icon: 'none' })
      return
    }
    if (!auth.requireLoginForAction('请先登录再加购')) return
    const id = e.currentTarget.dataset.id
    const product = this.data.products.find((item) => item.product_id === id)
    if (!product) return
    cart.addProduct(product)
    wx.showToast({ title: '已加入购物车', icon: 'success' })
  }
})
