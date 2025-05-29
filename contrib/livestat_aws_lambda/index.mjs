import { DynamoDBClient, } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  BatchGetCommand,
  UpdateCommand,
  PutCommand,
  DeleteCommand,
} from "@aws-sdk/lib-dynamodb";

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
 * @param {string} serviceId
 * @param {Date} dateBegin
 * @param {Date} dateEnd
 * @returns {{ since: string, status: string }[]}
 */
async function fetchHistory(serviceId, dateBegin, dateEnd) {
  const keys = []
  // https://stackoverflow.com/a/10040679
  for (let d = dateBegin; d <= dateEnd; d.setDate(d.getDate() + 1)) {
    keys.push({ id: serviceId, date: d.getTime() });
  }

  const res = await dynamo.send(new BatchGetCommand({
    RequestItems: {
      [DYNAMO_TABLE]: {
        AttributesToGet: ["history"],
        Keys: keys,
      },
    },
  }))

  const res1 = res.Responses[DYNAMO_TABLE];
  if (res1.length == 0)
    return []
  return res1[0].history
}

function renderHistory(history, format) {
  let contentType, body;

  switch (format) {
  case "json": {
    contentType = "application/json";
    body = JSON.stringify(history);
    break;
  }
  case "html": {
    contentType = "text/html";
    const rows = history.map(entr => `<tr><td>${renderDateString(entr.since)}</td><td>${entr.status}</td></tr>`)
    body =
`<!DOCTYPE html><html>
${HTML_COMMON_HEAD}
<body><table>
<tr><th>since...</th><th>is...</th></tr>
${rows.join("\n")}
</table></body></html>`;
    break;
  }
  default:
    return { statusCode: 400, body: "Invalid format" };
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
 * @param {string} servicesId
 * @returns {{id: string, status: string, lastUpdated: string}[]}
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

function renderDateString(dateStr) {
  const date = new Date(dateStr);
  // Timezone is set by TZ environment variable, which will get picked up by NodeJS (and libc) automatically
  return date.toLocaleString("en-US", { timeZoneName: "shortOffset" });
}

function renderStats(services, format) {
  let contentType, body;

  switch (format) {
  case "json":
    contentType = "application/json";
    // DynamoDB gives us [{id, ...}, {id, ...}]
    // we want to return {id: {...}, id: {...}} to signify that the order is meaningless
    body = JSON.stringify(Object.fromEntries(services.map(s => {
      const {id, ...rest} = s;
      return [id, rest];
    })));
    break;



  case "html":
    // CSS are inline because I really can't be bothered to spin up S3 (and pay for it)
    contentType = "text/html";
    const rows = services.map(s => `<tr><td>${s.id}</td><td>${s.status}</td><td>${renderDateString(s.lastUpdated)}</td></tr>`);
    body =
`<!DOCTYPE html><html>
${HTML_COMMON_HEAD}
<body><table>
<tr><th>The thing...</th><th>is...</th><th>since...</th></tr>
${rows.join("\n")}
</table></body></html>`;
    break;



  case "plaintext":
    contentType = "text/plain";
    body = services.map(s =>
`${s.id}
since: ${renderDateString(s.lastUpdated)}
is: ${s.status}
`).join("\n");
    break;
  default:
    return { statusCode: 400, body: "Invalid format" };
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
      return { statusCode: 409, body: "Service already exists" };
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



export const handler = async (event, context) => {
  const req = event.requestContext.http;
  const params = event.queryStringParameters || {};

  switch (req.method) {
  case "GET":
    switch (req.path) {
    case "/":
      // Validation
      if (!params.services) {
        return { statusCode: 400, body: "Missing parameter 'services'" };
      }

      // Respond
      const services = params.services.split(",");
      for (const service of services) {
        if (!SERVICE_NAME_REGEX.test(service)) {
          return { statusCode: 400, body: "Invalid service id" };
        }
      }

      const stats = await fetchStats(services);
      return renderStats(stats, params.format || 'json');
    case "/history": {
      // Validation
      if (!params.service) {
        return { statusCode: 400, body: "Missing parameter 'service" };
      }

      // Respond
      const service = params.service
      if (!SERVICE_NAME_REGEX.test(service))
        return { statusCode: 400, body: "Invalid service id" }
      const dateBegin = new Date(params.dateBegin)
      dateBegin.setHours(0, 0, 0, 0)
      const dateEnd = new Date(params.dateEnd)
      dateEnd.setHours(0, 0, 0, 0)

      const history = await fetchHistory(service, dateBegin, dateEnd);
      return renderHistory(history, params.format || 'json');
    }
    }
    break;
  case "POST":
    if (params.token !== MASTER_TOKEN) {
      return { statusCode: 401, body: "Invalid token" };
    }
    if (!SERVICE_NAME_REGEX.test(params.id)) {
      return { statusCode: 400, body: "Invalid service id" };
    }

    switch (req.path) {
    case "/service/status":
      return await updateServiceStat(params.id, event.body);
    case "/service":
      return await newService(params.id);
    }
    break;
  case "DELETE":
    if (params.token !== MASTER_TOKEN) {
      return { statusCode: 401, body: "Invalid token" };
    }
    if (!SERVICE_NAME_REGEX.test(params.id)) {
      return { statusCode: 400, body: "Invalid service id" };
    }

    switch (req.path) {
    case "/service":
      return await deleteService(params.id);
    }
  }

  return { statusCode: 400, body: "Invalid request" };
};
