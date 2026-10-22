resource "aws_cloudwatch_log_group" "api" {
  #checkov:skip=CKV_AWS_158:Default CloudWatch Logs encryption; a CMK for short-lived demo logs is evaluated in M6.
  #checkov:skip=CKV_AWS_338:7-day retention is deliberate: the stack is destroyed every session (ADR-0004).
  name              = "/ecs/${local.name}/api"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "main" {
  #checkov:skip=CKV_AWS_65:Container Insights adds per-metric charges; observability is designed in M6.
  name = local.name
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${data.aws_ecr_repository.app.repository_url}@${data.aws_ecr_image.app.image_digest}"
      essential = true
      user      = "10001:10001"

      portMappings = [{ containerPort = var.container_port, protocol = "tcp" }]

      environment = [
        { name = "SERVICE_NAME", value = "${local.name}-api" },
        { name = "QUEUE_BACKEND", value = "memory" },
        { name = "LOG_LEVEL", value = "INFO" },
      ]

      # Same hardening the CI smoke test proves: read-only root, no capabilities.
      readonlyRootFilesystem = true
      linuxParameters        = { capabilities = { drop = ["ALL"] } }

      # Liveness only (/healthz). Readiness is the ALB's job (/readyz).
      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/healthz', timeout=2)"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 10
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Rolling deploy: start new tasks before stopping old ones, and roll back
  # automatically if the new ones never become healthy.
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 30

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  network_configuration {
    subnets          = [for s in aws_subnet.private : s.id]
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = var.container_port
  }

  availability_zone_rebalancing = "ENABLED"
  enable_execute_command        = false
  propagate_tags                = "SERVICE"
  wait_for_steady_state         = true

  # The target group must be attached to a listener before ECS can register tasks.
  depends_on = [aws_lb_listener.https]
}
