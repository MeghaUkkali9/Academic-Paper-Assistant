# Lets GitHub Actions run deploy commands on the instance via SSM
# (aws ssm send-command) instead of SSH, so port 22 never needs to be open
# to GitHub's runner IPs (which number in the thousands of CIDR blocks —
# far past AWS's security group rule limits).

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ssm" {
  name               = "academic-paper-assistant-ssm-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
}

# IAM is eventually consistent across its API — attaching a policy or
# creating an instance profile immediately after CreateRole can 404 before
# the role has propagated. A short wait avoids flaky applies.
resource "time_sleep" "role_propagation" {
  depends_on      = [aws_iam_role.ssm]
  create_duration = "15s"
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  depends_on = [time_sleep.role_propagation]
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  depends_on = [time_sleep.role_propagation]
  name       = "academic-paper-assistant-ssm-profile"
  role       = aws_iam_role.ssm.name
}
