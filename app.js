App({
  globalData: {
    pendingAsk: '',
    cartCount: 0
  },

  onLaunch() {
    this.initCloud()
    const auth = require('./utils/auth')
    const cart = require('./utils/cart')
    auth.getLocalKey()
    const local = cart.getState()
    const count = (local.items || []).reduce((sum, item) => sum + (item.quantity || 0), 0)
    this.globalData.cartCount = count
    this.updateCartBadge(count)
    this.restoreWechatSession()
    if (auth.isLoggedIn()) {
      const api = require('./utils/request')
      api.getMe()
        .then((me) => {
          auth.saveProfile(me)
          cart.pullFromServer()
        })
        .catch(() => cart.pullFromServer())
    }
  },

  initCloud() {
    if (!wx.cloud) return
    const { CLOUD_ENV } = require('./utils/config')
    wx.cloud.init({
      env: CLOUD_ENV || wx.cloud.DYNAMIC_CURRENT_ENV,
      traceUser: true
    })
  },

  restoreWechatSession() {
    const auth = require('./utils/auth')
    const api = require('./utils/request')
    const cart = require('./utils/cart')
    if (auth.shouldSkipAutoLogin()) return
    if (auth.isLoggedIn()) return
    if (auth.getLoginType() !== 'wechat') return
    wx.login({
      success: async (res) => {
        try {
          const result = await api.wechatLogin({
            code: res.code || '',
            local_key: auth.getLocalKey()
          })
          result.login_type = 'wechat'
          auth.saveAuth(result)
          cart.pullFromServer()
        } catch (err) {}
      }
    })
  },

  updateCartBadge(count) {
    this.globalData.cartCount = count
    if (count > 0) {
      wx.setTabBarBadge({
        index: 2,
        text: String(count > 99 ? '99+' : count),
        fail() {}
      })
    } else {
      wx.removeTabBarBadge({
        index: 2,
        fail() {}
      })
    }
  }
})
