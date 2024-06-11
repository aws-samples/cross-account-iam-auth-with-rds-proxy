# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import Aws as Aws
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_ram as ram
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import CfnOutput
from aws_cdk import Duration
from aws_cdk import Fn
from aws_cdk import RemovalPolicy
from aws_cdk import Stack
from constructs import Construct


class ApplicationStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Config

        database_account_id = self.node.try_get_context("database_account_id")
        database_account_rdsdb_connect_role_name = self.node.try_get_context(
            "database_account_rdsdb_connect_role_name",
        )
        connectiontest_lambda_role_name = self.node.try_get_context(
            "connectiontest_lambda_role_name",
        )
        application_rds_proxy_endpoint = self.node.try_get_context(
            "application_rds_proxy_endpoint",
        )
        application_vpc_cidr = self.node.try_get_context("application_vpc_cidr")
        database_username = self.node.try_get_context("database_username")
        database_name = self.node.try_get_context("database_name")
        python_version = self.node.try_get_context("python_version")

        database_account_rdsdb_connect_role_arn = f"arn:{Aws.PARTITION}:iam::{database_account_id}:role/{database_account_rdsdb_connect_role_name}"

        POSTGRESQL_PORT = 5432

        # Networking

        cw_group = logs.LogGroup(
            self,
            "ApplicationVpcFlowLogsCWGroup",
            log_group_name="application-vpc-flow-logs",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )

        application_vpc = ec2.Vpc(
            self,
            "ApplicationVpc",
            vpc_name="application_vpc",
            ip_addresses=ec2.IpAddresses.cidr(application_vpc_cidr),
            restrict_default_security_group=True,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="application",
                    cidr_mask=27,
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                ),
                ec2.SubnetConfiguration(
                    name="public",
                    cidr_mask=27,
                    subnet_type=ec2.SubnetType.PUBLIC,
                ),
            ],
        )

        ec2.FlowLog(
            self,
            "ApplicationVpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(application_vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(cw_group),
            flow_log_name="application-vpc-flow-logs",
        )

        application_subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        )
        application_subnet_ids = application_vpc.select_subnets(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        ).subnet_ids

        application_subnet_arns = []
        for subnet_id in application_subnet_ids:
            subnet_arn = f"arn:{Aws.PARTITION}:ec2:{Aws.REGION}:{Aws.ACCOUNT_ID}:subnet/{subnet_id}"
            application_subnet_arns.append(subnet_arn)

        connectiontest_lambda_sg = ec2.SecurityGroup(
            self,
            "connectiontest-lambda-sg",
            vpc=application_vpc,
            description="Security group allowing access from connectiontest lambda to the application RDS proxy endpoint for PostgreSQL traffic and internet for HTTPS traffic",
            security_group_name="connectiontest-lambda-sg",
            allow_all_outbound=False,
        )

        connectiontest_lambda_sg.add_egress_rule(
            ec2.Peer.ipv4(application_vpc.vpc_cidr_block),
            ec2.Port.tcp(POSTGRESQL_PORT),
            description="Allow outbound PostgreSQL access from connectiontest lambda to the RDS database",
        )

        connectiontest_lambda_sg.add_egress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            description="Allow outbound HTTPS access from connectiontest lambda to the internet",
        )

        # RAM

        ram.CfnResourceShare(
            self,
            "rds-proxy-subnetshare",
            name="rds-proxy-subnetshare",
            allow_external_principals=False,
            principals=[database_account_id],
            resource_arns=application_subnet_arns,
        )

        # IAM

        connectiontest_lambda_role = iam.Role(
            self,
            "connectiontest-lambda-role",
            role_name=connectiontest_lambda_role_name,
            description="IAM role for the ConnectionTest Lambda function",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        rds_db_assume_role_policy = iam.ManagedPolicy(
            self,
            "cross-account-db-connect-policy",
            description="Policy to allow IAM entity to AssumeRole in Database Account to perform IAM authentication to the database",
            managed_policy_name="rdsdb-connect-assume-role",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "sts:AssumeRole",
                        ],
                        resources=[
                            database_account_rdsdb_connect_role_arn,
                        ],
                    ),
                ],
            ),
        )

        lambda_basic_execution_policy = iam.ManagedPolicy(
            self,
            "lambda_execution_policy",
            description="Allows Lambda function to write to log groups",
            managed_policy_name="lambda-basic-execution-policy",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        actions=[
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources=["*"],
                    ),
                    iam.PolicyStatement(
                        actions=[
                            "ec2:DescribeNetworkInterfaces",
                            "ec2:CreateNetworkInterface",
                            "ec2:DeleteNetworkInterface",
                            "ec2:DescribeInstances",
                            "ec2:AttachNetworkInterface",
                        ],
                        resources=["*"],
                    ),
                ],
            ),
        )

        connectiontest_lambda_role.add_managed_policy(rds_db_assume_role_policy)
        connectiontest_lambda_role.add_managed_policy(lambda_basic_execution_policy)

        # Lambda

        lambda_layer_bucket_name_id = (
            f"connectiontest-lambda-layer-bucket-{Stack.of(self).account}"
        )

        lambda_layer_bucket_key = kms.Key(
            self,
            "connectiontest-lambda-layer-bucket-key",
            removal_policy=RemovalPolicy.DESTROY,
            alias=f"alias/{lambda_layer_bucket_name_id}-kms-key",
            description="KMS Key to encrypt the connectiontest lambda layer bucket",
            enable_key_rotation=True,
        )

        layer_bucket = s3.Bucket(
            self,
            id=lambda_layer_bucket_name_id,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=lambda_layer_bucket_key,
            removal_policy=RemovalPolicy.DESTROY,
            enforce_ssl=True,
            bucket_name=lambda_layer_bucket_name_id,
            auto_delete_objects=True,
            versioned=False,
        )

        s3_deployment = s3deploy.BucketDeployment(
            self,
            "psycopg2-s3-deployment",
            sources=[
                s3deploy.Source.asset(
                    "assets/layers/psycopg2/layer.zip",
                ),
            ],
            destination_bucket=layer_bucket,
            destination_key_prefix="layers/psycopg2",
            extract=False,
            memory_limit=1024,
        )

        destination_key = Fn.select(0, s3_deployment.object_keys)

        python_runtime = _lambda.Runtime(f"python{python_version}")

        psycopg2_layer = _lambda.LayerVersion(
            self,
            "psycopg2-layer",
            layer_version_name="psycopg2",
            code=_lambda.Code.from_bucket(
                layer_bucket,
                f"layers/psycopg2/{destination_key}",
            ),
            compatible_runtimes=[
                python_runtime,
            ],
            compatible_architectures=[_lambda.Architecture.X86_64],
        )

        _lambda.Function(
            self,
            "connectiontest-lambda",
            runtime=python_runtime,
            code=_lambda.Code.from_asset("assets/lambda/code/"),
            function_name="connectiontest-lambda",
            handler="connection_test.handler",
            layers=[psycopg2_layer],
            memory_size=1024,
            timeout=Duration.seconds(30),
            role=connectiontest_lambda_role,
            vpc=application_vpc,
            vpc_subnets=application_subnet_selection,
            security_groups=[connectiontest_lambda_sg],
            tracing=_lambda.Tracing.ACTIVE,
            reserved_concurrent_executions=5,
            environment={
                "DATABASE_ACCOUNT_IAM_ROLE": database_account_rdsdb_connect_role_arn,
                "RDS_PROXY_APPLICATION_ENDPOINT": application_rds_proxy_endpoint,
                "DB_USERNAME": database_username,
                "DBNAME": database_name,
            },
        )

        # CFN Outputs

        subnet_ids_output_string = ""
        for subnet_id in application_vpc.private_subnets:
            subnet_ids_output_string += subnet_id.subnet_id + ","

        CfnOutput(
            self,
            "ApplicationVpcId",
            value=application_vpc.vpc_id,
            description="VPC ID",
        )

        CfnOutput(
            self,
            "ApplicationSubnetIds",
            value=subnet_ids_output_string,
            description="Subnet IDs",
        )
