"""Bounded AWS credential resolution, including console-login refresh calls."""
import boto3
import botocore.session
from botocore.config import Config
from botocore.exceptions import (ConnectionClosedError, ConnectTimeoutError, EndpointConnectionError,
    LoginRefreshRequired, NoCredentialsError, ReadTimeoutError, SSLError)


def aws_problem(error):
    if isinstance(error, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ConnectionClosedError)):
        return "AWS could not be reached. Check this computer's network and DNS access to AWS, then retry."
    if isinstance(error, SSLError):
        return "AWS certificate verification failed. Check the computer clock and trusted certificate setup; certificate checks remain enabled."
    if isinstance(error, (LoginRefreshRequired, NoCredentialsError)):
        return "AWS sign-in needs refreshing. Run sign-in-aws.cmd in your terminal, then retry."
    code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
    if code in {"AccessDeniedException", "AccessDenied", "UnauthorizedException"}:
        return "AWS denied access. Check account permissions for the selected model and inference profile."
    if code in {"ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId", "UnrecognizedClientException"}:
        return "AWS credentials expired or were rejected. Run sign-in-aws.cmd in your terminal, then retry."
    if code in {"ThrottlingException", "TooManyRequestsException"}:
        return "AWS is throttling requests. Wait a moment before trying again."
    return "AWS access is unavailable. Check AWS sign-in and the selected model's availability and permissions."


def transient_aws_error(error):
    return isinstance(error, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ConnectionClosedError))


def aws_session():
    sdk = botocore.session.get_session()
    # Login refresh follows the profile's home region. Model clients explicitly
    # select us-east-1 independently of that authentication region.
    if not sdk.get_config_variable("region"):
        sdk.set_config_variable("region", "us-east-1")
    sdk.set_default_client_config(Config(connect_timeout=5, read_timeout=10, retries={"total_max_attempts": 1}))
    return boto3.Session(botocore_session=sdk)
