# import os
import boto3

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from config import SLACK_BOT_TOKEN

slack_client = WebClient(token=SLACK_BOT_TOKEN)

s3 = boto3.client('s3')

def get_message(channel_id: str, message_ts: str):
    try:
        response = slack_client.conversations_history(
            channel=channel_id,
            latest=message_ts,
            inclusive=True,
            limit=1
        )
        message = response["messages"][0]['text']
        return message
    except SlackApiError as e:
        print(f"Error getting message: {e}")
        return ''

def update_message(channel_id, message_ts, blocks):
    # Use chat.update to update the message
    response = slack_client.chat_update(
        channel=channel_id,
        ts=message_ts,
        blocks=blocks['blocks']
    )
    return []

# Send a message given a user, message text, and optional reactions
def send_message(user_id, message, extra_reactions = [], file_name = '', blocks = []):
    try:
        if file_name != '':
            
            # Fetch the file from S3
            s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key=file_name)
            file_data = s3_object['Body'].read()
            
            response = slack_client.files_upload(
                channels=user_id,
                content=file_data,
                filename=file_name,
                initial_comment=message
            )
        elif blocks != []:
            response = slack_client.chat_postMessage(
                channel=user_id,
                text=message,
                blocks = blocks['blocks']
                )
            
        else:
            response = slack_client.chat_postMessage(
                channel=user_id,
                text=message
                )
    except SlackApiError as e:
        print(f"Error sending {message} to user {user_id}: {e}")
        return []

def get_users():
    try:
        response = slack_client.users_list()
        users = response["members"]
        return [user for user in users if not user["is_bot"]]
    except SlackApiError as e:
        print(f"Error getting users: {e}")
        return []
        
def log(text):
    log_channel = 'C05EANK93MY'
    send_message(log_channel, text)
    return
    
def log_exception(e):
    log(e)
    log(traceback.format_exc())
    return