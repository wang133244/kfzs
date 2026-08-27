const auth = require('../../utils/auth')
const api = require('../../utils/request')
const userStore = require('../../utils/userStore')
const { INTRO_MESSAGE } = require('../../utils/config')
const media = require('../../utils/media')
const brand = require('../../utils/brand')
const chatSocket = require('../../utils/chat-socket')

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
    statusBarHeight: 20,
    navBarHeight: 44,
    capsuleGap: 96,
    myAvatar: brand.DEFAULT_AVATAR,
    botAvatar: brand.LOGO
  },

  onLoad() {
    this.fitCapsule()
  },

  fitCapsule() {
    try {
      const sys = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync()
      const statusBarHeight = sys.statusBarHeight || 20
      const windowWidth = sys.windowWidth || 375
      let menu = { width: 87, height: 32, left: windowWidth - 97, top: statusBarHeight + 4 }
      try {
        menu = wx.getMenuButtonBoundingClientRect() || menu
      } catch (err) {}
      const gap = Math.max((menu.top || statusBarHeight) - statusBarHeight, 4)
      const navBarHeight = (menu.height || 32) + gap * 2
      const capsuleGap = Math.max(windowWidth - (menu.left || windowWidth) + 12, 96)
      this.setData({ statusBarHeight, navBarHeight, capsuleGap })
    } catch (err) {}
  },

  onAvatarError() {
    const patch = {}
    if ((this.data.myAvatar || '').indexOf('/assets/') !== 0) {
      patch.myAvatar = brand.DEFAULT_AVATAR
    }
    if ((this.data.botAvatar || '').indexOf('/assets/') !== 0) {
      patch.botAvatar = brand.LOGO
    }
    if (Object.keys(patch).length) this.setData(patch)
  },

  async onShow() {
    if (!auth.requireCustomer()) return
    await this.refreshAvatar()
    await this.restoreOrIntro()
    const ask = getApp().globalData.pendingAsk
    if (ask) {
      getApp().globalData.pendingAsk = ''
      this.sendText(ask)
    }
    this._poll = setInterval(() => this.pollHistory(), 4000)
    chatSocket.setPushHandler((data) => this.onSocketPush(data))
  },

  async refreshAvatar() {
    try {
      const me = await api.getMe()
      auth.saveProfile(me)
    } catch (err) {}
    this.setData({
      myAvatar: await media.loadAvatar(auth.getAvatar()),
      botAvatar: brand.LOGO
    })
  },

  onHide() {
    if (this._poll) {
      clearInterval(this._poll)
      this._poll = null
    }
    chatSocket.setPushHandler(null)
    if (!this.data.sending) chatSocket.close()
  },

  onUnload() {
    if (this._poll) {
      clearInterval(this._poll)
      this._poll = null
    }
    chatSocket.setPushHandler(null)
    chatSocket.close()
  },

  async pollHistory() {
    if (!this.data.sessionId || this.data.sending) return
    try {
      const history = await api.getMessages(this.data.sessionId)
      const messages = await this.mapHistory(history)
      const lastOld = (this.data.messages || []).slice(-1)[0]
      const lastNew = messages.slice(-1)[0]
      if (!messages.length) return
      if (!lastOld || !lastNew || lastOld.id !== lastNew.id || lastOld.content !== lastNew.content) {
        this.applyChat(this.data.sessionId, messages)
      }
    } catch (err) {}
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

  patchMessage(id, patch) {
    const messages = (this.data.messages || []).map((item) =>
      item.id === id ? Object.assign({}, item, patch) : item
    )
    this.setData({ messages, scrollTo: 'bottom' })
  },

  appendDelta(id, delta) {
    if (!delta) return
    this._deltaBuf = (this._deltaBuf || '') + delta
    if (this._deltaTimer) return
    this._deltaTimer = setTimeout(() => {
      this._deltaTimer = null
      const chunk = this._deltaBuf
      this._deltaBuf = ''
      if (!chunk) return
      const current = (this.data.messages || []).find((item) => item.id === id)
      const prev = current ? current.content || '' : ''
      this.patchMessage(id, { content: prev + chunk, streaming: true })
    }, 48)
  },

  flushDelta(id) {
    if (this._deltaTimer) {
      clearTimeout(this._deltaTimer)
      this._deltaTimer = null
    }
    const chunk = this._deltaBuf || ''
    this._deltaBuf = ''
    if (!chunk) return
    const current = (this.data.messages || []).find((item) => item.id === id)
    const prev = current ? current.content || '' : ''
    this.patchMessage(id, { content: prev + chunk })
  },

  async finishStream(id, result) {
    this.flushDelta(id)
    const cards = await hydrateCards(result.product_cards)
    this.patchMessage(id, {
      id: 'a-' + result.message_id,
      content: result.response || '',
      product_cards: cards,
      streaming: false
    })
    this.setData({
      sessionId: result.session_id || this.data.sessionId,
      sending: false,
      scrollTo: 'bottom'
    })
    this.cacheChat()
  },

  failStream(id, err) {
    this.flushDelta(id)
    this.patchMessage(id, {
      content: (err && err.message) || '请求失败，请稍后重试',
      streaming: false
    })
    this.setData({ sending: false, scrollTo: 'bottom' })
    this.cacheChat()
  },

  async onSocketPush(data) {
    if (!data || data.type !== 'review_reply' || this.data.sending) return
    const content = data.response || ''
    if (!content) return
    const messages = (this.data.messages || []).concat([
      {
        id: 'p-' + Date.now(),
        role: 'staff',
        content,
        product_cards: await hydrateCards(data.product_cards)
      }
    ])
    this.setData({
      sessionId: data.session_id || this.data.sessionId,
      messages,
      scrollTo: 'bottom'
    })
    this.cacheChat()
  },

  async sendText(text) {
    const userMsg = {
      id: 'u-' + Date.now(),
      role: 'user',
      content: text,
      product_cards: []
    }
    const streamId = 's-' + Date.now()
    this._deltaBuf = ''
    if (this._deltaTimer) {
      clearTimeout(this._deltaTimer)
      this._deltaTimer = null
    }
    this.setData({
      sending: true,
      messages: this.data.messages.concat([
        userMsg,
        {
          id: streamId,
          role: 'assistant',
          content: '',
          product_cards: [],
          streaming: true
        }
      ]),
      scrollTo: 'bottom'
    })
    this.cacheChat()
    const cached = userStore.getChat() || {}
    const sessionId = this.data.sessionId || cached.sessionId || null
    try {
      const result = await chatSocket.ask({
        sessionId,
        message: text,
        onDelta: (delta) => this.appendDelta(streamId, delta)
      })
      await this.finishStream(streamId, result)
    } catch (err) {
      if (err && err.fallback) {
        try {
          const result = await api.chat(sessionId, text)
          await this.finishStream(streamId, result)
          return
        } catch (httpErr) {
          this.failStream(streamId, httpErr)
          return
        }
      }
      this.failStream(streamId, err)
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

  openProduct(e) {
    const id = e.currentTarget.dataset.id
    if (!id) return
    wx.navigateTo({ url: '/pages/detail/detail?id=' + id })
  }
})
