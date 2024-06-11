# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import Aws as Aws
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import CfnOutput
from aws_cdk import Duration
from aws_cdk import RemovalPolicy
from aws_cdk import Stack
from constructs import Construct


class DatabaseStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Config
        application_account_id = self.node.try_get_context("application_account_id")
        connectiontest_lambda_role_name = self.node.try_get_context(
            "connectiontest_lambda_role_name",
        )
        application_vpc_id = self.node.try_get_context("application_vpc_id")
        application_vpc_subnet_ids = str(
            self.node.try_get_context("application_vpc_subnets"),
        ).split(",")
        database_vpc_cidr = self.node.try_get_context("database_vpc_cidr")
        target_roles = self.node.try_get_context("target_roles")
        database_name = self.node.try_get_context("database_name")
        database_account_rdsdb_connect_role_name = self.node.try_get_context(
            "database_account_rdsdb_connect_role_name",
        )

        connectiontest_lambda_role_arn = f"arn:{Aws.PARTITION}:iam::{application_account_id}:role/{connectiontest_lambda_role_name}"
        POSTGRESQL_PORT = 5432
        stack_output_dict = {}

        # Networking

        cw_group = logs.LogGroup(
            self,
            "DatabaseVpcFlowLogsCWGroup",
            log_group_name="database-vpc-flow-logs",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_DAY,
        )

        database_vpc = ec2.Vpc(
            self,
            "DatabaseVPC",
            vpc_name="database_vpc",
            ip_addresses=ec2.IpAddresses.cidr(database_vpc_cidr),
            restrict_default_security_group=True,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="database",
                    cidr_mask=27,
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                ),
            ],
        )

        ec2.FlowLog(
            self,
            "DatabaseVpcFlowLog",
            resource_type=ec2.FlowLogResourceType.from_vpc(database_vpc),
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(cw_group),
            flow_log_name="database-vpc-flow-logs",
        )

        database_subnet_selection = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
        )

        rds_sg = ec2.SecurityGroup(
            self,
            # TODO: update naming
            "RdsClusterSecurityGroup",
            vpc=database_vpc,
            description="RDS instance security group",
            allow_all_outbound=False,
            security_group_name="rds-sg",
        )

        rds_proxy_sg = ec2.SecurityGroup(
            self,
            "RdsProxySecurityGroup",
            vpc=database_vpc,
            description="RDS proxy security group",
            allow_all_outbound=False,
            security_group_name="rdsproxy-sg",
        )

        rds_sg.connections.allow_from(
            rds_proxy_sg,
            ec2.Port.tcp(POSTGRESQL_PORT),
            "Allow inbound PostgreSQL access to RDS database from the database proxy",
        )

        rds_proxy_sg.connections.allow_to(
            rds_sg,
            ec2.Port.tcp(POSTGRESQL_PORT),
            "Allow outbound PostgreSQL access from RDS Proxy to the RDS database",
        )

        # RDS

        db_cluster = rds.DatabaseCluster(
            self,
            "PostgreSQLCluster",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_2,
            ),
            cloudwatch_logs_exports=["postgresql"],
            deletion_protection=False,
            iam_authentication=True,
            security_groups=[rds_sg],
            monitoring_interval=Duration.seconds(60),
            serverless_v2_max_capacity=10,
            serverless_v2_min_capacity=0.5,
            storage_encrypted=True,
            vpc=database_vpc,
            vpc_subnets=database_subnet_selection,
            writer=rds.ClusterInstance.serverless_v2("writer"),
            default_database_name=database_name,
        )

        db_cluster.secret.add_rotation_schedule(
            "RotationSchedule",
            automatically_after=Duration.days(30),
            hosted_rotation=secretsmanager.HostedRotation.postgre_sql_single_user(
                function_name="PostgreSQLClusterSecretRotationFunction",
            ),
        )

        db_proxy = rds.DatabaseProxy(
            self,
            "RdsProxy",
            proxy_target=rds.ProxyTarget.from_cluster(db_cluster),
            secrets=[db_cluster.secret],
            vpc=database_vpc,
            iam_auth=True,
            vpc_subnets=database_subnet_selection,
            security_groups=[rds_proxy_sg],
        )

        # IAM

        cross_account_rds_connect_role = iam.Role(
            self,
            "CrossAccountRdsConnectRole",
            role_name=database_account_rdsdb_connect_role_name,
            description="IAM role for principals in workload accounts to assume and access the database with IAM authentication",
            assumed_by=iam.AccountPrincipal(account_id=Aws.ACCOUNT_ID),
        )

        db_proxy.grant_connect(cross_account_rds_connect_role, db_user="postgres")

        assume_role_statement = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            sid="AllowApplicationAccountAssumption",
            actions=["sts:AssumeRole"],
            principals=[
                iam.ArnPrincipal(
                    arn=connectiontest_lambda_role_arn,
                ),
            ],
        )

        cross_account_rds_connect_role.assume_role_policy.add_statements(
            assume_role_statement,
        )

        application_vpc = ec2.Vpc.from_lookup(
            self,
            "AppVpc",
            vpc_id=application_vpc_id,
        )

        proxy_endpoint_sg = ec2.SecurityGroup(
            self,
            "app-proxy-endpoint-sg",
            vpc=application_vpc,
            description="RDS Proxy Application Endpoint security group",
            allow_all_outbound=False,
            security_group_name="application-proxy-endpoint",
        )

        proxy_endpoint_sg.add_egress_rule(
            ec2.Peer.ipv4(application_vpc.vpc_cidr_block),
            ec2.Port.tcp(POSTGRESQL_PORT),
            description="Allow outbound PostgreSQL access from RDS Proxy application endpoint to the RDS database",
        )

        proxy_endpoint_sg.add_ingress_rule(
            ec2.Peer.ipv4(application_vpc.vpc_cidr_block),
            ec2.Port.tcp(POSTGRESQL_PORT),
            description="Allow inbound PostgreSQL access to RDS Proxy application endpoint from the VPC",
        )

        for target_role in target_roles.split(","):

            target_role_string = target_role.lower().replace("_", "-")

            endpoint = rds.CfnDBProxyEndpoint(
                self,
                f"ApplicationProxyEndpoint-{target_role_string}",
                db_proxy_endpoint_name=f"application-db-endpoint-{target_role_string}",
                db_proxy_name=db_proxy.db_proxy_name,
                vpc_subnet_ids=application_vpc_subnet_ids,
                target_role=target_role,
                vpc_security_group_ids=[proxy_endpoint_sg.security_group_id],
            )

            stack_output_dict[
                f"ApplicationProxyEndpointOutput-{target_role_string}"
            ] = endpoint.attr_endpoint

        for key, value in stack_output_dict.items():
            CfnOutput(
                self,
                key,
                export_name=key,
                value=value,
            )
