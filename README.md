# LunchTag-SlackBot
A comprehensive Slack Bot to manage a weekly 1x1 pairing program for the Effective Altruism at UT Austin Student Group.

**Member Experience**

New members receive this invite
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/5ec2895b-b1cf-4941-8a04-6fe9f12f8063)


If they decline, they can change their mind to accept
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/d985e441-197d-4c2c-ba7c-ed48d4b48547)
![image](https://github.com/AlexDial624/Lunchtag-Slack-Bot/assets/29134239/f83ec0d6-9205-4cac-a921-977313fb9c97)




Once joined, they instantly can set their interests and other preferences.

When the next round of lunchtag begins, they are asked to confirm their interest.

Once the admin has generated and published the pairings, they receive their pairing as well as a survey.

Users can also view their account details and update their profile interests. 

**Admin Experience**

All admin commands are controlled through the admin prefix.

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
  Then, use the hungarian algorithm to assign pairings so as to maximize the total compatibility score.

Admins can also swap users around

**How does the code work?**

Slack interacts with an AWS serverless lambda function, which handles all of the operations and stores the json database in a s3 bucket. Since slack requires an immediate return to the function call, I use one function to acknowledge the call and another to handle the operations. In the handler function, constants and configurables are stores in config.py, the program entrypoint and command handling is in lambda_function.py, posting to slack is handled in slack_client.py, and user data management is handled in user_management.py. There are two dependency layers on the handler function to import all the libraries (numpy, pandas, tabulate, munkes, etc).
