const auth = require('../../utils/auth')
const api = require('../../utils/request')
const userStore = require('../../utils/userStore')
const { INTRO_MESSAGE } = require('../../utils/config')
const media = require('../../utils/media')

function hydrateCards(cards) {
  return Promise.all((cards || []).map((card) => media.hydrateProduct(card)))
}

Page({
  data: {
    messages: [],
    draft: '',
    sending: false,
    sessionId: null,
    scrollTo: '',
    statusBarHeight: 20
  },

  onLoad() {
    try {
      const sys = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      this.setData({ statusBarHeight: sys.statusBarHeight || 20 })
    } catch (err) {}
  },

  async onShow() {
    if (!auth.requireCustomer()) return
    await this.restoreOrIntro()
    const ask = getApp().globalData.pendingAsk
    if (ask) {
      getApp().globalData.pendingAsk = ''
      this.sendText(ask)
    }
  },

  cacheChat() {
    userStore.setChat({
      sessionId: this.data.sessionId,
      messages: this.data.messages || []
    })
  },

  applyChat(sessionId, messages) {
    this.setData({
      sessionId: sessionId || null,
      messages: messages || [],
      scrollTo: 'bottom'
    })
    this.cacheChat()
  },

  async restoreOrIntro() {
    try {
      const sessions = await api.listSessions()
      if (sessions && sessions.length) {
        const latest = sessions[0]
        const history = await api.getMessages(latest.id)
        const messages = await this.mapHistory(history)
        if (messages.length) {
          this.applyChat(latest.id, messages)
          return
        }
        this.setData({ sessionId: latest.id })
        userStore.setChat({ sessionId: latest.id, messages: [] })
      } else {
        userStore.clearChat()
      }
    } catch (err) {
      const cached = userStore.getChat()
      if (cached && cached.messages && cached.messages.length) {
        this.setData({
          sessionId: cached.sessionId || null,
          messages: await Promise.all(
            (cached.messages || []).map(async (msg) =>
              Object.assign({}, msg, {
                product_cards: await hydrateCards(msg.product_cards)
              })
            )
          ),
          scrollTo: 'bottom'
        })
        return
      }
    }
    if (!this.data.messages.length) {
      this.resetIntro(false)
    }
  },

  async mapHistory(history) {
    const messages = []
    for (const item of history || []) {
      messages.push({
        id: 'h-' + item.id + '-' + messages.length,
        role: item.role === 'user' ? 'user' : item.role === 'staff' ? 'staff' : 'assistant',
        content: item.content,
        product_cards: await hydrateCards(item.product_cards)
      })
    }
    return messages
  },

  resetIntro(saveCache) {
    const messages = [{ id: 'intro', role: 'assistant', content: INTRO_MESSAGE, product_cards: [] }]
    this.setData({
      sessionId: null,
      messages,
      draft: ''
    })
    if (saveCache !== false) {
      userStore.setChat({ sessionId: null, messages })
    }
  },

  onDraft(e) {
    this.setData({ draft: e.detail.value })
  },

  onChip(e) {
    const text = (e.currentTarget.dataset.text || '').trim()
    if (!text || this.data.sending) return
    this.sendText(text)
  },

  onSend() {
    const text = (this.data.draft || '').trim()
    if (!text || this.data.sending) return
    this.setData({ draft: '' })
    this.sendText(text)
  },

  async sendText(text) {
    const userMsg = {
      id: 'u-' + Date.now(),
      role: 'user',
      content: text,
      product_cards: []
    }
    this.setData({
      sending: true,
      messages: this.data.messages.concat([userMsg]),
      scrollTo: 'bottom'
    })
    this.cacheChat()
    try {
      const cached = userStore.getChat() || {}
      const sessionId = this.data.sessionId || cached.sessionId || null
      const result = await api.chat(sessionId, text)
      const assistant = {
        id: 'a-' + result.message_id,
        role: 'assistant',
        content: result.response || '',
        product_cards: await hydrateCards(result.product_cards)
      }
      this.setData({
        sessionId: result.session_id,
        messages: this.data.messages.concat([assistant]),
        sending: false,
        scrollTo: 'bottom'
      })
      this.cacheChat()
    } catch (err) {
      this.setData({
        sending: false,
        messages: this.data.messages.concat([{
          id: 'e-' + Date.now(),
          role: 'assistant',
          content: err.message || '请求失败，请稍后重试',
          product_cards: []
        }]),
        scrollTo: 'bottom'
      })
      this.cacheChat()
    }
  },

  async onClear() {
    if (this.data.sending) return
    const ok = await new Promise((resolve) => {
      wx.showModal({
        title: '清空对话',
        content: '确定清空当前对话吗？清空后无法恢复。',
        success: (res) => resolve(res.confirm)
      })
    })
    if (!ok) return
    try {
      if (this.data.sessionId) {
        await api.deleteSession(this.data.sessionId)
      }
      userStore.clearChat()
      this.resetIntro(true)
    } catch (err) {
      wx.showToast({ title: err.message || '清空失败', icon: 'none' })
    }
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      content: '退出后下次需要重新登录。聊天记录和购物车会按账号保存。',
      confirmText: '退出',
      confirmColor: '#e11d48',
      success: (res) => {
        if (!res.confirm) return
        auth.clearAuth()
        auth.markManualLogout()
        wx.reLaunch({ url: '/pages/login/login' })
      }
    })
  },

  openProduct(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id })
  }
})
