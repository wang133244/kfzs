const cloud = require('wx-server-sdk')

cloud.init({
  env: cloud.DYNAMIC_CURRENT_ENV
})

exports.main = async () => {
  const wxContext = cloud.getWXContext()
  return {
    errCode: 0,
    errMsg: 'ok',
    openid: wxContext.OPENID || '',
    appid: wxContext.APPID || '',
    unionid: wxContext.UNIONID || ''
  }
}
