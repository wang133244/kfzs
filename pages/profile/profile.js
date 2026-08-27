const auth = require('../../utils/auth')
const api = require('../../utils/request')

Page({
  data: {
    username: '',
    avatar: '/assets/default-avatar.png',
    wallet: '2000.00',
    role: 'customer',
    loginType: '',
    editing: false,
    draftName: '',
    saving: false,
    isAdmin: false
  },

  onShow() {
    if (!auth.requireLogin()) return
    this._pageAlive = true
    this.setData({ isAdmin: auth.isAdmin() })
    this.syncLocal()
    this.refresh()
  },

  onHide() {
    this._pageAlive = false
  },

  onUnload() {
    this._pageAlive = false
  },

  syncLocal() {
    this.setData({
      username: auth.getUsername() || '微信用户',
      avatar: auth.resolveMediaUrl(auth.getAvatar()),
      wallet: Number(auth.getWallet() || 0).toFixed(2),
      role: auth.getRole() || 'customer',
      loginType: auth.getLoginType() || '',
      draftName: auth.getUsername() || ''
    })
  },

  async refresh() {
    try {
      const me = await api.getMe()
      if (!this._pageAlive) return
      auth.saveProfile(me)
      this.syncLocal()
    } catch (err) {}
  },

  onChooseAvatar(e) {
    const url = e.detail && e.detail.avatarUrl
    if (!url) return
    wx.showLoading({ title: '上传中', mask: true })
    api.uploadAvatar(url)
      .then((me) => {
        auth.saveProfile(me)
        this.syncLocal()
        wx.showToast({ title: '头像已更新', icon: 'success' })
      })
      .catch((err) => {
        wx.showToast({ title: err.message || '上传失败', icon: 'none' })
      })
      .finally(() => wx.hideLoading())
  },

  startEdit() {
    this.setData({ editing: true, draftName: this.data.username })
  },

  onDraftName(e) {
    this.setData({ draftName: e.detail.value })
  },

  async saveName() {
    if (this.data.saving) return
    const name = (this.data.draftName || '').trim()
    if (!name) {
      wx.showToast({ title: '请输入用户名', icon: 'none' })
      return
    }
    this.setData({ saving: true })
    try {
      const me = await api.updateMe({ username: name })
      auth.saveProfile(me)
      this.setData({ editing: false })
      this.syncLocal()
      wx.showToast({ title: '用户名已保存', icon: 'success' })
    } catch (err) {
      wx.showToast({ title: err.message || '保存失败', icon: 'none' })
    } finally {
      this.setData({ saving: false })
    }
  },

  goWallet() {
    wx.navigateTo({ url: '/pages/wallet/wallet' })
  },

  goOrders() {
    wx.navigateTo({ url: '/pages/orders/orders' })
  },

  logout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后下次需要重新登录',
      confirmText: '退出',
      confirmColor: '#e11d48',
      success: (res) => {
        if (!res.confirm) return
        this._pageAlive = false
        auth.clearAuth()
        auth.markManualLogout()
        wx.reLaunch({
          url: '/pages/login/login',
          fail: () => {
            wx.redirectTo({
              url: '/pages/login/login',
              fail: () => {
                wx.showToast({ title: '退出失败，请重试', icon: 'none' })
              }
            })
          }
        })
      }
    })
  }
})
