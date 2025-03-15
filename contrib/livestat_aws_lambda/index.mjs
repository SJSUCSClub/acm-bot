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

const DYNAMO_TABLE = process.env.DYNAMO_TABLE;
const MASTER_TOKEN = process.env.MASTER_TOKEN;

async function fetchStats(services) {
  const res = await dynamo.send(new BatchGetCommand({
    RequestItems: {
      [DYNAMO_TABLE]: {
        Keys: services.map(id => ({ id })),
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

function renderStats(stats, format) {
  let contentType, body;

  switch (format) {
  case "json":
    contentType = "application/json";
    body = JSON.stringify(Object.fromEntries(stats.map(service => {
      const {id, ...rest} = service;
      return [id, rest];
    })));
    break;
  case "html":
    contentType = "text/html";
    const styles = `<style>table { border-collapse: collapse; } th, td { border: 1px solid black; padding: 0.5em; }</style>`;
    const headerRow = `<tr><th>Service</th><th>Status</th><th>Last Updated</th></tr>`;
    const rows = stats.map(service => `<tr><td>${service.id}</td><td>${service.status}</td><td>${renderDateString(service.lastUpdated)}</td></tr>`);
    body = `<html><head>${styles}</head><body><table>${headerRow}${rows}</table></body></html>`;
    break;
  case "plaintext":
    // TODO better way to format this?
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
      "Cache-Control": "max-age=300", // Cache up to 5 minutes
    },
    body: body,
  }
}

async function updateServiceStat(id, status) {
  // Let errors propagate into logs and a 500
  await dynamo.send(new UpdateCommand({
    TableName: DYNAMO_TABLE,
    Key: { id },
    UpdateExpression: "set #status = :status, #lastUpdated = :now",
    ExpressionAttributeNames: {
      "#status": "status",
      "#lastUpdated": "lastUpdated",
    },
    ExpressionAttributeValues: {
      ":status": status,
      ":now": new Date().toISOString(),
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
    if (req.path === "/") {
      // Validation
      if (!params.services) {
        return {
          statusCode: 400,
          body: "Missing parameter 'services'",
        };
      }

      // Respond
      const services = params.services.split(",");
      const stats = await fetchStats(services);
      return renderStats(stats, params.format || 'json');
    }
    break;
  case "POST":
    if (params.token !== MASTER_TOKEN) {
      return { statusCode: 401, body: "Invalid token" };
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

    switch (req.path) {
    case "/service":
      return await deleteService(params.id);
    }
  }

  return { statusCode: 400, body: "Invalid request" };
};
