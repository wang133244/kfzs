const auth = require('../../utils/auth')
const api = require('../../utils/request')

function statusText(status) {
  if (status === 'paid') return '已付款'
  if (status === 'unpaid') return '待付款'
  if (status === 'shipped') return '已发货'
  if (status === 'refunding') return '退款中'
  return status || '未知'
}

function formatTime(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 19)
}

Page({
  data: {
    keyword: '',
    orders: [],
    loading: true,
    error: ''
  },

  onShow() {
    if (!auth.requireAdmin()) return
    this.search()
  },

  onKeyword(e) {
    this.setData({ keyword: e.detail.value })
  },

  async search() {
    this.setData({ loading: true, error: '' })
    try {
      const rows = await api.listAdminOrders((this.data.keyword || '').trim())
      this.setData({
        loading: false,
        orders: (rows || []).map((item) => ({
          ...item,
          statusText: statusText(item.status),
          amountText: Number(item.amount || 0).toFixed(2),
          timeText: formatTime(item.created_at)
        }))
      })
    } catch (err) {
      this.setData({ loading: false, error: err.message || '加载失败', orders: [] })
    }
  }
})
