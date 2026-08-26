Page({
  data: {
    src: '',
    error: ''
  },

  onLoad(query) {
    const src = decodeURIComponent(query.src || '')
    if (!src) {
      this.setData({ error: '缺少原网址' })
      return
    }
    this.setData({ src })
  },

  onWebError() {
    const src = this.data.src
    wx.setClipboardData({
      data: src,
      success() {
        wx.showModal({
          title: '无法直接打开',
          content: '原网址已复制，请到手机浏览器中打开查看。',
          showCancel: false
        })
      }
    })
  }
})
