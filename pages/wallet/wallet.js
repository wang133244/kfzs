const auth = require('../../utils/auth')
const api = require('../../utils/request')

function statusText(status) {
  if (status === 'paid') return '已付款'
  if (status === 'unpaid') return '待付款'
  if (status === 'shipped') return '已发货'
  if (status === 'refunding') return '退款中'
  return status || '未知'
}

Page({
  data: {
    wallet: '2000.00',
    orders: [],
    loading: true
  },

  onShow() {
    if (!auth.requireCustomer()) return
    this.setData({ wallet: Number(auth.getWallet() || 0).toFixed(2) })
    this.refresh()
  },

  async refresh() {
    this.setData({ loading: true })
    try {
      const me = await api.getMe()
      auth.saveProfile(me)
      const orders = await api.listMyOrders()
      this.setData({
        wallet: Number(me.wallet_balance || 0).toFixed(2),
        orders: (orders || []).map((item) => ({
          ...item,
          statusText: statusText(item.status),
          amountText: Number(item.amount || 0).toFixed(2)
        })),
        loading: false
      })
    } catch (err) {
      this.setData({ loading: false })
      wx.showToast({ title: err.message || '加载失败', icon: 'none' })
    }
  }
})
