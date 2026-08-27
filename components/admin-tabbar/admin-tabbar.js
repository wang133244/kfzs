Component({
  properties: {
    current: {
      type: String,
      value: 'inbox'
    }
  },

  methods: {
    onTap(e) {
      const key = e.currentTarget.dataset.key
      if (!key || key === this.data.current) return
      if (key === 'inbox') {
        wx.reLaunch({ url: '/pages/admin-inbox/admin-inbox' })
        return
      }
      if (key === 'shop') {
        wx.switchTab({ url: '/pages/showcase/showcase' })
        return
      }
      if (key === 'orders') {
        wx.reLaunch({ url: '/pages/admin-orders/admin-orders' })
        return
      }
      if (key === 'me') {
        wx.switchTab({ url: '/pages/profile/profile' })
      }
    }
  }
})
