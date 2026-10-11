resource "aws_budgets_budget" "monthly" {
  name         = "shipsafe-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [
      { pct = 50, type = "ACTUAL" },
      { pct = 80, type = "ACTUAL" },
      { pct = 100, type = "FORECASTED" },
    ]

    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.pct
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_email_addresses = [var.budget_email]
    }
  }
}
