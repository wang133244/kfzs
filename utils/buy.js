function openProductWeb(url) {
  const target = (url || '').trim()
  if (!target) {
    wx.showToast({ title: '该商品暂无原网址', icon: 'none' })
    return
  }
  wx.navigateTo({
    url: '/pages/webview/webview?src=' + encodeURIComponent(target)
  })
}

module.exports = {
  openProductWeb
}
