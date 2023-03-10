from aws_cdk import (Stack, aws_ec2 as ec2, aws_ecs as ecs, 
                     aws_ecs_patterns as ecs_patterns, aws_rds as rds,
                     aws_secretsmanager as secretsmanager,
                     aws_iam as iam)
from constructs import Construct

class CdkPythoncStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        #get VPC
        self.vpc = ec2.Vpc.from_lookup(self, "VPC",
                vpc_id = "vpc-0a80e435cc7a23539"
        )
        
        #DB Security Group with required ingress rules
        self.sg= ec2.SecurityGroup(
            self, "SonarQubeSG",
            vpc=self.vpc,
            allow_all_outbound=True,
            description="Aurora Security Group"
        )
        self.sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(5432), "SonarDBAurora")
        pgroup = rds.ParameterGroup.from_parameter_group_name(
            self, "SonarDBParamGroup",
            parameter_group_name='default.aurora-postgresql12'
        )
   
        #create RDS Cluster
        self.db= rds.DatabaseCluster(self, 'SonarDBCluster',
            engine= rds.DatabaseClusterEngine.aurora_postgres(version=rds.AuroraPostgresEngineVersion.VER_12_9),
            default_database_name= 'sonarqube',
            parameter_group= pgroup,
            instance_props= rds.InstanceProps(
                instance_type= ec2.InstanceType.of(
                    ec2.InstanceClass.BURSTABLE3,
                    ec2.InstanceSize.MEDIUM
                ),
                security_groups= [self.sg],
                vpc= self.vpc
            )
        )
        #create Cluster
        self.cluster= ecs.Cluster(self, "SonarCluster",
            capacity= ecs.AddCapacityOptions(
            instance_type= ec2.InstanceType('t3.large')),
            vpc= self.vpc
        )

        asg= self.cluster.autoscaling_group
        user_data= asg.user_data
        user_data.add_commands('sysctl -qw vm.max_map_count=262144')
        user_data.add_commands('sysctl -w fs.file-max=65536')
        user_data.add_commands('ulimit -n 65536')
        user_data.add_commands('ulimit -u 4096')

        #Create iam Role for Task
        self.task_role = iam.Role(
            self,
            id= "SonarTaskRole",
            role_name= "SonarTaskRole",
            assumed_by= iam.ServicePrincipal(service= "ecs-tasks.amazonaws.com"),
            managed_policies= [
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        #Grant permission for Task to read secret from SecretsManager
        self.db.secret.grant_read(self.task_role)

        url = 'jdbc:postgresql://{}/sonarqube'.format(self.db.cluster_endpoint.socket_address)
        #create task
        task= ecs_patterns.ApplicationLoadBalancedEc2Service(self, "SonarService",
            # if a cluster is provided use the same vpc
            cluster= self.cluster,            
            # cpu=512,
            desired_count=1,
            max_healthy_percent = 100,
            min_healthy_percent = 0,
            task_image_options= ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("sonarqube:9.8-community"),
                container_port=9000,
                secrets={
                    "sonar.jdbc.username": ecs.Secret.from_secrets_manager(self.db.secret, field="username"),
                    "sonar.jdbc.password": ecs.Secret.from_secrets_manager(self.db.secret, field="password")
                },
                environment={
                    'sonar.jdbc.url': url
                },
                task_role= self.task_role
            ),
            memory_limit_mib=2048,
            public_load_balancer=True
        )

        container = task.task_definition.default_container
        container.add_ulimits(
            ecs.Ulimit(
                name=ecs.UlimitName.NOFILE,
                soft_limit=65536,
                hard_limit=65536
            )
        )
