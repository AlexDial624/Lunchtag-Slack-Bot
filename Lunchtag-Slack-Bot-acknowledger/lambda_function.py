import boto3
import json
import base64
import urllib.parse

def lambda_handler(event, context):
    print(f"Received event:\n{event}\nWith context:\n{context}")
    
    """
    challenge_answer = json.loads(event.get('body')).get("challenge")
    return {
        'statusCode': 200,
        'body': challenge_answer
    }
    """



    if event.get('isBase64Encoded', False):
        decoded_body_str = base64.b64decode(event['body']).decode()
        slack_event_body = urllib.parse.parse_qs(decoded_body_str)
        for key in slack_event_body:
            slack_event_body[key] = slack_event_body[key][0]
        
        
        # check if request is a command
        if "command" in slack_event_body:
            

            lambda_client = boto3.client('lambda')
            invoke_response = lambda_client.invoke(
                FunctionName='Lunchtag-Slack-Bot-handler',  # Update with your Lambda #2 function name
                InvocationType='Event',
                Payload=json.dumps({'slack_event_body': slack_event_body}),
            )

            return {'statusCode': 200, 'body': "Processing your command..."}
            
        # check if request is a button
        elif "payload" in slack_event_body:
            payload = json.loads(slack_event_body['payload'])
            if payload['type'] == 'block_actions' and payload['actions'][0]['type'] == 'button':
            
                lambda_client = boto3.client('lambda')
                invoke_response = lambda_client.invoke(
                    FunctionName='Lunchtag-Slack-Bot-handler',  # Update with your Lambda #2 function name
                    InvocationType='Event',
                    Payload=json.dumps({'payload': payload}),
                )
                
                return {'statusCode': 200, 'body': "Processing your button click..."}
                
            
    else:
        return {'statusCode': 500, 'body': 'This function requires a valid Slack command.'}