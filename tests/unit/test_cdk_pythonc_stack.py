import aws_cdk as core
import aws_cdk.assertions as assertions

from cdk_pythonc.cdk_pythonc_stack import CdkPythoncStack

# example tests. To run these tests, uncomment this file along with the example
# resource in cdk_pythonc/cdk_pythonc_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = CdkPythoncStack(app, "cdk-pythonc")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
