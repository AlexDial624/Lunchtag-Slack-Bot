import numpy as np
import pandas as pd
from tabulate import tabulate
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from datetime import date
from munkres import Munkres
import boto3
from botocore.exceptions import NoCredentialsError
from io import BytesIO, StringIO

from slack_client import send_message
from user_management import save_users, load_users, update_user_history
from config import all_blocks, BUCKET_NAME, ADDITIONAL_USERS, AVOID_ADJUSTMENT_WEIGHT, PROMOTE_ADJUSTMENT_WEIGHT, HISTORY_PENALTY, SELF_MATCH_PENALTY

s3 = boto3.client('s3')

def generate_pairings():
    """ Generate pairings of users based on their compatibility scores. """

    user_data = load_users()
    users = [user_id for user_id, data in user_data.items() if data["weekly_interest"] == "confirmed"]
    users += ADDITIONAL_USERS
    num_users = len(users)
    compatibility_matrix = np.full((num_users, num_users), -SELF_MATCH_PENALTY)

    for user1_index in range(num_users):
        for user2_index in range(user1_index + 1, num_users):
            user1 = users[user1_index]
            user2 = users[user2_index]
            compatibility_matrix[user1_index, user2_index] = calculate_score(user_data, user1, user2)
            compatibility_matrix[user2_index, user1_index] = compatibility_matrix[user1_index, user2_index]

    # Solve the assignment problem
    m = Munkres()
    indexes = m.compute(-compatibility_matrix)

    final_pairings = compute_final_pairings(user_data, users, compatibility_matrix, indexes)
    final_df = pd.DataFrame(final_pairings)

    return final_df


def calculate_score(user_data, user1, user2):
    """ Calculate the compatibility score between two users. """
    common_interests = set(user_data[user1]['profile']['all_interests']) & set(user_data[user2]['profile']['all_interests'])
    avoid_adjust = AVOID_ADJUSTMENT_WEIGHT *((user1 in user_data[user2]['profile']['avoid_people']) + (user2 in user_data[user1]['profile']['avoid_people']))
    promote_adjust = PROMOTE_ADJUSTMENT_WEIGHT * (((user1 in user_data[user2]['profile']['promoted_people']) or (user2 in user_data[user1]['profile']['promoted_people'])))
    history_adjust = HISTORY_PENALTY * ((user2 in user_data[user1]['history'].values()) or (user1 in user_data[user2]['history'].values()))
    self_match_adjust = SELF_MATCH_PENALTY * (user1 == user2)
    
    score = len(common_interests) + promote_adjust - avoid_adjust - history_adjust - self_match_adjust
    return score


def compute_final_pairings(user_data, users, compatibility_matrix, indexes):
    """ Generate the final pairings given the assignment of users. """
    final_pairings = []

    for user1_index, user2_index in indexes:
        if user1_index < user2_index:
            user1 = users[user1_index]
            user2 = users[user2_index]
            common_interests = list(set(user_data[user1]['profile']['all_interests']) & set(user_data[user2]['profile']['all_interests']))
            score = compatibility_matrix[user1_index, user2_index]

            final_pairings.append({
                'Person 1': user_data[user1]['real_name'],
                'Person 2': user_data[user2]['real_name'],
                'Score': score,
                'Person 1 Interests': ', '.join(user_data[user1]['profile']['all_interests']),
                'Person 2 Interests': ', '.join(user_data[user2]['profile']['all_interests']),
                'Common Interests': ', '.join(common_interests),
                'Person 1 ID': user1,
                'Person 2 ID': user2
            })

    return final_pairings


