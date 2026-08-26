const auth = require('../../utils/auth')
const api = require('../../utils/request')
const cart = require('../../utils/cart')

function withMedia(product) {
  if (!product) return product
  const gallery = (product.gallery || []).map((item) => auth.resolveProductMedia(item))
  return Object.assign({}, product, {
    cover: auth.resolveProductMedia(product.cover),
    gallery
  })
}

Page({
  data: {
    categories: [{ code: 'all', name: '全部' }],
    activeCategory: 'all',
    keyword: '',
    products: [],
    loading: false,
    error: ''
  },

  onShow() {
    if (!auth.requireCustomer()) return
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
        this.setData({
          categories: [{ code: 'all', name: '全部' }].concat(cats || [])
        })
      } catch (err) {}
      await this.loadProducts()
    } catch (err) {
      this.setData({ error: err.message || '商品加载失败', products: [] })
    } finally {
      this.setData({ loading: false })
    }
  },

  async loadProducts() {
    const data = await api.listShopProducts({
      q: (this.data.keyword || '').trim() || undefined,
      category: this.data.activeCategory === 'all' ? undefined : this.data.activeCategory,
      page: 1,
      size: 50
    })
    this.setData({ products: (data.items || []).map(withMedia) })
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

  openDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id })
  },

  addCart(e) {
    const id = e.currentTarget.dataset.id
    const product = this.data.products.find((item) => item.product_id === id)
    if (!product) return
    cart.addProduct(product)
    wx.showToast({ title: '已加入购物车', icon: 'success' })
  }
})
