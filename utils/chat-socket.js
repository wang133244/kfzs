const { USE_CLOUD, BASE_URL } = require('./config')
const { getToken } = require('./auth')
const { ensureCloud, connectContainerSocket } = require('./cloud')

const WS_PATH = '/api/v1/chat/ws'
const OPEN_MS = 8000
const ASK_MS = 90000

function parsePayload(res) {
  let data = res && res.data
  if (typeof data === 'string') {
    try {
      data = JSON.parse(data)
    } catch (err) {
      return null
    }
  }
  return data && typeof data === 'object' ? data : null
}

function nativeUrl(token) {
  return BASE_URL.replace(/^http/i, 'ws') + WS_PATH + '?token=' + encodeURIComponent(token)
}

function waitOpen(task, ms) {
  return new Promise((resolve, reject) => {
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      reject(new Error('客服连接超时'))
    }, ms)
    const done = (fn) => (value) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      fn(value)
    }
    task.onOpen(done(() => resolve(task)))
    task.onError(done((err) => reject(err || new Error('客服连接失败'))))
  })
}

function connectNative(token) {
  return new Promise((resolve, reject) => {
    const task = wx.connectSocket({
      url: nativeUrl(token),
      fail: reject
    })
    if (!task) {
      reject(new Error('客服连接失败'))
      return
    }
    resolve(task)
  })
}

function connectCloud(token) {
  ensureCloud()
  return connectContainerSocket(WS_PATH + '?token=' + encodeURIComponent(token))
}

function ChatSocket() {
  this._task = null
  this._pending = null
  this._opening = null
  this._onPush = null
}

ChatSocket.prototype.setPushHandler = function (handler) {
  this._onPush = handler
}

ChatSocket.prototype.close = function () {
  const task = this._task
  this._task = null
  this._pending = null
  this._opening = null
  if (task) {
    try {
      task.close({})
    } catch (err) {}
  }
}

ChatSocket.prototype._bind = function (task) {
  const self = this
  task.onMessage((res) => {
    const data = parsePayload(res)
    if (!data) return
    if (data.type === 'review_reply') {
      if (self._onPush) self._onPush(data)
      return
    }
    if (self._pending) self._pending.onEvent(data)
  })
  task.onClose(() => {
    if (self._task === task) self._task = null
    if (self._pending) {
      const pending = self._pending
      self._pending = null
      pending.fail(Object.assign(new Error('客服连接已断开'), { fallback: false }))
    }
  })
  task.onError(() => {})
}

ChatSocket.prototype.ensure = function () {
  if (this._task) return Promise.resolve(this._task)
  if (this._opening) return this._opening
  const token = getToken()
  if (!token) {
    const err = new Error('请先登录')
    err.fallback = false
    return Promise.reject(err)
  }
  const self = this
  this._opening = (USE_CLOUD ? connectCloud(token) : connectNative(token))
    .then((task) => {
      self._bind(task)
      return waitOpen(task, OPEN_MS)
    })
    .then((task) => {
      self._task = task
      return task
    })
    .finally(() => {
      self._opening = null
    })
  return this._opening
}

ChatSocket.prototype.ask = function (opts) {
  const self = this
  return this.ensure()
    .catch((err) => {
      const wrapped = err instanceof Error ? err : new Error(String(err && err.errMsg ? err.errMsg : err))
      if (wrapped.fallback !== false) wrapped.fallback = true
      return Promise.reject(wrapped)
    })
    .then((task) =>
      new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          self._pending = null
          reject(Object.assign(new Error('客服回复超时'), { fallback: false }))
        }, ASK_MS)
        const finish = (fn) => (value) => {
          if (!self._pending) return
          self._pending = null
          clearTimeout(timer)
          fn(value)
        }
        self._pending = {
          onEvent(data) {
            if (data.type === 'final_delta' && opts.onDelta) opts.onDelta(data.delta || '')
            if (data.type === 'final') finish(resolve)(data)
            if (data.type === 'error') {
              finish(reject)(Object.assign(new Error(data.message || '请求失败'), { fallback: false }))
            }
          },
          fail: finish(reject)
        }
        task.send({
          data: JSON.stringify({
            message: opts.message,
            session_id: opts.sessionId || null
          }),
          fail(err) {
            finish(reject)(Object.assign(new Error((err && err.errMsg) || '发送失败'), { fallback: true }))
          }
        })
      })
    )
}

module.exports = new ChatSocket()
