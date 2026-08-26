const auth = require('../../utils/auth')
const api = require('../../utils/request')

function formatTime(value) {
  if (!value) return ''
  const text = String(value).replace('T', ' ')
  return text.slice(0, 19)
}

function statusText(status) {
  if (status === 'paid') return '已付款（待发货）'
  if (status === 'unpaid') return '待付款'
  if (status === 'shipped') return '已发货'
  if (status === 'refunding') return '退款中'
  return status || '未知'
}

Page({
  data: {
    orders: [],
    loading: true
  },

  onShow() {
    if (!auth.requireCustomer()) return
    this.refresh()
  },

  async refresh() {
    this.setData({ loading: true })
    try {
      const orders = await api.listMyOrders()
      this.setData({
        loading: false,
        orders: (orders || []).map((item) => ({
          ...item,
          statusText: statusText(item.status),
          amountText: Number(item.amount || 0).toFixed(2),
          timeText: formatTime(item.created_at)
        }))
      })
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    }
  }
})
