const { USE_CLOUD, BASE_URL } = require('./config')
const { callContainer } = require('./cloud')

const pending = {}

function toContainerPath(url) {
  const value = String(url || '').trim()
  if (!value) return ''
  if (value.indexOf('/api/v1/') === 0 || value.indexOf('/uploads/') === 0) return value
  const apiAt = value.indexOf('/api/v1/')
  if (apiAt >= 0) return value.slice(apiAt)
  const uploadAt = value.indexOf('/uploads/')
  if (uploadAt >= 0) return value.slice(uploadAt)
  return ''
}

function fileName(path) {
  let hash = 0
  for (let i = 0; i < path.length; i += 1) {
    hash = (hash * 31 + path.charCodeAt(i)) | 0
  }
  return 'media_' + (hash >>> 0) + '.jpg'
}

function load(url) {
  const value = String(url || '').trim()
  if (!value) return Promise.resolve('')
  if (value.indexOf('cloud://') === 0) return Promise.resolve(value)
  if (value.indexOf('/assets/') === 0) return Promise.resolve(value)
  if (wx.env && value.indexOf(wx.env.USER_DATA_PATH) === 0) return Promise.resolve(value)

  if (!USE_CLOUD) {
    if (value.indexOf('http://') === 0 || value.indexOf('https://') === 0) return Promise.resolve(value)
    return Promise.resolve(BASE_URL + value)
  }

  const path = toContainerPath(value)
  if (!path) {
    if (value.indexOf('http://') === 0 || value.indexOf('https://') === 0) {
      return Promise.resolve(value)
    }
    return Promise.resolve('')
  }
  if (pending[path]) return pending[path]

  const localPath = wx.env.USER_DATA_PATH + '/' + fileName(path)
  const fs = wx.getFileSystemManager()
  try {
    fs.accessSync(localPath)
    pending[path] = Promise.resolve(localPath)
    return pending[path]
  } catch (err) {}

  pending[path] = callContainer({
    path,
    method: 'GET',
    dataType: '其他',
    responseType: 'arraybuffer'
  })
    .then((res) => {
      if (!res || res.statusCode < 200 || res.statusCode >= 300 || !res.data) {
        throw new Error('图片加载失败')
      }
      fs.writeFileSync(localPath, res.data)
      return localPath
    })
    .catch(() => {
      delete pending[path]
      if (BASE_URL && path.indexOf('/api/v1/') === 0) return BASE_URL + path
      return ''
    })
  return pending[path]
}

function loadAvatar(url) {
  const fallback = '/assets/default-avatar.png'
  const value = String(url || '').trim()
  if (!value) return Promise.resolve(fallback)
  if (value.indexOf('/assets/') === 0) return Promise.resolve(value)
  return load(value).then((src) => src || fallback)
}

function hydrateProduct(product) {
  if (!product) return Promise.resolve(product)
  const gallery = product.gallery || []
  return Promise.all([load(product.cover)].concat(gallery.map(load))).then((urls) =>
    Object.assign({}, product, {
      coverSrc: urls[0] || '',
      gallerySrc: urls.slice(1)
    })
  )
}

module.exports = {
  load,
  loadAvatar,
  hydrateProduct
}
