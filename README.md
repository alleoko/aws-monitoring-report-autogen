# AWS Infrastructure Daily Monitoring Report

Generates a multi-sheet Excel report covering EC2, ECS, RDS, Security, Cost, CloudWatch Alarms, Load Balancers, EBS, and Auto Scaling Groups across multiple AWS regions.

---

## Prerequisites

**Python 3.8+**

Install dependencies:

```bash
pip install boto3 openpyxl
```

**AWS CLI profile** configured for the target account:

```bash
aws configure --profile 'your-aws-profile-name'
```

The profile must have read permissions for: EC2, ECS, RDS, S3, IAM, CloudWatch, ELB, Auto Scaling, STS.

---

## How to Run

```bash
cd "C:\Users\123\Daily Monitoring Report"
python aws_infra_report.py
```

Output file is saved to the same folder:

```
AWS_Infra_Report_YYYYMMDD_HHMM.xlsx
```

---

## Configuration

Edit `sheets/common.py` to change the AWS profile or regions:

```python
PROFILE      = "your-aws-profile-name"
ACCOUNT_NAME = "Your Company Name"
REGIONS      = ["ap-southeast-1", "us-west-2"]
```

The AWS Account ID is fetched automatically via STS — no need to hardcode it.

---

## Project Structure

```
Daily Monitoring Report/
├── aws_infra_report.py       # Entry point — run this
└── sheets/
    ├── common.py             # Shared constants, styling, AWS helpers
    ├── sheet_summary.py      # Executive Summary (cover sheet)
    ├── sheet_ec2.py          # EC2 Health — CPU, memory, disk, SG exposure
    ├── sheet_ecs.py          # ECS Clusters — task health, deployments, OOM
    ├── sheet_rds.py          # RDS Health — storage, backups, encryption
    ├── sheet_security.py     # Security Posture — open ports, IAM, S3, EBS
    ├── sheet_cost.py         # Cost & Utilization — EC2 spend, savings potential
    ├── sheet_alarms.py       # CloudWatch Alarms — states and actions
    ├── sheet_alb.py          # Load Balancers — error rates, response times
    ├── sheet_ebs.py          # EBS Volumes — encryption, snapshots, orphans
    └── sheet_asg.py          # Auto Scaling Groups — capacity and policies
```

---

## Adding a New Sheet

1. Create `sheets/sheet_yourservice.py` with a `build_yourservice_sheet(wb)` function
2. In `aws_infra_report.py`, add:
   ```python
   from sheets.sheet_yourservice import build_yourservice_sheet
   ```
3. Call it inside `main()`:
   ```python
   build_yourservice_sheet(wb)
   ```

---

## Report Sheets

| # | Sheet | Description |
|---|-------|-------------|
| 0 | Executive Summary | Cover page with risk legend and sheet directory |
| 1 | EC2_Health_Report | Per-instance CPU, memory, disk, network, SG risk |
| 2 | ECS_Cluster_Report | Service task counts, OOM events, deployment state |
| 3 | RDS_Health_Report | DB status, storage, connections, backup retention |
| 4 | Security_Posture_Report | Critical findings sorted by severity |
| 5 | Cost_And_Utilization | Underutilized instances, estimated monthly cost |
| 6 | CloudWatch_Alarms | All alarm states with action guidance |
| 7 | LoadBalancer_Report | 4xx/5xx rates, response time, unhealthy targets |
| 8 | EBS_Volumes_Report | Encryption status, snapshot age, detached volumes |
| 9 | AutoScaling_Report | ASG min/max/desired, scaling policies, health |

## Risk Levels

| Color | Level | Meaning |
|-------|-------|---------|
| Green | Low | Healthy — no action needed |
| Yellow | Medium | Minor warning — monitor closely |
| Orange | High | Performance degradation or cost issue |
| Red | Critical | Immediate action required |
