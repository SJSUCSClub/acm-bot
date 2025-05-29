export const returnable = Symbol()

function makeErrFunc(statusCode) {
  return msg => ({ [returnable]: true, statusCode, body: msg })
}

export const badRequest = makeErrFunc(400)
export const unauthorized = makeErrFunc(401)
export const forbidden = makeErrFunc(403)
export const notFound = makeErrFunc(404)
export const conflict = makeErrFunc(409)

export function invalidMethod() {
  return badRequest("Invalid method")
}
