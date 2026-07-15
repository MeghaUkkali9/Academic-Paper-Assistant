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

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.ssm.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "ssm" {
  name = "academic-paper-assistant-ssm-profile"
  role = aws_iam_role.ssm.name
}
