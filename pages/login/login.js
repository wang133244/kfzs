const auth = require('../../utils/auth')
const api = require('../../utils/request')

Page({
  data: {
    username: '',
    password: '',
    error: '',
    loading: false,
    wxLoading: false
  },

  onShow() {
    if (auth.consumeManualLogout()) {
      this._wxTried = true
      return
    }
    if (auth.isLoggedIn()) {
      wx.switchTab({ url: '/pages/chat/chat' })
      return
    }
    if (auth.getLoginType() === 'wechat' && !this._wxTried) {
      this._wxTried = true
      this.onWechatLogin()
    }
  },

  onUsername(e) {
    this.setData({ username: e.detail.value })
  },

  onPassword(e) {
    this.setData({ password: e.detail.value })
  },

  async onWechatLogin() {
    if (this.data.wxLoading || this.data.loading) return
    this.setData({ wxLoading: true, error: '' })
    try {
      let code = ''
      try {
        const loginRes = await new Promise((resolve, reject) => {
          wx.login({
            success: resolve,
            fail: () => reject(new Error('微信登录失败'))
          })
        })
        code = loginRes.code || ''
      } catch (err) {}
      const result = await api.wechatLogin({
        code,
        local_key: auth.getLocalKey()
      })
      if (result.role === 'staff') {
        this.setData({ error: '员工请打开原来的网页工作台' })
        return
      }
      result.login_type = 'wechat'
      auth.saveAuth(result)
      require('../../utils/cart').pullFromServer()
      wx.switchTab({ url: '/pages/chat/chat' })
    } catch (err) {
      this.setData({ error: err.message || '微信登录失败' })
    } finally {
      this.setData({ wxLoading: false })
    }
  },

  async onSubmit() {
    if (this.data.loading || this.data.wxLoading) return
    const username = (this.data.username || '').trim()
    const password = this.data.password || ''
    if (!username || !password) {
      this.setData({ error: '请输入用户名和密码' })
      return
    }
    this.setData({ loading: true, error: '' })
    try {
      const result = await api.login(username, password)
      if (result.role === 'staff') {
        this.setData({
          loading: false,
          error: '本小程序仅供顾客使用，员工请打开原来的网页工作台'
        })
        return
      }
      result.login_type = 'password'
      auth.saveAuth(result)
      require('../../utils/cart').pullFromServer()
      wx.switchTab({ url: '/pages/chat/chat' })
    } catch (err) {
      this.setData({ error: err.message || '登录失败' })
    } finally {
      this.setData({ loading: false })
    }
  }
})
