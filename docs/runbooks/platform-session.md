# Runbook: platform session (up, verify, down)

`infra/platform` is destroyed at the end of every working session (ADR-0004). Use this runbook every time.

**Cost:** about $0.128/hour while up (NAT gateway, ALB, 2 Fargate tasks, 3 public IPv4 addresses). The ALB and NAT gateway bill per **started** hour, so batch work into one session instead of several short ones.

**Measured timings (M3C):** apply about 4 minutes; destroy about 4.5 minutes before the M3D dependency fix.

## Before you start

```bash
cd ~/shipsafe && git switch main && git pull
aws sso login --profile shipsafe-admin
export AWS_PROFILE=shipsafe-admin
aws sts get-caller-identity --query Account --output text      # 699281550756

# The tag in infra/platform/terraform.tfvars must already exist in ECR
grep image_tag infra/platform/terraform.tfvars
aws ecr describe-images --repository-name shipsafe --query 'imageDetails[].imageTags[]' --output text
```

Allow at least 60 minutes, including the destroy. Do not start a session you cannot finish.

## Up

```bash
cd ~/shipsafe/infra/platform
rm -f platform.tfplan && terraform plan -out=platform.tfplan      # 37 to add on an empty stack
date +%T; time terraform apply platform.tfplan
terraform output
```

## Verify

```bash
URL=https://shipsafe.regopsintelligence.com
curl -sS "$URL/"; echo
curl -sS "$URL/readyz"; echo
curl -sSI "http://shipsafe.regopsintelligence.com/" | head -1     # 301

TG=$(aws elbv2 describe-target-groups --names shipsafe-api --query 'TargetGroups[0].TargetGroupArn' --output text)
aws elbv2 describe-target-health --target-group-arn "$TG" \
  --query 'TargetHealthDescriptions[].{ip:Target.Id,az:Target.AvailabilityZone,state:TargetHealth.State}' --output table
```

## Traffic log (for any test that changes running tasks)

Start this **before** the change, in its own terminal, and stop it with Ctrl-C afterwards. Every line has a timestamp, the response body (which includes the version) and the status code; `000` means no response within 3 seconds.

```bash
URL=https://shipsafe.regopsintelligence.com
while :; do
  printf '%s %s\n' "$(date +%T.%3N)" "$(curl -s -m 3 -w ' %{http_code}' "$URL/version")"
  sleep 0.5
done | tee ~/traffic.log
```

Summarise:

```bash
wc -l < ~/traffic.log                        # total requests
grep -cE ' 200$' ~/traffic.log               # successful
grep -vE ' 200$' ~/traffic.log               # every failure, with its time
```

## Down

```bash
cd ~/shipsafe/infra/platform
date +%T; time terraform destroy             # 37 to destroy; type yes
cd ../..

aws ec2 describe-vpcs --filters Name=tag:Project,Values=shipsafe --query 'Vpcs[].VpcId'
aws ec2 describe-nat-gateways --filter Name=tag:Project,Values=shipsafe --query 'NatGateways[?State!=`deleted`].NatGatewayId'
aws ec2 describe-addresses --filters Name=tag:Project,Values=shipsafe --query 'Addresses[].PublicIp'
aws elbv2 describe-load-balancers --query 'LoadBalancers[?LoadBalancerName==`shipsafe`].LoadBalancerArn'
aws ecs describe-clusters --clusters shipsafe --query 'clusters[?status==`ACTIVE`].clusterName'
aws logs describe-log-groups --log-group-name-prefix /ecs/shipsafe --query 'logGroups[].logGroupName'
```

All six must print `[]`. The session is not over until they do.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Plan fails on `data.aws_ecr_image.app` | The tag in `terraform.tfvars` was never pushed. Push it (build with `--provenance=false --sbom=false`) or use an existing tag. |
| Apply waits on `aws_ecs_service.api` for more than 10 minutes | Tasks are failing to start. In another terminal: `aws ecs describe-services --cluster shipsafe --services shipsafe-api --query 'services[0].events[:5].message'` and the `stoppedReason` of stopped tasks. Do not cancel Terraform. |
| Destroy fails with `DependencyViolation` | Network interfaces are still being released. Run `terraform destroy` again; it is safe to repeat. |
| `ExpiredToken` mid-session | `aws sso login --profile shipsafe-admin`, then rerun the same command. |
| `Error acquiring the state lock` | Another run holds the S3 lock, or a run was interrupted. Confirm nothing else is running before `terraform force-unlock <ID>`. |
| A leftover check prints a resource | Rerun `terraform destroy`. If it is not in state, investigate before deleting anything by hand. |
