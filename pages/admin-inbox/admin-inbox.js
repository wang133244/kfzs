const auth = require('../../utils/auth')
const api = require('../../utils/request')

function statusText(status, canChat) {
  if (status === 'waiting') return '待接入'
  if (status === 'active') return '会话中'
  if (canChat) return '可接入'
  return '未转人工'
}

Page({
  data: {
    customers: [],
    loading: true,
    error: ''
  },

  onShow() {
    if (!auth.requireAdmin()) return
    this.loadList()
    this._timer = setInterval(() => this.loadList(true), 5000)
  },

  onHide() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  onUnload() {
    if (this._timer) {
      clearInterval(this._timer)
      this._timer = null
    }
  },

  onPullDownRefresh() {
    this.loadList().finally(() => wx.stopPullDownRefresh())
  },

  async loadList(silent) {
    if (!silent) this.setData({ loading: true, error: '' })
    try {
      const rows = await api.listAdminCustomers()
      const customers = (rows || []).map((item) => ({
        ...item,
        avatar: auth.resolveMediaUrl(item.avatar_url),
        preview: item.last_message || '暂无消息',
        statusText: statusText(item.handoff_status, item.can_chat)
      }))
      this.setData({ customers, loading: false, error: '' })
    } catch (err) {
      this.setData({
        loading: false,
        error: silent ? this.data.error : err.message || '加载失败'
      })
    }
  },

  openChat(e) {
    const userId = e.currentTarget.dataset.id
    const item = (this.data.customers || []).find((row) => String(row.user_id) === String(userId))
    if (!item) return
    const query = [
      'userId=' + encodeURIComponent(item.user_id),
      'username=' + encodeURIComponent(item.username || ''),
      'avatar=' + encodeURIComponent(item.avatar_url || ''),
      'sessionId=' + encodeURIComponent(item.session_id || ''),
      'canChat=' + (item.can_chat ? '1' : '0'),
      'status=' + encodeURIComponent(item.handoff_status || 'none')
    ].join('&')
    wx.navigateTo({ url: '/pages/admin-chat/admin-chat?' + query })
  }
})
