import json

from config import SLACK_BOT_TOKEN, specific_users, all_blocks, admin_users, messages
from slack_client import get_message, send_message, update_message, log, log_exception
from user_management import invite_users, confirm_weekly_interest, ask_interests, save_users, load_users, confirm_weekly_interest_followup, get_user_profile, update_profile, preload_profile, update_survey
from pairings_manager import generate_pairings, save_pairings, read_pairings, swap_pairings, publish_and_send_dm
import traceback

        
    
def button_handler(user_id, channel_id, state, value, message_ts):
    """Check which button was pressed and take action"""

    log(f'{user_id} just activated button {value}')
    user_data = load_users()
    user_status = user_data.get(user_id, {}).get('status')
    user_interest = user_data.get(user_id, {}).get('weekly_interest')
    
    if value == 'invite_accepted':
        user_data[user_id]['status'] = "joined"
        user_data[user_id]["weekly_interest"] = "confirmed"
        update_message(channel_id, message_ts, all_blocks['invite_accepted'])
        send_message(user_id, "Setup your LunchTag Profile", blocks=all_blocks['profile'])


    elif value == 'invite_declined':
        user_data[user_id]['status'] = "declined"
        update_message(channel_id, message_ts, all_blocks['invite_declined'])
    
    elif value == 'invite_reconsider':
        update_message(channel_id, message_ts, all_blocks['invite'])

    elif value == 'weekly_interest_confirmed':
        user_data[user_id]["weekly_interest"] = "confirmed"
        update_message(channel_id, message_ts, all_blocks['weekly_interest_confirmed'])

    elif value == 'weekly_interest_skipping':
        user_data[user_id]["weekly_interest"] = "skipping"
        update_message(channel_id, message_ts, all_blocks['weekly_interest_skipping'])
    
    elif value == 'weekly_interest_paused':
        user_data[user_id]["weekly_interest"] = "paused"
        update_message(channel_id, message_ts, all_blocks['weekly_interest_paused'])
    
    elif value == 'weekly_interest_reconsider':
        user_data[user_id]["weekly_interest"] = "noResponse"
        update_message(channel_id, message_ts, all_blocks['weekly_interest'])
    
    elif value == 'survey-complete':
        update_survey(user_id, state)
        update_message(channel_id, message_ts, all_blocks['survey_completed'])
        
    save_users(user_data)
    
    if value == 'profile_update':
        update_profile(user_id, state)
        update_message(channel_id, message_ts, preload_profile(user_id))
        send_message(user_id, f'Your profile has been updated.') 
        
    return {}
    
    
    

def command_handler(command, text, user_id):
    """ Handles commands received from Slack and performs the corresponding action. """
    log(user_id + ' just ran command ' + command)

    if command == "/lunchtag-join":
        invite_users('specified', user_id)
    
    elif command == "/lunchtag-profile":
        send_message(user_id, "View and edit your profile", blocks=preload_profile(user_id))
    
    elif command == "/lunchtag-status":
        send_message(user_id, "Set your status", blocks=all_blocks['weekly_interest'])
    
    elif command == "/lunchtag-account":
        send_message(user_id, get_user_profile(user_id))

    elif command == "/lunchtag-admin":
        if user_id not in admin_users:
            send_message(user_id, "You're not authorized to perform this function")
            return {}
        
        if text in ("",None):
            send_message(user_id, messages['admin_controls'])
        
        elif text == 'view':
            user_data = load_users()
            message = str(user_data)
            send_message(user_id, message)
        
        elif 'invite' in text:
            params = text.split()[-1]

            if params == 'invite' or "":
                # send_message(user_id, "Please specify.")
                specific_users = ['U03UFPNSDT6']
                send_message(user_id, "Sending invitations to specified users.")
                invite_users('specified', specific_users)
                
            elif params == 'nonresponders':
                send_message(user_id, "Sending invitations to all nonresponded.")
                invite_users('nonresponders')

            elif params == 'new':
                send_message(user_id, "Sending invitations to all new members.")
                invite_users('new')

            else:
                specific_users = params.split(',')
                send_message(user_id, "Sending invitations to specified users.")
                invite_users('specified', specific_users)
        
        elif text == 'confirm':
            send_message(user_id, "Clearing last weeks status and asking active members for weekly confirmation")
            confirm_weekly_interest()
            
        elif text == 'confirm-followup':
            send_message(user_id, "Following up on asking members for weekly confirmation")
            confirm_weekly_interest_followup()
        
        elif 'generate' in text:
            send_message(user_id, "Generating pairings among Confirmed interested participants.")
            generated_df = generate_pairings()
            save_pairings(generated_df)
            file_name = read_pairings(text)
            send_message(user_id, 'Here is pairing data that was just generated', [], file_name)
        
        elif 'swap' in text:
            send_message(user_id, "Swapping pairings...")
            swapped_df = swap_pairings(text)
            save_pairings(swapped_df)
            file_name = read_pairings()
            send_message(user_id, 'Here is swapped data that was just generated', [], file_name)
        
        elif text == 'publish':
            send_message(user_id, "Publishing the final pairings and creating private chats.")
            publish_and_send_dm()
            send_message(user_id, 'Just published!')
        
        elif 'pairings' in text:
            file_name = read_pairings(text)
            send_message(user_id, 'Here is pairing data that currently is saved', [], file_name)
            
        elif 'set_users' in text:
            user_data = {}
            save_users(user_data)
        
    return {}
    
    
    
def handle_slack_event_body(slack_event_body):
    """
    Handle the slack event body.
    Extract command, text, and user_id, and call the command handler.
    """
    command = slack_event_body.get('command')
    text = slack_event_body.get('text')
    user_id = slack_event_body.get('user_id')

    command_handler(command, text, user_id)


def handle_payload(payload):
    """
    Handle the payload.
    Extract user_id, channel_id, state, value, and message_ts, and call the button handler.
    """
    user_id = payload.get('user', {}).get('id')
    channel_id = payload.get('channel', {}).get('id')
    state = payload.get('state', {}).get('values')
    value = payload.get('actions', [{}])[0].get('value')
    message_ts = payload.get('message', {}).get('ts')

    button_handler(user_id, channel_id, state, value, message_ts)
    
    
def lambda_handler(event, context):
    """
    AWS Lambda handler.
    Logs the received event and context.
    Depending on the presence of 'slack_event_body' or 'payload' in the event,
    calls the respective handling function.
    """
    print(f"Received event:\n{event}\nWith context:\n{context}")

    slack_event_body = event.get('slack_event_body')
    payload = event.get('payload')

    try:
        if slack_event_body:
            handle_slack_event_body(slack_event_body)
        elif payload:
            handle_payload(payload)
    except Exception as e:
        log_exception(e)

    return {'statusCode': 200}