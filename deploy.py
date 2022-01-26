import re
from pathlib import Path

from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_s3 as s3
from aws_cdk import core, aws_lambda, aws_ecr
from aws_cdk.aws_lambda import IFunction
from aws_cdk.aws_stepfunctions_tasks import LambdaInvoke
from kedro.framework.project import pipelines
from kedro.framework.session import KedroSession
from kedro.framework.startup import bootstrap_project
from kedro.pipeline.node import Node


def _clean_name(name: str) -> str:
    """Reformat a name to be compliant with AWS requirements for their resources.

    Returns:
        name: formatted name.
    """
    return re.sub(r"[\W_]+", "-", name).strip("-")[:63]


class KedroStepFunctionsStack(core.Stack):
    """A CDK Stack to deploy a Kedro pipeline to AWS Step Functions."""

    env = "aws"
    project_path = Path.cwd()
    erc_repository_name = project_path.name
    s3_data_bucket_name = (
        "spaceflights-step-functions-ro62"  # this is where the raw data is located
    )

    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self._parse_kedro_pipeline()
        self._set_ecr_repository()
        self._set_ecr_image()
        self._set_s3_data_bucket()
        self._convert_kedro_pipeline_to_step_functions_state_machine()

    def _parse_kedro_pipeline(self) -> None:
        """Extract the Kedro pipeline from the project"""
        metadata = bootstrap_project(self.project_path)

        self.project_name = metadata.project_name
        self.pipeline = pipelines.get("__default__")

    def _set_ecr_repository(self) -> None:
        """Set the ECR repository for the Lambda base image"""
        self.ecr_repository = aws_ecr.Repository.from_repository_name(
            self, id="ECR", repository_name=self.erc_repository_name
        )

    def _set_ecr_image(self) -> None:
        """Set the Lambda base image"""
        self.ecr_image = aws_lambda.EcrImageCode(repository=self.ecr_repository)

    def _set_s3_data_bucket(self) -> None:
        """Set the S3 bucket containing the raw data"""
        self.s3_bucket = s3.Bucket(
            self, "RawDataBucket", bucket_name=self.s3_data_bucket_name
        )

    def _convert_kedro_node_to_lambda_function(self, node: Node) -> IFunction:
        """Convert a Kedro node into an AWS Lambda function"""
        func = aws_lambda.Function(
            self,
            id=_clean_name(f"{node.name}_fn"),
            description=str(node),
            code=self.ecr_image,
            handler=aws_lambda.Handler.FROM_IMAGE,
            runtime=aws_lambda.Runtime.FROM_IMAGE,
            environment={},
            function_name=_clean_name(node.name),
            memory_size=256,
            reserved_concurrent_executions=10,
            timeout=core.Duration.seconds(15 * 60),
        )
        self.s3_bucket.grant_read_write(func)
        return func

    def _convert_kedro_node_to_sfn_task(self, node: Node) -> LambdaInvoke:
        """Convert a Kedro node into an AWS Step Functions Task"""
        return LambdaInvoke(
            self,
            _clean_name(node.name),
            lambda_function=self._convert_kedro_node_to_lambda_function(node),
            payload=sfn.TaskInput.from_object({"node_name": node.name}),
        )

    def _convert_kedro_pipeline_to_step_functions_state_machine(self) -> None:
        """Convert Kedro pipeline into an AWS Step Functions State Machine"""
        definition = sfn.Pass(self, "Start")

        for i, group in enumerate(self.pipeline.grouped_nodes, 1):
            group_name = f"Group {i}"
            sfn_state = sfn.Parallel(self, group_name)
            for node in group:
                sfn_task = self._convert_kedro_node_to_sfn_task(node)
                sfn_state.branch(sfn_task)

            definition = definition.next(sfn_state)

        sfn.StateMachine(
            self,
            self.project_name,
            definition=definition,
            timeout=core.Duration.seconds(5 * 60),
        )


app = core.App()
KedroStepFunctionsStack(app, "KedroStepFunctionsStack")
app.synth()