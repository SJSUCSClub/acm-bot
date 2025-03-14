import { KMSClient, DecryptCommand } from "@aws-sdk/client-kms";

// Optional functionality if you want to encrypt environment variables

const kmsClient = new KMSClient({region: 'us-west-2'});

export async function decryptEnvVar(name) {
  try {
    const encrypted = process.env[name];
    const command = new DecryptCommand({
      CiphertextBlob: Buffer.from(encrypted, 'base64'),
      EncryptionContext: { LambdaFunctionName: process.env.AWS_LAMBDA_FUNCTION_NAME },
    });
    const response = await kmsClient.send(command);
    const decrypted = new TextDecoder().decode(response.Plaintext);
    process.env[name] = decrypted;
    return decrypted;
  } catch (err) {
    console.log('Decrypt error:', err);
    throw err;
  }
}