def swap_pairings(command):
    """ Swap pairings based on the passed command and recalculate scores. """
    # Parse the command to get the corresponding row and column indices
    tokens = command[command.find('[')+1:].split(',')
    row1, cols1 = int(tokens[0][1]), [0,3,6] if tokens[0][0].upper() == 'A' else [1,4,7]
    row2, cols2 = int(tokens[1][1]), [0,3,6] if tokens[1][0].upper() == 'A' else [1,4,7]

    # Create a new DataFrame to store the updated pairings
    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    df = pd.read_excel(BytesIO(s3_object['Body'].read()))
    new_df = df.copy()
    user_data = load_users()

    # Swap the users according to the specified row and column indices
    new_df.iloc[row1, cols1], new_df.iloc[row2, cols2] = new_df.iloc[row2, cols2], new_df.iloc[row1, cols1]

    # Recalculate the score for the swapped rows
    for row in [row1, row2]:
        user1, user2 = new_df.iloc[row, -2], new_df.iloc[row, -1]
        score, common_interests = calculate_score(user_data, user1, user2)
        new_df.iloc[row, 2] = score
        new_df.iloc[row, 5] = ', '.join(common_interests)
        
    return new_df


def save_pairings(df):
    print('saving df...')
    # df.to_excel("pairings_full.xlsx", index=False)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    s3.put_object(Body=output, Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    
    return


def read_pairings(text='tiny'):
    
    if text == None:
        text='tiny'
    
    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    final_df = pd.read_excel(BytesIO(s3_object['Body'].read()))
        
    # final_df = pd.read_excel("pairings_full.xlsx")
    if 'full' in text:
        return "pairings_full.xlsx"

    elif 'short' in text:
        short_df = final_df.copy()[final_df.columns[0:5]]
        short_df_text = tabulate(short_df, tablefmt="grid", headers=short_df.columns)
        short_df = pd.DataFrame.from_dict([{'Summary': short_df_text}])
        # short_df.to_csv("pairings_short.csv", index=False)
        csv_buffer = StringIO()
        short_df.to_csv(csv_buffer, index=False)
        s3.put_object(Body=csv_buffer.getvalue(), Bucket='lunchtag-slack-bot-user-data', Key='pairings_short.csv')
       
        return "pairings_short.csv"
    
    tiny_df = final_df.copy()[final_df.columns[0:2]]
    tiny_df_text = tabulate(tiny_df, tablefmt="grid", headers=tiny_df.columns)
    tiny_df = pd.DataFrame.from_dict([{'Summary': tiny_df_text}])
    #tiny_df.to_csv("pairings_tiny.csv", index=False)
    csv_buffer = StringIO()
    tiny_df.to_csv(csv_buffer, index=False)
    s3.put_object(Body=csv_buffer.getvalue(), Bucket='lunchtag-slack-bot-user-data', Key='pairings_tiny.csv')
   
    return "pairings_tiny.csv"


def publish_and_send_dm():
    user_data = load_users()
    meeting_date = date.today().strftime("%m-%d-%y")

    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    df = pd.read_excel(BytesIO(s3_object['Body'].read()))

    file_name = 'pairings_full' + meeting_date + '.xlsx'
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    s3.put_object(Body=output, Bucket='lunchtag-slack-bot-user-data', Key=file_name)

    for index, row in df.iterrows():
        user1_id = row['Person 1 ID']
        user1_real_name = row['Person 1']
        user2_id = row['Person 2 ID']
        user2_real_name = row['Person 2']
        shared_interests = row['Common Interests']

        message_to_user1 = f"Hi {user1_real_name}, you've been paired up for LunchTag with <@{user2_id}>! \
                            You both share interests in {shared_interests}. Please initiate the conversation \
                            and plan a meetup. Enjoy!"
        message_to_user2 = f"Hi {user2_real_name}, you've been paired up for LunchTag with <@{user1_id}>! \
                            You both share interests in {shared_interests}. Please initiate the conversation \
                            and plan a meetup. Enjoy!"

        send_message(user1_id, message_to_user1)
        send_message(user2_id, message_to_user2)
        send_message(user1_id, "Before the next Lunchtag pairings, please complete the survey below!", 
                      blocks=all_blocks['survey'])
        send_message(user2_id, "Before the next Lunchtag pairings, please complete the survey below!", 
                      blocks=all_blocks['survey'])

        user_data[user1_id]['history'][meeting_date] = ", " + user2_id if meeting_date in user_data[user1_id]['history'].keys() else user2_id
        user_data[user2_id]['history'][meeting_date] = ", " + user1_id if meeting_date in user_data[user2_id]['history'].keys() else user1_id


    save_users(user_data)

    print('Done sending dms!')






