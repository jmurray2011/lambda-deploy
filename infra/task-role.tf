data "aws_caller_identity" "current" {}

variable "permission_boundary_arn" {
  description = "ARN of the detent permission boundary policy."
  type        = string
}

variable "lock_table_arn" {
  description = "ARN of the detent-locks DynamoDB table."
  type        = string
}

resource "aws_iam_role" "lambda_deploy_task" {
  name                 = "detent-lambda-deploy-task"
  permissions_boundary = var.permission_boundary_arn

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_deploy" {
  name = "lambda-deploy-policy"
  role = aws_iam_role.lambda_deploy_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaOperations"
        Effect = "Allow"
        Action = [
          "lambda:GetFunction",
          "lambda:PublishVersion",
          "lambda:GetAlias",
          "lambda:UpdateAlias",
          "lambda:CreateAlias",
          "lambda:InvokeFunction",
        ]
        Resource = "arn:aws:lambda:*:${data.aws_caller_identity.current.account_id}:function:*"
      },
      {
        Sid    = "FrameworkState"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = "arn:aws:dynamodb:*:${data.aws_caller_identity.current.account_id}:table/detent-*"
      },
      {
        Sid      = "SNSPublish"
        Effect   = "Allow"
        Action   = ["sns:Publish", "sns:ListTopics"]
        Resource = "arn:aws:sns:*:${data.aws_caller_identity.current.account_id}:detent-*"
      },
    ]
  })
}
