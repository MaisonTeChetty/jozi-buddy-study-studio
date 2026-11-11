# AWS sign-in for this project

The existing AWS project is in **Europe (Stockholm), `eu-north-1`**, confirmed in AWS Settings → Project → Overview → Additional Info. The AI models are configured separately in **US East (N. Virginia), `us-east-1`**.

With AWS's projects experience, the region used for interactive sign-in must match the project's assigned region. Using the model region for sign-in can produce a failed browser flow even when the AWS profile page is already signed in. See [AWS CLI troubleshooting](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in-troubleshoot.html) and [project regions](https://docs.aws.amazon.com/accounts/latest/reference/project-regions.html).

From a Kiro PowerShell terminal:

```powershell
aws configure set region eu-north-1
aws login
aws sts get-caller-identity
```

If `aws` is missing from the inherited PATH, use `& 'C:\Program Files\Amazon\AWSCLIV2\aws.exe'` in place of `aws`. Open the newly generated link in the same Chrome window where the existing project is signed in. Select the existing workshop project; do not create a new project for a credential refresh. The link is temporary and its terminal must remain running.

`sign-in-aws.cmd` uses the official `aws login --remote` alternative. Enter any authorization code only into the terminal that started the flow. Never put passwords, tokens, AWS keys or authorization codes into chat or source code.

The backend resolves the default profile and temporary credential cache. Its study model client explicitly selects `us-east-1`; the Sonic model also explicitly selects `us-east-1`. A successful STS check verifies identity, not individual Bedrock model permissions.

If the backend reports DNS/network failure, first check connectivity to AWS. That error occurs before AWS can validate credentials. Do not disable TLS verification. If the correct-region browser flow still fails, retain its visible error and use AWS's account sign-in support rather than repeatedly creating new login links.
