const auth = require('../../utils/auth')
const api = require('../../utils/request')

function statusHint(status, canChat) {
  if (status === 'waiting') return '用户已转人工，可以接入回复'
  if (status === 'active') return '人工会话进行中'
  if (canChat) return '可以接入回复'
  return '用户尚未转人工，只能查看记录，不能发送'
}

Page({
  data: {
    username: '',
    avatar: '/assets/default-avatar.png',
    messages: [],
    draft: '',
    sending: false,
    canChat: false,
    statusHint: '',
    scrollTo: '',
    loading: true
  },

  onLoad(query) {
    this.userId = String((query && query.userId) || '')
    this.sessionId = decodeURIComponent((query && query.sessionId) || '')
    const username = decodeURIComponent((query && query.username) || '用户')
    const avatar = decodeURIComponent((query && query.avatar) || '')
    const canChat = String((query && query.canChat) || '') === '1'
    const status = decodeURIComponent((query && query.status) || 'none')
    wx.setNavigationBarTitle({ title: username })
    this.setData({
      username,
      avatar: auth.resolveMediaUrl(avatar),
      canChat,
      statusHint: statusHint(status, canChat)
    })
  },

  onShow() {
    if (!auth.requireAdmin()) return
    this.refresh()
    this._timer = setInterval(() => this.refresh(true), 3000)
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

  async refresh(silent) {
    try {
      const rows = await api.listAdminCustomers()
      const row = (rows || []).find((item) => String(item.user_id) === this.userId)
      if (row) {
        this.sessionId = row.session_id || this.sessionId
        this.setData({
          username: row.username || this.data.username,
          avatar: auth.resolveMediaUrl(row.avatar_url),
          canChat: Boolean(row.can_chat),
          statusHint: statusHint(row.handoff_status, row.can_chat)
        })
        wx.setNavigationBarTitle({ title: row.username || this.data.username })
      }
      if (!this.sessionId) {
        this.setData({ messages: [], loading: false })
        return
      }
      const history = await api.getAdminSessionMessages(this.sessionId)
      const messages = (history || []).map((item) => ({
        id: item.id,
        role: item.role,
        content: item.content,
        mine: item.role === 'staff'
      }))
      this.setData({
        messages,
        loading: false,
        scrollTo: messages.length ? 'bottom' : ''
      })
    } catch (err) {
      if (!silent) {
        this.setData({ loading: false })
        wx.showToast({ title: err.message || '加载失败', icon: 'none' })
      }
    }
  },

  onDraft(e) {
    this.setData({ draft: e.detail.value })
  },

  async onSend() {
    const text = (this.data.draft || '').trim()
    if (!text || this.data.sending) return
    if (!this.data.canChat || !this.sessionId) {
      wx.showToast({ title: '用户转人工后才能接入', icon: 'none' })
      return
    }
    this.setData({ sending: true, draft: '' })
    try {
      await api.replyAdminSession(this.sessionId, text)
      await this.refresh(true)
    } catch (err) {
      wx.showToast({ title: err.message || '发送失败', icon: 'none' })
    } finally {
      this.setData({ sending: false, scrollTo: 'bottom' })
    }
  },

  async onClose() {
    if (!this.sessionId || !this.data.canChat) return
    const ok = await new Promise((resolve) => {
      wx.showModal({
        title: '结束人工',
        content: '结束后顾客会重新由智能客服接待。',
        confirmText: '结束',
        success: (res) => resolve(res.confirm)
      })
    })
    if (!ok) return
    try {
      await api.closeAdminSession(this.sessionId)
      await this.refresh()
      wx.showToast({ title: '已结束人工', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '操作失败', icon: 'none' })
    }
  }
})
