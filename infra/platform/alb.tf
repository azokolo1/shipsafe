resource "aws_lb" "main" {
  #checkov:skip=CKV_AWS_150:Deletion protection would block the end-of-session destroy that ADR-0004 requires.
  #checkov:skip=CKV_AWS_91:ALB access logs need an S3 bucket with its own policy; added with the rest of logging in M6.
  #checkov:skip=CKV2_AWS_28:AWS WAF costs ~$5/month per web ACL plus rules; evaluated in M10 against the $40 budget.
  #checkov:skip=CKV2_AWS_76:Log4j WAF rule set: the service is Python, and WAF is evaluated in M10.
  name                       = local.name
  load_balancer_type         = "application"
  internal                   = false
  security_groups            = [aws_security_group.alb.id]
  subnets                    = [for s in aws_subnet.public : s.id]
  drop_invalid_header_fields = true
  enable_deletion_protection = false

  tags = { Name = local.name }

  # An internet-facing ALB needs the IGW, and holds public IPs that block the IGW
  # from detaching. Explicit ordering: IGW first on create, ALB first on destroy.
  # Without it, destroy spent 2m55s retrying the IGW detach (M3C evidence).
  depends_on = [aws_internet_gateway.main]
}

resource "aws_lb_target_group" "api" {
  #checkov:skip=CKV_AWS_378:TLS terminates at the ALB; ALB-to-task traffic stays inside the VPC and is limited to the ALB security group.
  name                 = "${local.name}-api"
  target_type          = "ip"
  protocol             = "HTTP"
  port                 = var.container_port
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30

  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = { Name = "${local.name}-api" }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = data.aws_acm_certificate.shipsafe.arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_lb_listener" "http_redirect" {
  #checkov:skip=CKV_AWS_103:This listener only redirects to HTTPS; TLS policy applies to the HTTPS listener.
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_route53_record" "app" {
  zone_id = data.aws_route53_zone.shipsafe.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
