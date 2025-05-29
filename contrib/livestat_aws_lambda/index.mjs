import { DynamoDBClient, } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  BatchGetCommand,
  UpdateCommand,
  PutCommand,
  DeleteCommand,
} from "@aws-sdk/lib-dynamodb";

import * as utils from "./utils.mjs"
import * as err from "./err.mjs"

const dynamoClient = new DynamoDBClient({});
const dynamo = DynamoDBDocumentClient.from(dynamoClient);

// DynamoDB table for storing services' status and history
const DYNAMO_TABLE = process.env.DYNAMO_TABLE;
// Highest permission token; permits add/remove/update services
const MASTER_TOKEN = process.env.MASTER_TOKEN;
// TODO implement lower tokens
//      per-service update only

const SERVICE_NAME_REGEX = /[a-zA-Z0-9-_.]+/;

const HTML_COMMON_HEAD = `<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
<style>
body { display: flex; justify-content: center; }
table { border-collapse: collapse; }
tr { border: 1px solid black; border-left: none; border-right: none; border-top: none; }
th, td { padding: 0.5em; }
</style>
</head>`;



/**
 * Assumes provided dates are whole-days, without hour/minute/second part.
 *
 * @typedef {{ since: string, status: string }} HistoryItem
 * @typedef {{ id: string, history: HistoryItem[] }[]} HistoryFetchRes
 *
 * @param {string[]} servicesId
 * @param {Date} dateBegin
 * @param {Date} dateEnd
 * @returns {HistoryFetchRes}
 */
async function fetchHistory(servicesId, dateBegin, dateEnd) {
  const keys = []
  // https://stackoverflow.com/a/10040679
  for (const id of servicesId) {
    for (let d = new Date(dateBegin); d <= dateEnd; d.setDate(d.getDate() + 1)) {
      keys.push({ id, date: d.getTime() });
    }
  }

  const res = await dynamo.send(new BatchGetCommand({
    RequestItems: {
      [DYNAMO_TABLE]: {
        AttributesToGet: ["id", "history"],
        Keys: keys,
      },
    },
  }))

  return res.Responses[DYNAMO_TABLE]
}

/**
 * @param {Date} dateBegin
 * @param {Date} dateEnd
 * @param {HistoryFetchRes} history
 * @param {'json' | 'html'} format
 */
function renderHistory(dateBegin, dateEnd, history, format) {
  let contentType, body;

  switch (format) {
  case "json": {
    contentType = "application/json";
    body = JSON.stringify(history);
  } break;

  case "html": {
    contentType = "text/html";
    const rows = history.flatMap(
      ({ id, history }) => history.map(
        item => `<tr><td>${id}</td><td>${item.status}</td><td>${utils.dateStored2Locale(item.since)}</td></tr>`
      )
    )
    body =
`<!DOCTYPE html><html>
${HTML_COMMON_HEAD}
<body>
<main>
  <h1>HISTORY OF THINGS</h1>
  <p>from: ${dateBegin.toDateString()}
  <br>to: ${dateEnd.toDateString()}
  </p>
  <table>
    <tr><th>The thing...</th><th>is...</th><th>since...</th></tr>
    ${rows.join("\n")}
    </table>
</main>
</body></html>`
  } break;

  default:
    throw err.badRequest(`Invalid format "${format}"`)
  }

  return {
    statusCode: 200,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "max-age=86400",
      // Cache up to 1 day, the history report shouldn't change that often
      // so we can afford to cache it longer
    },
    body,
  };
}



/**
 * @typedef {{id: string, status: string, lastUpdated: string}[]} StatsFetchRes
 *
 * @param {string} servicesId
 * @returns {StatsFetchRes}
 */
async function fetchStats(servicesId) {
  const res = await dynamo.send(new BatchGetCommand({
    RequestItems: {
      [DYNAMO_TABLE]: {
        AttributesToGet: ["id", "status", "lastUpdated"],
        Keys: servicesId.map(id => ({ id, date: 0 })),
      },
    },
  }));

  return res.Responses[DYNAMO_TABLE];
}

/**
 * @param {StatsFetchRes} services
 * @param {'json' | 'html' | 'plaintext'} format
 */
function renderStats(services, format) {
  let contentType, body;

  switch (format) {
  case "json": {
    contentType = "application/json";
    // DynamoDB gives us [{id, ...}, {id, ...}]
    // we want to return {id: {...}, id: {...}} to signify that the order is meaningless
    body = JSON.stringify(utils.list2obj(services));
  } break;

  case "html": {
    // CSS are inline because I really can't be bothered to spin up S3 (and pay for it)
    contentType = "text/html";
    const rows = services.map(s => `<tr><td>${s.id}</td><td>${s.status}</td><td>${utils.dateStored2Locale(s.lastUpdated)}</td></tr>`);
    body =
`<!DOCTYPE html><html>
${HTML_COMMON_HEAD}
<body>
<main>
  <table>
  <tr><th>The thing...</th><th>is...</th><th>since...</th></tr>
  ${rows.join("\n")}
  </table>
</main>
</body></html>`;
  } break;

  case "plaintext": {
    contentType = "text/plain";
    body = services.map(s =>
`${s.id}
since: ${utils.dateStored2Locale(s.lastUpdated)}
is: ${s.status}
`).join("\n");
  } break;

  default:
    throw err.badRequest(`Invalid format "${format}"`)
  }

  return {
    statusCode: 200,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "max-age=300", // Cache up to 5 minutes, just an arbitrary number I made up
    },
    body: body,
  }
}



