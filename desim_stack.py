from aws_cdk import (
    Stack,
    RemovalPolicy,
    aws_ec2 as ec2,
    aws_ssm as ssm,
    aws_s3 as s3,
    aws_ecs as ecs,
    aws_sqs as sqs,
    aws_lambda as _lambda,
    aws_s3_notifications as s3n,
    aws_certificatemanager as acm,
    aws_elasticloadbalancingv2 as elbv2,
    aws_applicationautoscaling as appscaling,
    aws_autoscaling as autoscaling,
    aws_cognito as cognito,
    aws_secretsmanager as secretsmanager,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    Duration,
    Tags,
    SecretValue,
)
from constructs import Construct


class DESimStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        vpc_id = self.node.try_get_context("vpcId")
        security_group_id = self.node.try_get_context("securityGroupIds")
        private_subnet_ids = self.node.try_get_context("privateSubnetIds")
        public_subnet_ids = self.node.try_get_context("publicSubnetIds")
        acm_cert_arn = self.node.try_get_context("acmCertArn")

        vpc = ec2.Vpc.from_vpc_attributes(
            self,
            "VPC",
            vpc_id=vpc_id,
            availability_zones=[
                "ap-southeast-2a",
                "ap-southeast-2b",
                "ap-southeast-2c",
            ],
            public_subnet_ids=public_subnet_ids,
            private_subnet_ids=private_subnet_ids,
        )

        sg = ec2.SecurityGroup.from_security_group_id(
            self, "SecurityGroup", security_group_id=security_group_id, mutable=False
        )

        sims_bucket = s3.Bucket(
            self,
            "sims-bucket",
            bucket_name="desim-sims",
            versioned=True,
        )
        self.add_student_tags(sims_bucket)

        dlq = sqs.Queue(
            self,
            "DESimDLQ",
            queue_name="desim-simulation-dlq",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.add_student_tags(dlq)

        queue = sqs.Queue(
            self,
            "DESimSimulationQueue",
            queue_name="desim-simulation-queue",
            visibility_timeout=Duration.seconds(180),
            receive_message_wait_time=Duration.seconds(20),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dlq, max_receive_count=5),
            retention_period=Duration.days(4),
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.add_student_tags(queue)

        # ======= Spawn Microservices ===========#
        #                                        #
        # =======================================#

        cluster = ecs.Cluster(
            self,
            "DESimCluster",
            cluster_name="nXXXXXXXX-desim-cluster",
            vpc=vpc,
            container_insights_v2=ecs.ContainerInsights.ENABLED,
        )
        self.add_student_tags(cluster)

        # ======= Spawn DLQ ====================#
        #                                       #
        # ======================================#

        # Don't have permission to pass IAM roles apparently
        # dlq_task_definition = ecs.CfnTaskDefinition(
        #     self,
        #     "DESimDLQTaskDef",
        #     family="desim-dlq",
        #     cpu="1024",
        #     memory="2048",
        #     network_mode="awsvpc",
        #     requires_compatibilities=["FARGATE"],
        #     task_role_arn="arn:aws:iam::123456789012:role/Task-Role-CAB432-ECS",
        #     execution_role_arn="arn:aws:iam::123456789012:role/Execution-Role-CAB432-ECS",
        #     container_definitions=[
        #         {
        #             "name": "DESimDLQContainer",
        #             "image": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/nXXXXXXXX/desim-dlq:latest",
        #             "essential": True,
        #             "portMappings": [{"containerPort": 80}],
        #         }
        #     ],
        # )
        # self.add_student_tags(dlq_task_definition)

        dlq_service = ecs.CfnService(
            self,
            "DESimDLQService",
            cluster="nXXXXXXXX-desim-cluster",
            service_name="desim-dlq-service",
            desired_count=1,
            capacity_provider_strategy=[
                {"capacityProvider": "FARGATE", "base": 0, "weight": 1}
            ],
            scheduling_strategy="REPLICA",
            platform_version="LATEST",
            availability_zone_rebalancing="ENABLED",
            deployment_configuration={
                "deploymentCircuitBreaker": {
                    "enable": True,
                    "rollback": True,
                },
                "minimumHealthyPercent": 50,
            },
            deployment_controller={"type": "ECS"},
            service_connect_configuration={"enabled": False},
            enable_ecs_managed_tags=True,
            enable_execute_command=False,
            network_configuration={
                "awsvpcConfiguration": {
                    "assignPublicIp": "ENABLED",
                    "securityGroups": [security_group_id],
                    "subnets": private_subnet_ids,
                }
            },
            task_definition="arn:aws:ecs:ap-southeast-2:123456789012:task-definition/desim-dlq:3",
            propagate_tags="TASK_DEFINITION",
        )
        self.add_student_tags(dlq_service)
        dlq_service.node.add_dependency(cluster)

        dlq_scaling = appscaling.CfnScalableTarget(
            self,
            "DESimDLQScalableTarget",
            max_capacity=1,
            min_capacity=1,
            resource_id=f"service/{cluster.cluster_name}/desim-dlq-service",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            scheduled_actions=[
                appscaling.CfnScalableTarget.ScheduledActionProperty(
                    schedule="cron(30 15 * * ? *)",
                    scheduled_action_name="desim-dlq-scale_out_at_lights_out",
                    scalable_target_action=appscaling.CfnScalableTarget.ScalableTargetActionProperty(
                        max_capacity=1,
                        min_capacity=1,
                    ),
                )
            ],
        )
        dlq_scaling.add_dependency(dlq_service)
        dlq_scaling.node.add_dependency(cluster)

        # ======= Spawn Simulation =============#
        #                                       #
        # ======================================#

        # Don't have permission to pass IAM roles apparently
        # sim_task_definition = ecs.CfnTaskDefinition(
        #     self,
        #     "DESimSimTaskDef",
        #     family="desim-simulator",
        #     cpu="1024",
        #     memory="2048",
        #     network_mode="awsvpc",
        #     requires_compatibilities=["FARGATE"],
        #     task_role_arn="arn:aws:iam::123456789012:role/Task-Role-CAB432-ECS",
        #     execution_role_arn="arn:aws:iam::123456789012:role/Execution-Role-CAB432-ECS",
        #     container_definitions=[
        #         {
        #             "name": "DESimSimContainer",
        #             "image": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/nXXXXXXXX/desim-simulator:latest",
        #             "essential": True,
        #             "portMappings": [{"containerPort": 80}],
        #         }
        #     ],
        # )
        # self.add_student_tags(sim_task_definition)

        sim_service = ecs.CfnService(
            self,
            "DESimSimService",
            cluster="nXXXXXXXX-desim-cluster",
            service_name="desim-sim-service",
            desired_count=1,
            capacity_provider_strategy=[
                {"capacityProvider": "FARGATE", "base": 0, "weight": 1}
            ],
            scheduling_strategy="REPLICA",
            platform_version="LATEST",
            availability_zone_rebalancing="ENABLED",
            deployment_configuration={
                "deploymentCircuitBreaker": {
                    "enable": True,
                    "rollback": True,
                },
                "minimumHealthyPercent": 50,
            },
            deployment_controller={"type": "ECS"},
            service_connect_configuration={"enabled": False},
            enable_ecs_managed_tags=True,
            enable_execute_command=False,
            network_configuration={
                "awsvpcConfiguration": {
                    "assignPublicIp": "ENABLED",
                    "securityGroups": [security_group_id],
                    "subnets": private_subnet_ids,
                }
            },
            task_definition="arn:aws:ecs:ap-southeast-2:123456789012:task-definition/desim-simulator:4",
            propagate_tags="TASK_DEFINITION",
        )
        self.add_student_tags(sim_service)
        sim_service.node.add_dependency(cluster)

        scalable_target = appscaling.CfnScalableTarget(
            self,
            "DESimSimScalableTarget",
            max_capacity=3,
            min_capacity=1,
            resource_id=f"service/{cluster.cluster_name}/desim-sim-service",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            scheduled_actions=[
                appscaling.CfnScalableTarget.ScheduledActionProperty(
                    schedule="cron(30 15 * * ? *)",
                    scheduled_action_name="desim-sim-scale_out_at_lights_out",
                    scalable_target_action=appscaling.CfnScalableTarget.ScalableTargetActionProperty(
                        max_capacity=3,
                        min_capacity=1,
                    ),
                )
            ],
        )
        scalable_target.add_dependency(sim_service)

        appscaling.CfnScalingPolicy(
            self,
            "DESimSimScalingPolicy",
            policy_name="DESimSimQueueScalingPolicy",
            policy_type="TargetTrackingScaling",
            scaling_target_id=scalable_target.ref,
            target_tracking_scaling_policy_configuration=appscaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                customized_metric_specification=appscaling.CfnScalingPolicy.CustomizedMetricSpecificationProperty(
                    metric_name="ApproximateNumberOfMessagesVisible",
                    namespace="AWS/SQS",
                    statistic="Average",
                    dimensions=[{"name": "QueueName", "value": queue.queue_name}],
                ),
                target_value=10.0,
                scale_in_cooldown=60,
                scale_out_cooldown=60,
            ),
        )

        # ======= Front End Load Balancer ===== #
        #                                       #
        # ===================================== #

        alb = elbv2.ApplicationLoadBalancer(
            self,
            "DESimALB",
            vpc=vpc,
            internet_facing=True,
            load_balancer_name="desim-alb",
            security_group=sg,
        )
        self.add_student_tags(alb)

        listener = elbv2.CfnListener(
            self,
            "DESimListener",
            load_balancer_arn=alb.load_balancer_arn,
            port=80,
            protocol="HTTP",
            default_actions=[
                {
                    "type": "fixed-response",
                    "fixedResponseConfig": {
                        "statusCode": "200",
                        "contentType": "text/plain",
                        "messageBody": "Oops!",
                    },
                }
            ],
        )
        listener.node.add_dependency(alb)

        api_target_group = elbv2.CfnTargetGroup(
            self,
            "ApiTargetGroup",
            name="desim-api-tg",
            port=80,
            protocol="HTTP",
            target_type="ip",
            vpc_id=vpc_id,
            health_check_path="/",
            health_check_interval_seconds=30,
            healthy_threshold_count=2,
            unhealthy_threshold_count=4,
        )
        self.add_student_tags(api_target_group)

        ui_target_group = elbv2.CfnTargetGroup(
            self,
            "UiTargetGroup",
            name="desim-ui-tg",
            port=80,
            protocol="HTTP",
            target_type="ip",
            vpc_id=vpc_id,
            health_check_path="/",
            health_check_interval_seconds=30,
            healthy_threshold_count=2,
            unhealthy_threshold_count=4,
        )
        self.add_student_tags(ui_target_group)

        listener_rule_api = elbv2.CfnListenerRule(
            self,
            "DESimAPIListenerRule",
            listener_arn=listener.ref,
            priority=10,
            conditions=[
                {"field": "path-pattern", "pathPatternConfig": {"values": ["/v1/*"]}}
            ],
            actions=[{"type": "forward", "targetGroupArn": api_target_group.ref}],
        )
        listener_rule_api.add_dependency(listener)
        listener_rule_api.add_dependency(api_target_group)

        listener_rule_ui = elbv2.CfnListenerRule(
            self,
            "DESimUIListenerRule",
            listener_arn=listener.ref,
            priority=20,
            conditions=[
                {"field": "path-pattern", "pathPatternConfig": {"values": ["/*"]}}
            ],
            actions=[{"type": "forward", "targetGroupArn": ui_target_group.ref}],
        )
        listener_rule_ui.add_dependency(listener)
        listener_rule_ui.add_dependency(ui_target_group)

        alb_origin = origins.LoadBalancerV2Origin(
            alb, protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY
        )

        distribution = cloudfront.Distribution(
            self,
            "DESimCloudFront",
            domain_names=["desim.cab432.com"],
            certificate=acm.Certificate.from_certificate_arn(
                self, "DESimCert", certificate_arn=acm_cert_arn
            ),
            default_behavior=cloudfront.BehaviorOptions(
                origin=alb_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/v1/*": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
                "/callback": cloudfront.BehaviorOptions(
                    origin=alb_origin,
                    viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
                    allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                ),
            },
        )
        distribution.node.add_dependency(alb)
        distribution.node.add_dependency(listener)

        # ===== Front End ECS ===== #
        #                           #
        # ========================= #

        # Don't have permission to pass IAM roles apparently
        # api_task_definition = ecs.CfnTaskDefinition(
        #     self,
        #     "DESimAPITaskDef",
        #     family="desim-api",
        #     cpu="1024",
        #     memory="2048",
        #     network_mode="awsvpc",
        #     requires_compatibilities=["FARGATE"],
        #     task_role_arn="arn:aws:iam::123456789012:role/Task-Role-CAB432-ECS",
        #     execution_role_arn="arn:aws:iam::123456789012:role/Execution-Role-CAB432-ECS",
        #     container_definitions=[
        #         {
        #             "name": "DESimAPIContainer",
        #             "image": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/nXXXXXXXX/desim-api:latest",
        #             "essential": True,
        #             "portMappings": [{"containerPort": 80}],
        #         }
        #     ],
        # )
        # self.add_student_tags(api_task_definition)

        api_service = ecs.CfnService(
            self,
            "DESimAPIService",
            cluster="nXXXXXXXX-desim-cluster",
            service_name="desim-api-service",
            desired_count=1,
            capacity_provider_strategy=[
                {"capacityProvider": "FARGATE", "base": 0, "weight": 1}
            ],
            scheduling_strategy="REPLICA",
            platform_version="LATEST",
            availability_zone_rebalancing="ENABLED",
            deployment_configuration={
                "deploymentCircuitBreaker": {
                    "enable": True,
                    "rollback": True,
                },
                "minimumHealthyPercent": 50,
            },
            deployment_controller={"type": "ECS"},
            service_connect_configuration={"enabled": False},
            enable_ecs_managed_tags=True,
            enable_execute_command=False,
            network_configuration={
                "awsvpcConfiguration": {
                    "assignPublicIp": "ENABLED",
                    "securityGroups": [security_group_id],
                    "subnets": private_subnet_ids,
                }
            },
            load_balancers=[
                {
                    "containerName": "DESimAPIService",
                    "containerPort": 80,
                    "targetGroupArn": api_target_group.ref,
                }
            ],
            task_definition="arn:aws:ecs:ap-southeast-2:123456789012:task-definition/desim-api:5",
            propagate_tags="TASK_DEFINITION",
        )
        self.add_student_tags(api_service)
        api_service.add_dependency(listener_rule_api)
        api_service.node.add_dependency(cluster)

        api_scalable_target = appscaling.CfnScalableTarget(
            self,
            "DESimAPIScalableTarget",
            max_capacity=3,
            min_capacity=1,
            resource_id=f"service/{cluster.cluster_name}/desim-api-service",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            scheduled_actions=[
                appscaling.CfnScalableTarget.ScheduledActionProperty(
                    schedule="cron(30 15 * * ? *)",
                    scheduled_action_name="desim-api-scale_out_at_lights_out",
                    scalable_target_action=appscaling.CfnScalableTarget.ScalableTargetActionProperty(
                        max_capacity=3,
                        min_capacity=1,
                    ),
                )
            ],
        )
        api_scalable_target.add_dependency(api_service)

        appscaling.CfnScalingPolicy(
            self,
            "DESimAPIScalingPolicy",
            policy_name="DESimAPICpuScalingPolicy",
            policy_type="TargetTrackingScaling",
            scaling_target_id=api_scalable_target.ref,
            target_tracking_scaling_policy_configuration=appscaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                predefined_metric_specification=appscaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                    predefined_metric_type="ECSServiceAverageCPUUtilization"
                ),
                target_value=70.0,
                scale_in_cooldown=60,
                scale_out_cooldown=60,
            ),
        )

        # # Don't have permission to pass IAM roles apparently
        # ui_task_definition = ecs.CfnTaskDefinition(
        #     self,
        #     "DESimUITaskDef",
        #     family="desim-ui",
        #     cpu="1024",
        #     memory="2048",
        #     network_mode="awsvpc",
        #     requires_compatibilities=["FARGATE"],
        #     task_role_arn="arn:aws:iam::123456789012:role/Task-Role-CAB432-ECS",
        #     execution_role_arn="arn:aws:iam::123456789012:role/Execution-Role-CAB432-ECS",
        #     container_definitions=[
        #         {
        #             "name": "DESimUIContainer",
        #             "image": "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/nXXXXXXXX/desim-ui:latest",
        #             "essential": True,
        #             "portMappings": [{"containerPort": 80}],
        #         }
        #     ],
        # )
        # self.add_student_tags(ui_task_definition)

        ui_service = ecs.CfnService(
            self,
            "DESimUIService",
            cluster="nXXXXXXXX-desim-cluster",
            service_name="desim-ui-service",
            desired_count=1,
            capacity_provider_strategy=[
                {"capacityProvider": "FARGATE", "base": 0, "weight": 1}
            ],
            scheduling_strategy="REPLICA",
            platform_version="LATEST",
            availability_zone_rebalancing="ENABLED",
            deployment_configuration={
                "deploymentCircuitBreaker": {
                    "enable": True,
                    "rollback": True,
                },
                "minimumHealthyPercent": 50,
            },
            deployment_controller={"type": "ECS"},
            service_connect_configuration={"enabled": False},
            enable_ecs_managed_tags=True,
            enable_execute_command=False,
            network_configuration={
                "awsvpcConfiguration": {
                    "assignPublicIp": "ENABLED",
                    "securityGroups": [security_group_id],
                    "subnets": private_subnet_ids,
                }
            },
            load_balancers=[
                {
                    "containerName": "DESimUITaskDef",
                    "containerPort": 80,
                    "targetGroupArn": ui_target_group.ref,
                }
            ],
            task_definition="arn:aws:ecs:ap-southeast-2:123456789012:task-definition/desim-ui:6",
            propagate_tags="TASK_DEFINITION",
        )
        self.add_student_tags(ui_service)
        ui_service.add_dependency(listener_rule_ui)
        ui_service.node.add_dependency(cluster)

        ui_scalable_target = appscaling.CfnScalableTarget(
            self,
            "DESimUIScalableTarget",
            max_capacity=3,
            min_capacity=1,
            resource_id=f"service/{cluster.cluster_name}/desim-ui-service",
            scalable_dimension="ecs:service:DesiredCount",
            service_namespace="ecs",
            scheduled_actions=[
                appscaling.CfnScalableTarget.ScheduledActionProperty(
                    schedule="cron(30 15 * * ? *)",
                    scheduled_action_name="desim-ui-scale_out_at_lights_out",
                    scalable_target_action=appscaling.CfnScalableTarget.ScalableTargetActionProperty(
                        max_capacity=3,
                        min_capacity=1,
                    ),
                )
            ],
        )
        ui_scalable_target.add_dependency(ui_service)

        appscaling.CfnScalingPolicy(
            self,
            "DESimUIScalingPolicy",
            policy_name="DESimUICpuScalingPolicy",
            policy_type="TargetTrackingScaling",
            scaling_target_id=ui_scalable_target.ref,
            target_tracking_scaling_policy_configuration=appscaling.CfnScalingPolicy.TargetTrackingScalingPolicyConfigurationProperty(
                predefined_metric_specification=appscaling.CfnScalingPolicy.PredefinedMetricSpecificationProperty(
                    predefined_metric_type="ECSServiceAverageCPUUtilization"
                ),
                target_value=70.0,
                scale_in_cooldown=60,
                scale_out_cooldown=60,
            ),
        )

        # ===== Other Stuff ======= #
        #                           #
        # ========================= #

        user_pool = cognito.CfnUserPool(
            self,
            "DESimUserPool",
            user_pool_name="desim-user-pool",
            auto_verified_attributes=["email"],
            email_configuration=cognito.CfnUserPool.EmailConfigurationProperty(
                email_sending_account="DEVELOPER",
                from_="DESim login <logins@cab432.com>",
                source_arn="arn:aws:ses:ap-southeast-2:123456789012:identity/cab432.com",
            ),
            mfa_configuration="OPTIONAL",
            enabled_mfas=["SOFTWARE_TOKEN_MFA"],
        )

        user_pool_client = cognito.CfnUserPoolClient(
            self,
            "DESimUserPoolClient",
            client_name="desim-user-pool-client",
            user_pool_id=user_pool.ref,
            generate_secret=True,
            explicit_auth_flows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
                "ALLOW_USER_SRP_AUTH",
            ],
            allowed_o_auth_flows_user_pool_client=True,
            allowed_o_auth_flows=["code"],
            allowed_o_auth_scopes=[
                "openid",
                "email",
                "profile",
                "aws.cognito.signin.user.admin",
            ],
            callback_ur_ls=["https://desim.cab432.com/callback"],
            supported_identity_providers=["COGNITO", "Google"],
        )

        google_provider = cognito.CfnUserPoolIdentityProvider(
            self,
            "DESimGoogleIDP",
            provider_name="Google",
            provider_type="Google",
            user_pool_id=user_pool.ref,
            provider_details={
                "client_id": "XXX.apps.googleusercontent.com",
                "client_secret": "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                "authorize_scopes": "openid email profile",
            },
            attribute_mapping={
                "email": "email",
                "given_name": "given_name",
                "family_name": "family_name",
            },
        )

        user_pool_client.add_dependency(google_provider)

        cognito.CfnUserPoolGroup(
            self, "AdminGroup", group_name="admin", user_pool_id=user_pool.ref
        )

        cognito.CfnUserPoolDomain(
            self,
            "DESimUserPoolDomain",
            domain="desim-login",
            user_pool_id=user_pool.ref,
        )

        # ===== Lambda Function ===== #
        #                             #
        # =========================== #

        # lambda_fn = _lambda.Function(
        #     self,
        #     "DESimEmailOnFinished",
        #     runtime=_lambda.Runtime.PYTHON_3_11,
        #     handler="handler.main",
        #     code=_lambda.Code.from_asset("email_on_upload"),
        #     environment={
        #         "DB_SECRET_NAME": "nXXXXXXXX/desim-db-credentials",
        #         "COGNITO_USER_POOL_ID": user_pool.ref,
        #         "BUCKET_NAME": sims_bucket.bucket_name,
        #         "SES_FROM_EMAIL": "logins@cab432.com",
        #     },
        #     vpc=vpc,
        #     vpc_subnets=ec2.SubnetSelection(
        #         subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
        #     ),
        #     security_groups=[sg],
        #     timeout=Duration.seconds(30),
        # )

        # sims_bucket.add_event_notification(
        #     s3.EventType.OBJECT_CREATED,
        #     s3n.LambdaDestination(lambda_fn),
        #     s3.NotificationKeyFilter(suffix=".h5"),
        # )

        ssm.StringParameter(
            self,
            "SQSUrlParameter",
            parameter_name="/nXXXXXXXX/desim-sqs-queue-url",
            string_value=queue.queue_url,
        )

        ssm.StringParameter(
            self,
            "DLQUrlParameter",
            parameter_name="/nXXXXXXXX/desim-dlq-queue-url",
            string_value=dlq.queue_url,
        )

        ssm.StringParameter(
            self,
            "CognitoClientIdParameter",
            parameter_name="/nXXXXXXXX/desim-cognito-client-id",
            string_value=user_pool_client.attr_client_id,
        )

        ssm.StringParameter(
            self,
            "CognitoUserPoolIdParameter",
            parameter_name="/nXXXXXXXX/desim-cognito-user-pool-id",
            string_value=user_pool.ref,
        )

        ssm.StringParameter(
            self,
            "S3SimsParameter",
            parameter_name="/nXXXXXXXX/desim-sims",
            string_value=sims_bucket.bucket_name,
        )

        ssm.StringParameter(
            self,
            "RDBHostParameter",
            parameter_name="/nXXXXXXXX/desim-db-host",
            string_value="xxxxxxx.xxxxxxx.ap-southeast-2.rds.amazonaws.com",
        )

        ssm.StringParameter(
            self,
            "RDBPortParameter",
            parameter_name="/nXXXXXXXX/desim-db-port",
            string_value="XXXX",
        )

        ssm.StringParameter(
            self,
            "RDBNameParameter",
            parameter_name="/nXXXXXXXX/desim-db-name",
            string_value="XXXXXXX",
        )

        secretsmanager.Secret(
            self,
            "DBLoginSecret",
            secret_name="nXXXXXXXX/desim-db-credentials",
            secret_object_value={
                "username": SecretValue.unsafe_plain_text("XXXX"),
                "password": SecretValue.unsafe_plain_text(
                    self.node.try_get_context("dbpassword")
                ),
            },
        )

        secretsmanager.Secret(
            self,
            "CognitoClientSecret",
            secret_name="nXXXXXXXX/desim-cognito-client-secret",
            secret_string_value=SecretValue.unsafe_plain_text(
                user_pool_client.attr_client_secret
            ),
        )

    def add_student_tags(self, cdk_object):
        Tags.of(cdk_object).add("qut-username", "nXXXXXXXX@qut.edu.au")
        Tags.of(cdk_object).add("purpose", "assessment 3")
