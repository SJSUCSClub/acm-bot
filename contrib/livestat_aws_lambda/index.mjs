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

async function fetchServicesInfo(services, attribs) {
  const res = await dynamo.send(new BatchGetCommand({
    RequestItems: {
      [DYNAMO_TABLE]: {
        AttributesToGet: attribs,
        Keys: services.map(id => ({ id })),
      },
    },
  }));

  return res.Responses[DYNAMO_TABLE];
}

async function fsiHistory(service) {
  return await fetchServicesInfo([service], ["history"]);
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
    const content = ["<!DOCTYPE html><html>", HTML_COMMON_HEAD, "<body>"];
    for (const [date, status] of Object.entries(history).reverse()) {
      content.push(`<tr><td>${renderDateString(date)}</td><td>${status}</td></tr>`);
    }
    content.push("</body></html>");
    body = content.join("");
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

async function fsiStats(services) {
  return await fetchServicesInfo(services, ["id", "status", "lastUpdated"]);
}

function renderDateString(dateStr) {
  const date = new Date(dateStr);
  // Timezone is set by TZ environment variable, which will get picked up by NodeJS (and libc) automatically
  return date.toLocaleString("en-US", { timeZoneName: "shortOffset" });
}

function renderStats(stats, format) {
  let contentType, body;

  switch (format) {
  case "json":
    contentType = "application/json";
    // DynamoDB gives us [{id, ...}, {id, ...}]
    // we want to return {id: {...}, id: {...}} to signify that the order is meaningless
    body = JSON.stringify(Object.fromEntries(stats.map(service => {
      const {id, ...rest} = service;
      return [id, rest];
    })));
    break;
  case "html":
      // CSS are inline because I really can't be bothered to spin up S3 (and pay for it)
    contentType = "text/html";
    const headerRow = `<tr><th>The thing...</th><th>is...</th><th>since...</th></tr>`;
    const rows = stats.map(service => `<tr><td>${service.id}</td><td>${service.status}</td><td>${renderDateString(service.lastUpdated)}</td></tr>`);
    body = `<!DOCTYPE html><html>${HTML_COMMON_HEAD}<body><table>${headerRow}${rows}</table></body></html>`;
    break;
  case "plaintext":
    contentType = "text/plain";
    body = stats.map(service => `${service.id}\nsince: ${renderDateString(service.lastUpdated)}\nis: ${service.status}\n`).join("\n");
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
  const timeNow = new Date().toISOString();
  // Let errors propagate into logs and a 500
  await dynamo.send(new UpdateCommand({
    TableName: DYNAMO_TABLE,
    Key: { id },
    UpdateExpression: "set #status = :status, #lastUpdated = :now, #history = list_append(#history, :historyItem)",
    ExpressionAttributeNames: {
      "#status": "status",
      "#lastUpdated": "lastUpdated",
      "#history": "history",
    },
    ExpressionAttributeValues: {
      ":status": status,
      ":now": timeNow,
      ":historyItem": [{ status, since: timeNow }],
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
        status: '',
        lastUpdated: new Date().toISOString(),
        history: [],
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
    Key: { id },
  }));
  console.log(`delete-service: "${id}" deleted`);
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

      const stats = await fsiStats(services);
      return renderStats(stats, params.format || 'json');
    case "/history": {
      // Validation
      if (!params.service) {
        return { statusCode: 400, body: "Missing parameter 'service" };
      }

      // Respond
      const history = await fsiHistory(param.service);
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
