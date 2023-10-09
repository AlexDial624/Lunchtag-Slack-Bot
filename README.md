# LunchTag-SlackBot
A comprehensive Slack Bot to manage a weekly 1x1 pairing program for the Effective Altruism at UT Austin Student Group.

**Member Experience**

New members receive this invite
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/8455eec4-00fa-4a50-8139-8cfa93878228)


If they decline, they can change their mind to accept
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/453ba40d-7f43-4ca2-ba23-bbc781f20a84)
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/7e04b10e-8196-4737-8cfc-08856dcb6225)




Once joined, they instantly can set their interests and other preferences.
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/d014685a-92b2-47c2-bd0e-021673d433d2)

When the next round of lunchtag begins, they are asked to confirm their availability.
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/4dc34544-7383-4d0b-8511-e50eef98201a)
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/d5eafb0f-377b-41cc-b302-0b882c8deb12)


Once the admin has generated and published the pairings, they receive their pairing as well as a survey.
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/d46b9f28-c4b8-4107-9675-78d02b96eda0)

Users can also view their account details and update their profile interests. 

**Admin Experience**

All admin commands are controlled through the admin prefix.
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/3596f2f8-1db1-47ef-a0ff-fdf21260ba3f)


**How does pairings work?**

Admins generate pairings with:

• /lunchtag-admin generate {tiny, short, full} -> provides sized response file of existing pairings

Pairings are generated with the following algorithm:
  
Compute a compatibility score between all confirmed members for this week of Lunchtag with the following policies

 • +1 point per mutual interest

 • +10 point if user #1 expressed interest in being paired with user #2, and vice versa

 • -100 points if these users have already been paired before
 
 • -1000 points if user #1 expressed a preference to avoid being paired with user #2, and vice versa
 
 • -10000 points if user #1 is the same person as user #2

Then, use the Hungarian algorithm to assign pairings so as to maximize the total compatibility score.

Admins can also swap users around using admin commands, and in the config of the application can define users that should be given multiple pairings, to have multiple 1x1s in a given pairing.

**How does the code work?**

Slack interacts with an AWS serverless lambda function, which handles all of the operations and stores the json database in a s3 bucket. Since slack requires an immediate return to the function call, I use one function to acknowledge the call and another to handle the operations. In the handler function, constants and configurables are stores in config.py, the program entrypoint and command handling is in lambda_function.py, posting to slack is handled in slack_client.py, and user data management is handled in user_management.py. There are two dependency layers on the handler function to import all the libraries (numpy, pandas, tabulate, munkes, etc).
