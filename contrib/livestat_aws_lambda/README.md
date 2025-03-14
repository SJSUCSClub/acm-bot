# HTTP Updates Endpoint based on AWS Lambda

An HTTP server that takes updates from the monitor's `DOOR_HTTP_ENDPOINT` feature.

Deploy using AWS console:

- Create a DynamoDB table _YourTable_. Set partition key to `id` (string), sort key to none.
- Create a Lambda _YourHttpEndpoint_ "author from scratch" on NodeJS 22.x.
  Select "create a new role from AWS policy templates", and use "simple microservice permissions (DynamoDB)".
  Check "enable function URL" in Advanced Configurations.
- Upload all `.mjs` files.
- Open the link Configurations > Permissions > Exection Role (to IAM page). In `AWSLambdaMicroserviceExecutionRole`, choose Edit, and set:
  ```
  "dynamodb:DeleteItem",
  "dynamodb:GetItem",
  "dynamodb:BatchGetItem",
  "dynamodb:PutItem",
  "dynamodb:UpdateItem",
  "dynamodb:Query",
  "dynamodb:Scan"
  ```