async function updateServiceStat(id, status) {
  let nowIso8601, currDateUnix
  {
    const now = new Date();
    nowIso8601 = now.toISOString();
    now.setHours(0, 0, 0, 0);
    currDateUnix = now.getTime();
  }

  // Let errors propagate into logs and a 500
  await dynamo.send(new UpdateCommand({
    TableName: DYNAMO_TABLE,
    Key: { id, date: 0 },
    UpdateExpression: "set #status = :status, #lastUpdated = :now",
    ExpressionAttributeNames: {
      "#status": "status",
      "#lastUpdated": "lastUpdated",
    },
    ExpressionAttributeValues: {
      ":status": status,
      ":now": nowIso8601,
    },
  }));
  await dynamo.send(new UpdateCommand({
    TableName: DYNAMO_TABLE,
    Key: { id, date: currDateUnix },
    UpdateExpression: "set #history = list_append(if_not_exists(#history, :empty_list), :historyItem)",
    ExpressionAttributeNames: { "#history": "history" },
    ExpressionAttributeValues: {
      ":empty_list": [],
      ":historyItem": [{ status, since: nowIso8601 }],
    },
  }));

  return {
    statusCode: 200,
    body: "OK",
  };
}

async function newService(id) {
  try {
    const res = await dynamo.send(new PutCommand({
      TableName: DYNAMO_TABLE,
      Item: {
        id,
        date: 0,
        status: '',
        lastUpdated: new Date().toISOString(),
      },
      // Don't override an existing service
      ConditionExpression: "attribute_not_exists(id)",
    }));
    console.log(`new-service: "${id}" added`);
  } catch (e) {
    if (e.name === "ConditionalCheckFailedException") {
      throw err.conflict(`Service "${id} already exists`)
    }

    // Exception not recognized, fail dramatically
    throw e;
  }
}

async function deleteService(id) {
  const res = await dynamo.send(new DeleteCommand({
    TableName: DYNAMO_TABLE,
    Key: { id, date: 0 },
  }));
  console.log(`delete-service: "${id}" deleted`);
  // TODO do we want to delete all history associated with the service as well?
}



function checkToken(tok) {
  if (tok !== MASTER_TOKEN)
    throw err.unauthorized("Invalid token")
}

function checkServiceId(id) {
  if (!SERVICE_NAME_REGEX.test(id))
    throw err.badRequest(`Invalid service ID "${id}"`)
}

function parseServiceList(str) {
  if (!str)
    throw err.badRequest("Missing parameter 'services'");

  const services = str.split(",")
  services.forEach(checkServiceId)
  return services
}



const ACTUAL_HANDLER_MAP = {
  // Compatibility measure
  // Previously, querying service status landed here; telling everybody who use the website, iOS shortcut, etc. to switch is probably impractical
  // Problem: cache will store duplicates for this AND /service
  //       -- probably not an issue, anticipating low volumes
  "/": async (event, context) => {
    return await ACTUAL_HANDLER_MAP["/service"](event, context)
  },

  "/service": async (event, context) => {
    const params = event.queryStringParameters || {}

    switch (event.requestContext.http.method) {
    case "GET": {
      // Validation
      const services = parseServiceList(params.services)

      // Respond
      const stats = await fetchStats(services);
      return renderStats(stats, params.format || 'json');
    }

    case "POST": {
      // Validation
      checkToken(params.token);
      checkServiceId(params.service)

      // Respond
      return await newService(params.id);
    }

    case "DELETE": {
      // Validation
      checkToken(params.token);
      checkServiceId(params.service)

      // Respond
      return await deleteService(params.id);
    }
    }
    throw err.invalidMethod()
  },



  "/service/status": async (event, context) => {
    const params = event.queryStringParameters || {}

    switch (event.requestContext.http.method) {
    case "POST": {
      // Validation
      checkToken(params.token);
      checkServiceId(params.service)

      // Respond
      return await updateServiceStat(params.id, event.body);
    }
    }
    throw err.invalidMethod()
  },



  "/service/history": async (event, context) => {
    if (event.requestContext.http.method !== "GET")
      throw err.invalidMethod()
    const params = event.queryStringParameters || {}

    // Validation
    const services = parseServiceList(params.services)

    const dateBegin = new Date(params.dateBegin)
    dateBegin.setHours(0, 0, 0, 0)
    const dateEnd = new Date(params.dateEnd)
    dateEnd.setHours(0, 0, 0, 0)

    // Respond
    const history = await fetchHistory(services, dateBegin, dateEnd)
    return renderHistory(dateBegin, dateEnd, history, params.format || 'json')
  },
}

export const handler = async (event, context) => {
  try {
    const h = ACTUAL_HANDLER_MAP[event.requestContext.http.path]
    if (!h) {
      return { statusCode: 404, body: "Not found" }
    }

    return await h(event, context)
  } catch (e) {
    if (e[err.returnable]) {
      return e
    }

    console.log("Error cannot be converted to HTTP response:", e)
    return { statusCode: 500, body: "Internal server error" }
  }
}
