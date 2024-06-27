# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks
from cdk_nag import NagPackSuppression
from cdk_nag import NagSuppressions
from cdk_nag import NIST80053R5Checks

from cdk.application_account import ApplicationStack
from cdk.database_account import DatabaseStack

app = cdk.App()

env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ["CDK_DEFAULT_REGION"],
)

databaes_stack = DatabaseStack(app, "DatabaseStack", env=env)
application_stack = ApplicationStack(app, "ApplicationStack", env=env)

# ApplicationStack Surpressions

NagSuppressions.add_resource_suppressions_by_path(
    application_stack,
    path=[
        "/ApplicationStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C1024MiB/ServiceRole/DefaultPolicy/Resource",
        "/ApplicationStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C1024MiB/ServiceRole/Resource",
        "/ApplicationStack/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C1024MiB/Resource",
    ],
    suppressions=[
        NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="AwsSolutions-L1",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-IAMNoInlinePolicy",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-LambdaConcurrency",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-LambdaDLQ",
            reason="Cannot control CDKBucketDeployment resources",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-LambdaInsideVPC",
            reason="Cannot control CDKBucketDeployment resources",
        ),
    ],
)

NagSuppressions.add_resource_suppressions_by_path(
    application_stack,
    path=[
        "/ApplicationStack/connectiontest-lambda-role/DefaultPolicy/Resource",
        "/ApplicationStack/lambda_execution_policy/Resource",
        "/ApplicationStack/ApplicationVpcFlowLog/IAMRole/DefaultPolicy/Resource",
        "/ApplicationStack/connectiontest-lambda-role/DefaultPolicy/Resource",
    ],
    suppressions=[
        NagPackSuppression(
            id="AwsSolutions-IAM5",
            reason="Lambda basic execution policy uses minimal wildcarding",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-IAMNoInlinePolicy",
            reason="Cannot change default VPC flow log policy",
        ),
    ],
)

NagSuppressions.add_stack_suppressions(
    application_stack,
    suppressions=[
        NagPackSuppression(
            id="AwsSolutions-S1",
            reason="Server access logging is not in scope for this project",
        ),
        NagPackSuppression(
            id="AwsSolutions-L1",
            reason="Users of this project can specify a Python runtime version that works in their environment. This project was tested on Python3.9",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-S3BucketLoggingEnabled",
            reason="Server access logging is not in scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-S3BucketReplicationEnabled",
            reason="S3 bucket replication is not in scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-S3BucketVersioningEnabled",
            reason="Server access logging is not in scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-CloudWatchLogGroupEncrypted",
            reason="CloudWatch log encryption is not in scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-VPCNoUnrestrictedRouteToIGW",
            reason="Default routes to IGW is acceptable for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-LambdaDLQ",
            reason="Adding a DLQ for the connectiontest Lambda is not in scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-VPCSubnetAutoAssignPublicIpDisabled",
            reason="Not deploying EC2 instances in the public subnet",
        ),
    ],
)

# DatabaseStack Surpressions

NagSuppressions.add_resource_suppressions_by_path(
    databaes_stack,
    path=[
        "/DatabaseStack/PostgreSQLCluster/MonitoringRole/Resource",
        "/DatabaseStack/DatabaseVpcFlowLogsCWGroup/Resource",
        "/DatabaseStack/DatabaseVpcFlowLog/IAMRole/DefaultPolicy/Resource",
        "/DatabaseStack/PostgreSQLCluster/Secret/Resource",
        "/DatabaseStack/PostgreSQLCluster/Resource",
        "/DatabaseStack/PostgreSQLCluster/writer/Resource",
        "/DatabaseStack/RdsProxy/IAMRole/DefaultPolicy/Resource",
        "/DatabaseStack/CrossAccountRdsConnectRole/DefaultPolicy/Resource",
    ],
    suppressions=[
        NagPackSuppression(
            id="AwsSolutions-IAM4",
            reason="Cannot control AmazonRDSEnhancedMonitoringRole permissions",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-CloudWatchLogGroupEncrypted",
            reason="CloudWatch log encryption out of scope for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-IAMNoInlinePolicy",
            reason="Cannot change default VPC flow log policy",
        ),
        NagPackSuppression(
            id="AwsSolutions-SMG4",
            reason="Automatic secret rotation is out of scope for this project.",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-SecretsManagerRotationEnabled",
            reason="Automatic secret rotation is out of scope for this project.",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-SecretsManagerUsingKMSKey",
            reason="KMS encryption with an AWS managed key is acceptable for this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-RDSInstanceDeletionProtectionEnabled",
            reason="Deletion protection is intentionally disabled to make for easy destruction of this project",
        ),
        NagPackSuppression(
            id="AwsSolutions-RDS10",
            reason="Deletion protection is intentionally disabled to make for easy destruction of this project",
        ),
        NagPackSuppression(
            id="NIST.800.53.R5-RDSInBackupPlan",
            reason="A backup plan is intentionally omitted to make for easy destruction of this project",
        ),
    ],
)

cdk.Aspects.of(app).add(AwsSolutionsChecks())
cdk.Aspects.of(app).add(NIST80053R5Checks())

app.synth()
