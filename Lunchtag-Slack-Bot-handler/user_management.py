import json
from slack_client import send_message, get_users
from config import messages, all_blocks
from datetime import date

import boto3
s3 = boto3.client('s3')

def load_users():
    """Load user data from the S3 bucket."""
    try:
        s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='userdata.json')
        user_data = json.loads(s3_object['Body'].read().decode('utf-8'))
    except NoCredentialsError:
        print("No AWS credentials found")
        return {}
    except Exception as e:
        print("Error occurred while reading from S3:", str(e))
        return {}
    return user_data

def save_users(user_data):
    """Save updated user_data to the S3 bucket."""
    try:
        s3.put_object(Body=json.dumps(user_data).encode('utf-8'), Bucket='lunchtag-slack-bot-user-data', Key='userdata.json')
    except NoCredentialsError:
        print("No AWS credentials found")
    except Exception as e:
        print("Error occurred while writing to S3:", str(e))


# invite all specific users
def invite_users(audience, specific_users = []):
    """Invite specific users to join the event."""
    SafeMode = True
    
    message = messages['invite']
    invite_block = all_blocks['invite']
    
    user_data = load_users()
    users = get_users()

    
    for user in users:
        user_id, real_name = user['id'], user['real_name']
        
        if SafeMode and user_id not in specific_users:
            continue

        if user_id not in user_data:
            user_data[user_id] = {'real_name': real_name,
                                    'status': 'noResponse',
                                   'weekly_interest': 'noResponse',
                                   'profile': {
                                                "all_interests": [],
                                                "custom_interest": "",
                                                "promoted_people": [],
                                                "avoid_people": []
                                            },
                                   'history': {},
                                   'surveys': {}
                                 }
            new = True
        if (audience == 'new' and new) or (audience == 'nonresponders' and user_data[user_id]['status'] == 'noResponse') or (user_id in specific_users):
            print('Sending invite to ' + str(user_id))
            send_message(user_id, message, blocks = invite_block)
            
    save_users(user_data)

def confirm_weekly_interest():
    """Confirm weekly interest of users."""
    user_data = load_users()
    print('Confirming weekly interest')
    message = messages['weekly_interest']
    for user_id in user_data:
        if user_data[user_id]['weekly_interest'] != 'paused':
            user_data[user_id]['weekly_interest'] = 'noResponse'
        print(user_data[user_id]['weekly_interest'])
        if user_data[user_id]["status"] == "joined" and user_data[user_id]['weekly_interest'] == 'noResponse':
            send_message(user_id, message, blocks=all_blocks['weekly_interest'])
    save_users(user_data)

def confirm_weekly_interest_followup():
    """Confirm weekly interest of users."""
    user_data = load_users()
    print('Confirming weekly interest')
    message = messages['weekly_interest_followup']
    for user_id in user_data:
        if user_data[user_id]["status"] == "joined" and user_data[user_id]['weekly_interest'] == 'noResponse':
            send_message(user_id, message)
    save_users(user_data)


def ask_interests(user_id):
    """Ask the user about their interests."""
    message = messages['all_interests']
    print('asking interest of '+ user_id)
    send_message(user_id, message, blocks=all_blocks['profile'])


def update_survey(user_id, state):
    user_data = load_users()
    
    meeting_date = date.today().strftime("%m/%d/%y")
    
    user_responses = {
        "MetUp": "",
        "Rating": -1,
        "Survey_Feedback": ""
    }
    
    for block_id, response_data in state.items():
        for action_id, response in response_data.items():
            key = block_id
            if response['type'] == 'plain_text_input':
                user_responses[key] = response['value']
            elif response['type'] == 'static_select':
                value = response['selected_option']['value']
                if "MetUp" in value:
                    user_responses['MetUp'] = response['selected_option']['value']
                else:
                    user_responses['Rating'] = response['selected_option']['value']
    
    user_data[user_id]['surveys'][meeting_date] = user_responses
    save_users(user_data)

    return []


def update_profile(user_id, state):
    user_data = load_users()
    
    user_responses = {
        "all_interests": [],
        "custom_interest": "",
        "promoted_people": [],
        "avoid_people": []
    }
    
    for block_id, response_data in state.items():
        for action_id, response in response_data.items():
            key = block_id
            
            if response['type'] == 'checkboxes':
                user_responses[key] = [option['value'] for option in response['selected_options']]
            elif response['type'] == 'plain_text_input':
                user_responses[key] = str(response['value'])
            elif response['type'] == 'multi_users_select':
                user_responses[key] = list(response['selected_users'])
    
    user_data[user_id]['profile'] = user_responses
    save_users(user_data)

    return []
    
def preload_profile(user_id):
    user_data = load_users()
    
    blocks = all_blocks['profile_update']

    user_profile = user_data[user_id]['profile']
    profile_properties = user_profile.keys()
    for block in blocks['blocks']:
        cur_property = block.get('block_id')
        if cur_property in profile_properties:
            if block['element']['type'] == 'checkboxes':
                initial_options = []
                for checkbox in block['element']['options']:
                    if checkbox['value'] in user_profile[cur_property]:
                        initial_options.append(checkbox)
                if len(initial_options) > 0:
                    block['element']['initial_options'] = initial_options
    
            elif block['element']['type'] == 'plain_text_input':
                initial_options = user_profile[cur_property]
                if len(initial_options) > 0:
                    block['element']['initial_value'] = initial_options
    
            elif block['element']['type'] == 'multi_users_select':
                initial_options = user_profile[cur_property]
                if len(initial_options) > 0:
                    block['element']['initial_users'] = initial_options

    return blocks
    

def update_user_history(user1_id, user2_id, meeting_date):
    """Update the history of user1 and user2 with the meeting details."""
    user_data = load_users()
    user_data[user1_id]['history'][meeting_date] = user2_id
    user_data[user2_id]['history'][meeting_date] = user1_id
    save_users(user_data)


def get_user_profile(requested_user_id):
    """ Pulls, formats, and returns the account of a given user"""
    user_data = load_users()
    message = messages['invite']
    if requested_user_id not in user_data.keys():
        message = messages['missing_user']
    else:
        requested_data = user_data[requested_user_id]
        account = {}
        account['real_name'] = requested_data['real_name']
        account['status'] = requested_data['status']
        account['weekly_interest'] = requested_data['weekly_interest']
        account['Interests'] = ', '.join(requested_data['profile']['all_interests'])
        account['Custom_Interest'] = requested_data['profile']['custom_interest']
        account['Promoted_People'] = '<@' + '>, <@'.join(requested_data['profile']['promoted_people']) + '>'
        account['Avoid_People'] = '<@' + '>, <@'.join(requested_data['profile']['avoid_people']) + '>'
        account['History'] = ', '.join([date + ': ' + '<@' + name + '>' for date, name in requested_data['history'].items()])
        account['Survey'] = ', '.join([date + ': ' +  ', '.join([Metup, Rating, Feedback]) for date, (Metup, Rating, Feedback) in requested_data['surveys'].items()])


        
        message = messages['get_user_profile']
        message = message.format(**account)
    return message
    # Add functionality to change interests / edit profile
    