"""
def generate_pairings():
    user_data = load_users()
    additional_users = ['U03UFPNSDT6','U03UFPNSDT6','U03UFPNSDT6']

    users = [user_id for user_id, data in user_data.items() if data["weekly_interest"] == "confirmed"]
    users += additional_users
    num_users = len(users)
    compatibility_matrix = np.zeros((num_users, num_users))-10000

    for i in range(num_users):
        for j in range(i + 1, num_users):
            user1 = users[i]
            user2 = users[j]

            common_interests = list(set(user_data[user1]['profile']['all_interests']) & set(user_data[user2]['profile']['all_interests']))
            avoid_adjust = ((user1 in user_data[user2]['profile']['avoid_people']) + (user2 in user_data[user1]['profile']['avoid_people'])) * 1000
            promote_adjust = ((user1 in user_data[user2]['profile']['promoted_people']) + (user2 in user_data[user1]['profile']['promoted_people'])) * 10
            
            score = len(common_interests) + promote_adjust - avoid_adjust

            if user2 in user_data[user1]['history'].values() and user1 in user_data[user2]['history'].values():
                score -= 100
            
            if user1 == user2:
                score -= 10000

            compatibility_matrix[i, j] = score
            compatibility_matrix[j, i] = score

    # row_ind, col_ind = linear_sum_assignment(-compatibility_matrix)
    m = Munkres()
    indexes = m.compute(-compatibility_matrix)
    print(compatibility_matrix)
    print(indexes)

    final_pairings = []
    for i, j in indexes:
        if i < j:
            user1 = users[i]
            user2 = users[j]
            common_interests = list(set(user_data[user1]['profile']['all_interests']) & set(user_data[user2]['profile']['all_interests']))
            score = compatibility_matrix[i, j]

            final_pairings.append({
                'Person 1': user_data[user1]['real_name'],
                'Person 2': user_data[user2]['real_name'],
                'Score': score,
                'Person 1 Interests': ', '.join(user_data[user1]['profile']['all_interests']),
                'Person 2 Interests': ', '.join(user_data[user2]['profile']['all_interests']),
                'Common Interests': ', '.join(common_interests),
                'Person 1 ID': user1,
                'Person 2 ID': user2
            })

    final_df = pd.DataFrame(final_pairings)
    return final_df


def swap_pairings(command):
    # Parse the command to get the corresponding row and column indices
    tokens = command[command.find('[')+1:].split(',')
    row1, cols1 = int(tokens[0][1]), [0,3,6] if tokens[0][0].upper() == 'A' else [1,4,7]
    row2, cols2 = int(tokens[1][1]), [0,3,6] if tokens[1][0].upper() == 'A' else [1,4,7]

    # Create a new DataFrame to store the updated pairingsmm
    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    df = pd.read_excel(BytesIO(s3_object['Body'].read()))
    new_df = df.copy()
    user_data = load_users()

    # Swap the users according to the specified row and column indices
    new_df.iloc[row1, cols1], new_df.iloc[row2, cols2] = new_df.iloc[row2, cols2], new_df.iloc[row1, cols1]

    for row in [row1, row2]:
        user1, user2 = new_df.iloc[row, -2], new_df.iloc[row, -1]
        common_interests = list(set(user_data[user1]['profile']['all_interests']) & set(user_data[user2]['profile']['all_interests']))
        avoid_adjust = ((user1 in user_data[user2]['profile']['avoid_people']) + (user2 in user_data[user1]['profile']['avoid_people'])) * 1000
        promote_adjust = ((user1 in user_data[user2]['profile']['promoted_people']) + (user2 in user_data[user1]['profile']['promoted_people'])) * 10
        
        score = len(common_interests) + promote_adjust - avoid_adjust
        if user2 in user_data[user1]['history'].values() and user1 in user_data[user2]['history'].values():
            score -= 100
        new_df.iloc[row, 2] = score
        new_df.iloc[row, 5] = ', '.join(common_interests)
        
    return new_df


def save_pairings(df):
    print('saving df...')
    # df.to_excel("pairings_full.xlsx", index=False)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    s3.put_object(Body=output, Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    
    return


def read_pairings(text='tiny'):
    
    if text == None:
        text='tiny'
    
    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    final_df = pd.read_excel(BytesIO(s3_object['Body'].read()))
        
    # final_df = pd.read_excel("pairings_full.xlsx")
    if 'full' in text:
        return "pairings_full.xlsx"

    elif 'short' in text:
        short_df = final_df.copy()[final_df.columns[0:5]]
        short_df_text = tabulate(short_df, tablefmt="grid", headers=short_df.columns)
        short_df = pd.DataFrame.from_dict([{'Summary': short_df_text}])
        # short_df.to_csv("pairings_short.csv", index=False)
        csv_buffer = StringIO()
        short_df.to_csv(csv_buffer, index=False)
        s3.put_object(Body=csv_buffer.getvalue(), Bucket='lunchtag-slack-bot-user-data', Key='pairings_short.csv')
       
        return "pairings_short.csv"
    
    tiny_df = final_df.copy()[final_df.columns[0:2]]
    tiny_df_text = tabulate(tiny_df, tablefmt="grid", headers=tiny_df.columns)
    tiny_df = pd.DataFrame.from_dict([{'Summary': tiny_df_text}])
    #tiny_df.to_csv("pairings_tiny.csv", index=False)
    csv_buffer = StringIO()
    tiny_df.to_csv(csv_buffer, index=False)
    s3.put_object(Body=csv_buffer.getvalue(), Bucket='lunchtag-slack-bot-user-data', Key='pairings_tiny.csv')
   
    return "pairings_tiny.csv"


def publish_and_send_dm():
    user_data = load_users()
    meeting_date = date.today().strftime("%m-%d-%y")
    survey_block = all_blocks['survey']
    file_name = 'pairings_full' + meeting_date + '.xlsx'

    s3_object = s3.get_object(Bucket='lunchtag-slack-bot-user-data', Key='pairings_full.xlsx')
    df = pd.read_excel(BytesIO(s3_object['Body'].read()))
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    s3.put_object(Body=output, Bucket='lunchtag-slack-bot-user-data', Key=file_name)
    
    
    user_data = load_users()

    for index, row in df.iterrows():
        user1_id = row['Person 1 ID']
        user1_real_name = row['Person 1']
        user2_id = row['Person 2 ID']
        user2_real_name = row['Person 2']
        shared_interests = row['Common Interests']
        message_to_user1 = f"Hi {user1_real_name}, you've been paired up for LunchTag with <@{user2_id}>! You both share interests in {shared_interests}. Please initiate the conversation and plan a meetup. Enjoy!"
        message_to_user2 = f"Hi {user2_real_name}, you've been paired up for LunchTag with <@{user1_id}>! You both share interests in {shared_interests}. Please initiate the conversation and plan a meetup. Enjoy!"
        

        send_message(user1_id, message_to_user1)
        send_message(user2_id, message_to_user2)
        
        send_message(user1_id, "Before the next Lunchtag pairings, please complete the survey below!", blocks = all_blocks['survey'])
        send_message(user2_id, "Before the next Lunchtag pairings, please complete the survey below!", blocks = all_blocks['survey'])
        
        # Update user history
        # update_user_history(user1_id, user_data[user1_id]['real_name'], user2_id, user_data[user2_id]['real_name'], meeting_date)
        
        user_data[user1_id]['history'][meeting_date] = user_data[user1_id]['history'].setdefault(meeting_date, "")
        user_data[user1_id]['history'][meeting_date] += user2_id

        user_data[user2_id]['history'][meeting_date] = user_data[user2_id]['history'].setdefault(meeting_date, "")
        user_data[user2_id]['history'][meeting_date] += user1_id
        
    save_users(user_data)
        
    print('Done sending dms!')

"""